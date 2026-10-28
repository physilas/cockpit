"""New experimental public contract policy; existing releases stay unchanged."""
from .contract_advice import contract_masks
from .safe_environment import SafeResearchEnv
from .rollout_search import GuidedBlueprint


class ContractTrainingEnv(SafeResearchEnv):
    def __init__(self,*args,contract_beam=24,**kwargs):
        self.contract_beam=contract_beam
        self.contract_report={}
        super().__init__(*args,**kwargs)

    def _assist(self,mask):
        allowed,self._reference_mask,self.contract_report=contract_masks(
            self.game.landung._flughafen_code,self.view(),mask,beam=self.contract_beam)
        return allowed


class ContractBlueprint(GuidedBlueprint):
    def __init__(self,airport,model,*,beam=24):
        super().__init__(model)
        self.airport,self.beam=airport,beam
        self.last_report={}

    def masks(self,view,raw):
        allowed,reference,self.last_report=contract_masks(self.airport,view,raw,beam=self.beam)
        return allowed,reference
