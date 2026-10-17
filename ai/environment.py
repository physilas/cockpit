"""Turn-based cooperative environment backed by Spielplan (base game only).

reset()/step() return (observation, info) and
(observation, reward, terminated, truncated, info), respectively. This is a
small native adapter, not a Gymnasium Env subclass. No torch dependency here.
"""
from contextlib import contextmanager
import random

from backend.spielplan import Spielplan
from .actions import ACTIONS, ACTION_COUNT, ROLES, execute_placement, placement_is_legal, subset_indices, SLOTS
from .observation import MAX_TRACK_LENGTH, encode, visible_state


class CrewEnv:
    def __init__(self, airport="MUC", round_reward=0.02, max_steps=256):
        if max_steps < 1 or not 0 <= round_reward <= 0.1:
            raise ValueError("max_steps muss positiv sein, round_reward zwischen 0 und 0.1.")
        self.airport = airport
        self.round_reward = float(round_reward)
        self.max_steps = max_steps
        self.rng = random.Random(0)
        self.game = None
        self.reroll = None
        self.steps = 0
        self.truncated = False
        self.blocked = False

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
        with self._engine_randomness():
            self.game = Spielplan(self.airport)
            if self.game.cockpit.module or self.game.zusatz.karten:
                raise ValueError("Dieser erste KI-Rahmen unterstützt nur das Grundspiel ohne Module/Karten.")
            if self.game.landung.get_laenge() > MAX_TRACK_LENGTH:
                raise ValueError(f"Maximal {MAX_TRACK_LENGTH} Streckenfelder werden unterstützt.")
            self.game.starte_spiel()
            self._advance()
        return self.observation(), self.info()

    def _advance(self):
        while self.game.status == "laeuft":
            if self.game.phase == "verkehr":
                result = self.game.wirf_verkehrswuerfel()
                if not result.erfolg:
                    raise RuntimeError(result.grund)
            elif self.game.phase == "vorbereitung":
                if not self.game.wuerfeln_fuer_runde():
                    raise RuntimeError("Runde konnte nicht gestartet werden.")
            elif self.game.alle_wuerfel_platziert():
                result = self.game.rundenende()
                if not result.erfolg:
                    raise RuntimeError(result.grund)
            else:
                break

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
            return mask
        for i, action in enumerate(ACTIONS):
            if action.kind == "place":
                mask[i] = placement_is_legal(self.game, role, dice[action.die], SLOTS[action.slot])
            elif action.kind == "coffee":
                mask[i] = dice[action.die].ist_verfuegbar() and action.delta in self.game.moegliche_kaffee_deltas(role, action.die)
            elif action.kind == "reroll_start":
                mask[i] = self.game.neuwurf_plaettchen > 0 and any(w.ist_verfuegbar() for w in dice)
        return mask

    def info(self):
        return {"role": self.current_role, "action_mask": self.action_mask(),
                "status": "truncated" if self.truncated else "verloren" if self.blocked else self.game.status,
                "reason": "step_limit" if self.truncated else "no_legal_actions" if self.blocked else self.game.verlust_grund,
                "round": self.game.aktuelle_runde, "steps": self.steps}

    def step(self, action_id):
        if self.game is None or self.done:
            raise ValueError("Vor einem Schritt eine laufende Partie mit reset() starten.")
        if type(action_id) is not int or not 0 <= action_id < ACTION_COUNT or not self.action_mask()[action_id]:
            raise ValueError(f"Aktion {action_id!r} ist in diesem Zustand nicht erlaubt.")
        action, role = ACTIONS[action_id], self.current_role
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
            self._advance()
        self.steps += 1
        if self.game.status == "laeuft" and not any(self.action_mask()):
            self.blocked = True
        terminated = self.game.status != "laeuft" or self.blocked
        self.truncated = self.steps >= self.max_steps and not terminated
        reward = self.round_reward * (self.game.aktuelle_runde - old_round)
        if terminated:
            reward += 1.0 if self.game.status == "gewonnen" else -1.0
        return self.observation(), reward, terminated, self.truncated, self.info()
