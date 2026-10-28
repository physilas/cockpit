"""Development hypothesis: defer private plan deviations until a public cue.

A partner's first rudder/thrust placement is a public constraint. Before
that cue, keep the familiar safe blueprint instead of asking an unknown
partner to infer a new private convention. No partner hand is inspected.
"""
from .actions import ROLES
from .coherent_advice import profile12_masks
from .coherent_safety import coherent_safe_actions
from .module_capacity import reserve_controls
from .public_contract import PublicContractAgent
from .safety_guard import safe_actions


def partner_control_published(view):
    other=1-ROLES.index(view['role'])
    return any(view['board'][i] is not None for i in (other,other+2))


class ResponseContractAgent(PublicContractAgent):
    def select(self,view,raw):
        if partner_control_published(view):
            return super().select(view,raw)
        allowed,_=coherent_safe_actions(self.airport,view,raw)
        allowed=reserve_controls(view,allowed)
        baseline_safe,_=safe_actions(self.airport,view,allowed)
        baseline_mask,reference=profile12_masks(view,baseline_safe)
        chosen=self.agent.select(view,baseline_mask,reference_mask=reference)
        self.last_report=dict(baseline=chosen,chosen=chosen,ranks={},planning_mode='await_public_partner_control')
        return chosen
