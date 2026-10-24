"""Turn-based cooperative environment backed by Spielplan (base game only).

reset()/step() return (observation, info) and
(observation, reward, terminated, truncated, info), respectively. This is a
small native adapter, not a Gymnasium Env subclass. No torch dependency here.
"""
from contextlib import contextmanager
import math
import random

from backend.spielplan import Spielplan
from backend.regeln import ANZAHL_RUNDEN
from .actions import ACTIONS, ACTION_COUNT, ROLES, execute_placement, placement_is_legal, slot_field, subset_indices, SLOTS
from .observation import MAX_TRACK_LENGTH, encode, visible_state


class CrewEnv:
    def __init__(self, airport="MUC", round_reward=0.02, max_steps=256, *, sync_weight=0.0, sync_tolerance=1.0, task_weight=0.0, assistance_version=0,
                 curriculum_airports=()):
        if max_steps < 1 or not 0 <= round_reward <= 0.1:
            raise ValueError("max_steps muss positiv sein, round_reward zwischen 0 und 0.1.")
        if any(not math.isfinite(v) or v < 0 for v in (sync_weight, sync_tolerance, task_weight)):
            raise ValueError("Reward-Gewichte und Toleranz müssen endlich und nichtnegativ sein.")
        self.airport = airport
        self.round_reward = float(round_reward)
        self.max_steps = max_steps
        self.sync_weight = float(sync_weight)
        self.sync_tolerance = float(sync_tolerance)
        self.task_weight = float(task_weight)
        if assistance_version not in (0, 1, 2, 3, 4, 5, 6, 7, 8):
            raise ValueError('Unbekanntes KI-Assistenzprofil.')
        self.assistance_version = assistance_version
        self.curriculum_airports = tuple(curriculum_airports)
        self.assisted_roles = ROLES
        self.rng = random.Random(0)
        self.game = None
        self.reroll = None
        self.steps = 0
        self.truncated = False
        self.blocked = False
        self.rounds_resolved = 0
        self.task_urgency = 0.0
        self.reward_components = {"outcome": 0.0, "round": 0.0, "sync": 0.0, "tasks": 0.0}
        self.reward_totals = self.reward_components.copy()
        self._reset_diagnostics()

    def _reset_diagnostics(self):
        self.diagnostics = {'coffee_actions': 0, 'coffee_units': 0, 'rerolls': 0,
                            'coffee_reversals': 0, 'first_action_reroll': 0, 'capacity_impossible': 0}
        self._last_action = None

    @contextmanager
    def _engine_randomness(self):
        """Isolate the existing engine's global RNG without changing its rules.

        Safe for sequential envs and process workers; not for threads sharing
        Python's random module. Policy exploration uses a different RNG.
        """
        outside = random.getstate()
        random.setstate(self.rng.getstate())
        try:
            yield
        finally:
            self.rng.setstate(random.getstate())
            random.setstate(outside)

    @property
    def done(self):
        return self.game is not None and (self.game.status != "laeuft" or self.truncated or self.blocked)

    @property
    def current_role(self):
        if self.reroll:
            return next(r for r in (self.reroll["initiator"], self.other_role(self.reroll["initiator"]))
                        if self.reroll["selections"][r] is None)
        return self.game.am_zug

    @staticmethod
    def other_role(role):
        return ROLES[1 - ROLES.index(role)]

    def reset(self, *, seed=None):
        if seed is not None:
            self.rng.seed(seed)
        self.reroll, self.steps, self.truncated = None, 0, False
        self.blocked = False
        self.rounds_resolved = 0
        self.task_urgency = 0.0
        self.reward_components = {"outcome": 0.0, "round": 0.0, "sync": 0.0, "tasks": 0.0}
        self.reward_totals = self.reward_components.copy()
        self._reset_diagnostics()
        with self._engine_randomness():
            # Use the engine RNG already isolated by this context, so restart
            # and parallel worker seed namespaces remain reproducible.
            airport = random.choice(self.curriculum_airports) if self.curriculum_airports else self.airport
            self.game = Spielplan(airport)
            if self.game.cockpit.module or self.game.zusatz.karten:
                raise ValueError("Dieser erste KI-Rahmen unterstützt nur das Grundspiel ohne Module/Karten.")
            if self.game.landung.get_laenge() > MAX_TRACK_LENGTH:
                raise ValueError(f"Maximal {MAX_TRACK_LENGTH} Streckenfelder werden unterstützt.")
            self.game.starte_spiel()
            self._advance()
        return self.observation(), self.info()

    def _advance(self):
        round_resolved = False
        while self.game.status == "laeuft":
            if self.game.phase == "verkehr":
                result = self.game.wirf_verkehrswuerfel()
                if not result.erfolg:
                    raise RuntimeError(result.grund)
            elif self.game.phase == "vorbereitung":
                if not self.game.wuerfeln_fuer_runde():
                    raise RuntimeError("Runde konnte nicht gestartet werden.")
            elif self.game.alle_wuerfel_platziert():
                round_resolved = True
                result = self.game.rundenende()
                if not result.erfolg:
                    raise RuntimeError(result.grund)
            else:
                break
        return round_resolved

    def sync_error(self):
        """Late progress beyond a tolerance, in route fields (1000 ft per round).

        Early arrival and holding are allowed. This is a deliberately biased,
        optional training heuristic, not potential-based shaping.
        """
        return max(0.0, self.game.landung.entfernung - self.game.landung.hoehe / 1000 - self.sync_tolerance)

    def unfinished_tasks(self):
        """Persistent landing preparation, counted from public board state.

        Only enough braking for the minimum base-game engine sum (1+1) is a
        requirement. Extra brake upgrades remain useful but optional.
        """
        c = self.game.cockpit
        return {"gear": sum(not done for done in c.fahrwerk_ausgefahren),
                "flaps": sum(not done for done in c.landeklappen_ausgefahren),
                "braking": int(c.bremsstaerke() < 2),
                "traffic": sum(self.game.landung.flugzeuge)}

    def _task_penalty(self, round_resolved, terminated):
        """Charge the increase in quadratic urgency, not its full value again.

        For a fixed task count, charges telescope to at most weight * count.
        On a real terminal outcome settle the remaining urgency, so early
        failure cannot escape the unpaid task cost. Truncations do not settle.
        """
        if round_resolved:
            self.rounds_resolved += 1
        urgency = 1.0 if terminated else min(1.0, self.rounds_resolved / ANZAHL_RUNDEN) ** 2
        increase = max(0.0, urgency - self.task_urgency)
        self.task_urgency = urgency
        return -self.task_weight * sum(self.unfinished_tasks().values()) * increase

    def view(self, role=None):
        return visible_state(self.game, role or self.current_role, self.reroll,
                             max(0, 1 - self.steps / self.max_steps))

    def observation(self):
        return encode(self.view())

    def action_mask(self):
        mask = [False] * ACTION_COUNT
        if self.done:
            return mask
        role = self.current_role
        dice = self.game._wuerfel_liste(role)
        if self.reroll:
            partner_selection = self.reroll["selections"][self.other_role(role)]
            for i, action in enumerate(ACTIONS):
                if action.kind == "reroll_select":
                    selected = subset_indices(action.subset)
                    partner_can_choose = partner_selection is None and bool(self.game.verfuegbare_wuerfel(self.other_role(role)))
                    nonempty_pair = bool(selected or partner_selection) or partner_can_choose
                    mask[i] = nonempty_pair and all(dice[j].ist_verfuegbar() for j in selected)
            return self._assist(mask)
        # Own available dice and public occupied fields are sufficient. A
        # non-mandatory placement may not make this round impossible to finish.
        missing_required = sum(s.owner == role and s.target in ("ruder", "triebwerk")
                               and slot_field(self.game, s).ist_frei() for s in SLOTS)
        reserve_remaining = sum(w.ist_verfuegbar() for w in dice) <= missing_required
        for i, action in enumerate(ACTIONS):
            if action.kind == "place":
                slot = SLOTS[action.slot]
                mask[i] = (not reserve_remaining or slot.target in ("ruder", "triebwerk")) and placement_is_legal(self.game, role, dice[action.die], slot)
            elif action.kind == "coffee":
                mask[i] = dice[action.die].ist_verfuegbar() and action.delta in self.game.moegliche_kaffee_deltas(role, action.die)
            elif action.kind == "reroll_start":
                mask[i] = self.game.neuwurf_plaettchen > 0 and any(w.ist_verfuegbar() for w in dice)
        return self._assist(mask)

    def _assist(self, mask):
        if not self.assistance_version or self.current_role not in self.assisted_roles:
            return mask
        if self.game.cockpit.module or self.game.zusatz.karten:
            raise ValueError('Die Rundenplanung unterstützt noch keine Module oder Fähigkeitskarten/Zusatzwürfel.')
        from .tactics import assisted_mask
        return assisted_mask(self.view(), mask, version=self.assistance_version)

    def info(self):
        return {"role": self.current_role, "action_mask": self.action_mask(),
                "status": "truncated" if self.truncated else "verloren" if self.blocked else self.game.status,
                "reason": "step_limit" if self.truncated else "no_legal_actions" if self.blocked else self.game.verlust_grund,
                "round": self.game.aktuelle_runde, "steps": self.steps,
                "reward_components": self.reward_components.copy(), "reward_totals": self.reward_totals.copy()}

    def episode_record(self, seed, ai_role, total_return):
        """Public final-state diagnostics; no hidden hands in logs or replays."""
        info, c, landing = self.info(), self.game.cockpit, self.game.landung
        tasks = self.unfinished_tasks()
        return {"seed": seed, "ai_role": ai_role, "status": info["status"], "reason": info["reason"] or "",
                'scenario': self.game.landung.get_code(),
                "round": info["round"], "steps": info["steps"], "return": total_return,
                **{f"{name}_return": value for name, value in self.reward_totals.items()},
                "distance_remaining": landing.entfernung, "height_remaining": landing.hoehe,
                "airport_reached": int(landing.entfernung == 0),
                "landing_round_started": int(self.game.letzte_runde), "sync_error": self.sync_error(),
                "gear_count": sum(c.fahrwerk_ausgefahren), "flap_count": sum(c.landeklappen_ausgefahren),
                "brake_strength": c.bremsstaerke(), "planes_remaining": sum(landing.flugzeuge),
                "tasks_undone": sum(tasks.values()), **{f"{key}_undone": value for key, value in tasks.items()},
                **self.diagnostics}

    def step(self, action_id):
        if self.game is None or self.done:
            raise ValueError("Vor einem Schritt eine laufende Partie mit reset() starten.")
        if type(action_id) is not int or not 0 <= action_id < ACTION_COUNT or not self.action_mask()[action_id]:
            raise ValueError(f"Aktion {action_id!r} ist in diesem Zustand nicht erlaubt.")
        action, role = ACTIONS[action_id], self.current_role
        if action.kind == 'coffee':
            self.diagnostics['coffee_actions'] += 1
            self.diagnostics['coffee_units'] += abs(action.delta)
            previous = self._last_action
            if previous and previous[0] == role and previous[1].kind == 'coffee' and previous[1].die == action.die and previous[1].delta * action.delta < 0:
                self.diagnostics['coffee_reversals'] += 1
        if action.kind == 'reroll_start':
            self.diagnostics['rerolls'] += 1
            self.diagnostics['first_action_reroll'] = max(self.diagnostics['first_action_reroll'], int(self.steps == 0))
        self._last_action = (role, action)
        old_round = self.game.aktuelle_runde
        with self._engine_randomness():
            result = None
            if action.kind == "place":
                result = execute_placement(self.game, role, action)
            elif action.kind == "coffee":
                result = self.game.trinke_kaffee(role, action.die, action.delta)
            elif action.kind == "reroll_start":
                self.reroll = {"initiator": role, "selections": {r: None for r in ROLES}}
            else:
                self.reroll["selections"][role] = subset_indices(action.subset)
                if all(s is not None for s in self.reroll["selections"].values()):
                    selections = self.reroll["selections"]
                    result = self.game.benutze_neuwurf(selections["pilot"], selections["kopilot"])
                    self.reroll = None
            if result is not None and not result.erfolg:
                raise RuntimeError(f"Maske und Engine widersprechen sich: {result.grund}")
            round_resolved = self._advance()
        self.steps += 1
        from .tactics import capacity
        public = self.view()
        if any(capacity(public, r)['slack'] < 0 for r in ROLES):
            self.diagnostics['capacity_impossible'] = 1
        if self.game.status == "laeuft" and not any(self.action_mask()):
            self.blocked = True
        terminated = self.game.status != "laeuft" or self.blocked
        self.truncated = self.steps >= self.max_steps and not terminated
        self.reward_components = {
            "outcome": (1.0 if self.game.status == "gewonnen" else -1.0) if terminated else 0.0,
            "round": self.round_reward * (self.game.aktuelle_runde - old_round),
            "sync": -self.sync_weight * self.sync_error() if round_resolved else 0.0,
            "tasks": self._task_penalty(round_resolved, terminated),
        }
        for name, value in self.reward_components.items():
            self.reward_totals[name] += value
        reward = sum(self.reward_components.values())
        return self.observation(), reward, terminated, self.truncated, self.info()
