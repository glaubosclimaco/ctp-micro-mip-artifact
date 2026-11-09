"""Exact monodirectional fixed-order coverage-label kernel.

Implements the state/dominance of sections 3.1-3.2 of Vargas et al. 2017.
Topological extension order differs from Algorithms1-5. It deliberately omits
look-ahead, fractional bound, bidirectional search and ALNS: not a full replica.
No triangle-inequality pruning: rounded Euclidean costs can violate it by one.
"""
from dataclasses import dataclass
import time
from instances import audit_route

@dataclass(frozen=True)
class Label:
    cost: int
    covered: int
    route: tuple


def solve(d,order,time_limit=None,max_labels=None,min_visits=3):
    began=time.perf_counter();order=tuple(order)
    assert order[0]==0 and sorted(order)==list(range(d.n))
    assert min_visits>=3
    initial=list(order);best=audit_route(d,initial,min_visits);best_route=initial
    suffix=[0]*(d.n+1)
    for i in range(d.n-1,-1,-1):suffix[i]=suffix[i+1]|d.masks[order[i]]
    queues=[[] for _ in order];queues[0]=[Label(0,d.masks[0],(0,))]
    created=1;expanded=0;dominated=0;peak=1;completed=True;reason=None
    for i in range(d.n):
        for label in queues[i]:
            if time_limit is not None and time.perf_counter()-began>=time_limit:
                completed=False;reason='TIME_LIMIT';break
            expanded+=1
            for j in range(i+1,d.n):
                # Mandatory visits cannot be skipped. The last mandatory rank
                # can still be visited before terminating the tour.
                if any(order[k] in d.mandatory for k in range(i+1,j)):break
                v=order[j];cost=label.cost+int(d.costs[order[i],v]);covered=label.covered|d.masks[v];route=label.route+(v,)
                if cost>=best:continue
                if covered==d.full_mask and len(route)>=min_visits and d.mandatory<=set(route):
                    closed=cost+int(d.costs[v,0])
                    if closed<best:best,best_route=closed,list(route)
                if covered|suffix[j+1]!=d.full_mask:continue
                # A superset at no greater cost dominates at the same rank.
                # Before min_visits is reached cardinality must remain equal.
                bucket=min(len(route),min_visits);q=queues[j]
                if any(min(len(a.route),min_visits)==bucket and a.cost<=cost and a.covered|covered==a.covered for a in q):
                    dominated+=1;continue
                q[:]=[a for a in q if not(min(len(a.route),min_visits)==bucket and cost<=a.cost and covered|a.covered==covered)]
                q.append(Label(cost,covered,route));created+=1;peak=max(peak,len(q))
                if max_labels is not None and created>=max_labels:
                    completed=False;reason='LABEL_LIMIT';break
            if not completed:break
        if not completed:break
    assert audit_route(d,best_route,min_visits)==best
    return dict(cost=best,route=best_route,optimal_for_order=completed,termination=reason or 'EXHAUSTED',labels_created=created,labels_expanded=expanded,labels_dominated=dominated,peak_queue=peak,wall_seconds=time.perf_counter()-began,scope='Fixed permutation only; not global CTP optimality or full 2017 ALNS replica')
