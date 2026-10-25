"""One local heavy AI job at a time, with a persistent user stop switch.

python -m ai.job_control run -- python -m ai.train_fuel ...
python -m ai.job_control stop
The stop switch remains until an explicit `clear-stop` command.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]
LOCK=ROOT/'runs/ai-job.lock'
STOP=ROOT/'runs/STOP_AI_TRAINING'
STATUS=ROOT/'runs/ai-job.json'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=('run','stop','clear-stop','status'))
    p.add_argument('command',nargs=argparse.REMAINDER)
    args=p.parse_args()
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
        child=subprocess.Popen(command,cwd=ROOT,start_new_session=True)
        state={'wrapper_pid':os.getpid(),'child_pid':child.pid,'command':command,'started_at':time.time(),'state':'running'}
        STATUS.write_text(json.dumps(state,indent=2)+'\n')
        stopping=False
        try:
            while child.poll() is None:
                if STOP.exists():
                    stopping=True
                    os.killpg(child.pid,signal.SIGINT)
                    try:child.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        os.killpg(child.pid,signal.SIGTERM)
                    break
                time.sleep(.5)
            code=child.wait()
        except KeyboardInterrupt:
            stopping=True
            os.killpg(child.pid,signal.SIGINT)
            try:code=child.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid,signal.SIGTERM)
                code=child.wait()
        finally:
            state.update(state='stopped' if stopping else 'finished',finished_at=time.time(),returncode=child.poll())
            STATUS.write_text(json.dumps(state,indent=2)+'\n')
        raise SystemExit(0 if stopping else code)


if __name__=='__main__':main()
