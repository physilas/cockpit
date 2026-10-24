"""Voluntary CPU duty cycle for local simulations, independent of GPU updates."""
import math
import time


class CpuBudget:
    def __init__(self, duty_cycle=1.0):
        if not math.isfinite(duty_cycle) or not 0 < duty_cycle <= 1:
            raise ValueError('CPU duty cycle must be in (0, 1].')
        self.duty_cycle=duty_cycle
        self.last=time.perf_counter() if duty_cycle < 1 else None

    def pause(self):
        if self.last is None:
            return
        work=max(0,time.perf_counter()-self.last)
        time.sleep(work*(1/self.duty_cycle-1))
        self.last=time.perf_counter()
