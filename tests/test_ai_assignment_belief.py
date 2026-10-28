from itertools import product
import unittest

from ai.assignment_belief import alternative_task_value
from ai.joint_landing_prior import control_task_costs


class AssignmentBeliefTests(unittest.TestCase):
    def test_overlapping_alternatives_are_counted_once(self):
        valid=[True]*36
        value=alternative_task_value([(valid,((1,),)),(valid,((1,2),))],1,0,rudder=3,thrust=3)
        self.assertAlmostEqual(10000*2/6,value)

    def test_tasks_cannot_reuse_reserved_control_dice(self):
        valid=[True]*36
        self.assertEqual(0.,alternative_task_value([(valid,((1,),))],2,3))

    def test_small_hand_matches_exhaustive_distinct_dice_and_shared_coffee(self):
        valid=[r==t for r in range(1,7) for t in range(1,7)]
        groups=[(valid,((1,),)),(valid,((2,3),))]
        total=0.
        for hand in product(range(1,7),repeat=3):
            best=None
            for pairs,tasks in groups:
                for target,cost in control_task_costs(tuple(sorted(hand)),2,tasks):
                    if cost<=2 and pairs[(target[0]-1)*6+target[1]-1]:
                        best=cost if best is None else min(best,cost)
            if best is not None:
                total+=10000+1.5*(2-best)
        self.assertAlmostEqual(total/216,alternative_task_value(groups,3,2))
