"""Matched-budget (equal-time) evaluation on 11 fast cases where Micro-MIP improved ALNS.

Purpose: Definitively prove that Micro-MIP superiority is algorithmic and exact,
not simply the result of consuming a few extra seconds of CPU.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
CTP = HERE.parent
ROOT = CTP.parents[1]
OUT = HERE / 'matched_budget_11cases'
BINARY = CTP / 'mdm/article_all_cases_10seed/bin/alns_mdm_faithful'
ALL59_SNAP = HERE / 'all59_10seed/audit_snapshot.json'

sys.path[:0] = [str(CTP / 'replication_v2'), str(CTP / 'src'), str(HERE)]
from data_audit import coordinates, matrix, build, digest
from instances import audit_route
from native_bridge import encode

CASES = [
    'kroA100.V50', 'kroA150.V25', 'kroA150.V50', 'kroA150.V75',
    'kroB100.V25', 'kroB100.V50', 'kroB200.V25', 'kroB200.V50',
    'kroB200.V75', 'rd400.V60', 'ali535.V81'
]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load_case(case):
    name, n = case.split('.V')
    path = CTP / 'data/tsplib' / f'{name}.tsp'
    h, xy = coordinates(path)
    d = build(matrix(xy, h['EDGE_WEIGHT_TYPE']), int(n), case)
    return d


def run_matched_experiment():
    OUT.mkdir(parents=True, exist_ok=True)
    snap = json.loads(ALL59_SNAP.read_text())
    base_rows = {f"{r['case']}.seed{r['seed']}": r for r in snap['rows'] if r['case'] in CASES}
    print(f'Starting matched-budget evaluation on {len(base_rows)} configurations...', flush=True)

    results = []
    case_cache = {}

    for idx, (key, base) in enumerate(base_rows.items(), 1):
        res_file = OUT / f'{key}.json'
        if res_file.exists():
            row = json.loads(res_file.read_text())
            results.append(row)
            continue

        case = base['case']
        seed = base['seed']
        t_base_alns = base['alns_seconds']
        t_base_total = base['total_seconds']
        h_cost = base['final_cost']
        orig_alns_cost = base['alns_cost']

        matched_iters = int(round(30000 * (t_base_total / max(1e-6, t_base_alns))))

        if case not in case_cache:
            d = load_case(case)
            data = encode(d)
            case_cache[case] = (d, data)
        d, data = case_cache[case]

        cmd = [str(BINARY), 'M', str(seed), str(matched_iters), '1800', '2000000']
        t0 = time.monotonic()
        proc = subprocess.run(cmd, input=data, text=True, capture_output=True)
        t_matched = time.monotonic() - t0

        assert proc.returncode == 0, f'Exit {proc.returncode}: {proc.stderr}'
        lines = proc.stdout.strip().splitlines()
        final = json.loads(lines[-1])
        assert final['event'] == 'final'
        matched_cost = final['cost']

        assert audit_route(d, final['route'], min_visits=2) == matched_cost

        row = {
            'key': key,
            'case': case,
            'seed': seed,
            'alns_30k_cost': orig_alns_cost,
            'alns_30k_seconds': t_base_alns,
            'hybrid_cost': h_cost,
            'hybrid_seconds': t_base_total,
            'hybrid_gain_vs_30k': base['gain'],
            'matched_iters': matched_iters,
            'matched_alns_cost': matched_cost,
            'matched_alns_seconds': t_matched,
            'hybrid_gain_vs_matched': matched_cost - h_cost
        }
        results.append(row)
        res_file = OUT / f'{key}.json'
        res_file.write_text(json.dumps(row, indent=2) + '\n')

        print(f"[{idx:3d}/{len(base_rows)}] {key:26s} | 30k:{orig_alns_cost} -> Matched:{matched_cost} vs Hybrid:{h_cost} | Gain:{row['hybrid_gain_vs_matched']} | Time: {t_matched:.1f}s / {t_base_total:.1f}s", flush=True)

    summary_file = OUT / 'summary.json'
    summary_file.write_text(json.dumps(results, indent=2) + '\n')
    print('Matched-budget evaluation complete! Results saved in summary.json', flush=True)


if __name__ == '__main__':
    run_matched_experiment()
