"""Reconstruct CTP input from section 4 of Vargas et al. (2017).

This is a documented reconstruction, not an author-supplied CTP file.
"""
from dataclasses import dataclass
from pathlib import Path
import hashlib
import numpy as np

@dataclass
class Instance:
    name: str
    costs: np.ndarray
    masks: tuple
    demands: int
    mandatory: frozenset
    radius: int
    source_sha256: str
    depot_covers: bool = False

    @property
    def n(self): return len(self.costs)

    @property
    def full_mask(self): return (1 << self.demands)-1


def coordinates(path):
    lines=Path(path).read_text().splitlines();header={};points=[];active=False
    for line in lines:
        if line.strip()=='EOF':break
        if line.strip()=='NODE_COORD_SECTION':active=True;continue
        if active:
            parts=line.split()
            if parts:points.append((int(parts[0]),float(parts[1]),float(parts[2])))
        elif ':' in line:
            k,v=line.split(':',1);header[k.strip()]=v.strip()
    assert len(points)==int(header['DIMENSION'])
    assert [p[0] for p in points]==list(range(1,len(points)+1)), 'Unexpected coordinate order; review rather than silently reorder'
    return header,np.array([p[1:] for p in points],dtype=float)


def reconstruct(path,n_visitable,depot_covers=False):
    header,xy=coordinates(path);assert 3<=n_visitable<len(xy)
    # Paper uses rounded Euclidean costs even when native TSPLIB has other metrics.
    costs=np.floor(np.sqrt(((xy[:,None]-xy[None,:])**2).sum(axis=2))+.5).astype(np.int64)
    cover=costs[1:n_visitable,n_visitable:]
    # Eq.2: every nondepot visit covers at least one demand; each demand
    # has at least two nondepot visits in its coverage set.
    radius=int(max(cover.min(axis=1).max(),np.partition(cover,1,axis=0)[1].max()))
    mask=lambda row:sum(1<<j for j,x in enumerate(row) if x<=radius)
    masks=[mask(costs[v,n_visitable:]) for v in range(n_visitable)]
    if not depot_covers:masks[0]=0
    assert all(masks[v] for v in range(1,n_visitable))
    for j in range(len(xy)-n_visitable):assert sum(bool(m&(1<<j)) for m in masks[1:])>=2
    return Instance(header['NAME']+f'.V{n_visitable}',costs[:n_visitable,:n_visitable],tuple(masks),len(xy)-n_visitable,frozenset([0]),radius,hashlib.sha256(Path(path).read_bytes()).hexdigest(),depot_covers)


def audit_route(d,route,min_visits=3):
    assert len(route)>=min_visits and route[0]==0
    assert len(set(route))==len(route) and set(route)<=set(range(d.n))
    assert d.mandatory<=set(route)
    covered=0
    for v in route:covered |= d.masks[v]
    assert covered==d.full_mask, 'Uncovered demand'
    return sum(int(d.costs[a,b]) for a,b in zip(route,route[1:]+route[:1]))
