"""Separate all-module research phase with conservative control reservation."""
from .all_modules_environment import AllModulesEnv
from .module_capacity import reserve_controls


class CapacityModulesEnv(AllModulesEnv):
    def _assist(self, mask):
        allowed = super()._assist(mask)
        if self.game.cockpit.module <= {'kerosene'} and not self.game.zusatz.karten:
            return allowed
        result = reserve_controls(self.view(), allowed)
        self._reference_mask = list(result)
        return result
