"""Torch-free coherent immediate shield with the existing profile-12 prior."""
from .coherent_safety import coherent_safe_actions
from .module_capacity import reserve_controls
from .module_guidance import module_guidance


def profile12_masks(view,raw):
    legacy_allowed,reference=module_guidance(view,raw)
    modules=set(view['modules_state']['modules'])
    if 'leak' in modules and not modules&{'wind','ice','intern'}:
        from .leak_card_advice import leak_card_reference
        reference=leak_card_reference(view,legacy_allowed)
    if not any(legacy_allowed):legacy_allowed=list(raw)
    reference=[bool(a and r) for a,r in zip(legacy_allowed,reference)]
    if not any(reference):reference=list(legacy_allowed)
    return legacy_allowed,reference


def coherent_masks(airport,view,raw):
    safe,report=coherent_safe_actions(airport,view,raw)
    safe=reserve_controls(view,safe)
    _,reference=profile12_masks(view,safe)
    reference=[bool(a and r) for a,r in zip(safe,reference)]
    if not any(reference):reference=list(safe)
    return safe,reference,report


class CoherentBlueprint:
    def __init__(self,airport,model):
        from .agents import ModelAgent
        self.airport,self.model,self.agent=airport,model,ModelAgent(model)
        self.last_report={}

    def masks(self,view,raw):
        allowed,reference,self.last_report=coherent_masks(self.airport,view,raw)
        return allowed,reference

    def select(self,view,raw):
        allowed,reference=self.masks(view,raw)
        return self.agent.select(view,allowed,reference_mask=reference)

    def rank(self,view,raw):
        import torch
        from .modules import module_encode
        allowed,reference=self.masks(view,raw)
        device=next(self.model.parameters()).device
        with torch.no_grad():
            logits,_=self.model.policy_output(torch.tensor(module_encode(view),dtype=torch.float32,device=device),
                                              reference_mask=reference)
        values=logits.detach().cpu().tolist()
        ranked=sorted((i for i,ok in enumerate(allowed) if ok),key=lambda i:(-values[i],i))
        return ranked[0],ranked
