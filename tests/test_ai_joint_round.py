from itertools import permutations, product
from math import inf
import random
import unittest

from ai.actions import ACTIONS, SLOTS
from ai.environment import CrewEnv
from ai.horizon import control_prior, task_prior
from ai.joint_round import assignment_prior, minimum_coffee


class JointRoundTests(unittest.TestCase):
    def test_control_only_matches_existing_exact_eight_die_prior(self):
        for args in ((0, 2, 2, 0), (-2, 8, 10, 0), (1, 6, 9, 2), (0, 2, 12, 3)):
            self.assertAlmostEqual(assignment_prior(*args), control_prior(*args))
        self.assertEqual(assignment_prior(6, 2, 12, 3), 0.)

    def test_two_controls_and_two_tasks_cannot_reuse_the_same_faces(self):
        tasks = ((6,), (6,))
        exact = assignment_prior(0, 2, 2, 0, tasks, tasks)
        # Thrust is 1, tasks consume two sixes, and the remaining rudder face
        # must match across roles: six orders for r=1, four for r=6, else 12.
        self.assertAlmostEqual(exact, (6 ** 2 + 4 ** 2 + 4 * 12 ** 2) / 6 ** 8)
        independent = control_prior(0, 2, 2, 0) * task_prior(tasks) ** 2
        self.assertLess(exact, independent)
        self.assertEqual(minimum_coffee((1, 1, 1, 6), (1, 1, 1, 6), 0, 2, 2, tasks, tasks), 10)

    def test_black_die_has_one_owner_and_cannot_rescue_both_overfull_roles(self):
        three = ((2,), (3,), (4,))
        self.assertEqual(assignment_prior(0, 2, 12, 3, three, three, shared_face=3), 0.)
        self.assertEqual(minimum_coffee((1, 2, 3, 4), (1, 2, 3, 4), 0, 2, 12,
                                       three, three, shared_face=3), inf)
        self.assertEqual(assignment_prior(0, 2, 12, 0, three), 0.)
        self.assertGreater(assignment_prior(0, 2, 12, 0, three, shared_face=3), 0.)
        # With no task/control restriction both ownership options succeed;
        # unioning them still gives 1, never 2.
        self.assertEqual(assignment_prior(0, 2, 12, 3, shared_face=3), 1.)

    def test_shared_coffee_is_spent_on_both_tasks_and_controls(self):
        p, c = ((5, 6), (2,)), ((5, 6), (1,))
        self.assertEqual(minimum_coffee((1, 2, 2, 6), (1, 1, 1, 6), 0, 2, 2, p, c), 1)
        values = [assignment_prior(0, 2, 2, coffee, p, c) for coffee in range(4)]
        self.assertEqual(values, sorted(values))
        self.assertTrue(all(0 <= value <= 1 for value in values))

    def test_shared_fuel_task_spends_one_regular_die_of_one_role(self):
        tasks = ((2,), (6,))
        self.assertEqual(assignment_prior(0, 2, 12, 3, tasks, tasks, shared_tasks=((1,),)), 0.)
        # One black die makes nine placements available, with the shared fuel
        # field and the black die each assigned exactly once.
        self.assertGreater(assignment_prior(0, 2, 12, 3, tasks, tasks,
                                           shared_tasks=((1,),), shared_face=3), 0.)

    def test_cost_matches_independent_full_assignments(self):
        rng = random.Random(251034)
        # Independently enumerate FINAL control faces and task/die permutations,
        # rather than reusing the implementation's cost projection.
        tasks = ((2,), (5, 6))
        for _ in range(3):
            hand = tuple(rng.randint(1, 6) for _ in range(4))
            options = {}
            for dice in permutations(hand):
                task_cost = abs(dice[2] - 2) + min(abs(dice[3] - n) for n in (5, 6))
                for rudder, thrust in product(range(1, 7), repeat=2):
                    cost = abs(dice[0] - rudder) + abs(dice[1] - thrust) + task_cost
                    options[rudder, thrust] = min(options.get((rudder, thrust), inf), cost)
            other = (1, 2, 3, 4)
            expected = inf
            for r, t in permutations(other, 2):
                for (p_r, p_t), cost in options.items():
                    if r - p_r == 1 and 5 <= t + p_t <= 7:
                        expected = min(expected, cost)
            # The partner's controls may also use coffee; enumerate those final
            # faces and distinct assigned dice explicitly as well.
            for a, b in permutations(range(4), 2):
                for r, t in product(range(1, 7), repeat=2):
                    for (p_r, p_t), cost in options.items():
                        if r - p_r == 1 and 5 <= t + p_t <= 7:
                            expected = min(expected, cost + abs(other[a] - r) + abs(other[b] - t))
            self.assertEqual(minimum_coffee(hand, other, 1, 5, 7, tasks), expected)

    def test_feasible_landing_assignment_executes_in_the_real_engine(self):
        env = CrewEnv('MUC', round_reward=0.)
        env.reset(seed=251034)
        g, c = env.game, env.game.cockpit
        g.am_zug = 'pilot';g.letzte_runde = True
        g.landung.entfernung = g.landung.hoehe = 0
        g.landung.flugzeuge = [0] * len(g.landung.flugzeuge)
        g.landung.flugzeuge[-1] = 1
        c.fahrwerk_ausgefahren[:] = [True, True, False]
        c.landeklappen_ausgefahren[:] = [True, True, True, False]
        c.kaffeetassen = 1
        hands = {'pilot': (1, 2, 2, 6), 'kopilot': (1, 1, 1, 6)}
        for role, hand in hands.items():
            for die, value in zip(g._wuerfel_liste(role), hand):
                die.augenzahl = value
        self.assertEqual(minimum_coffee(hands['pilot'], hands['kopilot'], 0, 2, 2,
                                       ((5, 6), (2,)), ((5, 6), (1,))), 1)
        for role, target, index, die in (('pilot', 'fahrwerk', 2, 3), ('kopilot', 'landeklappe', 3, 3),
                                       ('pilot', 'bremse', 0, 2), ('kopilot', 'funk', None, 2),
                                       ('pilot', 'ruder', None, 0), ('kopilot', 'ruder', None, 0),
                                       ('pilot', 'triebwerk', None, 1), ('kopilot', 'triebwerk', None, 1)):
            self.assertEqual(env.current_role, role)
            if role == 'pilot' and target == 'triebwerk':
                coffee = next(i for i, a in enumerate(ACTIONS) if a.kind == 'coffee' and a.die == die and a.delta == -1)
                env.step(coffee)
            slot = next(i for i, s in enumerate(SLOTS) if (s.owner, s.target, s.index) == (role, target, index))
            action = next(i for i, a in enumerate(ACTIONS) if a.kind == 'place' and (a.die, a.slot) == (die, slot))
            _, _, _, _, info = env.step(action)
        self.assertEqual(info['status'], 'gewonnen')


if __name__ == '__main__':
    unittest.main()
