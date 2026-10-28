import math
import unittest
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from ai.thermal import SensorUnavailable, ThermalGate


class ThermalTests(unittest.TestCase):
    def test_hottest_sensor_and_hysteresis(self):
        gate = ThermalGate(75)
        self.assertFalse(gate.update({'cpu0': 55., 'cpu1': 71.9}))
        self.assertTrue(gate.update({'cpu0': 72., 'cpu1': 40.}))
        self.assertTrue(gate.update({'cpu0': 68.}))
        self.assertFalse(gate.update({'cpu0': 67.}))

    def test_missing_sensor_never_means_cool(self):
        for readings in ({}, {'cpu': math.nan}, {'cpu': 0.}, {'cpu': math.inf}):
            with self.assertRaises(SensorUnavailable):
                ThermalGate().update(readings)

    def test_invalid_configuration(self):
        for value in (-1, 0, math.nan, math.inf):
            with self.assertRaises(ValueError):
                ThermalGate(value)

    def test_wrapper_pauses_and_resumes_owned_child_then_honors_stop(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder/'temperature').write_text('60')
            driver = '''import sys
from pathlib import Path
import ai.job_control as j
import ai.thermal as t
root=Path(sys.argv[1])
class Sensor:
 def read(self): return {'cpu':float((root/'temperature').read_text())}
 def close(self): pass
t.ComputerTemperatures=Sensor
j.ROOT=root;j.LOCK=root/'lock';j.STOP=root/'STOP';j.STATUS=root/'state.json'
code="import time;from pathlib import Path;p=Path("+repr(str(root/'ticks'))+");n=0\\nwhile True:\\n n+=1;p.write_text(str(n));time.sleep(.02)"
sys.argv=['job_control','--max-temperature','75','run','--',sys.executable,'-c',code]
j.main()
'''
            process = subprocess.Popen([sys.executable, '-c', driver, tmp],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            def wait_state(state):
                deadline = time.monotonic()+6
                while time.monotonic() < deadline:
                    try:
                        data = json.loads((folder/'state.json').read_text())
                        if data['state'] == state:
                            return data
                    except (FileNotFoundError, json.JSONDecodeError):
                        pass
                    time.sleep(.02)
                self.fail(f'No {state} state; child exit {process.poll()}')
            try:
                wait_state('running')
                (folder/'temperature').write_text('73')
                state = wait_state('cooling')
                self.assertEqual(73., state['peak_temperature_c'])
                count = (folder/'ticks').read_text()
                time.sleep(.15)
                self.assertEqual(count, (folder/'ticks').read_text())
                (folder/'temperature').write_text('66')
                wait_state('running')
                (folder/'STOP').touch()
                process.communicate(timeout=6)
                self.assertEqual(0, process.returncode)
                self.assertEqual('stopped', json.loads((folder/'state.json').read_text())['state'])
            finally:
                if process.poll() is None:
                    (folder/'STOP').touch()
                    process.communicate(timeout=6)
