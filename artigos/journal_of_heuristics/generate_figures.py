"""Generates figures/fig_gain.tex (pgfplots) from the 590 audited result bundles."""
import glob, json, collections
from pathlib import Path

HERE = Path(__file__).resolve().parent
RES = HERE.parents[1] / 'research/ctp/matheuristic/all59_10seed/results'

by = collections.defaultdict(list)
for f in glob.glob(str(RES / '*.json')):
    r = json.loads(Path(f).read_text())
    by[r['job']['case']].append(r)

rows = []
for c, runs in by.items():
    g = sum(r['gain'] for r in runs)
    if g > 0:
        cens = any(not r['alns']['complete'] for r in runs)
        rows.append((c, g, sum(r['gain'] > 0 for r in runs), cens))
rows.sort(key=lambda t: t[1])  # pgfplots draws the first y coordinate at the bottom

ycoords = ','.join(c for c, *_ in rows)
unc = ' '.join(f'({g},{c})' for c, g, n, cens in rows if not cens)
cen = ' '.join(f'({g},{c})' for c, g, n, cens in rows if cens)
labels = '\n'.join(f'\\node[font=\\scriptsize,anchor=west] at (axis cs:{g},{c}) {{~{n}/10}};'
                   for c, g, n, cens in rows)
tex = f"""\\begin{{tikzpicture}}
\\begin{{axis}}[xbar,width=0.88\\textwidth,height=7.4cm,bar width=5pt,
  symbolic y coords={{{ycoords}}},ytick=data,y tick label style={{font=\\scriptsize}},
  x tick label style={{font=\\scriptsize}},xlabel={{total cost gain over the 10 seeds}},xmin=0,xmax=1300,
  enlarge y limits=0.04,legend pos=south east,legend style={{font=\\scriptsize}},
  xmajorgrids,major grid style={{gray!25}}]
\\addplot[fill=blue!60!black,draw=none] coordinates {{{unc}}};
\\addplot[fill=orange!85!black,draw=none] coordinates {{{cen}}};
\\legend{{ALNS stage finished,ALNS stage cut off at 1800 s}}
{labels}
\\end{{axis}}
\\end{{tikzpicture}}
"""
(HERE / 'figures' / 'fig_gain.tex').write_text(tex)
print('wrote fig_gain.tex with', len(rows), 'instances')
