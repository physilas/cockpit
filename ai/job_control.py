"""One local heavy AI job at a time, with a persistent user stop switch.

python -m ai.job_control run -- python -m ai.train_fuel ...
python -m ai.job_control stop
The stop switch remains until an explicit `clear-stop` command.
"""
import argparse
import fcntl
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]
LOCK=ROOT/'runs/ai-job.lock'
STOP=ROOT/'runs/STOP_AI_TRAINING'
STATUS=ROOT/'runs/ai-job.json'


def write_status(state):
    temporary=STATUS.with_suffix('.tmp')
    temporary.write_text(json.dumps(state,indent=2)+'\n')
    temporary.replace(STATUS)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--max-temperature', type=float, default=None,
                   help='Require live HID readings; pause the owned process group 3 C below this limit.')
    p.add_argument('--max-runtime', type=float, default=None,
                   help='Stop this one owned job after this many wall-clock seconds, including cooling.')
    p.add_argument('action',choices=('run','stop','clear-stop','status'))
    p.add_argument('command',nargs=argparse.REMAINDER)
    args=p.parse_args()
    if args.max_runtime is not None and (not math.isfinite(args.max_runtime) or args.max_runtime<=0):
        p.error('Runtime limit must be finite and positive.')
    LOCK.parent.mkdir(parents=True,exist_ok=True)
    if args.action=='stop':
        STOP.touch()
        print('Stop requested. The active managed job will stop; further managed runs remain blocked.')
        return
    if args.action=='clear-stop':
        STOP.unlink(missing_ok=True)
        return
    if args.action=='status':
        print(STATUS.read_text() if STATUS.exists() else 'No managed job recorded.')
        print('Stop switch:',STOP.exists())
        return
    command=args.command[1:] if args.command[:1]==['--'] else args.command
    if not command:p.error('A command is required.')
    with LOCK.open('w') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:p.error('Another managed heavy AI job is already active.')
        if STOP.exists():p.error('Training was stopped. Resume requires an explicit clear-stop.')
        sensor=gate=None
        if args.max_temperature is not None:
            from .thermal import ComputerTemperatures, ThermalGate
            gate=ThermalGate(args.max_temperature)
            sensor=ComputerTemperatures()
            try:gate.update(sensor.read())
            except Exception:
                sensor.close()
                raise
        try:child=subprocess.Popen(command,cwd=ROOT,start_new_session=True)
        except Exception:
            if sensor:sensor.close()
            raise
        monotonic_start=time.monotonic()
        state={'wrapper_pid':os.getpid(),'child_pid':child.pid,'command':command,'started_at':time.time(),'state':'running'}
        write_status(state)
        stopping=False
        paused=False
        try:
            while child.poll() is None:
                expired=args.max_runtime is not None and time.monotonic()-monotonic_start>=args.max_runtime
                if STOP.exists() or expired:
                    stopping=True
                    state['stop_reason']='time_limit' if expired else 'user_stop'
                    if paused:os.killpg(child.pid,signal.SIGCONT)
                    os.killpg(child.pid,signal.SIGINT)
                    try:child.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        os.killpg(child.pid,signal.SIGTERM)
                    break
                if sensor:
                    readings=sensor.read()
                    should_pause=gate.update(readings)
                    if should_pause != paused:
                        os.killpg(child.pid,signal.SIGSTOP if should_pause else signal.SIGCONT)
                        paused=should_pause
                    state.update(state='cooling' if paused else 'running',
                                 temperature_c=max(readings.values()),
                                 peak_temperature_c=max(state.get('peak_temperature_c',0),max(readings.values())),
                                 temperature_limit_c=args.max_temperature,
                                 sampled_at=time.time())
                    hottest=max(readings,key=readings.get)
                    if readings[hottest]>=state['peak_temperature_c']:
                        state['peak_sensor']=hottest
                    write_status(state)
                time.sleep(.5)
            code=child.wait()
        except KeyboardInterrupt:
            stopping=True
            if paused:os.killpg(child.pid,signal.SIGCONT)
            os.killpg(child.pid,signal.SIGINT)
            try:code=child.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid,signal.SIGTERM)
                code=child.wait()
        except Exception:
            # A lost sensor must never silently leave a heavy job unmonitored.
            if child.poll() is None:
                if paused:os.killpg(child.pid,signal.SIGCONT)
                os.killpg(child.pid,signal.SIGTERM)
                try:child.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid,signal.SIGKILL)
                    child.wait()
            state['state']='failed'
            raise
        finally:
            if sensor:sensor.close()
            state.update(state='failed' if state['state']=='failed' else 'stopped' if stopping else 'finished',finished_at=time.time(),returncode=child.poll())
            write_status(state)
            with STATUS.with_name(STATUS.stem+'-history.jsonl').open('a') as stream:
                stream.write(json.dumps(state)+'\n')
        raise SystemExit(0 if stopping else code)


if __name__=='__main__':main()
