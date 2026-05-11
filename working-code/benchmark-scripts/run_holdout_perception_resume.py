#!/usr/bin/env python3
import json, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path
BASE=Path('/workspace/series-vault')
INBOX=BASE/'benchmark/anchors/inbox'
PERCEPTION_LOG=BASE/'benchmark/logs/perception_history.jsonl'
RUN_LOG=BASE/'benchmark/logs/baseline_holdout_preeval_run.log'
STATUS=BASE/'benchmark/logs/baseline_holdout_preeval_status.json'
try:
    SESSION_ID=json.loads(STATUS.read_text()).get('session_id')
except Exception:
    SESSION_ID=datetime.now(timezone.utc).isoformat()
files=sorted(INBOX.glob('holdout_*.png'))

def done_set():
    done=set()
    if PERCEPTION_LOG.exists():
        with PERCEPTION_LOG.open() as f:
            for line in f:
                if not line.strip(): continue
                try: o=json.loads(line)
                except Exception: continue
                if o.get('session_id')==SESSION_ID and o.get('image_origin')=='holdout_benchmark' and o.get('event_type')=='perception':
                    done.add(o.get('filename'))
    return done

def status(stage, failures=None):
    done=done_set(); pending=[p.name for p in files if p.name not in done]
    STATUS.write_text(json.dumps({'session_id':SESSION_ID,'updated_at':datetime.now(timezone.utc).isoformat(),'stage':stage,'total':len(files),'completed':len(done),'ok':len(done),'failed':len(failures or []),'pending':pending[:10],'failures':(failures or [])[-5:]}, indent=2))

failures=[]
with RUN_LOG.open('a') as log:
    log.write(f'\n=== resume {SESSION_ID} ===\n')
    for p in files:
        if p.name in done_set():
            continue
        status('perception', failures)
        log.write(f'describe {p.name}\n'); log.flush()
        cmd=[sys.executable, str(BASE/'benchmark/scripts/describe_image.py'), str(p), '--origin', 'holdout_benchmark', '--session-id', SESSION_ID]
        proc=subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=240)
        log.write(proc.stdout[-3000:]+'\nexit='+str(proc.returncode)+'\n'); log.flush()
        if proc.returncode:
            failures.append({'file':p.name,'exit_code':proc.returncode,'tail':proc.stdout[-1000:]})
            status('perception_failed', failures)
            sys.exit(proc.returncode)
        time.sleep(.2)
    status('perception_done', failures)
    log.write('=== perception done ===\n')
