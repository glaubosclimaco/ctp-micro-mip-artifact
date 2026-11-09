"""Benchmark Runner for the ALNS + Micro-MIP Matheuristic.

Runs experimental jobs under the optimization lock, records verified JSON bundles,
and prints structured progress metrics.
"""
import fcntl
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CTP = HERE.parent
ROOT = CTP.parents[1]
sys.path.insert(0, str(HERE))

from engine import run_hybrid_matheuristic

LOCK_FILE = ROOT / 'experiments/lkh/paired70_train.queue.lock'
RESULTS_DIR = HERE / 'results'


def run_benchmark(cases, seeds, iterations=30000, window_sizes=(4, 6), max_candidates=16):
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    total_jobs = len(cases) * len(seeds)
    print(f"=== Starting Matheuristic Benchmark: {total_jobs} jobs ({len(cases)} cases x {len(seeds)} seeds) ===")

    job_idx = 0
    with open(LOCK_FILE, 'r') as lock_handle:
        fcntl.flock(lock_handle, fcntl.LOCK_EX)
        try:
            for case in cases:
                for seed in seeds:
                    job_idx += 1
                    target_file = RESULTS_DIR / f"{case}.seed{seed}.json"

                    if target_file.exists():
                        print(f"[{job_idx}/{total_jobs}] {case} seed {seed}: ALREADY COMPLETED, skipping.")
                        continue

                    print(f"[{job_idx}/{total_jobs}] Running {case} seed {seed}...", flush=True)
                    t0 = time.perf_counter()
                    res = run_hybrid_matheuristic(
                        case_name=case,
                        seed=seed,
                        alns_iterations=iterations,
                        window_sizes=window_sizes,
                        max_candidates=max_candidates
                    )
                    elapsed = time.perf_counter() - t0

                    target_file.write_text(json.dumps(res, indent=2) + "\n")
                    print(f"  -> Done in {elapsed:.2f}s: ALNS={res['alns_cost']} -> Final={res['final_cost']} (Gain: {res['gain']}, {res['improvements_count']} improvements)", flush=True)
        finally:
            fcntl.flock(lock_handle, fcntl.LOCK_UN)

    print("\n=== Benchmark finished successfully. ===")


if __name__ == '__main__':
    # Default set of representative cases: open instances and Table 2 instances
    test_cases = ['kroB200.V75', 'rd400.V100']
    test_seeds = [20261120, 20261121, 20261122, 20261123, 20261124]
    run_benchmark(test_cases, test_seeds, iterations=30000)
