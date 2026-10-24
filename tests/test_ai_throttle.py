import unittest
from unittest.mock import patch

from ai.throttle import CpuBudget


class CpuBudgetTests(unittest.TestCase):
    def test_half_duty_inserts_equal_work_and_rest(self):
        with patch('ai.throttle.time.perf_counter',side_effect=[10,12,14]),patch('ai.throttle.time.sleep') as sleep:
            budget=CpuBudget(.5);budget.pause()
            sleep.assert_called_once_with(2)

    def test_full_duty_has_no_clock_or_sleep_overhead(self):
        with patch('ai.throttle.time.perf_counter') as clock,patch('ai.throttle.time.sleep') as sleep:
            budget=CpuBudget(1);budget.pause()
            clock.assert_not_called();sleep.assert_not_called()

    def test_invalid_duty_cycle_is_rejected(self):
        for value in (0,-1,1.1,float('nan'),float('inf')):
            with self.assertRaises(ValueError):
                CpuBudget(value)
