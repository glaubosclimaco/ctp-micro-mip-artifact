"""Read-only audit plus PDF report with literature BKS and ALNS gaps.
Preserves frozen all59_report.py untouched to protect running worker integrity checks.
"""
import hashlib
import json
from pathlib import Path
import statistics
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.graphics.shapes import Drawing, Rect, String

HERE = Path(__file__).resolve().parent
CTP = HERE.parent
ROOT = CTP.parents[1]
OUT = HERE / 'all59_10seed'
PDF = ROOT / 'output/pdf/ctp_alns_micro_mip_all59_gaps.pdf'
PDF_STANDARD = ROOT / 'output/pdf/ctp_alns_micro_mip_all59.pdf'
PAPER_REF = CTP / 'analysis/paper_reference_entries.json'

sys.path[:0] = [str(CTP / 'replication_v2'), str(CTP / 'src')]
from data_audit import coordinates, matrix, build, digest


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def route_cost(d, route):
    assert len(route) >= 2 and route[0] == 0 and len(route) == len(set(route))
    assert all(isinstance(v, int) and 0 <= v < d.n for v in route)
    assert d.mandatory <= set(route)
    covered = 0
    for v in route:
        covered |= d.masks[v]
    assert covered == d.full_mask
    return sum(int(d.costs[route[i], route[(i + 1) % len(route)]]) for i in range(len(route)))


def load_bks_map():
    paper = json.loads(PAPER_REF.read_text())
    t2 = {r['case']: r['optimum'] for r in paper['table2']}
    t5 = {}
    for r in paper['table5']:
        vals = [r[k] for k in ['M', 'B'] if r.get(k) is not None]
        if vals:
            t5[r['case']] = min(vals)
    bks = {}
    proto = json.loads((OUT / 'protocol.json').read_text())
    for c in proto['cases']:
        if c in t2:
            bks[c] = ('T2_OPT', t2[c])
        elif c in t5:
            bks[c] = ('T5_BKS', t5[c])
        else:
            bks[c] = ('NONE', None)
    return bks


def audit():
    protocol = OUT / 'protocol.json'
    p = json.loads(protocol.read_text())
    for f, h in p['source_hashes'].items():
        assert sha(ROOT / f) == h, f
    binary = CTP / 'mdm/article_all_cases_10seed/bin/alns_mdm_faithful'
    assert sha(binary) == p['binary_sha256']
    jobs = {j['key']: j for j in p['jobs']}
    seen = set()
    rows = []
    failed = []
    cache = {}
    bundle_hashes = {}
    for file in sorted((OUT / 'results').glob('*.json')):
        r = json.loads(file.read_text())
        j = r['job']
        key = j['key']
        assert key in jobs and j == jobs[key] and key not in seen
        seen.add(key)
        bundle_hashes[file.name] = sha(file)
        valid_protocols = {sha(protocol), p.get('initial_protocol_sha256')}
        if r['status'] not in ('COMPLETED', 'CENSORED'):
            failed.append(key)
            continue
        assert r['protocol_sha256'] in valid_protocols
        for log, h in r['log_hashes'].items():
            assert sha(OUT / log) == h
        case = j['case']
        if case not in cache:
            name, n = case.split('.V')
            data = CTP / 'data/tsplib' / f'{name}.tsp'
            h_tsplib, xy = coordinates(data)
            d = build(matrix(xy, h_tsplib['EDGE_WEIGHT_TYPE']), int(n), case)
            expected = p['inputs'][case]
            assert sha(data) == expected['data_sha256'] and digest(d.costs) == expected['matrix_sha256']
            assert hashlib.sha256(str(d.masks).encode()).hexdigest() == expected['masks_sha256']
            cache[case] = d
        d = cache[case]
        a = r['alns']
        b = r['polishing']
        events = [json.loads(l) for l in (OUT / 'logs' / f'{key}.alns.stdout').read_text().splitlines()]
        assert events[-1] == a and a['mode'] == 'M' and a['seed'] == j['seed']
        if r['status'] == 'COMPLETED':
            assert a['complete'] and a['iterations'] == 30000
        else:
            assert (not a['complete']) or a['iterations'] < 30000
        assert route_cost(d, a['route']) == a['cost']
        assert route_cost(d, b['final_route']) == b['final_cost'] <= a['cost']
        assert b['initial_cost'] == a['cost'] and r['gain'] == a['cost'] - b['final_cost'] == b['total_gain']
        assert sum(x['gain'] for x in b['improvements_log']) == r['gain']
        assert r['total_seconds'] >= r['alns_wrapper_seconds'] + b['elapsed_seconds'] >= 0
        assert a['wall_seconds'] <= r['alns_wrapper_seconds'] + 0.1
        assert abs(r['finished_unix'] - r['started_unix'] - r['total_seconds']) < 2
        rows.append(dict(case=case, seed=j['seed'], alns_cost=a['cost'], final_cost=b['final_cost'],
                         gain=r['gain'], alns_seconds=r['alns_wrapper_seconds'],
                         mip_seconds=b['elapsed_seconds'], total_seconds=r['total_seconds'],
                         finished_unix=r['finished_unix']))
    final = len(rows) == p['planned'] and not failed
    return p, dict(status='FINAL_AUDITED' if final else 'PARTIAL_AUDITED_BUNDLES',
                  complete=len(rows), failed=failed, planned=p['planned'],
                  protocol_sha256=sha(protocol), bundle_hashes=bundle_hashes, rows=rows,
                  recent=sorted(rows, key=lambda r: r['finished_unix'], reverse=True)[:4])


def render(p, a, bks_map):
    styles = getSampleStyleSheet()
    stamp = datetime.now(ZoneInfo('America/Sao_Paulo')).strftime('%d/%m/%Y %H:%M %z')
    story = [
        Paragraph('CTP | ALNS original + Micro-MIP (com Gaps de BKS e ALNS)', styles['Title']),
        Paragraph(f"{a['status']} | {a['complete']}/{a['planned']} completas | {len(a['failed'])} falhas | {stamp}", styles['Normal']),
        Spacer(1, 7),
        Paragraph(
            '59 casos identificaveis, 10 sementes por caso (20261140-20261149). ALNS M: 30.000 iteracoes sem corte de tempo. '
            'Polimento: janelas 4/6, ate 16 candidatos, 3 passagens e 1 s por subproblema. '
            'Gap BKS = (Hibrido melhor - BKS) / BKS x 100% (24 otimos exatos Tabela 2; 29 melhores encontrados Tabela 5 Vargas 2017). '
            'Gap Best = (Hibrido melhor - ALNS melhor) / ALNS melhor x 100%. '
            'Gap Avg = (Hibrido media - ALNS media) / ALNS media x 100% (somente com 10/10 completas). '
            'Valores negativos indicam melhoria proporcionada pelo refinamento Micro-MIP.',
            styles['Normal']
        ),
        Spacer(1, 8)
    ]
    wins = sum(r['gain'] > 0 for r in a['rows'])
    ties = len(a['rows']) - wins
    graph = Drawing(730, 42)
    for y, label, value, col in [(24, 'Melhorou', wins, colors.HexColor('#19786A')), (6, 'Empatou', ties, colors.HexColor('#64748B'))]:
        graph.add(String(0, y, label, fontSize=8))
        graph.add(Rect(65, y - 2, 550 * value / max(1, len(a['rows'])), 10, fillColor=col, strokeColor=None))
        graph.add(String(625, y, str(value), fontSize=8))
    story.extend([graph, Spacer(1, 6)])

    headers = [
        'Caso', 'C/10', 'BKS\nlit.', 'Gap\nBKS',
        'ALNS\nmelhor', 'ALNS\nmédia', 'Híbrido\nmelhor', 'Híbrido\nmédia',
        'Gap\nBest', 'Gap\nAvg', 'Melhora\nN', 'ALNS\ns méd', 'MIP extra\ns méd', 'Total\ns méd'
    ]
    table = [headers]
    for case in sorted(p['cases']):
        rows = [r for r in a['rows'] if r['case'] == case]
        n = len(rows)
        bks_src, bks_val = bks_map.get(case, ('NONE', None))
        bks_str = str(bks_val) if bks_val is not None else '-'

        alns_min = min((r['alns_cost'] for r in rows), default=None)
        hib_min = min((r['final_cost'] for r in rows), default=None)

        alns_best_str = str(alns_min) if alns_min is not None else '-'
        hib_best_str = str(hib_min) if hib_min is not None else '-'

        if hib_min is not None and bks_val is not None:
            gap_bks_val = (hib_min - bks_val) / bks_val * 100.0
            gap_bks_str = f'{gap_bks_val:+.2f}%'
        else:
            gap_bks_str = '-'

        if hib_min is not None and alns_min is not None:
            gap_best_val = (hib_min - alns_min) / alns_min * 100.0
            gap_best_str = f'{gap_best_val:+.2f}%'
        else:
            gap_best_str = '-'

        if n == 10:
            alns_mean = statistics.mean(r['alns_cost'] for r in rows)
            hib_mean = statistics.mean(r['final_cost'] for r in rows)
            alns_mean_str = f'{alns_mean:.2f}'
            hib_mean_str = f'{hib_mean:.2f}'
            gap_avg_val = (hib_mean - alns_mean) / alns_mean * 100.0
            gap_avg_str = f'{gap_avg_val:+.2f}%'
            alns_sec_str = f"{statistics.mean(r['alns_seconds'] for r in rows):.1f}"
            mip_sec_str = f"+{statistics.mean(r['mip_seconds'] for r in rows):.2f}"
            tot_sec_str = f"{statistics.mean(r['total_seconds'] for r in rows):.1f}"
        else:
            alns_mean_str = '-'
            hib_mean_str = '-'
            gap_avg_str = '-'
            alns_sec_str = '-'
            mip_sec_str = '-'
            tot_sec_str = '-'

        wins_case = sum(r['gain'] > 0 for r in rows)
        melhora_str = f'{wins_case}'

        table.append([
            case, f'{n}/10', bks_str, gap_bks_str,
            alns_best_str, alns_mean_str, hib_best_str, hib_mean_str,
            gap_best_str, gap_avg_str, melhora_str, alns_sec_str, mip_sec_str, tot_sec_str
        ])

    col_widths = [86, 30, 42, 46, 48, 50, 48, 50, 44, 44, 40, 44, 48, 44]
    extra_styles = []
    for row_idx, case in enumerate(sorted(p['cases']), start=1):
        rows = [r for r in a['rows'] if r['case'] == case]
        n = len(rows)
        bks_src, bks_val = bks_map.get(case, ('NONE', None))
        alns_min = min((r['alns_cost'] for r in rows), default=None)
        hib_min = min((r['final_cost'] for r in rows), default=None)

        # Highlight best solutions in bold
        if hib_min is not None and alns_min is not None:
            if hib_min < alns_min:
                extra_styles.append(('FONTNAME', (6, row_idx), (6, row_idx), 'Helvetica-Bold'))
                extra_styles.append(('TEXTCOLOR', (6, row_idx), (6, row_idx), colors.HexColor('#0F5132')))
                extra_styles.append(('FONTNAME', (8, row_idx), (8, row_idx), 'Helvetica-Bold'))
                extra_styles.append(('TEXTCOLOR', (8, row_idx), (8, row_idx), colors.HexColor('#0F5132')))
            else:
                # Same best achieved
                extra_styles.append(('FONTNAME', (6, row_idx), (6, row_idx), 'Helvetica-Bold'))
                if hib_min == bks_val:
                    extra_styles.append(('FONTNAME', (4, row_idx), (4, row_idx), 'Helvetica-Bold'))
                    extra_styles.append(('FONTNAME', (2, row_idx), (2, row_idx), 'Helvetica-Bold'))

        if n == 10:
            alns_mean = statistics.mean(r['alns_cost'] for r in rows)
            hib_mean = statistics.mean(r['final_cost'] for r in rows)
            if hib_mean < alns_mean:
                extra_styles.append(('FONTNAME', (7, row_idx), (7, row_idx), 'Helvetica-Bold'))
                extra_styles.append(('TEXTCOLOR', (7, row_idx), (7, row_idx), colors.HexColor('#0F5132')))
                extra_styles.append(('FONTNAME', (9, row_idx), (9, row_idx), 'Helvetica-Bold'))
                extra_styles.append(('TEXTCOLOR', (9, row_idx), (9, row_idx), colors.HexColor('#0F5132')))
            else:
                extra_styles.append(('FONTNAME', (7, row_idx), (7, row_idx), 'Helvetica-Bold'))

        wins_case = sum(r['gain'] > 0 for r in rows)
        if wins_case > 0:
            extra_styles.append(('FONTNAME', (10, row_idx), (10, row_idx), 'Helvetica-Bold'))
            extra_styles.append(('TEXTCOLOR', (10, row_idx), (10, row_idx), colors.HexColor('#0F5132')))

    t = Table(table, colWidths=col_widths, repeatRows=1, hAlign='LEFT')
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#17324D')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 7),
        ('LEADING', (0, 0), (-1, -1), 8.5),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#EDF2F6')])
    ] + extra_styles))

    story.extend([
        t,
        Spacer(1, 8),
        Paragraph(
            'Notas: BKS provém da literatura (24 ótimos provados da Tabela 2 de Vargas et al. 2017 / Gendreau et al. 1997; '
            '29 melhores valores da busca mono/bidirecional da Tabela 5 de Vargas et al. 2017). Traço (-) indica valor não disponível. '
            'Gap Best e Gap Avg negativos indicam redução de custo proporcionada pelo refinamento Micro-MIP sobre a rota gerada pelo ALNS. '
            'MIP extra s méd: tempo computacional adicional despendido pelo polidor Micro-MIP (+Δt). '
            'Total s méd = ALNS s méd + MIP extra s méd. '
            'Médias publicadas apenas quando todas as 10 sementes estão concluídas.',
            styles['Normal']
        )
    ])

    PDF.parent.mkdir(parents=True, exist_ok=True)
    temp = PDF.with_suffix('.tmp.pdf')

    def footer(canvas, doc):
        canvas.setFont('Helvetica', 7.5)
        canvas.setFillColor(colors.HexColor('#475569'))
        canvas.drawString(25, 15, 'CTP | ALNS original + Micro-MIP com Gaps BKS e ALNS | ' + stamp)
        canvas.drawRightString(815, 15, f'Página {doc.page}')

    SimpleDocTemplate(
        str(temp), pagesize=landscape(A4),
        leftMargin=25, rightMargin=25, topMargin=20, bottomMargin=25
    ).build(story, onFirstPage=footer, onLaterPages=footer)
    temp.replace(PDF)
    print(f"Generated PDF with BKS and ALNS gaps: {PDF}")
    return PDF


if __name__ == '__main__':
    p, a = audit()
    bks = load_bks_map()
    render(p, a, bks)
