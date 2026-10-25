"""Separate terminal search overlay; preserves the earlier prior reference.

The evaluator may execute the first proven action instead of asking the policy.
This is an explicit search player, not new trained weights or a browser profile.
"""
import json

from .solo_landing import eligible, prove_landing, Proof
from .wind_ice_prior_environment import PriorWindIceEnv


class SoloLandingEnv(PriorWindIceEnv):
    def __init__(self, *args, **kwargs):
        self._landing_proof_cache = None
        super().__init__(*args, **kwargs)

    def info(self):
        result = super().info()
        view = self.view()
        proof = Proof()
        if not self.done and self.current_role in self.assisted_roles and eligible(view):
            key = json.dumps(view,sort_keys=True),tuple(result['action_mask']),self.max_steps-self.steps
            if self._landing_proof_cache is None or self._landing_proof_cache[0] != key:
                proof = prove_landing(view,self.game.landung.get_code(),allowed=result['action_mask'],
                    max_actions=min(32,self.max_steps-self.steps),cpu_duty_cycle=self.planning_cpu_duty_cycle)
                self._landing_proof_cache = key,proof
            proof = self._landing_proof_cache[1]
        result['research_solo_landing'] = True
        result['landing_proof'] = dict(eligible=proof.eligible,actions=list(proof.actions),
            nodes=proof.nodes,exhausted=proof.exhausted,unknown_roll=proof.unknown_roll)
        return result
