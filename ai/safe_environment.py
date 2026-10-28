"""Separate research environment: shield before the existing public guidance.

Preserves released profiles and their fingerprints. Real wall-clock evaluation
is required separately from this deterministic one-second training clock.
"""
from .modules import ModuleEnv
from .module_capacity import reserve_controls
from .safety_guard import safe_actions
from collections import Counter


class SafeResearchEnv(ModuleEnv):
    @property
    def assisted_roles(self):
        return ('pilot', 'kopilot')

    @assisted_roles.setter
    def assisted_roles(self, value):
        pass

    def __init__(self, *args, **kwargs):
        self.logical_time = 0.
        self.safety_report = {}
        self.training_budget_failure = False
        if 'clock' in kwargs:
            raise ValueError('Research environment owns its training clock.')
        kwargs.setdefault('assistance_version', 12)
        super().__init__(*args, clock=lambda: self.logical_time, **kwargs)

    def reset(self, **kwargs):
        self.logical_time = 0.
        self.training_budget_failure = False
        self.role_decisions = Counter()
        return super().reset(**kwargs)

    def _assist(self, mask):
        view = self.view()
        mask, self.safety_report = safe_actions(self.game.landung._flughafen_code, view, mask)
        mask = reserve_controls(view, mask)
        # Preserve earlier strategic advice as a finite prior, rather than
        # permanently forbidding a useful deviation the learner could discover.
        super()._assist(mask)
        self._reference_mask = [bool(a and r) for a, r in zip(mask, self._reference_mask)]
        if not any(self._reference_mask):
            self._reference_mask = list(mask)
        return mask

    def step(self, action):
        role = self.current_role
        self.logical_time += 1.
        result = super().step(action)
        self.role_decisions[role] += 1
        observation, reward, terminated, truncated, info = result
        if truncated and not terminated:
            self.training_budget_failure = True
            self.truncated, self.blocked = False, True
            self.reward_components['outcome'] -= 1.
            self.reward_totals['outcome'] -= 1.
            settlement = self._task_penalty(False, True)
            self.reward_components['tasks'] += settlement
            self.reward_totals['tasks'] += settlement
            result = observation, reward - 1. + settlement, True, False, self.info()
        return result

    def info(self):
        info = super().info()
        if self.training_budget_failure:
            info.update(status='verloren', reason='training_decision_budget')
        return info

    def episode_record(self, seed, ai_role, total_return):
        row = super().episode_record(seed, ai_role, total_return)
        row['engine_decisions'] = row['steps']
        if ai_role in ('pilot', 'kopilot'):
            row['steps'] = self.role_decisions[ai_role]
            row['partner_decisions'] = sum(self.role_decisions.values()) - row['steps']
        return row
