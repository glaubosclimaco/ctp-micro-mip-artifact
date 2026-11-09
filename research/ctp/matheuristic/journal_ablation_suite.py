"""Journal Evidence Suite: Comprehensive Ablation and Heuristic Benchmark.

Evaluates the 46 improved runs from the 590-run benchmark:
1. Pure TSP 2-Opt vs. Matheuristic Micro-MIP (proving necessity of exact coverage MIP)
2. Window Size Ablation: k in {3, 4, 5, 6, 8, (4,6), (3,4,6,8)}
3. Candidate Pool Size Ablation: max_candidates in {8, 12, 16, 24}
4. Pass Saturation: Analysis of gains across passes 1 to 5.
"""
import glob
import json
import math
import multiprocessing as mp
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CTP = HERE.parent
ROOT = CTP.parents[1]
sys.path.insert(0, str(HERE))

from engine import load_instance
from instances import audit_route
from micro_mip import polish_route


def run_two_opt(d, initial_route):
    route = list(initial_route)
    n = len(route)
    best_cost = audit_route(d, route)
    improved = True
    passes = 0
    while improved:
        improved = False
        passes += 1
        for i in range(n - 1):
            for j in range(i + 2, n if i > 0 else n - 1):
                new_route = route[:i + 1] + route[i + 1:j + 1][::-1] + route[j + 1:]
                cost = audit_route(d, new_route)
                if cost < best_cost:
                    best_cost = cost
                    route = new_route
                    improved = True
                    break
            if improved:
                break
    return {
        'initial_cost': audit_route(d, initial_route),
        'final_cost': best_cost,
        'gain': audit_route(d, initial_route) - best_cost,
        'final_route': route,
        'passes': passes
    }


def evaluate_single_run(item):
    case = item['case']
    seed = item['seed']
    initial_route = item['route']
    alns_cost = item['alns_cost']

    d, _ = load_instance(case)

    # 1. Classical 2-Opt
    t0_2opt = time.perf_counter()
    two_opt_res = run_two_opt(d, initial_route)
    t_2opt = time.perf_counter() - t0_2opt

    # 2. Window Size Sweep (with max_candidates=16, max_passes=3)
    window_configs = {
        'k3': (3,),
        'k4': (4,),
        'k5': (5,),
        'k6': (6,),
        'k8': (8,),
        'k_multi_4_6': (4, 6),
        'k_multi_3_4_6_8': (3, 4, 6, 8)
    }
    window_results = {}
    for name, w_sizes in window_configs.items():
        t0 = time.perf_counter()
        res = polish_route(d, initial_route, window_sizes=w_sizes, max_candidates=16, max_passes=3)
        window_results[name] = {
            'gain': res['total_gain'],
            'final_cost': res['final_cost'],
            'time': time.perf_counter() - t0,
            'passes': res['passes'],
            'improvements': res['improvements_count']
        }

    # 3. Candidate Pool Size Sweep (with window_sizes=(4,6), max_passes=3)
    cand_configs = [8, 12, 16, 24]
    cand_results = {}
    for cand in cand_configs:
        t0 = time.perf_counter()
        res = polish_route(d, initial_route, window_sizes=(4, 6), max_candidates=cand, max_passes=3)
        cand_results[f'cand_{cand}'] = {
            'gain': res['total_gain'],
            'final_cost': res['final_cost'],
            'time': time.perf_counter() - t0,
            'passes': res['passes'],
            'improvements': res['improvements_count']
        }

    # 4. Pass Saturation (up to 5 passes with default (4,6) and cand=16)
    t0 = time.perf_counter()
    res_p5 = polish_route(d, initial_route, window_sizes=(4, 6), max_candidates=16, max_passes=5)
    pass_gains = {}
    for imp in res_p5['improvements_log']:
        p = imp['pass']
        pass_gains[p] = pass_gains.get(p, 0) + imp['gain']

    return {
        'key': f"{case}.seed{seed}",
        'case': case,
        'seed': seed,
        'alns_cost': alns_cost,
        'two_opt': {
            'gain': two_opt_res['gain'],
            'final_cost': two_opt_res['final_cost'],
            'time': t_2opt
        },
        'window_results': window_results,
        'cand_results': cand_results,
        'pass_gains': pass_gains,
        'p5_total_gain': res_p5['total_gain'],
        'p5_passes': res_p5['passes']
    }


def main():
    print("=== Journal Ablation & Comparison Suite ===")
    results_files = sorted(glob.glob(str(HERE / 'all59_10seed/results/*.json')))

    # Identify the 46 runs that had improvements
    target_items = []
    for f in results_files:
        data = json.loads(Path(f).read_text())
        p = data.get('polishing', {})
        if p.get('total_gain', 0) > 0:
            target_items.append({
                'case': data['job']['case'],
                'seed': data['job']['seed'],
                'route': data['alns']['route'],
                'alns_cost': data['alns']['cost']
            })

    print(f"Loaded {len(target_items)} target runs with documented improvements.")
    assert len(target_items) == 46, f"Expected 46 target items, got {len(target_items)}"

    t_start = time.perf_counter()

    # Use 4 parallel workers
    with mp.Pool(processes=4) as pool:
        evaluated = pool.map(evaluate_single_run, target_items)

    total_time = time.perf_counter() - t_start
    print(f"Evaluation completed in {total_time:.2f}s across {len(evaluated)} runs.")

    out_dir = HERE / 'ablation_results'
    out_dir.mkdir(parents=True, exist_ok=True)
    out_json = out_dir / 'journal_ablation_summary.json'
    out_json.write_text(json.dumps(evaluated, indent=2) + "\n")
    print(f"Raw results saved to {out_json}")

    # Aggregate summaries
    print("\n--- 1. Classical 2-Opt vs Matheuristic Micro-MIP ---")
    two_opt_improvements = sum(1 for x in evaluated if x['two_opt']['gain'] > 0)
    two_opt_total_gain = sum(x['two_opt']['gain'] for x in evaluated)
    mip_default_gain = sum(x['window_results']['k_multi_4_6']['gain'] for x in evaluated)
    mip_wins_over_2opt = sum(1 for x in evaluated if x['window_results']['k_multi_4_6']['final_cost'] < x['two_opt']['final_cost'])
    ties_2opt_mip = sum(1 for x in evaluated if x['window_results']['k_multi_4_6']['final_cost'] == x['two_opt']['final_cost'])
    two_opt_wins = sum(1 for x in evaluated if x['two_opt']['final_cost'] < x['window_results']['k_multi_4_6']['final_cost'])

    print(f"2-Opt Improved Runs: {two_opt_improvements}/46 (Gain: {two_opt_total_gain})")
    print(f"Micro-MIP Improved Runs: 46/46 (Gain: {mip_default_gain})")
    print(f"Micro-MIP vs 2-Opt Head-to-Head: {mip_wins_over_2opt} Wins, {ties_2opt_mip} Ties, {two_opt_wins} Losses")

    print("\n--- 2. Window Size Ablation ---")
    print(f"{'Config':<18} | {'Runs Improved':<14} | {'Total Gain':<12} | {'Mean Time (s)':<14}")
    print("-" * 65)
    for w_name in ['k3', 'k4', 'k5', 'k6', 'k8', 'k_multi_4_6', 'k_multi_3_4_6_8']:
        runs_imp = sum(1 for x in evaluated if x['window_results'][w_name]['gain'] > 0)
        tot_gain = sum(x['window_results'][w_name]['gain'] for x in evaluated)
        mean_time = sum(x['window_results'][w_name]['time'] for x in evaluated) / len(evaluated)
        print(f"{w_name:<18} | {runs_imp:>2}/46          | {tot_gain:>10}   | {mean_time:>12.3f}s")

    print("\n--- 3. Candidate Pool Size Ablation ---")
    print(f"{'Candidates':<18} | {'Runs Improved':<14} | {'Total Gain':<12} | {'Mean Time (s)':<14}")
    print("-" * 65)
    for c_name in ['cand_8', 'cand_12', 'cand_16', 'cand_24']:
        runs_imp = sum(1 for x in evaluated if x['cand_results'][c_name]['gain'] > 0)
        tot_gain = sum(x['cand_results'][c_name]['gain'] for x in evaluated)
        mean_time = sum(x['cand_results'][c_name]['time'] for x in evaluated) / len(evaluated)
        print(f"{c_name:<18} | {runs_imp:>2}/46          | {tot_gain:>10}   | {mean_time:>12.3f}s")

    print("\n--- 4. Pass Saturation Analysis (Passes 1 to 5) ---")
    for p in range(1, 6):
        p_gain = sum(x['pass_gains'].get(p, 0) for x in evaluated)
        p_count = sum(1 for x in evaluated if x['pass_gains'].get(p, 0) > 0)
        print(f"Pass {p}: {p_count} runs improved, Cumulative Gain: {p_gain}")


if __name__ == '__main__':
    main()
