"""Case identity and route-balanced all-module development evaluation."""
from collections import Counter, defaultdict
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ai.module_training_eval import balanced_cases, case_key, evaluate_cases, load_cases, run_case


MATRIX = Path(__file__).resolve().parents[1] / 'ai/experiments/modules-50pct-2026-10-25/matrix.json'


class TinyPolicy:
    config = {'kind': 'guided_residual', 'observation_size': 489, 'action_count': 217}
    training = True

    def eval(self):
        self.training = False

    def train(self, value=True):
        self.training = value


class FirstLegalAgent:
    calls = 0

    def __init__(self, model):
        self.model = model

    def select(self, view, mask, *, reference_mask=None):
        if reference_mask is None or not any(reference_mask):
            raise AssertionError('Guided policy lost its reference mask.')
        if any(reference and not legal for reference, legal in zip(reference_mask, mask)):
            raise AssertionError('Reference escaped legality.')
        type(self).calls += 1
        return next(index for index, legal in enumerate(mask) if legal)


class ModuleTrainingEvaluationTests(unittest.TestCase):
    def test_matrix_and_balanced_curriculum_cover_all_cases(self):
        cases = load_cases(MATRIX)
        weighted = balanced_cases(cases)
        self.assertEqual(len(cases), 186)
        self.assertEqual(len(weighted), 630)
        self.assertEqual({case_key(case) for case in weighted}, {case_key(case) for case in cases})
        self.assertEqual(set(Counter(case['airport'] for case in weighted).values()), {30})
        by_route = defaultdict(Counter)
        for case in weighted:
            by_route[case['airport']][case_key(case)] += 1
        self.assertTrue(all(len(set(counts.values())) == 1 for counts in by_route.values()))
        weighted[0]['abilities'].append('fake')
        self.assertFalse(any('fake' in case['abilities'] for case in cases))

    def test_case_key_joins_order_without_merging_combinations(self):
        self.assertEqual(case_key({'airport': 'X', 'abilities': ['control', 'adaptation']}),
                         case_key({'airport': 'X', 'abilities': ['adaptation', 'control']}))
        self.assertNotEqual(case_key({'airport': 'X', 'abilities': ['control']}),
                            case_key({'airport': 'X', 'abilities': ['mastery']}))
        with self.assertRaises(ValueError):
            case_key({'airport': 'X', 'abilities': ['control', 'control']})

    def test_duplicate_missing_or_nonofficial_matrix_is_rejected(self):
        original = json.loads(MATRIX.read_text())
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'matrix.json'
            for mutate in (
                lambda rows: rows.__setitem__(1, dict(rows[0])),
                lambda rows: rows.pop(),
                lambda rows: rows[0].__setitem__('airport', 'MUC'),
                lambda rows: rows[0].__setitem__('modules', ['wind']),
            ):
                payload = json.loads(json.dumps(original))
                mutate(payload['cases'])
                path.write_text(json.dumps(payload))
                with self.assertRaises(ValueError):
                    load_cases(path)

    def test_run_case_uses_requested_cards_and_guidance(self):
        cases = load_cases(MATRIX)
        selected = next(case for case in cases if 'adaptation' in case['abilities']
                        and 'anticipation' not in case['abilities'])
        policy = TinyPolicy()
        FirstLegalAgent.calls = 0
        with patch('ai.module_training_eval.ModelAgent', FirstLegalAgent):
            result = run_case(policy, selected, 1, 14_880_000, duty=.7)
        self.assertGreater(FirstLegalAgent.calls, 0)
        self.assertEqual(result['games'], 1)
        self.assertEqual(result['abilities'], selected['abilities'])
        self.assertEqual(result['episodes'][0]['scenario'], selected['airport'])
        self.assertEqual(result['episodes'][0]['case_key'], case_key(selected))
        self.assertFalse(result['release_evidence'])
        self.assertTrue(policy.training)

    def test_evaluation_keeps_cases_separate_and_reserved_seeds_unused(self):
        cases = load_cases(MATRIX)
        route = next(case['airport'] for case in cases if len(case['abilities']) == 2)
        chosen = [case for case in cases if case['airport'] == route][:2]
        with patch('ai.module_training_eval.ModelAgent', FirstLegalAgent):
            result = evaluate_cases(TinyPolicy(), chosen, 1, 14_881_000)
        self.assertEqual(len(result['by_case']), 2)
        self.assertEqual(set(result['by_case']), {case_key(case) for case in chosen})
        self.assertEqual([row['episodes'][0]['seed'] for row in result['cases']], [14_881_000, 14_881_001])
        for invalid_seed in (13_999_999, 15_000_000, 15_200_000):
            with self.assertRaises(ValueError):
                run_case(TinyPolicy(), chosen[0], 1, invalid_seed)

    def test_small_real_guided_policy_runs_without_weight_changes(self):
        import torch
        from ai.nn_model import ActorCritic, GuidedResidualActorCritic

        torch.set_num_threads(1)
        source = ActorCritic(489, 217, hidden_size=8, hidden_layers=1)
        policy = GuidedResidualActorCritic(source, 489, 217, hidden_size=8, hidden_layers=1)
        weights = {name: value.detach().clone() for name, value in policy.state_dict().items()}
        case = next(case for case in load_cases(MATRIX) if case['modules'] == ['wind'])
        result = run_case(policy, case, 1, 14_882_000)
        self.assertEqual(result['games'], 1)
        self.assertTrue(all(torch.equal(value, weights[name]) for name, value in policy.state_dict().items()))


if __name__ == '__main__':
    unittest.main()
