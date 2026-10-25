"""Isolated research reference; no browser profile or released model change."""
import json

from .modules import ModuleEnv
from .wind_ice_advice import eligible, wind_ice_reference


class WindIceEnv(ModuleEnv):
    def __init__(self, *args, assistance_version=12, **kwargs):
        if type(assistance_version) is not int or assistance_version != 12:
            raise ValueError('Wind/ice research extends explicit profile 12 only.')
        self._source_reference_mask = None
        self._research_cache = None
        super().__init__(*args, assistance_version=assistance_version, **kwargs)

    def _assist(self, mask):
        allowed = super()._assist(mask)
        if self.current_role not in self.assisted_roles:
            self._source_reference_mask = list(allowed)
            return allowed
        self._source_reference_mask = list(self._reference_mask)
        view = self.view()
        if eligible(view):
            key = json.dumps(view, sort_keys=True), tuple(allowed), tuple(self._source_reference_mask)
            if self._research_cache is None or self._research_cache[0] != key:
                reference = wind_ice_reference(view, allowed, self._source_reference_mask,
                    cpu_duty_cycle=self.planning_cpu_duty_cycle)
                self._research_cache = key, tuple(reference)
            self._reference_mask = list(self._research_cache[1])
        return allowed

    def info(self):
        result = super().info()
        result['research_wind_ice'] = True
        result['source_reference_action_mask'] = (
            list(self._source_reference_mask) if any(result['action_mask'])
            and self._source_reference_mask is not None else list(result['action_mask']))
        return result
