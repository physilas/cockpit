"""Explicit new research mask over preserved prior/joint references.

Old masks/references remain available as pre_guard_* snapshots. They need not
be subsets of the NEW mask and must be paired with their original action mask.
Only the current reference must be a subset of the current allowed mask.
"""
import json
from copy import deepcopy

from .joint_landing_advice import joint_landing_reference
from .joint_landing_environment import JointLandingEnv
from .task_deadline_guard import preserve_task_budget
from .wind_ice_prior_advice import prior_reference


class TaskDeadlineEnv(JointLandingEnv):
    def __init__(self,*args,**kwargs):
        self._deadline_cache=None
        self._pre_guard_allowed=None
        self._pre_guard_reference=None
        self._deadline_metadata={}
        super().__init__(*args,**kwargs)

    def _assist(self,mask):
        previous_allowed=super()._assist(mask)
        previous_reference=list(self._reference_mask)
        self._pre_guard_allowed=list(previous_allowed)
        self._pre_guard_reference=list(previous_reference)
        view=self.view()
        key=json.dumps(view,sort_keys=True),tuple(previous_allowed),tuple(previous_reference)
        if self._deadline_cache is None or self._deadline_cache[0]!=key:
            if self.current_role in self.assisted_roles:
                allowed,metadata=preserve_task_budget(view,previous_allowed,cpu_duty_cycle=self.planning_cpu_duty_cycle)
            else:
                allowed,metadata=list(previous_allowed),dict(eligible=False,removed=[],fallback=False)
            reference=previous_reference
            if allowed!=previous_allowed:
                seed=[bool(a and r) for a,r in zip(allowed,previous_reference)]
                if not any(seed):seed=list(allowed)
                reference=prior_reference(view,allowed,seed,cpu_duty_cycle=self.planning_cpu_duty_cycle)
                reference=joint_landing_reference(view,allowed,reference,cpu_duty_cycle=self.planning_cpu_duty_cycle)
            self._deadline_cache=key,tuple(allowed),tuple(reference),metadata
        self._reference_mask=list(self._deadline_cache[2])
        self._deadline_metadata=self._deadline_cache[3]
        return list(self._deadline_cache[1])

    def info(self):
        result=super().info()
        result['research_task_deadline']=True
        active=any(result['action_mask'])
        result['pre_guard_action_mask']=list(self._pre_guard_allowed) if active and self._pre_guard_allowed is not None else list(result['action_mask'])
        result['pre_guard_reference_action_mask']=list(self._pre_guard_reference) if active and self._pre_guard_reference is not None else list(result['action_mask'])
        result['task_deadline']=deepcopy(self._deadline_metadata) if active else dict(eligible=False,removed=[],fallback=False)
        return result
