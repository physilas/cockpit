"""Explicit research reference wrapper; released profile 12 remains unchanged.

The engine mask and native clock are inherited verbatim. Only the narrow
public working-together proposal changes the soft reference. This environment
has no matching published browser profile and must not be exported as one.
"""
from .leak_donation_advice import donation_candidates, leak_donation_reference
from .modules import ModuleEnv


class DonationEnv(ModuleEnv):
    def __init__(self, *args, assistance_version=12, **kwargs):
        if type(assistance_version) is not int or assistance_version != 12:
            raise ValueError('Donation research extends the explicit public profile 12 only.')
        self._source_reference_mask = None
        super().__init__(*args, assistance_version=assistance_version, **kwargs)

    def _assist(self, mask):
        allowed = super()._assist(mask)
        if self.current_role not in self.assisted_roles:
            self._source_reference_mask = list(allowed)
            return allowed
        self._source_reference_mask = list(self._reference_mask)
        view = self.view()
        state = view['modules_state']
        if ('working-together' in state['cards']
                and (state['swap'] or state['swap_available'] and donation_candidates(view))):
            self._reference_mask = leak_donation_reference(view, allowed,
                cpu_duty_cycle=self.planning_cpu_duty_cycle)
        return allowed

    def info(self):
        result = super().info()
        result['research_leak_donation'] = True
        result['source_reference_action_mask'] = (
            list(self._source_reference_mask) if any(result['action_mask'])
            and self._source_reference_mask is not None else list(result['action_mask']))
        return result
