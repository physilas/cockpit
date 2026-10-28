from pathlib import Path
import tempfile
import unittest

import torch

from ai.train_robust import load_teacher


class RobustTrainingTests(unittest.TestCase):
    def payload(self):
        masks = torch.zeros((2,217), dtype=torch.bool)
        masks[:,0] = True
        return dict(training_seed_namespace='train:search-labels:tests', data=dict(
            observations=torch.zeros((2,489)), masks=masks,
            reference_masks=masks.clone(), actions=torch.zeros(2, dtype=torch.long),
            weights=torch.tensor([1., .1])))

    def save_and_load(self, payload):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'teacher.pt'
            torch.save(payload, path)
            return load_teacher(path)

    def test_namespaced_masked_training_labels_load(self):
        loaded = self.save_and_load(self.payload())
        self.assertEqual(2, len(loaded['data']['actions']))

    def test_development_or_qualification_examples_are_rejected(self):
        for namespace in ('14910000', '15400000', 'validation:10', ''):
            payload = self.payload()
            payload['training_seed_namespace'] = namespace
            with self.assertRaises(ValueError):
                self.save_and_load(payload)

    def test_mismatched_reference_illegal_label_and_invalid_weight_rejected(self):
        for defect in ('reference', 'label', 'weight'):
            payload = self.payload()
            if defect == 'reference':
                payload['data']['reference_masks'][0,1] = True
            elif defect == 'label':
                payload['data']['actions'][0] = 1
            else:
                payload['data']['weights'][0] = float('nan')
            with self.assertRaises(ValueError):
                self.save_and_load(payload)
