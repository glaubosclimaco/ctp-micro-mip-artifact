"""Window Size and Candidate Pool Size Sensitivity Analysis (Parallel).

Evaluates 15 representative runs (1 per case across all 15 cases with improvements in the 59-instance benchmark).
Explores:
1. Window size k in {3, 4, 5, 6, 8, (4,6)}
2. Candidate pool size C in {8, 12, 16, 24}
"""
import glob
import json
import multiprocessing as mp
import time
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from engine import load_instance
from micro_mip import polish_route

CASES = [
    'ali535.V188', 'ali535.V81', 'kroA100.V50', 'kroA150.V25', 'kroA150.V50',
    'kroA150.V75', 'kroB100.V25', 'kroB100.V50', 'kroB200.V100', 'kroB200.V25',
    'kroB200.V50', 'kroB200.V75', 'rd400.V100', 'rd400.V140', 'rd400.V60'
]

def eval_single(item):
    case = item['case']
    seed = item['seed']
    route = item['route']
    alns_cost = item['alns_cost']
    d, _ = load_instance(case)

    window_configs = {
        'k3': (3,),
        'k4': (4,),
        'k5': (5,),
        'k6': (6,),
        'k8': (8,),
        'k_multi_4_6': (4, 6)
    }
    cand_configs = [8, 12, 16, 24]

    w_res = {}
    for w_name, ws in window_configs.items():
        t0 = time.perf_counter()
        r = polish_route(d, route, window_sizes=ws, max_candidates=16, max_passes=2)
        t = time.perf_counter() - t0
        w_res[w_name] = {
            'gain': r['total_gain'],
            'time': t,
            'cost': r['final_cost'],
            'imps': r['improvements_count']
        }

    c_res = {}
    for c in cand_configs:
        t0 = time.perf_counter()
        r = polish_route(d, route, window_sizes=(4, 6), max_candidates=c, max_passes=2)
        t = time.perf_counter() - t0
        c_res[f'cand_{c}'] = {
            'gain': r['total_gain'],
            'time': t,
            'cost': r['final_cost'],
            'imps': r['improvements_count']
        }

    return {
        'case': case,
        'seed': seed,
        'alns_cost': alns_cost,
        'window_sweep': w_res,
        'cand_sweep': c_res
    }

def main():
    print("=== Window Size & Candidate Pool Sensitivity Suite (Parallel) ===")
    selected_items = []
    for c in CASES:
        files = sorted(glob.glob(str(HERE / f"all59_10seed/results/{c}.seed*.json")))
        for f in files:
            d = json.loads(Path(f).read_text())
            if d.get('polishing', {}).get('total_gain', 0) > 0:
                selected_items.append({
                    'case': c,
                    'seed': d['job']['seed'],
                    'route': d['alns']['route'],
                    'alns_cost': d['alns']['cost'],
                    'hybrid_cost': d['polishing']['final_cost'],
                    'hybrid_gain': d['polishing']['total_gain']
                })
                break

    print(f"Loaded {len(selected_items)} representative runs across all 15 improved cases.")

    t0 = time.perf_counter()
    with mp.Pool(processes=4) as pool:
        results = pool.map(eval_single, selected_items)
    t_tot = time.perf_counter() - t0
    print(f"Parallel evaluation completed in {t_tot:.2f}s.")

    out_file = HERE / 'window_cand_ablation_15cases.json'
    out_file.write_text(json.dumps(results, indent=2))
    print(f"Saved raw results to {out_file}")

    window_configs = ['k3', 'k4', 'k5', 'k6', 'k8', 'k_multi_4_6']
    cand_configs = [8, 12, 16, 24]

    print("\n--- Summary: Window Size Sweep across 15 Representative Cases ---")
    print(f"{'Config':<15} | {'Total Gain':<12} | {'Improved Cases':<16} | {'Mean Time (s)':<14}")
    print("-" * 65)
    for w_name in window_configs:
        tot_gain = sum(x['window_sweep'][w_name]['gain'] for x in results)
        imp_cases = sum(1 for x in results if x['window_sweep'][w_name]['gain'] > 0)
        mean_time = sum(x['window_sweep'][w_name]['time'] for x in results) / len(results)
        print(f"{w_name:<15} | {tot_gain:>10}   | {imp_cases:>2}/15           | {mean_time:>12.3f}s")

    print("\n--- Summary: Candidate Pool Size Sweep (k=(4,6)) ---")
    print(f"{'Candidates':<15} | {'Total Gain':<12} | {'Improved Cases':<16} | {'Mean Time (s)':<14}")
    print("-" * 65)
    for c in cand_configs:
        c_name = f'cand_{c}'
        tot_gain = sum(x['cand_sweep'][c_name]['gain'] for x in results)
        imp_cases = sum(1 for x in results if x['cand_sweep'][c_name]['gain'] > 0)
        mean_time = sum(x['cand_sweep'][c_name]['time'] for x in results) / len(results)
        print(f"{c_name:<15} | {tot_gain:>10}   | {imp_cases:>2}/15           | {mean_time:>12.3f}s")

if __name__ == '__main__':
    main()
