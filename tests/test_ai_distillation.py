import unittest

import torch

from ai.distillation import episode_split, target_loss


class DistillationTests(unittest.TestCase):
    def test_equivalent_legal_targets_use_total_probability(self):
        logits=torch.tensor([[0.,0.,1000.]],requires_grad=True)
        allowed=torch.tensor([[True,True,False]])
        targets=torch.tensor([[True,True,False]])
        loss=target_loss(logits,allowed,targets,torch.tensor([1.]))
        self.assertAlmostEqual(0.,loss.item())
        loss.backward()
        self.assertEqual(0.,logits.grad[0,2].item())

    def test_non_target_probability_and_one_shared_row_weight(self):
        logits=torch.zeros((2,3))
        allowed=torch.tensor([[True,True,False],[True,True,True]])
        targets=torch.tensor([[True,False,False],[True,True,False]])
        loss=target_loss(logits,allowed,targets,torch.tensor([1.,3.]))
        expected=(torch.log(torch.tensor(2.))+3*torch.log(torch.tensor(1.5)))/4
        self.assertAlmostEqual(expected.item(),loss.item())
        with self.assertRaises(ValueError):
            target_loss(logits,allowed,~allowed,torch.ones(2))

    def test_split_is_by_complete_namespaced_training_episode(self):
        episodes=[dict(seed=f'train:unit:split:{i}',decisions=3) for i in range(100)]
        payload=dict(episodes=episodes,decisions=300)
        train,validation=episode_split(payload)
        self.assertEqual(set(range(300)),set(train.tolist())|set(validation.tolist()))
        self.assertFalse(set(train.tolist())&set(validation.tolist()))
        for episode in range(100):
            self.assertIn(sum(i in set(validation.tolist()) for i in range(3*episode,3*episode+3)),(0,3))
        payload['episodes'][0]['seed']='15400000'
        with self.assertRaises(ValueError):episode_split(payload)
