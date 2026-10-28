"""Research policy with the same shield/prior boundary as SafeResearchEnv."""
from .module_capacity import reserve_controls
from .rollout_search import GuidedBlueprint
from .safety_guard import safe_actions


class RobustBlueprint(GuidedBlueprint):
    def __init__(self, airport, model):
        super().__init__(model)
        self.airport = airport

    def masks(self, view, raw):
        safe, _ = safe_actions(self.airport, view, raw)
        safe = reserve_controls(view, safe)
        _, reference = super().masks(view, safe)
        return safe, reference
