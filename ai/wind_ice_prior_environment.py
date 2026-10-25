"""New research phase on top of the preserved earlier microplan environment."""
import json

from .wind_ice_advice import eligible
from .wind_ice_environment import WindIceEnv
from .wind_ice_prior_advice import prior_reference


class PriorWindIceEnv(WindIceEnv):
    def __init__(self, *args, **kwargs):
        self._prior_cache = None
        self._microplan_reference_mask = None
        super().__init__(*args, **kwargs)

    def _assist(self, mask):
        allowed = super()._assist(mask)
        if self.current_role not in self.assisted_roles:
            self._microplan_reference_mask = list(allowed)
            return allowed
        self._microplan_reference_mask = list(self._reference_mask)
        view = self.view()
        if eligible(view):
            key = json.dumps(view, sort_keys=True), tuple(allowed), tuple(self._source_reference_mask)
            if self._prior_cache is None or self._prior_cache[0] != key:
                reference = prior_reference(view, allowed, self._source_reference_mask,
                    cpu_duty_cycle=self.planning_cpu_duty_cycle)
                self._prior_cache = key, tuple(reference)
            self._reference_mask = list(self._prior_cache[1])
        return allowed

    def info(self):
        result = super().info()
        result['research_wind_ice_prior'] = True
        result['microplans_reference_action_mask'] = (
            list(self._microplan_reference_mask) if any(result['action_mask'])
            and self._microplan_reference_mask is not None else list(result['action_mask']))
        return result
