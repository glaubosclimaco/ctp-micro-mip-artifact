"""Hybrid Matheuristic Engine: ALNS + Micro-MIP Polisher.

Runs the frozen ALNS kernel to discover the global route topology,
then applies the Micro-MIP window polisher to resolve localized coverage
bottlenecks and eliminate sub-optimal detours.
"""
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CTP = HERE.parent
ROOT = CTP.parents[1]
sys_paths = [str(CTP / 'replication_v2'), str(CTP / 'src')]
import sys
for p in sys_paths:
    if p not in sys.path:
        sys.path.insert(0, p)

from data_audit import coordinates, matrix, build
from instances import audit_route
from native_bridge import encode
from micro_mip import polish_route

FROZEN_ALNS = CTP / 'mdm/article_all_cases_10seed/bin/alns_mdm_faithful'


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_instance(case_name):
    name, size = case_name.split('.V')
    tsp_path = CTP / 'data/tsplib' / f'{name}.tsp'
    header, xy = coordinates(tsp_path)
    data = build(matrix(xy, header['EDGE_WEIGHT_TYPE']), int(size), case_name)
    return data, tsp_path


def run_alns_baseline(d, seed, iterations=30000, binary=FROZEN_ALNS, timeout=1800):
    """
    Executes the frozen ALNS binary in mode 'M' (ALNS original).
    """
    payload = encode(d)
    command = [
        str(binary),
        'M',
        str(seed),
        str(iterations),
        '1000000000000000',
        str(2**63 - 1)
    ]
    t0 = time.perf_counter()
    proc = subprocess.run(command, input=payload, text=True, capture_output=True, timeout=timeout)
    t1 = time.perf_counter()
    assert proc.returncode == 0, f"ALNS failed with code {proc.returncode}: {proc.stderr[-300:]}"

    events = [json.loads(line) for line in proc.stdout.splitlines()]
    final_event = events[-1]
    assert final_event['event'] == 'final' and final_event['complete']

    route = final_event['route']
    cost = final_event['cost']
    audited_cost = audit_route(d, route)
    assert audited_cost == cost, f"Cost mismatch: alns={cost} vs audited={audited_cost}"

    return {
        'route': route,
        'cost': cost,
        'wall_seconds': final_event.get('wall_seconds', t1 - t0),
        'wrapper_seconds': t1 - t0,
        'iterations': iterations,
        'selector_calls': final_event.get('selector_calls', 0),
        'labels': final_event.get('labels', 0),
        'events': events
    }


def run_hybrid_matheuristic(case_name, seed, alns_iterations=30000,
                            window_sizes=(4, 6), max_candidates=16,
                            binary=FROZEN_ALNS):
    """
    Full execution of the Matheuristic:
    Stage 1: ALNS discovery
    Stage 2: Micro-MIP window polish
    """
    d, tsp_path = load_instance(case_name)

    t_total_0 = time.perf_counter()

    # Stage 1: ALNS exploration
    alns_res = run_alns_baseline(d, seed, iterations=alns_iterations, binary=binary)

    # Stage 2: Micro-MIP Polisher
    mip_res = polish_route(d, alns_res['route'], window_sizes=window_sizes,
                           max_candidates=max_candidates)

    t_total_1 = time.perf_counter()
    total_time = t_total_1 - t_total_0

    final_route = mip_res['final_route']
    final_cost = mip_res['final_cost']
    audited = audit_route(d, final_route)
    assert audited == final_cost

    return {
        'case': case_name,
        'seed': seed,
        'alns_iterations': alns_iterations,
        'alns_cost': alns_res['cost'],
        'alns_seconds': alns_res['wall_seconds'],
        'mip_seconds': mip_res['elapsed_seconds'],
        'total_seconds': total_time,
        'final_cost': final_cost,
        'gain': alns_res['cost'] - final_cost,
        'improved': final_cost < alns_res['cost'],
        'improvements_count': mip_res['improvements_count'],
        'mip_passes': mip_res['passes'],
        'initial_route': alns_res['route'],
        'final_route': final_route,
        'improvements_log': mip_res['improvements_log'],
        'provenance': {
            'binary_sha256': sha256_file(binary),
            'tsp_sha256': sha256_file(tsp_path)
        }
    }
