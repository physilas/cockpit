"""Editable PyTorch actor-critic draft; shared weights, role-limited inputs.

The actor produces raw logits, NOT sigmoid scores. Masks are applied for both
sampling and PPO updates. The critic receives the SAME permitted observation.
"""
import torch
from torch import nn
from torch.distributions import Categorical

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

    def distribution(self, observation, action_mask, uniform_mix=0.0):
        if not 0 <= uniform_mix <= 1:
            raise ValueError("uniform_mix must be between 0 and 1.")
        logits, value = self(observation)
        mask = torch.as_tensor(action_mask, dtype=torch.bool, device=logits.device)
        if mask.shape != logits.shape or not bool(mask.any(dim=-1).all()):
            raise ValueError("Jede Beobachtung braucht eine passende Maske mit mindestens einer erlaubten Aktion.")
        logits = logits.masked_fill(~mask, torch.finfo(logits.dtype).min)
        distribution = Categorical(logits=logits)
        if uniform_mix:
            uniform = mask.to(logits.dtype) / mask.sum(dim=-1, keepdim=True)
            probabilities = (1 - uniform_mix) * distribution.probs + uniform_mix * uniform
            distribution = Categorical(probs=probabilities)
        return distribution, value

    def act(self, observation, action_mask, deterministic=False, uniform_mix=0.0):
        distribution, value = self.distribution(observation, action_mask, uniform_mix)
        action = distribution.logits.argmax(dim=-1) if deterministic else distribution.sample()
        return action, distribution.log_prob(action), value

    def evaluate_actions(self, observation, action_mask, actions, uniform_mix=0.0):
        distribution, value = self.distribution(observation, action_mask, uniform_mix)
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


def build_model(config):
    if config.get('kind')=='role_ensemble':
        if set(config['roles'])!={'pilot','kopilot'}:
            raise ValueError('Both role heads are required.')
        model=RoleActorCritic(*(build_model(config['roles'][role]) for role in ('pilot','kopilot')))
        if model.config!=config:
            raise ValueError('Non-canonical role model configuration.')
        return model
    return ActorCritic(**config)
