"""Deterministic alternative-metric audit; no optimization or frozen edits.
Native metric hypothesis is specified by TSPLIB headers, not fitted to outcomes.
"""
import sys,json,math,hashlib
from pathlib import Path
import numpy as np
B=Path(__file__).resolve().parents[1];sys.path.insert(0,str(B/'src'))
from instances import coordinates,reconstruct,audit_route,Instance
DOC='https://comopt.ifi.uni-heidelberg.de/software/TSPLIB95/tsp/tsp95.pdf'
def matrix(xy,metric):
 ds=((xy[:,None]-xy[None,:])**2).sum(axis=2)
 if metric=='EUC_2D':a=np.floor(np.sqrt(ds)+.5).astype(np.int64)
 elif metric=='ATT':
  rij=np.sqrt(ds/10);a=np.floor(rij+.5).astype(np.int64);a+=a<rij
 elif metric=='GEO':
  # TSPLIB: degrees=int(x), fractional part represents minutes/100.
  deg=np.trunc(xy);ll=3.141592*(deg+5*(xy-deg)/3)/180
  q1=np.cos(ll[:,None,1]-ll[None,:,1]);q2=np.cos(ll[:,None,0]-ll[None,:,0]);q3=np.cos(ll[:,None,0]+ll[None,:,0]);z=np.clip(.5*((1+q1)*q2-(1-q1)*q3),-1,1)
  a=np.floor(6378.388*np.arccos(z)+1).astype(np.int64)
 else:raise ValueError(metric)
 np.fill_diagonal(a,0);assert np.array_equal(a,a.T);return a

def build(c,n,name):
 cover=c[1:n,n:];radius=int(max(cover.min(axis=1).max(),np.partition(cover,1,axis=0)[1].max()));masks=tuple([0]+[sum(1<<j for j,x in enumerate(row) if x<=radius) for row in c[1:n,n:]])
 return Instance(name,c[:n,:n],masks,len(c)-n,frozenset([0]),radius,'diagnostic')
def digest(a):return hashlib.sha256(np.asarray(a,dtype='<i8').tobytes()).hexdigest()
def main():
 protocol=json.loads((B/'experiments/protocol.json').read_text());ref=json.loads((B/'analysis/paper_reference_entries.json').read_text());paper={r['case']:r for r in ref['table5']};records={}
 for phase in ['experiments','continuation_external','continuation_verified','continuation_remaining','continuation_after_e100','continuation_quarantine','continuation_unaffected']:
  for f in (B/phase/'results').glob('*.json'):
   if f.name.endswith(('.started.json','.external.json','.raw.json')):continue
   r=json.loads(f.read_text());j=r['job']
   if j['kind']=='alns' and r['status']=='COMPLETED':
    key=(j['case'],j['mode']);prev=records.get(key)
    if prev is None or r['result']['cost']<prev['result']['cost']:records[key]=r
 rows=[];cache={}
 for case in protocol['cases']:
  name=case['tsplib'];n=case['visitable'];path=B/'data/tsplib'/f'{name}.tsp';h,xy=coordinates(path);native=h['EDGE_WEIGHT_TYPE']
  if name not in cache:cache[name]={m:matrix(xy,m) for m in set(['EUC_2D',native])}
  literal=build(cache[name]['EUC_2D'],n,case['id']);frozen=reconstruct(path,n);assert np.array_equal(literal.costs,frozen.costs) and literal.masks==frozen.masks and literal.radius==frozen.radius
  for metric,c in cache[name].items():
   d=build(c,n,case['id']);r=dict(case=case['id'],header_metric=native,hypothesis_metric=metric,source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),matrix_sha256=digest(c),radius=d.radius,mask_sha256=hashlib.sha256(str(d.masks).encode()).hexdigest(),changed_visit_edges=int(np.count_nonzero(d.costs!=literal.costs)),changed_cover_bits=sum((x^y).bit_count() for x,y in zip(d.masks,literal.masks)),routes=[])
   for mode in ['M','B']:
    old=records.get((case['id'],mode))
    if old is None:continue
    route=old['result']['route'];union=0
    for v in route:union|=d.masks[v]
    cost=sum(int(d.costs[u,v]) for u,v in zip(route,route[1:]+route[:1]));valid=union==d.full_mask
    if valid:assert audit_route(d,route)==cost
    r['routes'].append(dict(mode=mode,frozen_cost=old['result']['cost'],recost=cost,feasible=valid,paper_best=paper.get(case['id'],{}).get(mode)))
   rows.append(r)
 result=dict(scope='Read-only deterministic diagnostic; no solver, no new benchmark, no adopted correction. Native TSPLIB interpretation conflicts with literal Euclidean wording in 2017 paper.',documentation=DOC,rows=rows)
 out=B/'replication_v2/data_audit.json';out.write_text(json.dumps(result,indent=2)+'\n')
 for r in rows:
  if r['header_metric']!='EUC_2D':print(r['case'],r['hypothesis_metric'],'radius',r['radius'],'cover changes',r['changed_cover_bits'],r['routes'])
if __name__=='__main__':main()
