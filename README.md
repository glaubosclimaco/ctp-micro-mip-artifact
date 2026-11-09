# ALNS + Micro-MIP polisher for the Covering Tour Problem: data and code

Data and code for the paper *Exact window re-optimization of Adaptive Large Neighborhood Search tours for the Covering Tour Problem* (G. Clímaco, submitted to the Journal of Heuristics).

The paper evaluates a post-optimization step (the *Micro-MIP polisher*) on tours produced by our re-implementation of the ALNS of Vargas, Jozefowiez and Ngueveu (2017). This repository holds what is needed to check the numbers in the paper: the 590 result files, the ALNS logs, the protocol, the polisher, the auditing code and the scripts that generate the tables and figures. It does not contain the manuscript.

## Contents

| Path | What it is |
|---|---|
| `research/ctp/matheuristic/all59_10seed/results/` | 590 JSON files, one per run (59 instances x 10 seeds): ALNS tour and cost, polished tour and cost, times, SHA-256 of the ALNS logs |
| `research/ctp/matheuristic/all59_10seed/logs/` | ALNS and worker logs of the 590 runs |
| `research/ctp/matheuristic/all59_10seed/protocol.json`, `audit_snapshot.json` | frozen protocol (jobs, hashes) and the independent audit of the bundles |
| `research/ctp/matheuristic/ALL59_PROTOCOL.md` | protocol text, including Amendment 1 (time limit introduced after 450 runs) |
| `research/ctp/matheuristic/micro_mip_batch.py` | the polisher used in the 590 runs (window model, SCIP, scan) |
| `research/ctp/matheuristic/micro_mip.py` | polisher used in the follow-up experiments (`polish_route`) |
| `research/ctp/matheuristic/matched_budget_*` | matched-budget evaluation (11 instances, 110 runs): script and results |
| `research/ctp/matheuristic/two_opt_vs_micromip_46runs.json`, `journal_ablation_suite.py` | 2-Opt comparison on the 46 improved tours |
| `research/ctp/matheuristic/window_cand_ablation*` | ablation of window length and pool size (15 tours) |
| `research/ctp/native/alns2017.cpp` | our C++ re-implementation of the ALNS with the Selector (source only) |
| `research/ctp/src/`, `research/ctp/replication_v2/data_audit.py` | instance reconstruction, route auditor, Selector code, native bridge |
| `research/ctp/data/tsplib/` | TSPLIB coordinate files used to rebuild the instances, with `provenance.json` (source URLs and SHA-256) |
| `research/ctp/benchmark_explicit_2017.json` | published optima transcribed from Table 2 of Vargas et al. (2017), for 24 of the 59 instances |
| `artigos/journal_of_heuristics/generate_tables.py`, `generate_figures.py`, `tables/`, `figures/` | scripts and output for the tables and figures of the paper |

The directory layout is the one of the original project; scripts locate each other through relative paths, so keep it.

## What has been checked from this repository

Run with Python 3.12, `numpy==2.5.4` and `pyscipopt==6.3.0` (SCIP 10.0); see `requirements.txt`.

1. **Tables and figure.** `python artigos/journal_of_heuristics/generate_tables.py` and `generate_figures.py` rebuild the LaTeX tables and the gain figure from the 590 result files. The output is identical to the files in `tables/` and `figures/`.
2. **Polisher.** Starting from the stored ALNS tour of a run, `polish_route` (in `micro_mip.py`) gives the stored polished cost. We checked 12 improved runs (kroA100.V50, kroA150.V50, kroB100.V25) and all 12 reproduced it. The solver is limited to 1 s per window, so a slower machine could in principle stop a window earlier and return a different result.
3. **Audit.** `audit_route` in `research/ctp/src/instances.py` recomputes the feasibility and cost of any stored tour.

## What has not been checked

- **Re-running the ALNS.** `native/alns2017.cpp` compiles with `g++ -O2 -std=c++17`, but the binary used in the study (SHA-256 `759f18af...6648422`, listed in `ALL59_PROTOCOL.md`) was built earlier with flags we did not record, so a new build will not have the same hash. We have not verified that a new build reproduces the stored tours.
- **The collection driver.** `all59.py` and `all59_report*.py` are included as a record of how the 590 runs were launched and reported. They assume the original project tree (a global lock file and an output folder) and were not tested outside it.

## Notes on the data

- 12 of the 590 runs were *censored*: the ALNS stage stopped at the 1800 s safety limit (all 10 runs of rd400.V140 and 2 of 10 of ali535.V268). They carry `"complete": false` and `"status": "CENSORED"`. The paper reports all results with and without them.
- The 59 instances are reconstructions from the recipe in Vargas et al. (2017); the original instance files were not available.
- The solver status of each window was not recorded.

## License

Code: MIT (`LICENSE`). Data, logs and tables: CC BY 4.0 (`LICENSE-DATA.md`). The TSPLIB files are not covered by these licenses; they come from the TSPLIB distribution (see `research/ctp/data/tsplib/provenance.json`).

## How to cite

Cite the paper once it is published and this archive through its Zenodo DOI (see `CITATION.cff`).
