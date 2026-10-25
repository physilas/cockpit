"""Editable PyTorch actor-critic draft; shared weights, role-limited inputs.

The actor produces raw logits, NOT sigmoid scores. Masks are applied for both
sampling and PPO updates. The critic receives the SAME permitted observation.
"""
import torch
from torch import nn
from torch.distributions import Categorical
import math

from .actions import ACTION_COUNT
from .observation import OBSERVATION_SIZE, feature_names


class ActorCritic(nn.Module):
    def __init__(self, observation_size=OBSERVATION_SIZE, action_count=ACTION_COUNT, hidden_size=128, hidden_layers=2):
        super().__init__()
        if any(type(n) is not int or n < 1 for n in (observation_size, action_count, hidden_size, hidden_layers)):
            raise ValueError("Netzdimensionen und Schichtanzahl müssen positive ganze Zahlen sein.")
        self.config = {"observation_size": observation_size, "action_count": action_count,
                       "hidden_size": hidden_size, "hidden_layers": hidden_layers}
        # Keep the original encoder keys (0, 2) for legacy two-layer checkpoints.
        layers = []
        for index in range(hidden_layers):
            layers.extend((nn.Linear(observation_size if index == 0 else hidden_size, hidden_size), nn.Tanh()))
        self.encoder = nn.Sequential(*layers)
        self.actor = nn.Linear(hidden_size, action_count)
        self.critic = nn.Linear(hidden_size, 1)
        for layer in self.modules():
            if isinstance(layer, nn.Linear):
                nn.init.orthogonal_(layer.weight, gain=2 ** 0.5)
                nn.init.zeros_(layer.bias)
        nn.init.orthogonal_(self.actor.weight, gain=0.01)
        nn.init.orthogonal_(self.critic.weight, gain=1.0)

    def forward(self, observation):
        features = self.encoder(observation)
        return self.actor(features), self.critic(features).squeeze(-1)

    def policy_output(self, observation, reference_mask=None):
        if reference_mask is not None:
            raise ValueError('This policy does not consume a reference planner mask.')
        return self(observation)

    def distribution(self, observation, action_mask, uniform_mix=0.0, *, reference_mask=None):
        if not 0 <= uniform_mix <= 1:
            raise ValueError("uniform_mix must be between 0 and 1.")
        logits, value = self.policy_output(observation, reference_mask)
        mask = torch.as_tensor(action_mask, dtype=torch.bool, device=logits.device)
        if mask.shape != logits.shape or not bool(mask.any(dim=-1).all()):
            raise ValueError("Jede Beobachtung braucht eine passende Maske mit mindestens einer erlaubten Aktion.")
        if reference_mask is not None and bool((torch.as_tensor(reference_mask, dtype=torch.bool, device=mask.device) & ~mask).any()):
            raise ValueError('Reference planner actions must be inside the allowed policy mask.')
        logits = logits.masked_fill(~mask, torch.finfo(logits.dtype).min)
        distribution = Categorical(logits=logits)
        if uniform_mix:
            uniform = mask.to(logits.dtype) / mask.sum(dim=-1, keepdim=True)
            probabilities = (1 - uniform_mix) * distribution.probs + uniform_mix * uniform
            distribution = Categorical(probs=probabilities)
        return distribution, value

    def act(self, observation, action_mask, deterministic=False, uniform_mix=0.0, *, reference_mask=None):
        distribution, value = self.distribution(observation, action_mask, uniform_mix, reference_mask=reference_mask)
        action = distribution.logits.argmax(dim=-1) if deterministic else distribution.sample()
        return action, distribution.log_prob(action), value

    def evaluate_actions(self, observation, action_mask, actions, uniform_mix=0.0, *, reference_mask=None):
        distribution, value = self.distribution(observation, action_mask, uniform_mix, reference_mask=reference_mask)
        return distribution.log_prob(actions), distribution.entropy(), value


class RoleActorCritic(ActorCritic):
    """Separate trainable role heads with the same permitted feature boundary."""
    def __init__(self, pilot, kopilot):
        nn.Module.__init__(self)
        if any(pilot.config[k]!=kopilot.config[k] for k in ('observation_size','action_count')):
            raise ValueError('Role models need the same observation and action schema.')
        if any('kind' in model.config for model in (pilot,kopilot)):
            raise ValueError('Nested role ensembles are not supported.')
        self.roles=nn.ModuleDict({'pilot':pilot,'kopilot':kopilot})
        self.config={**pilot.config,'kind':'role_ensemble',
                     'roles':{role:model.config for role,model in self.roles.items()}}
        self.pilot_feature=feature_names().index('role.pilot')

    def forward(self, observation):
        pilot_logits,pilot_value=self.roles['pilot'](observation)
        copilot_logits,copilot_value=self.roles['kopilot'](observation)
        pilot=observation[...,self.pilot_feature]>.5
        return torch.where(pilot.unsqueeze(-1),pilot_logits,copilot_logits),torch.where(pilot,pilot_value,copilot_value)



class ResidualActorCritic(ActorCritic):
    """A frozen inherited player plus a zero-output trainable detail branch."""
    def __init__(self,source,observation_size,action_count,hidden_size=256,hidden_layers=2):
        nn.Module.__init__(self)
        if source.config.get('kind') == 'guided_residual':
            raise ValueError('Resume guided policies; their planner prior cannot be frozen as raw logits.')
        if observation_size<source.config['observation_size'] or action_count<source.config['action_count']:
            raise ValueError('Residual transfer must preserve the source prefix.')
        self.source=source
        self.source.requires_grad_(False)
        self.residual=ActorCritic(observation_size,action_count,hidden_size,hidden_layers)
        nn.init.zeros_(self.residual.actor.weight);nn.init.zeros_(self.residual.actor.bias)
        nn.init.zeros_(self.residual.critic.weight);nn.init.zeros_(self.residual.critic.bias)
        self.config={'kind':'residual','observation_size':observation_size,'action_count':action_count,
                     'hidden_size':hidden_size,'hidden_layers':hidden_layers,'source':source.config}

    def forward(self,observation):
        original,value=self.source(observation[...,:self.source.config['observation_size']])
        detail,correction=self.residual(observation)
        original=nn.functional.pad(original,(0,detail.shape[-1]-original.shape[-1]))
        return original+detail,value+correction


class GuidedResidualActorCritic(ResidualActorCritic):
    """A finite public planner prior, with learnable departures from its advice.

    At initialization every newly admitted action starts `guide_margin` logits
    below the frozen player's best reference action. Its old reference rankings
    and deterministic decisions are preserved. Unlike a hard mask, departures
    have nonzero probability and gradients, and the residual can promote them.
    """
    def __init__(self, source, observation_size, action_count, hidden_size=256, hidden_layers=2, guide_margin=4.):
        if source.config.get('kind') == 'guided_residual' or not math.isfinite(guide_margin) or guide_margin <= 0:
            raise ValueError('A finite positive margin and an unguided frozen source are required.')
        super().__init__(source, observation_size, action_count, hidden_size, hidden_layers)
        if isinstance(source, ResidualActorCritic) and source.residual.config['hidden_size'] == hidden_size and source.residual.config['hidden_layers'] == hidden_layers:
            self.residual.encoder.load_state_dict(source.residual.encoder.state_dict())
        self.guide_margin = float(guide_margin)
        self.config.update(kind='guided_residual', guide_margin=self.guide_margin)

    def policy_output(self, observation, reference_mask=None):
        original, value = self.source(observation[..., :self.source.config['observation_size']])
        detail, correction = self.residual(observation)
        original = nn.functional.pad(original, (0, detail.shape[-1] - original.shape[-1]))
        if reference_mask is None:
            raise ValueError('Guided policy requires its public reference planner mask.')
        reference = torch.as_tensor(reference_mask, dtype=torch.bool, device=detail.device)
        if reference.shape != original.shape or not bool(reference.any(dim=-1).all()):
            raise ValueError('Every guided decision needs a matching nonempty reference mask.')
        top = original.masked_fill(~reference, torch.finfo(original.dtype).min).amax(-1, keepdim=True)
        prior = torch.where(reference, original, top - self.guide_margin)
        return prior + detail, value + correction

def build_model(config):
    if config.get('kind') == 'guided_residual':
        model = GuidedResidualActorCritic(build_model(config['source']), **{k: config[k] for k in
            ('observation_size', 'action_count', 'hidden_size', 'hidden_layers', 'guide_margin')})
        if model.config != config: raise ValueError('Non-canonical guided model configuration.')
        return model
    if config.get('kind')=='residual':
        model=ResidualActorCritic(build_model(config['source']),**{k:config[k] for k in ('observation_size','action_count','hidden_size','hidden_layers')})
        if model.config!=config:raise ValueError('Non-canonical residual model configuration.')
        return model
    if config.get('kind')=='role_ensemble':
        if set(config['roles'])!={'pilot','kopilot'}:
            raise ValueError('Both role heads are required.')
        model=RoleActorCritic(*(build_model(config['roles'][role]) for role in ('pilot','kopilot')))
        if model.config!=config:
            raise ValueError('Non-canonical role model configuration.')
        return model
    return ActorCritic(**config)
