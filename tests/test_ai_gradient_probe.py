import unittest

import torch

from ai.gradient_probe import diagnose, interference
from ai.nn_model import ActorCritic, GuidedResidualActorCritic


class GradientProbeTests(unittest.TestCase):
    def test_opposing_critic_can_reverse_joint_policy_step(self):
        result = interference(torch.tensor([1., 0.]), torch.tensor([-3., 0.]), torch.tensor([.5, 0.]))
        self.assertEqual(result['value_policy_norm_ratio'], 3.)
        self.assertEqual(result['policy_value_cosine'], -1.)
        self.assertTrue(result['policy_value_conflict'])
        self.assertTrue(result['joint_gradient_opposes_policy'])
        self.assertLess(result['joint_policy_projection'], 0.)
        # With zero policy gradient, the cosine/ratio are undefined, not NaN.
        result = interference(torch.zeros(2), torch.ones(2))
        self.assertIsNone(result['policy_value_cosine'])
        self.assertIsNone(result['value_policy_norm_ratio'])

    def test_probe_preserves_weights_and_existing_gradients(self):
        torch.manual_seed(17)
        model = ActorCritic(3, 2, 8, 1)
        observations = torch.randn(12, 3)
        masks = torch.ones(12, 2, dtype=torch.bool)
        with torch.no_grad():
            actions, logp, values = model.act(observations, masks, uniform_mix=.03)
        batch = dict(observations=observations, masks=masks, actions=actions,
                     log_probs=logp, values=values, advantages=torch.linspace(-1, 1, 12), returns=values + .3)
        before = {k: v.clone() for k, v in model.state_dict().items()}
        for p in model.parameters():
            p.grad = torch.full_like(p, 7.)
        result = diagnose(model, batch, minibatch_size=4, cpu_duty_cycle=1.)
        self.assertEqual(result['minibatches'], 3)
        self.assertLess(result['max_rollout_ratio_error']['max'], 1e-5)
        self.assertGreater(result['weighted_value_norm']['mean'], 0.)
        for key, value in model.state_dict().items():
            torch.testing.assert_close(value, before[key], rtol=0, atol=0)
        for p in model.parameters():
            self.assertTrue(torch.all(p.grad == 7.))

    def test_guided_replay_and_value_head_are_measured_with_reference_masks(self):
        torch.manual_seed(23)
        model = GuidedResidualActorCritic(ActorCritic(3, 2, 8, 1), 3, 2, 8, 1)
        # A fresh zero-output residual has no actor-to-encoder gradient yet.
        # Measure a trained branch with both heads connected to its encoder.
        torch.nn.init.normal_(model.residual.actor.weight, std=.03)
        torch.nn.init.constant_(model.residual.critic.weight, .1)
        observations = torch.randn(12, 3)
        masks = torch.ones(12, 2, dtype=torch.bool)
        reference = torch.tensor([[True, False]] * 12)
        with torch.no_grad():
            actions, logp, values = model.act(observations, masks, uniform_mix=.03, reference_mask=reference)
        batch = dict(observations=observations, masks=masks, reference_masks=reference, actions=actions,
                     log_probs=logp, advantages=torch.linspace(-1, 1, 12), returns=values + .3)
        replay = {k: batch[k] for k in ('observations', 'masks', 'reference_masks', 'actions')}
        result = diagnose(model, batch, minibatch_size=4, demonstrations=replay, cpu_duty_cycle=1.)
        self.assertGreater(result['weighted_demo_norm']['mean'], 0.)
        self.assertGreater(result['weighted_value_norm']['mean'], 0.)
        self.assertLess(result['max_rollout_ratio_error']['max'], 1e-5)
        self.assertTrue(all(p.grad is None for p in model.source.parameters()))


if __name__ == '__main__':
    unittest.main()
