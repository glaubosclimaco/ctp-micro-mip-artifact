"""LaTeX Table Generator in Journal of Heuristics (Springer) Style.

Extracts audited results from:
1. research/ctp/matheuristic/all59_10seed/results/*.json (590 runs)
2. research/ctp/matheuristic/matched_budget_11cases/summary.json (110 runs)
3. research/ctp/matheuristic/two_opt_vs_micromip_46runs.json (46 runs)
4. research/ctp/matheuristic/window_cand_ablation_15cases.json (15 cases)

Outputs clean, publication-ready LaTeX tables into artigos/journal_of_heuristics/tables/
following the exact typography of the Journal of Heuristics (booktabs, dcolumn/siunitx friendly).
"""
import glob
import json
import math
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MATH_DIR = ROOT / 'research/ctp/matheuristic'

TABLES_DIR = HERE / 'tables'
TABLES_DIR.mkdir(parents=True, exist_ok=True)

# Published optima (Table 2 of Vargas et al. 2017) transcribed in
# research/ctp/benchmark_explicit_2017.json. Only 24 of the 59 cases have one;
# the others are reported as "--". No best-known value is invented.
_EXPLICIT = json.loads((ROOT / 'research/ctp/benchmark_explicit_2017.json').read_text())
BKS = {f"{c['tsplib']}.V{c['visitable']}": c['reported_optimum']
       for c in _EXPLICIT['cases'] if c['reported_optimum'] is not None}

def generate_table_all59():
    """Generates Table: Benchmark Results of ALNS vs Matheuristic across all 59 instances."""
    res_files = sorted(glob.glob(str(MATH_DIR / 'all59_10seed/results/*.json')))
    by_case = {}
    for f in res_files:
        d = json.loads(Path(f).read_text())
        c = d['job']['case']
        by_case.setdefault(c, []).append(d)

    lines = []
    lines.append(r"{\scriptsize\setlength{\tabcolsep}{2.5pt}")
    lines.append(r"\begin{longtable}{llr rrr rrr r r}")
    lines.append(r"\caption{Results on the 59 benchmark instances over 10 runs per instance, before (ALNS) and after (ALNS + Micro-MIP) polishing. Gains in bold. Opt.: optimum published by Vargas et al. (2017), available for 24 cases (--: none published). $^\dagger$: at least one ALNS run hit the 1800~s safety cut-off (rd400.V140: 10 of 10; ali535.V268: 2 of 10). Gap: change of the average cost of the hybrid relative to ALNS (the best of 10 changes only on rd400.V140, 3682 to 3667).}\\")
    lines.append(r"\label{tab:all59_results}\\")
    hdr = [r"\toprule",
           r" & & & \multicolumn{3}{c}{\textbf{ALNS}} & \multicolumn{3}{c}{\textbf{ALNS + Micro-MIP}} & \textbf{Gap} & \textbf{MIP} \\",
           r"\cmidrule(lr){4-6} \cmidrule(lr){7-9}",
           r"\textbf{Instance} & $|V|$ & $|W|$ & \textbf{Best} & \textbf{Avg} & \textbf{t (s)} & \textbf{Best} & \textbf{Avg} & \textbf{Opt.} & \textbf{Avg} & \textbf{t (s)} \\",
           r"\midrule"]
    lines.extend(hdr)
    lines.append(r"\endfirsthead")
    lines.extend(hdr)
    lines.append(r"\endhead")
    lines.append(r"\bottomrule")
    lines.append(r"\endfoot")

    for c in sorted(by_case.keys(), key=lambda x: (int(x.split('.V')[1]), x)):
        runs = by_case[c]
        v_size = int(c.split('.V')[1])
        base_name = c.split('.V')[0]
        # Total nodes from base_name
        n_total = int(''.join(filter(str.isdigit, base_name)))
        w_size = n_total - v_size

        alns_costs = [r['alns']['cost'] for r in runs]
        hyb_costs = [r['polishing']['final_cost'] for r in runs]
        alns_times = [r['alns']['wall_seconds'] for r in runs]
        mip_times = [r['polishing']['elapsed_seconds'] for r in runs]

        alns_best = min(alns_costs)
        alns_avg = sum(alns_costs) / len(alns_costs)
        alns_t = sum(alns_times) / len(alns_times)

        hyb_best = min(hyb_costs)
        hyb_avg = sum(hyb_costs) / len(hyb_costs)
        mip_t = sum(mip_times) / len(mip_times)

        bks_val = BKS.get(c, "--")
        n_cens = sum(1 for r in runs if not r['alns']['complete'])
        cens_mark = r"$^\dagger$" if n_cens else ""

        gap_avg = ((hyb_avg - alns_avg) / alns_avg) * 100.0
        gap_best = ((hyb_best - alns_best) / alns_best) * 100.0

        def _fmt(g):
            if abs(g) <= 1e-9:
                return "0.00\\%"
            if abs(g) < 0.005:
                return f"{g:+.4f}\\%"
            return f"{g:+.2f}\\%"
        gap_avg_str = _fmt(gap_avg)
        gap_best_str = _fmt(gap_best)

        # Bold if improvement
        if hyb_avg < alns_avg:
            hyb_avg_str = f"\\textbf{{{hyb_avg:.1f}}}"
            gap_avg_str = f"\\textbf{{{gap_avg_str}}}"
        else:
            hyb_avg_str = f"{hyb_avg:.1f}"

        if hyb_best < alns_best:
            hyb_best_str = f"\\textbf{{{hyb_best}}}"
            gap_best_str = f"\\textbf{{{gap_best_str}}}"
        else:
            hyb_best_str = f"{hyb_best}"

        inst_label = c.replace('_', r'\_') + cens_mark
        lines.append(f"{inst_label} & {v_size} & {w_size} & {alns_best} & {alns_avg:.1f} & {alns_t:.1f} & {hyb_best_str} & {hyb_avg_str} & {bks_val} & {gap_avg_str} & {mip_t:.2f} \\\\")

    lines.append(r"\end{longtable}}")

    out_path = TABLES_DIR / "tab_all59_results.tex"
    out_path.write_text('\n'.join(lines) + '\n')
    print(f"Generated {out_path}")


def generate_table_matched_budget():
    """Generates Table: Matched-Budget / Equal-Time Evaluation."""
    data = json.loads((MATH_DIR / 'matched_budget_11cases/summary.json').read_text())
    by_case = {}
    for d in data:
        by_case.setdefault(d['case'], []).append(d)

    lines = []
    lines.append(r"\begin{table}[t]")
    lines.append(r"\centering")
    lines.append(r"\caption{Matched-budget evaluation on 11 instances selected because the polisher had improved at least one run there: ALNS run for the same wall-clock time as the hybrid versus the hybrid, 10 seeds per instance. Gain = matched-ALNS cost minus hybrid cost.}")
    lines.append(r"\label{tab:matched_budget}")
    lines.append(r"\footnotesize\setlength{\tabcolsep}{4pt}")
    lines.append(r"\begin{tabular}{l ccc cc c}")
    lines.append(r"\toprule")
    lines.append(r"\textbf{Instance} & \textbf{Runs} & \textbf{Wins} & \textbf{Ties} & \textbf{Losses} & \textbf{Mean gain} & \textbf{Max gain} \\")
    lines.append(r"\midrule")

    tot_runs = 0
    tot_wins = 0
    tot_ties = 0
    tot_losses = 0
    gains_all = []

    for c in sorted(by_case.keys()):
        runs = by_case[c]
        n = len(runs)
        wins = sum(1 for r in runs if r['hybrid_cost'] < r['matched_alns_cost'])
        ties = sum(1 for r in runs if r['hybrid_cost'] == r['matched_alns_cost'])
        losses = sum(1 for r in runs if r['hybrid_cost'] > r['matched_alns_cost'])
        gains = [r['matched_alns_cost'] - r['hybrid_cost'] for r in runs]
        mean_g = sum(gains) / len(gains)
        max_g = max(gains)

        tot_runs += n
        tot_wins += wins
        tot_ties += ties
        tot_losses += losses
        gains_all.extend(gains)

        inst_label = c.replace('_', r'\_')
        lines.append(f"{inst_label} & {n} & \\textbf{{{wins}}} & {ties} & {losses} & +{mean_g:.2f} & {max_g} \\\\")

    mean_tot_g = sum(gains_all) / len(gains_all)
    max_tot_g = max(gains_all)
    lines.append(r"\midrule")
    lines.append(f"\\textbf{{Total}} & \\textbf{{{tot_runs}}} & \\textbf{{{tot_wins}}} ({tot_wins/tot_runs*100:.1f}\\%) & \\textbf{{{tot_ties}}} & \\textbf{{{tot_losses}}} & \\textbf{{+{mean_tot_g:.2f}}} & \\textbf{{{max_tot_g}}} \\\\")
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\end{table}")

    out_path = TABLES_DIR / "tab_matched_budget.tex"
    out_path.write_text('\n'.join(lines) + '\n')
    print(f"Generated {out_path}")


def generate_table_two_opt_comparison():
    """Generates Table: Pure TSP 2-Opt vs. Matheuristic Micro-MIP."""
    data = json.loads((MATH_DIR / 'two_opt_vs_micromip_46runs.json').read_text())
    
    by_case = {}
    for d in data:
        c = d['key'].split('.seed')[0]
        by_case.setdefault(c, []).append(d)

    lines = []
    lines.append(r"\begin{table}[t]")
    lines.append(r"\centering")
    lines.append(r"\caption{2-Opt versus the Micro-MIP polisher on the 46 routes that the polisher improved (selected by that criterion; includes the 8 censored rd400.V140 runs). Columns 2-Opt, Polisher and Cascade (2-Opt then polisher) give the total cost gain; W-T-L: polisher wins, ties and losses against 2-Opt.}")
    lines.append(r"\label{tab:two_opt_comparison}")
    lines.append(r"\footnotesize\setlength{\tabcolsep}{4pt}")
    lines.append(r"\begin{tabular}{l c ccc c}")
    lines.append(r"\toprule")
    lines.append(r"\textbf{Instance} & \textbf{Routes} & \textbf{2-Opt} & \textbf{Polisher} & \textbf{Cascade} & \textbf{W-T-L} \\")
    lines.append(r"\midrule")

    tot_routes = 0
    tot_2opt = 0
    tot_mip = 0
    tot_cas = 0
    tot_w = 0
    tot_t = 0
    tot_l = 0

    for c in sorted(by_case.keys()):
        items = by_case[c]
        k = len(items)
        g_2opt = sum(x['two_opt_gain'] for x in items)
        g_mip = sum(x['hybrid_gain'] for x in items)
        g_cas = sum(x['cascade_gain'] for x in items)
        w = sum(1 for x in items if x['hybrid_cost'] < x['two_opt_cost'])
        t = sum(1 for x in items if x['hybrid_cost'] == x['two_opt_cost'])
        l = sum(1 for x in items if x['hybrid_cost'] > x['two_opt_cost'])

        tot_routes += k
        tot_2opt += g_2opt
        tot_mip += g_mip
        tot_cas += g_cas
        tot_w += w
        tot_t += t
        tot_l += l

        inst_label = c.replace('_', r'\_')
        lines.append(f"{inst_label} & {k} & {g_2opt} & \\textbf{{{g_mip}}} & {g_cas} & {w}-{t}-{l} \\\\")

    lines.append(r"\midrule")
    lines.append(f"\\textbf{{Total}} & \\textbf{{{tot_routes}}} & \\textbf{{{tot_2opt}}} & \\textbf{{{tot_mip}}} & \\textbf{{{tot_cas}}} & \\textbf{{{tot_w}-{tot_t}-{tot_l}}} \\\\")
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\end{table}")

    out_path = TABLES_DIR / "tab_two_opt_comparison.tex"
    out_path.write_text('\n'.join(lines) + '\n')
    print(f"Generated {out_path}")


def generate_table_ablation():
    """Generates Table: Window Size and Candidate Pool Size Ablation."""
    data = json.loads((MATH_DIR / 'window_cand_ablation_15cases.json').read_text())

    w_configs = [
        ('k3', r"$k=3$", "Single window"),
        ('k4', r"$k=4$", "Single window"),
        ('k5', r"$k=5$", "Single window"),
        ('k6', r"$k=6$", "Single window"),
        ('k8', r"$k=8$", "Single window"),
        ('k_multi_4_6', r"$k \in (4, 6)$", "Multi-scale (Proposed)")
    ]

    c_configs = [
        ('cand_8', r"$C = 8$", "Constrained pool"),
        ('cand_12', r"$C = 12$", "Intermediate pool"),
        ('cand_16', r"$C = 16$", "Default setting"),
        ('cand_24', r"$C = 24$", "Expanded pool")
    ]

    lines = []
    lines.append(r"\begin{table}[t]")
    lines.append(r"\centering")
    lines.append(r"\caption{Parameter ablation on one tour for each of the 15 instances where the default polisher had improved a run (post-hoc sample; see text).}")
    lines.append(r"\label{tab:ablation_sensitivity}")
    lines.append(r"\footnotesize\setlength{\tabcolsep}{4pt}")
    lines.append(r"\begin{tabular}{ll ccc}")
    lines.append(r"\toprule")
    lines.append(r"\textbf{Parameter} & \textbf{Configuration} & \textbf{Improved} & \textbf{Gain} & \textbf{Time (s)} \\")
    lines.append(r"\midrule")
    lines.append(r"\multicolumn{5}{l}{\textit{Panel A: Window Size ($k$) with default $C=16$}} \\")

    for key, label, note in w_configs:
        tot_gain = sum(x['window_sweep'][key]['gain'] for x in data)
        imp_cases = sum(1 for x in data if x['window_sweep'][key]['gain'] > 0)
        mean_time = sum(x['window_sweep'][key]['time'] for x in data) / len(data)
        bold = r"\textbf" if key == 'k_multi_4_6' else ""
        if bold:
            lines.append(f"Window size & {label} & \\textbf{{{imp_cases}/15}} & \\textbf{{{tot_gain}}} & {mean_time:.3f} \\\\")
        else:
            lines.append(f"Window size & {label} & {imp_cases}/15 & {tot_gain} & {mean_time:.3f} \\\\")

    lines.append(r"\midrule")
    lines.append(r"\multicolumn{5}{l}{\textit{Panel B: Candidate Pool Size ($C$) with $k \in (4,6)$}} \\")

    for key, label, note in c_configs:
        tot_gain = sum(x['cand_sweep'][key]['gain'] for x in data)
        imp_cases = sum(1 for x in data if x['cand_sweep'][key]['gain'] > 0)
        mean_time = sum(x['cand_sweep'][key]['time'] for x in data) / len(data)
        bold = r"\textbf" if key == 'cand_16' else ""
        if bold:
            lines.append(f"Candidate pool & {label} & \\textbf{{{imp_cases}/15}} & \\textbf{{{tot_gain}}} & {mean_time:.3f} \\\\")
        else:
            lines.append(f"Candidate pool & {label} & {imp_cases}/15 & {tot_gain} & {mean_time:.3f} \\\\")

    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\end{table}")

    out_path = TABLES_DIR / "tab_ablation_sensitivity.tex"
    out_path.write_text('\n'.join(lines) + '\n')
    print(f"Generated {out_path}")


def generate_table_scale():
    """Generates Table: performance by instance scale, separating censored runs."""
    res_files = sorted(glob.glob(str(MATH_DIR / 'all59_10seed/results/*.json')))
    runs = [json.loads(Path(f).read_text()) for f in res_files]
    cats = [('Small', r'$|V| \le 50$', lambda v: v <= 50),
            ('Medium', r'$51 \le |V| \le 100$', lambda v: 51 <= v <= 100),
            ('Large', r'$101 \le |V| \le 180$', lambda v: 101 <= v <= 180),
            ('Very large', r'$|V| > 180$', lambda v: v > 180)]
    lines = [r"\begin{table}[t]", r"\centering",
             r"\caption{Polisher performance by instance size $|V|$. ``Censored'' runs are those whose ALNS stage hit the 1800~s cut-off; the last two columns exclude them.}",
             r"\label{tab:scale_sensitivity}", r"\small",
             r"\begin{tabular}{l rr rr rr}", r"\toprule",
             r" & & & \multicolumn{2}{c}{\textbf{All runs}} & \multicolumn{2}{c}{\textbf{Uncensored runs}} \\",
             r"\cmidrule(lr){4-5} \cmidrule(lr){6-7}",
             r"\textbf{Class} & \textbf{Cases} & \textbf{Runs} & \textbf{Improved} & \textbf{Gain} & \textbf{Improved} & \textbf{Gain} \\",
             r"\midrule"]
    tot = [0, 0, 0, 0, 0, 0]
    for name, rng, f in cats:
        rs = [r for r in runs if f(int(r['job']['case'].split('.V')[1]))]
        cases = len({r['job']['case'] for r in rs})
        un = [r for r in rs if r['alns']['complete']]
        row = [cases, len(rs), sum(r['gain'] > 0 for r in rs), sum(r['gain'] for r in rs),
               sum(r['gain'] > 0 for r in un), sum(r['gain'] for r in un)]
        tot = [a + b for a, b in zip(tot, row)]
        lines.append(f"{name} ({rng}) & {row[0]} & {row[1]} & {row[2]} & {row[3]:,} & {row[4]} & {row[5]:,} \\\\")
    lines += [r"\midrule", f"\\textbf{{Total}} & {tot[0]} & {tot[1]} & {tot[2]} & {tot[3]:,} & {tot[4]} & {tot[5]:,} \\\\",
              r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    out_path = TABLES_DIR / "tab_scale.tex"
    out_path.write_text('\n'.join(lines) + '\n')
    print(f"Generated {out_path}")


if __name__ == '__main__':
    generate_table_all59()
    generate_table_matched_budget()
    generate_table_two_opt_comparison()
    generate_table_ablation()
    generate_table_scale()
    print("All LaTeX tables generated successfully!")
