"""Separate native environments for prospective public browser profiles.

Legacy ModuleEnv/profile behavior remains intact. This adapter uses the same
pure mask functions as strategy_bridge and retains the real engine clock.
"""
from .modules import ModuleEnv


class StrategyEnv(ModuleEnv):
    def __init__(self,*args,assistance_version=13,**kwargs):
        if assistance_version not in (13,14):
            raise ValueError('Use public strategy profile13 or14.')
        super().__init__(*args,assistance_version=0,**kwargs)
        self.assistance_version=assistance_version
        self.strategy_report={}

    def _assist(self,raw):
        if self.current_role not in self.assisted_roles:
            self._reference_mask=list(raw)
            return raw
        airport=self.game.landung._flughafen_code
        if self.assistance_version==13:
            from .public_contract import public_contract_inputs
            allowed,self._reference_mask,self.strategy_report=public_contract_inputs(airport,self.view(),raw)
        else:
            from .coherent_advice import coherent_masks
            allowed,self._reference_mask,self.strategy_report=coherent_masks(airport,self.view(),raw)
        return allowed

    def info(self):
        result=super().info()
        result['reference_action_mask']=(list(self._reference_mask) if any(result['action_mask'])
                                         else list(result['action_mask']))
        if self.assistance_version==13:
            result['public_plan']=self.strategy_report if any(result['action_mask']) else None
        return result
