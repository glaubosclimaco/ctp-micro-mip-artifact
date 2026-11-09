"""Frozen, durable ALNS M + Micro-MIP collection; 59 cases x 10 fresh seeds."""
import argparse
import concurrent.futures
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import subprocess
import sys
import time
import traceback

HERE = Path(__file__).resolve().parent
CTP = HERE.parent
ROOT = CTP.parents[1]
OUT = HERE / 'all59_10seed'
BINARY = CTP / 'mdm/article_all_cases_10seed/bin/alns_mdm_faithful'
REFERENCE = CTP / 'mdm/article_all_cases_10seed/protocol.json'
LOCK = ROOT / 'experiments/lkh/paired70_train.queue.lock'
PDF = ROOT / 'output/pdf/ctp_alns_micro_mip_all59.pdf'
sys.path[:0] = [str(CTP/'replication_v2'), str(CTP/'src')]
from data_audit import coordinates, matrix, build, digest
from instances import audit_route
from native_bridge import encode
from micro_mip_batch import polish_route


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def write(p, obj):
    p = Path(p)
    tmp = p.with_suffix(p.suffix+'.tmp')
    tmp.write_text(json.dumps(obj, indent=2)+'\n')
    tmp.replace(p)


def load_case(case):
    name, n = case.split('.V')
    path = CTP/'data/tsplib'/f'{name}.tsp'
    h, xy = coordinates(path)
    d = build(matrix(xy, h['EDGE_WEIGHT_TYPE']), int(n), case)
    return d, dict(data_sha256=sha(path), matrix_sha256=digest(d.costs),
                  masks_sha256=hashlib.sha256(str(d.masks).encode()).hexdigest())


def prepare():
    assert not OUT.exists(), 'Existing collection: inspect; do not overwrite or restart silently'
    ref = json.loads(REFERENCE.read_text())
    cases = sorted(ref['cases'], key=lambda c: (int(c.split('.V')[1]), c))
    assert len(cases) == len(set(cases)) == 59
    assert sha(BINARY) == ref['binary_sha256']
    seeds = list(range(20261140, 20261150))
    jobs = [dict(case=c, seed=s, key=f'{c}.seed{s}') for c in cases for s in seeds]
    files = [Path(__file__), HERE/'micro_mip_batch.py', HERE/'all59_report.py',
             CTP/'replication_v2/data_audit.py', CTP/'src/instances.py', CTP/'src/native_bridge.py']
    proto = dict(scope='Exploratory paired before/after polishing on 59 previously exposed cases',
                 cases=cases, seeds=seeds, jobs=jobs, planned=len(jobs),
                 iterations=30000, alns_mode='M', alns_timeout=None,
                 safety_seconds=10**15, label_cap=2**63-1,
                 window_sizes=[4,6], max_candidates=16, max_passes=3,
                 mip_seconds_per_window=1.0, minimum_visits=2, cpus=[0,2],
                 source_hashes={str(f.relative_to(ROOT)):sha(f) for f in files},
                 binary_sha256=sha(BINARY), reference_protocol_sha256=sha(REFERENCE),
                 inputs={c:load_case(c)[1] for c in cases},
                 host=platform.uname()._asdict(), created_unix=time.time(),
                 interpretation='ALNS 30000 plus extra polishing time. Not an equal-time superiority test; no MDM.',
                 missing_case='Paper announces 60; only 59 explicit configurations identified',
                 failure_policy='Preserve logs and stop admissions on any failed job; no scientific TO for ALNS')
    for folder in ('results','logs','started'):
        (OUT/folder).mkdir(parents=True,exist_ok=True)
    write(OUT/'protocol.json',proto)
    write(OUT/'state.json',dict(status='PREPARED',planned=590,finished=0,complete=0,failed=0,active={}))
    print('PREPARED 590 jobs',flush=True)


def integrity(proto):
    assert sha(BINARY) == proto['binary_sha256']
    for p,h in proto['source_hashes'].items():
        assert sha(ROOT/p)==h, f'Changed frozen source: {p}'


def worker(key,cpu):
    proto=json.loads((OUT/'protocol.json').read_text())
    integrity(proto)
    job=next(j for j in proto['jobs'] if j['key']==key)
    target=OUT/'results'/f'{key}.json'
    assert not target.exists()
    os.sched_setaffinity(0,{cpu})
    begin=time.monotonic(); started=time.time()
    write(OUT/'started'/f'{key}.json',dict(job=job,pid=os.getpid(),cpu=cpu,started_unix=started))
    stdout=OUT/'logs'/f'{key}.alns.stdout'; stderr=OUT/'logs'/f'{key}.alns.stderr'
    result=dict(job=job,status='FAILED',started_unix=started,cpu=cpu,protocol_sha256=sha(OUT/'protocol.json'))
    try:
        prep=time.monotonic()
        d,fingerprints=load_case(job['case'])
        assert fingerprints==proto['inputs'][job['case']]
        data=encode(d)
        result['preparation_seconds']=time.monotonic()-prep
        safety=proto.get('safety_seconds',1800); cap=proto.get('label_cap',2000000)
        command=[str(BINARY),'M',str(job['seed']),'30000',str(safety),str(cap)]
        alns_start=time.monotonic()
        with stdout.open('w') as out,stderr.open('w') as err:
            p=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=out,stderr=err,text=True)
            write(OUT/'started'/f'{key}.json',dict(job=job,pid=os.getpid(),alns_pid=p.pid,cpu=cpu,started_unix=started))
            p.communicate(data)
        alns_seconds=time.monotonic()-alns_start
        assert p.returncode==0, f'ALNS exit {p.returncode}'
        events=[json.loads(line) for line in stdout.read_text().splitlines()]
        final=events[-1]
        assert final['event']=='final' and final['mode']=='M' and final['seed']==job['seed']
        assert audit_route(d,final['route'],min_visits=2)==final['cost']
        result.update(alns=final,alns_wrapper_seconds=alns_seconds)
        write(OUT/'started'/f'{key}.json',dict(job=job,pid=os.getpid(),phase='MICRO_MIP',cpu=cpu,started_unix=started,alns_cost=final['cost']))
        polished=polish_route(d,final['route'],window_sizes=(4,6),max_candidates=16,max_passes=3)
        assert audit_route(d,polished['final_route'],min_visits=2)==polished['final_cost']
        assert polished['final_cost']<=final['cost']
        is_complete=bool(final['complete'] and final['iterations']==30000)
        status='COMPLETED' if is_complete else 'CENSORED'
        result.update(status=status,polishing=polished,gain=final['cost']-polished['final_cost'])
    except Exception:
        result['error']=traceback.format_exc()
    result.update(finished_unix=time.time(),total_seconds=time.monotonic()-begin,
                  max_rss_worker_kb=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                  max_rss_alns_kb=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
                  log_hashes={str(p.relative_to(OUT)):sha(p) for p in (stdout,stderr) if p.exists()})
    write(target,result)
    print(json.dumps(dict(key=key,status=result['status'],gain=result.get('gain'))),flush=True)
    return 0 if result['status'] in ('COMPLETED','CENSORED') else 1


def report():
    p=subprocess.run([sys.executable,str(HERE/'all59_report.py')],capture_output=True,text=True)
    if p.returncode:
        print('REPORT ERROR '+p.stderr,flush=True)
    return p.returncode==0


def collect():
    proto=json.loads((OUT/'protocol.json').read_text());integrity(proto)
    state_file=OUT/'state.json'
    done={p.stem for p in (OUT/'results').glob('*.json')}
    state=dict(status='RUNNING',planned=590,finished=len(done),complete=len(done),failed=0,active={},pid=os.getpid(),started_unix=time.time())
    with LOCK.open('r') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        write(state_file,state)
        pending=iter([j for j in proto['jobs'] if j['key'] not in done]); active={};stop=False;last_report=0
        while True:
            for cpu in proto['cpus']:
                if cpu in active or stop:continue
                job=next(pending,None)
                if job is None:continue
                cmd=[sys.executable,str(Path(__file__)),'worker','--key',job['key'],'--cpu',str(cpu)]
                log=(OUT/'logs'/f"{job['key']}.worker.log").open('w')
                process=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT)
                active[cpu]=(process,job,log)
                state['active'][str(cpu)]=dict(key=job['key'],pid=process.pid)
                write(OUT/'state.json',state)
            if not active:break
            for cpu,(p,job,log) in list(active.items()):
                code=p.poll()
                if code is None:continue
                log.close();del active[cpu];del state['active'][str(cpu)]
                path=OUT/'results'/f"{job['key']}.json"
                if not path.exists():
                    write(path,dict(job=job,status='FAILED_ENVIRONMENT',error=f'Worker exit {code}; see logs',finished_unix=time.time()))
                row=json.loads(path.read_text())
                state['finished']+=1;state['complete']+=row['status'] in ('COMPLETED','CENSORED');state['failed']+=row['status'] not in ('COMPLETED','CENSORED')
                stop=bool(state['failed'])
                state['updated_unix']=time.time();write(OUT/'state.json',state)
                print(f"{state['finished']}/590 {job['key']} {row['status']}",flush=True)
            if state['finished'] and time.monotonic()-last_report>60:
                report();last_report=time.monotonic()
            time.sleep(1)
        state['status']='COLLECTED' if state['complete']==590 else 'FAILED_REVIEW_REQUIRED'
        state['finished_unix']=time.time();write(OUT/'state.json',state)
        report()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','collect','worker'])
    parser.add_argument('--key');parser.add_argument('--cpu',type=int,default=0);args=parser.parse_args()
    if args.action=='prepare':prepare()
    elif args.action=='collect':collect()
    else:sys.exit(worker(args.key,args.cpu))
