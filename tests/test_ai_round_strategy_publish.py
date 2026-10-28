import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import torch
from ai.round_strategy_training import RoundActor
from ai.module_training_eval import case_key
from ai.round_strategy_evaluate import freeze
from ai.round_strategy_publish import validated


class RoundStrategyPublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):torch.set_num_threads(1)

    def fixture(self,folder):
        weights=Path(folder)/'weights.json';data=RoundActor().portable();data['training_updates']=1;weights.write_text(json.dumps(data))
        protocol=freeze(weights,Path('ai/releases/crew6-abilities-2026-10-28-v1/best.pt'),'confirmation:unit-only-no-games',1)
        favorable=set(sorted({j['seed'] for j in protocol['jobs']})[:4])
        records=[{'seed':job['seed'],'mode':job['mode'],'case':case_key(job['case']),'modules':job['case']['modules'],'abilities':job['case']['abilities'],'won':job['mode']=='learned' and job['seed'] in favorable,'truncated':False,'avoidable_immediate_losses':0,'strategy_overrides':int(job['mode']=='learned')} for job in protocol['jobs']]
        return {'complete':True,'protocol':protocol,'records':records},weights

    def test_complete_frozen_winner_can_pass_but_omissions_and_replacements_cannot(self):
        with TemporaryDirectory() as folder:
            report,weights=self.fixture(folder);self.assertTrue(validated(report)['qualification_granted'])
            missing=copy.deepcopy(report);missing['records'].pop()
            with self.assertRaises(ValueError):validated(missing)
            wrong=copy.deepcopy(report);wrong['records'][0]['modules']=['wrong-module']
            with self.assertRaises(ValueError):validated(wrong)
            partial={**report,'complete':False}
            with self.assertRaises(ValueError):validated(partial)
            weights.write_text('{}')
            with self.assertRaises(ValueError):validated(report)

    def test_frozen_protocol_or_inherited_strategy_may_not_be_relabelled(self):
        with TemporaryDirectory() as folder:
            report,_=self.fixture(folder);report['protocol']['legacy_profile15_sha256']='wrong'
            with self.assertRaises(ValueError):validated(report)
