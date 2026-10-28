from copy import deepcopy
import unittest

from ai.strategy_report import paired_analysis


class StrategyReportTests(unittest.TestCase):
    def fixture(self):
        cases=[dict(airport='A',abilities=[]),dict(airport='B',abilities=[]),dict(airport='B',abilities=['control'])]
        rows={}
        for case in cases:
            key=case['airport']+'|'+','.join(case['abilities'])
            for mode in ('old','new'):
                statuses=['gewonnen','verloren'] if mode=='old' else ['gewonnen','gewonnen']
                rows[key+'/'+mode]=dict(case_key=key,games=2,episodes=[
                    dict(seed=i,status=s,round=7) for i,s in enumerate(statuses)])
        return dict(complete=True,config=dict(cases=cases),results=rows)

    def test_route_weight_and_paired_discordance(self):
        data=paired_analysis(self.fixture(),'old','new')
        self.assertEqual(2,data['route_count'])
        self.assertEqual(3,data['case_count'])
        self.assertEqual(.5,data['paired_route_delta'])
        self.assertEqual(3,data['improved'])
        self.assertEqual(0,data['regressed'])
        self.assertFalse(data['release_evidence'])

    def test_each_case_must_have_the_identical_seed_cohort(self):
        data=self.fixture()
        data['results']['A|/new']['episodes'][0]['seed']=3
        with self.assertRaises(ValueError):
            paired_analysis(data,'old','new')

    def test_incomplete_and_duplicate_records_are_rejected(self):
        data=self.fixture()
        data['complete']=False
        with self.assertRaises(ValueError):paired_analysis(data,'old','new')
        data=self.fixture()
        data['results']['A|/new']['episodes'][0]['seed']=1
        with self.assertRaises(ValueError):paired_analysis(data,'old','new')
