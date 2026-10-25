import unittest

import torch

from ai.checkpoints import weight_fingerprint
from ai.nn_model import ActorCritic, GuidedResidualActorCritic
from ai.route_policy_probe import PolicyProbeEnv, actor_gradients, gradient_geometry
from ai.search_environment import OpenRiskEnv
from ai.train import collect_rollout


class RoutePolicyProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)

    def test_probe_preserves_stochastic_actions_engine_draws_and_rollout_tensors(self):
        torch.manual_seed(251042)
        model = GuidedResidualActorCritic(ActorCritic(489, 217, 8, 1), 489, 217, 8, 1)
        sha = weight_fingerprint(model)
        ordinary = OpenRiskEnv('LOG_HND_GREEN', assistance_version=9, proposal_beam=16)
        probe = PolicyProbeEnv('LOG_HND_GREEN', assistance_version=9, proposal_beam=16,
                               control=model, candidate=model, uniform_mix=.03)
        options = dict(seed='route-policy-probe-unit', episodes_done=0, gamma=.995,
                       gae_lambda=.95, uniform_mix=.03, discount_unit='placement')
        torch.manual_seed(123)
        expected, records = collect_rollout(model, ordinary, 8, **options)
        rng = torch.get_rng_state().clone()
        torch.manual_seed(123)
        actual, observed = collect_rollout(model, probe, 8, **options)
        self.assertEqual(observed, records)
        self.assertTrue(torch.equal(torch.get_rng_state(), rng))
        for key in expected:
            torch.testing.assert_close(expected[key], actual[key], rtol=0, atol=0)
        count = probe.probe_counts['LOG_HND_GREEN']
        self.assertEqual(count['decisions'], len(actual['actions']))
        self.assertEqual(len(probe.probe_routes), len(actual['actions']))
        self.assertEqual(count['learning_changes'], 0)
        self.assertEqual(count['semantic_learning_changes'], 0)
        self.assertAlmostEqual(count['control_policy_proposal_mass'], count['candidate_policy_proposal_mass'])
        self.assertAlmostEqual(count['control_sampling_proposal_mass'], count['candidate_sampling_proposal_mass'])
        self.assertEqual(weight_fingerprint(model), sha)

    def test_route_projection_detects_a_conflicting_weighted_actor_direction(self):
        result = gradient_geometry({'OSL':torch.tensor([1., 0.]), 'HND':torch.tensor([-3., 0.])},
                                   {'OSL':1, 'HND':3})
        self.assertEqual(result['pairs'][0]['cosine'], -1.)
        self.assertTrue(result['routes']['OSL']['combined_opposes_route'])
        self.assertFalse(result['routes']['HND']['combined_opposes_route'])
        zero = gradient_geometry({'a':torch.zeros(2), 'b':torch.ones(2)}, {'a':1, 'b':1})
        self.assertIsNone(zero['pairs'][0]['cosine'])

    def test_actor_probe_keeps_parameters_gradients_and_reference_probabilities(self):
        torch.manual_seed(251043)
        model = GuidedResidualActorCritic(ActorCritic(3, 2, 8, 1), 3, 2, 8, 1)
        torch.nn.init.normal_(model.residual.actor.weight, std=.03)
        observations = torch.randn(12, 3)
        masks = torch.ones(12, 2, dtype=torch.bool)
        references = torch.tensor([[True, False]] * 12)
        with torch.no_grad():
            actions, logp, _ = model.act(observations, masks, uniform_mix=.03, reference_mask=references)
        batch = dict(observations=observations, masks=masks, reference_masks=references,
                     actions=actions, log_probs=logp, advantages=torch.linspace(-1, 1, 12))
        before = weight_fingerprint(model)
        for parameter in model.parameters():
            parameter.grad = torch.full_like(parameter, 7.)
        result = actor_gradients(model, batch, ['OSL']*6 + ['HND']*6,
                                 [0]*3+[1]*3+[0]*3+[1]*3, uniform_mix=.03, duty=1.)
        self.assertEqual(weight_fingerprint(model), before)
        self.assertTrue(all(bool((p.grad == 7.).all()) for p in model.parameters()))
        self.assertLess(result['max_rollout_ratio_error'], 1e-5)
        self.assertEqual(result['full_actor']['routes']['OSL']['weight'], .5)
        self.assertEqual(result['independent_episode_halves']['HND']['decisions'], [3, 3])
        self.assertFalse(result['value_entropy_imitation_gradients_included'])
        with self.assertRaises(ValueError):
            actor_gradients(model, batch, ['OSL'], [0], uniform_mix=.03)


if __name__ == '__main__':
    unittest.main()
