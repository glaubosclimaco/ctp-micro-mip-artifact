"""Small independent enumeration checks before the broad collection."""
import fcntl
import itertools
import json
from pathlib import Path
import random
import sys
import numpy as np

HERE=Path(__file__).resolve().parent;CTP=HERE.parent;ROOT=CTP.parents[1]
sys.path.insert(0,str(CTP/'src'))
from instances import Instance,audit_route
from micro_mip_batch import reoptimize_window,polish_route


def check():
    rng=random.Random(20261105);checks=0
    for trial in range(3):
        xy=np.array([[rng.randrange(100),rng.randrange(100)] for _ in range(10)])
        c=np.floor(np.sqrt(((xy[:,None]-xy[None,:])**2).sum(axis=2))+.5).astype(np.int64)
        masks=[0]+[rng.randrange(1,16) for _ in range(9)];masks[1]=15
        d=Instance('synthetic',c,tuple(masks),4,frozenset([0]),1,'synthetic')
        route=list(range(8));old=audit_route(d,route,min_visits=2)
        for start in range(8):
            ids={(start+t)%8 for t in range(4)}
            A=route[(start-1)%8];B=route[(start+4)%8]
            frozen=[v for i,v in enumerate(route) if i not in ids]
            covered=0
            for v in frozen:covered|=masks[v]
            candidates=[v for v in range(10) if v not in frozen]
            oldpath=[A]+[route[(start+t)%8] for t in range(4)]+[B]
            outside=old-sum(int(c[a,b]) for a,b in zip(oldpath,oldpath[1:]))
            best=old
            for length in range(len(candidates)+1):
                for perm in itertools.permutations(candidates,length):
                    if not d.mandatory<=set(frozen)|set(perm):continue
                    cov=covered
                    for v in perm:cov|=masks[v]
                    if cov!=15:continue
                    path=[A]+list(perm)+[B]
                    best=min(best,outside+sum(int(c[a,b]) for a,b in zip(path,path[1:])))
            result=reoptimize_window(d,route,start,4,max_candidates=10,time_limit=10)
            got=result.get('new_cost',old)
            assert got==best,(trial,start,got,best)
            if result['improved']:assert audit_route(d,result['new_route'],min_visits=2)==best
            checks+=1
    d=Instance('two-visits',np.array([[0,1,2],[1,0,1],[2,1,0]]),(0,1,1),1,frozenset([0]),1,'synthetic')
    assert polish_route(d,[0,1])['final_cost']==2
    result=dict(status='PASS',enumerated_windows=checks,two_visit_route='PASS',
                scope='Synthetic correctness gate, including windows crossing the depot; no performance claim')
    (HERE/'batch_gate.json').write_text(json.dumps(result,indent=2)+'\n');print(result)


if __name__=='__main__':
    with (ROOT/'experiments/lkh/paired70_train.queue.lock').open('r') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);check()
