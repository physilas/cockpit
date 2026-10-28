"""Small synthetic checks of optional offline actor-head refinement."""
from copy import deepcopy
import unittest

import torch

from ai.feedback import Feedback, load_feedback
from ai.nn_model import ActorCritic, GuidedResidualActorCritic
from ai.train_feedback import candidate_config, feedback_loss, refine_actor, session_split
from tests.test_ai_feedback import HISTORICAL_EXPORTS


def fixture(version=1):
    features, actions = (349, 121) if version == 1 else (489, 217)
    observation = tuple([1., 0.] + [0.]*(features-2))
    mask = tuple([True, True] + [False]*(actions-2))
    chosen = tuple(1 if index % 2 else 0 for index in range(64))
    ratings = tuple(1 if action else -1 for action in chosen)
    return Feedback((observation,)*64, (mask,)*64, chosen, ratings,
                    (mask,)*64 if version == 3 else None,
                    tuple(f'session-{index//16}' for index in range(64)),
                    {'schema_version': version, 'sha256': 'synthetic-unit-test'})


class OfflineFeedbackLearningTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(1)
        torch.manual_seed(23)

    def test_session_split_never_shares_a_game(self):
        data = fixture()
        train, validation = session_split(data.session_ids)
        first = {data.session_ids[index] for index in train}
        second = {data.session_ids[index] for index in validation}
        self.assertFalse(first & second)
        self.assertEqual(len(train)+len(validation), 64)
        self.assertEqual((train, validation), session_split(data.session_ids))

    def test_sparse_real_archives_are_rejected_without_any_update(self):
        data = load_feedback(HISTORICAL_EXPORTS, schema_version=1)
        policy = ActorCritic(hidden_size=8, hidden_layers=1)
        original = deepcopy(policy.state_dict())
        with self.assertRaisesRegex(ValueError, 'Insufficient feedback'):
            refine_actor(policy, data)
        self.assertTrue(all(torch.equal(value, original[name]) for name, value in policy.state_dict().items()))

    def test_positive_and_negative_feedback_have_the_intended_direction(self):
        for rating in (1., -1.):
            logits = torch.zeros(2, requires_grad=True)
            distribution = torch.distributions.Categorical(logits=logits)
            loss = feedback_loss(distribution, torch.tensor(1), torch.tensor(rating))
            loss.backward()
            self.assertLess(float(logits.grad[1])*rating, 0.)

    def test_negative_rating_reduces_the_entire_equivalent_action_family(self):
        logits=torch.zeros(3,requires_grad=True)
        distribution=torch.distributions.Categorical(logits=logits)
        loss=feedback_loss(distribution,torch.tensor(0),torch.tensor(-1.),torch.tensor([True,True,False]))
        loss.backward()
        self.assertGreater(float(logits.grad[0]),0.)
        self.assertGreater(float(logits.grad[1]),0.)
        self.assertLess(float(logits.grad[2]),0.)

    def test_guided_refinement_changes_only_existing_head_and_preserves_critic_values(self):
        data = fixture(3)
        policy = GuidedResidualActorCritic(ActorCritic(489, 217, 8, 1), 489, 217,
                                           hidden_size=8, hidden_layers=1)
        original = deepcopy(policy.state_dict())
        flags = [parameter.requires_grad for parameter in policy.parameters()]
        observations = data.tensors()['observations']
        with torch.no_grad(): initial_values = policy(observations)[1].clone()
        result = refine_actor(policy, data)
        self.assertTrue(result['candidate_accepted'])
        self.assertLess(result['selected_validation_feedback_loss'], result['baseline_validation_feedback_loss'])
        changed = [name for name, value in policy.state_dict().items() if not torch.equal(value, original[name])]
        self.assertTrue(changed)
        self.assertTrue(all(name.startswith('residual.actor.') for name in changed), changed)
        self.assertEqual(flags, [parameter.requires_grad for parameter in policy.parameters()])
        with torch.no_grad(): self.assertTrue(torch.equal(initial_values, policy(observations)[1]))
        self.assertFalse(result['release_evidence'])
        self.assertFalse(result['goal_achieved'])
        self.assertTrue(all(row['validation_policy_kl'] <= .01 for row in result['history']))

    def test_mismatched_schema_or_guided_reference_is_rejected(self):
        policy = GuidedResidualActorCritic(ActorCritic(489, 217, 8, 1), 489, 217,
                                           hidden_size=8, hidden_layers=1)
        with self.assertRaisesRegex(ValueError, 'schemas differ'):
            refine_actor(policy, fixture(1))
        data = fixture(3)
        missing = Feedback(data.observations, data.masks, data.actions, data.ratings, None,
                           data.session_ids, data.manifest)
        with self.assertRaisesRegex(ValueError, 'saved reference'):
            refine_actor(policy, missing)

    def test_candidate_cannot_inherit_release_approval_or_supported_routes(self):
        source = {'quality': {'approved': True, 'route_results': {'MUC': {'win_rate': .99}}},
                  'recommended': True, 'display_name': 'Crew 2', 'id': 'crew2-v1',
                  'supported_airports': ['MUC'], 'supported_modules': ['kerosene'],
                  'supported_cards': ['control'], 'seed': 123, 'assistance_version': 9}
        before = deepcopy(source)
        config = candidate_config(source, feedback_sha='ratings-sha', source_sha='source-sha',
                                  source_checkpoint='ai/releases/crew2-v1/best.pt')
        self.assertEqual(source, before)
        self.assertFalse(config['quality']['approved'])
        self.assertFalse(config['recommended'])
        self.assertEqual(config['supported_airports'], [])
        self.assertNotIn('supported_modules', config)
        self.assertNotIn('supported_cards', config)
        self.assertNotIn('route_results', config['quality'])
        self.assertNotIn('id', config)
        self.assertEqual(config['feedback_source_weights_sha256'], 'source-sha')
        self.assertEqual(config['feedback_sha256'], 'ratings-sha')
        self.assertEqual(config['assistance_version'], 9)


if __name__ == '__main__':
    unittest.main()
