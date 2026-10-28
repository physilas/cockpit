from copy import deepcopy
import unittest
from unittest.mock import patch
from ai.ability_publish import validate
from ai.module_training_eval import case_key


class AbilityPublicationTests(unittest.TestCase):
    def fixture(self):
        case=dict(airport='LOG_KUL_YELLOW',abilities=['synchronisation'],modules=['kerosene'])
        manifest=dict(checkpoint='candidate',games=5,cohort='confirmation:test',focus=False,confirmation=True,cases=[case])
        rows={}
        for mode in ('baseline','candidate'):
            episodes=[dict(seed=f'confirmation:test:{case_key(case)}:{i}',status='gewonnen' if mode=='candidate' else 'verloren',
                avoidable_immediate_losses=0,stranded_plane_events=0,synchronisation_bonuses=0,switch_refills=0,
                coffee_reversals=0) for i in range(5)]
            rows[case_key(case)+'/'+mode]=dict(case=case,mode=mode,execution_method='played',episodes=episodes,games=5,wins=5 if mode=='candidate' else 0,
                                            win_rate=1. if mode=='candidate' else 0.)
        return manifest,dict(config=manifest,complete=True,release_evidence=True,results=rows),case

    def test_only_complete_paired_improvement_can_pass(self):
        manifest,report,case=self.fixture()
        with patch('ai.ability_publish.freeze',return_value=manifest),patch('ai.ability_publish.catalogue_cases',return_value=[case]):
            self.assertEqual(5,validate(report,manifest)['candidate']['wins'])
            broken=deepcopy(report);broken['results'][case_key(case)+'/candidate']['episodes'][0]['seed']='wrong'
            with self.assertRaises(ValueError):validate(broken,manifest)
            broken=deepcopy(report);broken['complete']=False
            with self.assertRaises(ValueError):validate(broken,manifest)
            broken=deepcopy(report);broken['results'][case_key(case)+'/candidate']['episodes'][0]['avoidable_immediate_losses']=1
            with self.assertRaises(ValueError):validate(broken,manifest)
            broken=deepcopy(report);del broken['results'][case_key(case)+'/baseline']
            with self.assertRaises(ValueError):validate(broken,manifest)

    def test_unaffected_realtime_cases_use_real_clock_without_fake_identity(self):
        manifest,report,case=self.fixture()
        realtime=dict(airport='LOG_TLL_YELLOW',abilities=['adaptation'],modules=['realtime'])
        manifest['cases'].append(realtime)
        for mode in ('baseline','candidate'):
            row=deepcopy(report['results'][case_key(case)+'/'+mode]);row['case']=realtime;row['wins']=0;row['win_rate']=0.
            for i,e in enumerate(row['episodes']):
                e.update(seed=f'confirmation:test:{case_key(realtime)}:{i}',status='verloren',decisions=2 if mode=='baseline' else 3)
            report['results'][case_key(realtime)+'/'+mode]=row
        with patch('ai.ability_publish.freeze',return_value=manifest),patch('ai.ability_publish.catalogue_cases',return_value=manifest['cases']):
            self.assertEqual(5,validate(report,manifest)['candidate']['ability_wins'])
            report['results'][case_key(realtime)+'/candidate']['execution_method']='identical_policy_reuse'
            with self.assertRaises(ValueError):validate(report,manifest)
