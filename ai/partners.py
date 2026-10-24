"""Frozen, separately owned partners; only their own permitted view is used."""
from pathlib import Path

from .agents import HeuristicAgent, ModelAgent


class FrozenPartner:
    def __init__(self, checkpoint, *, stochastic=False):
        from .checkpoints import load_checkpoint
        model, payload = load_checkpoint(checkpoint)
        self.profile = payload['train_config'].get('assistance_version', 0)
        self.agent = ModelAgent(model, deterministic=not stochastic, uniform_mix=.05 if stochastic else 0)

    def select(self, view, mask):
        if self.profile:
            from .tactics import assisted_mask
            mask = assisted_mask(view, mask, version=self.profile)
        return self.agent.select(view, mask)


def partner_specs(checkpoints=()):
    """Retain the independent weak partner alongside deterministic/noisy releases."""
    specs = [{'kind': 'heuristic'}]
    for checkpoint in checkpoints:
        specs.extend({'kind': 'frozen', 'checkpoint': str(Path(checkpoint).resolve()), 'stochastic': noisy}
                     for noisy in (False, True))
    return specs


def make_partner(spec):
    if spec['kind'] == 'heuristic':
        return HeuristicAgent()
    if spec['kind'] == 'frozen':
        return FrozenPartner(spec['checkpoint'], stochastic=spec.get('stochastic', False))
    raise ValueError(f"Unknown partner: {spec['kind']}")
