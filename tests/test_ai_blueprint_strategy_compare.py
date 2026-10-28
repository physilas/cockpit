from copy import deepcopy
import unittest

from ai.blueprint_strategy_compare import select_blueprint


class BlueprintSelectionTests(unittest.TestCase):
    def fixture(self):
        rows={}
        for mode,wins in (('crew4',1),('crew3',6)):
            rows['X|/'+mode]=dict(games=10,episodes=[dict(seed=i,status='gewonnen' if i<wins else 'verloren',
                coffee_reversals=0,stranded_plane_events=0,avoidable_immediate_losses=0) for i in range(10)])
        return dict(complete=True,config=dict(cases=[dict(airport='X',abilities=[])],games=10),results=rows)

    def test_predeclared_minimum_improvement_is_enforced(self):
        report=self.fixture();self.assertEqual('crew3',select_blueprint(report)['selected'])
        report['results']['X|/crew3']['episodes'][5]['status']='verloren'
        self.assertEqual('crew4',select_blueprint(report)['selected'])

    def test_quality_regression_vetoes_additional_wins(self):
        for metric in ('coffee_reversals','stranded_plane_events','avoidable_immediate_losses'):
            report=self.fixture();report['results']['X|/crew3']['episodes'][0][metric]=1
            self.assertEqual('crew4',select_blueprint(report)['selected'],metric)

    def test_incomplete_or_mismatched_evidence_is_rejected(self):
        report=self.fixture();report['complete']=False
        with self.assertRaises(ValueError):select_blueprint(report)
        report=self.fixture();report['results']['X|/crew3']['episodes'][0]['seed']=90
        with self.assertRaises(ValueError):select_blueprint(report)
