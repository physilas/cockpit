"""Explicit all-module research phase, separate from published player masks.

Base/kerosene without cards retains the published planner. Other cases use
engine-legal choices without a claimed module strategy. A logical action clock
is a reproducible realtime proxy, not evidence of human time-pressure skill.
Training decision-budget exhaustion is a terminal training failure, never a
bootstrapped escape from an engine loss. The engine result remains untouched.
"""
import math

from .modules import ModuleEnv


class AllModulesEnv(ModuleEnv):
    def __init__(self, *args, step_seconds=1., clock=None, **kwargs):
        if not math.isfinite(step_seconds) or step_seconds <= 0:
            raise ValueError('The logical action duration must be finite and positive.')
        if clock is not None:
            raise ValueError('All-module research owns its deterministic logical clock.')
        self.step_seconds = float(step_seconds)
        self.logical_time = 0.
        self.training_budget_failure = False
        self._raw_action_mask = []
        kwargs.setdefault('assistance_version', 9)
        super().__init__(*args, clock=lambda: self.logical_time, **kwargs)

    def reset(self, *, seed=None):
        self.logical_time = 0.
        self.training_budget_failure = False
        self._raw_action_mask = []
        return super().reset(seed=seed)

    def _assist(self, mask):
        self._raw_action_mask = list(mask)
        plain = self.game.cockpit.module <= {'kerosene'} and not self.game.zusatz.karten
        if plain:
            result = super()._assist(mask)
            if self.assistance_version != 9 or self.current_role not in self.assisted_roles:
                self._reference_mask = list(result)
            return result
        allowed = list(mask)
        # Cancellation leaves the card unused and enables start/cancel forever.
        # Self-play can always finish a legal offered selection instead.
        if any(valid and action.kind == 'swap_choose'
               for valid, action in zip(allowed, self.actions)):
            for index, action in enumerate(self.actions):
                if action.kind == 'swap_cancel':
                    allowed[index] = False
        self._reference_mask = list(allowed)
        return allowed

    def info(self):
        result = super().info()
        live = any(result['action_mask'])
        result['reference_action_mask'] = (list(self._reference_mask) if live
                                           else list(result['action_mask']))
        result['raw_action_mask'] = (list(self._raw_action_mask) if live
                                     else list(result['action_mask']))
        result['training_budget_failure'] = self.training_budget_failure
        if self.training_budget_failure:
            result['status'] = 'verloren'
            result['reason'] = 'training_decision_budget'
        return result

    def step(self, action_id):
        if self.done:
            raise ValueError('Reset before stepping a finished research episode.')
        self.logical_time += self.step_seconds
        observation, reward, terminated, truncated, info = super().step(action_id)
        if truncated and not terminated:
            self.training_budget_failure = True
            self.truncated = False
            self.blocked = True
            # The normal adapter has already accumulated this transition's
            # rewards. Add only the missing terminal outcome/task settlement.
            self.reward_components['outcome'] -= 1.
            self.reward_totals['outcome'] -= 1.
            settlement = self._task_penalty(False, True)
            self.reward_components['tasks'] += settlement
            self.reward_totals['tasks'] += settlement
            reward += -1. + settlement
            terminated, truncated = True, False
            info = self.info()
        return observation, reward, terminated, truncated, info

    def episode_record(self, seed, ai_role, total_return):
        record = super().episode_record(seed, ai_role, total_return)
        record.update(abilities=sorted(self.game.zusatz.karten),
                      modules=sorted(self.game.cockpit.module),
                      training_budget_failure=self.training_budget_failure)
        return record
