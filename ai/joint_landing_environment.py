"""Separate static joint-task reference, over the preserved public prior."""
import json

from .joint_landing_advice import eligible,joint_landing_plans
from .wind_ice_prior_environment import PriorWindIceEnv


class JointLandingEnv(PriorWindIceEnv):
    def __init__(self,*args,**kwargs):
        self._joint_cache=None
        self._prior_reference=None
        self._joint_metadata={}
        super().__init__(*args,**kwargs)

    def _assist(self,mask):
        allowed=super()._assist(mask)
        self._prior_reference=list(self._reference_mask)
        view=self.view()
        self._joint_metadata=dict(eligible=False,positive_candidates=0,maximum_assignment_score=0.)
        if self.current_role not in self.assisted_roles or not eligible(view):return allowed
        key=json.dumps(view,sort_keys=True),tuple(allowed),tuple(self._prior_reference)
        if self._joint_cache is None or self._joint_cache[0]!=key:
            scores=joint_landing_plans(view,allowed,cpu_duty_cycle=self.planning_cpu_duty_cycle)
            best=max(scores.values(),default=0.)
            reference=tuple(bool(flag and scores.get(i,-1)>=best-1.) for i,flag in enumerate(allowed)) if best>0 else tuple(self._prior_reference)
            metadata=dict(eligible=True,positive_candidates=sum(score>0 for score in scores.values()),
                          maximum_assignment_score=best)
            self._joint_cache=key,reference,metadata
        self._reference_mask=list(self._joint_cache[1]);self._joint_metadata=dict(self._joint_cache[2])
        return allowed

    def info(self):
        result=super().info()
        result['research_joint_landing']=True
        result['prior_reference_action_mask']=list(self._prior_reference) if any(result['action_mask']) and self._prior_reference is not None else list(result['action_mask'])
        result['joint_landing']=dict(self._joint_metadata) if not self.done else dict(eligible=False,positive_candidates=0,maximum_assignment_score=0.)
        return result
