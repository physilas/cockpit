import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest


class JobControlTests(unittest.TestCase):
    def test_one_job_wall_time_limit_works_without_a_persistent_schedule(self):
        with tempfile.TemporaryDirectory() as tmp:
            driver="""import sys
from pathlib import Path
import ai.job_control as j
j.ROOT=Path(sys.argv[1]);j.LOCK=j.ROOT/'lock';j.STOP=j.ROOT/'STOP';j.STATUS=j.ROOT/'state.json'
sys.argv=['job_control','--max-runtime','.1','run','--',sys.executable,'-c','import time; time.sleep(30)']
j.main()
"""
            result=subprocess.run([sys.executable,'-c',driver,tmp],capture_output=True,text=True,timeout=6)
            self.assertEqual(0,result.returncode,result.stderr)
            state=json.loads((Path(tmp)/'state.json').read_text())
            self.assertEqual('time_limit',state['stop_reason'])
            self.assertEqual('stopped',state['state'])
            self.assertFalse((Path(tmp)/'STOP').exists())
            self.assertEqual(state,json.loads((Path(tmp)/'state-history.jsonl').read_text()))

    def test_persistent_stop_terminates_owned_job_and_blocks_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            driver="""import sys
from pathlib import Path
import ai.job_control as j
j.ROOT=Path(sys.argv[1]);j.LOCK=j.ROOT/'lock';j.STOP=j.ROOT/'STOP';j.STATUS=j.ROOT/'state.json'
sys.argv=['job_control','run','--',sys.executable,'-c','import time; time.sleep(30)']
j.main()
"""
            process=subprocess.Popen([sys.executable,'-c',driver,tmp],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            try:
                deadline=time.monotonic()+5
                while not (folder/'state.json').exists() and time.monotonic()<deadline:time.sleep(.05)
                state=json.loads((folder/'state.json').read_text())
                # The lease prevents another heavy job, even before stop.
                blocked=subprocess.run([sys.executable,'-c',driver,tmp],capture_output=True,text=True,timeout=5)
                self.assertNotEqual(blocked.returncode,0)
                self.assertIn('already active',blocked.stderr)
                (folder/'STOP').touch()
                process.communicate(timeout=5)
                self.assertEqual(process.returncode,0)
                self.assertEqual(json.loads((folder/'state.json').read_text())['state'],'stopped')
                with self.assertRaises(ProcessLookupError):os.kill(state['child_pid'],0)
                blocked=subprocess.run([sys.executable,'-c',driver,tmp],capture_output=True,text=True,timeout=5)
                self.assertNotEqual(blocked.returncode,0)
                self.assertIn('explicit clear-stop',blocked.stderr)
            finally:
                if process.poll() is None:process.terminate();process.communicate(timeout=5)
