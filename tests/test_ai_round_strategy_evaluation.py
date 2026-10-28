import unittest
from ai.round_strategy_evaluate import paired_statistics


def rows(outcomes):
    return [{'seed':str(i),'mode':mode,'won':outcome,'truncated':False,'avoidable_immediate_losses':0,'strategy_overrides':int(mode=='learned')}
            for i,triple in enumerate(outcomes) for mode,outcome in zip(('default','learned','autonomous'),triple)]


class RoundEvaluationTests(unittest.TestCase):
    def test_few_lucky_wins_are_not_published(self):
        self.assertFalse(paired_statistics(rows([(False,True,False)]*3))['qualification_granted'])
        self.assertTrue(paired_statistics(rows([(False,True,False)]*4))['qualification_granted'])
        self.assertFalse(paired_statistics(rows([(False,True,True)]*6+[(True,False,True)]*3))['qualification_granted'])

    def test_unchanged_expert_only_behavior_is_not_claimed_as_learned_improvement(self):
        data=rows([(False,True,False)]*4)
        for row in data:row['strategy_overrides']=0
        self.assertFalse(paired_statistics(data)['qualification_granted'])

    def test_incomplete_or_duplicate_comparisons_are_rejected(self):
        data=rows([(False,True,False)])
        for invalid in ([],data[:-1],data+[data[0]]):
            with self.assertRaises(ValueError):paired_statistics(invalid)

    def test_new_strategy_must_not_lose_to_autonomous_or_hide_safety_issues(self):
        data=rows([(False,True,True)]*4+[(False,False,True)])
        self.assertFalse(paired_statistics(data)['qualification_granted'])
        data=rows([(False,True,False)]*4);data[0]['truncated']=True
        self.assertFalse(paired_statistics(data)['qualification_granted'])


    def test_an_impossible_learned_goal_blocks_release_even_with_more_wins(self):
        data=rows([(False,True,False)]*4)
        data[0]['public_goal_violations']=1
        self.assertTrue(paired_statistics(data)['qualification_granted'])
        data[1]['public_goal_violations']=1
        self.assertFalse(paired_statistics(data)['qualification_granted'])

    def test_wind_and_synchronisation_losses_cannot_hide_behind_other_wins(self):
        for field,flag in [('modules','wind'),('abilities','synchronisation')]:
            data=rows([(False,True,False)]*6+[(True,False,False)])
            for row in data[-3:]:row[field]=[flag]
            stats=paired_statistics(data)
            self.assertLessEqual(stats['one_sided_p'],.1)
            self.assertFalse(stats['no_stratum_regression'])
            self.assertFalse(stats['qualification_granted'])


if __name__=='__main__':unittest.main()
