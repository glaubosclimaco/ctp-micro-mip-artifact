"""Native protocol and independent Python route validation."""
from pathlib import Path
import json,subprocess
from instances import audit_route
BASE=Path(__file__).resolve().parents[1]
def encode(d,order=None):
    lines=[f'{d.n} {d.demands}']+[' '.join(map(str,row)) for row in d.costs.tolist()]
    lines+=[' '.join(str(int(bool(m&(1<<w)))) for w in range(d.demands)) for m in d.masks]
    if order is not None:lines.append(' '.join(map(str,order)))
    return '\n'.join(lines)+'\n'
def run(d,mode,seed=1,iterations=30000,safety=14400,order=None,cap=2000000):
    proc=subprocess.run([str(BASE/'native/alns2017'),mode,str(seed),str(iterations),str(safety),str(cap)],input=encode(d,order),text=True,capture_output=True,timeout=safety+30)
    assert proc.returncode==0,proc.stderr
    events=[json.loads(x) for x in proc.stdout.splitlines()];result=events[-1]
    assert audit_route(d,result['route'])==result['cost']
    if mode in ('M','B'):assert result['mode']==mode and result['seed']==seed
    return result,events
