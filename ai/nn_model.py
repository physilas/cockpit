"""Editable PyTorch actor-critic draft; shared weights, role-limited inputs.

The actor produces raw logits, NOT sigmoid scores. Masks are applied for both
sampling and PPO updates. The critic receives the SAME permitted observation.
"""
import torch
from torch import nn
from torch.distributions import Categorical

from .actions import ACTION_COUNT
from .observation import OBSERVATION_SIZE


class ActorCritic(nn.Module):
    def __init__(self, observation_size=OBSERVATION_SIZE, action_count=ACTION_COUNT, hidden_size=128):
        super().__init__()
        self.config = {"observation_size": observation_size, "action_count": action_count, "hidden_size": hidden_size}
        self.encoder = nn.Sequential(nn.Linear(observation_size, hidden_size), nn.Tanh(),
                                     nn.Linear(hidden_size, hidden_size), nn.Tanh())
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
