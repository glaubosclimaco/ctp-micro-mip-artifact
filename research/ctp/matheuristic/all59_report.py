"""Read-only independent bundle checks plus atomic partial/final PDF."""
import fcntl
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

HERE=Path(__file__).resolve().parent;CTP=HERE.parent;ROOT=CTP.parents[1]
OUT=HERE/'all59_10seed';PDF=ROOT/'output/pdf/ctp_alns_micro_mip_all59.pdf'
sys.path[:0]=[str(CTP/'replication_v2'),str(CTP/'src')]
from data_audit import coordinates,matrix,build,digest


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def route_cost(d,route):
    assert len(route)>=2 and route[0]==0 and len(route)==len(set(route))
    assert all(isinstance(v,int) and 0<=v<d.n for v in route)
    assert d.mandatory<=set(route)
    covered=0
    for v in route:covered|=d.masks[v]
    assert covered==d.full_mask
    return sum(int(d.costs[route[i],route[(i+1)%len(route)]]) for i in range(len(route)))


def audit():
    protocol=OUT/'protocol.json';p=json.loads(protocol.read_text())
    for f,h in p['source_hashes'].items():assert sha(ROOT/f)==h,f
    binary=CTP/'mdm/article_all_cases_10seed/bin/alns_mdm_faithful'
    assert sha(binary)==p['binary_sha256']
    jobs={j['key']:j for j in p['jobs']};seen=set();rows=[];failed=[];cache={};bundle_hashes={}
    for file in sorted((OUT/'results').glob('*.json')):
        r=json.loads(file.read_text());j=r['job'];key=j['key']
        assert key in jobs and j==jobs[key] and key not in seen
        seen.add(key);bundle_hashes[file.name]=sha(file)
        valid_protocols={sha(protocol), p.get('initial_protocol_sha256')}
        if r['status'] not in ('COMPLETED','CENSORED'):failed.append(key);continue
        assert r['protocol_sha256'] in valid_protocols
        for log,h in r['log_hashes'].items():assert sha(OUT/log)==h
        case=j['case']
        if case not in cache:
            name,n=case.split('.V');data=CTP/'data/tsplib'/f'{name}.tsp';h,xy=coordinates(data)
            d=build(matrix(xy,h['EDGE_WEIGHT_TYPE']),int(n),case);expected=p['inputs'][case]
            assert sha(data)==expected['data_sha256'] and digest(d.costs)==expected['matrix_sha256']
            assert hashlib.sha256(str(d.masks).encode()).hexdigest()==expected['masks_sha256']
            cache[case]=d
        d=cache[case];a=r['alns'];b=r['polishing']
        events=[json.loads(l) for l in (OUT/'logs'/f'{key}.alns.stdout').read_text().splitlines()]
        assert events[-1]==a and a['mode']=='M' and a['seed']==j['seed']
        if r['status']=='COMPLETED':assert a['complete'] and a['iterations']==30000
        else:assert (not a['complete']) or a['iterations']<30000
        assert route_cost(d,a['route'])==a['cost']
        assert route_cost(d,b['final_route'])==b['final_cost']<=a['cost']
        assert b['initial_cost']==a['cost'] and r['gain']==a['cost']-b['final_cost']==b['total_gain']
        assert sum(x['gain'] for x in b['improvements_log'])==r['gain']
        assert r['total_seconds']>=r['alns_wrapper_seconds']+b['elapsed_seconds']>=0
        assert a['wall_seconds']<=r['alns_wrapper_seconds']+0.1
        assert abs(r['finished_unix']-r['started_unix']-r['total_seconds'])<2
        rows.append(dict(case=case,seed=j['seed'],alns_cost=a['cost'],final_cost=b['final_cost'],
                         gain=r['gain'],alns_seconds=r['alns_wrapper_seconds'],
                         mip_seconds=b['elapsed_seconds'],total_seconds=r['total_seconds'],
                         finished_unix=r['finished_unix']))
    final=len(rows)==p['planned'] and not failed
    return p,dict(status='FINAL_AUDITED' if final else 'PARTIAL_AUDITED_BUNDLES',
                  complete=len(rows),failed=failed,planned=p['planned'],
                  protocol_sha256=sha(protocol),bundle_hashes=bundle_hashes,rows=rows,
                  recent=sorted(rows,key=lambda r:r['finished_unix'],reverse=True)[:4])


def render(p,a):
    styles=getSampleStyleSheet();stamp=datetime.now(ZoneInfo('America/Sao_Paulo')).strftime('%d/%m/%Y %H:%M %z')
    story=[Paragraph('CTP | ALNS original + Micro-MIP',styles['Title']),
           Paragraph(f"{a['status']} | {a['complete']}/{a['planned']} completas | {len(a['failed'])} falhas | {stamp}",styles['Normal']),Spacer(1,9),
           Paragraph('59 casos identificaveis, 10 sementes por caso (20261140-20261149). ALNS M: 30.000 iteracoes sem corte de tempo. '
                     'Polimento: janelas 4/6, ate 16 candidatos, 3 passagens e 1 s por subproblema. '
                     'O tempo total inclui o polimento adicional; esta tabela nao demonstra superioridade sob tempo igual. '
                     'Casos ja vistos: avaliacao exploratoria. Medias publicadas apenas com 10/10 completas.',styles['Normal']),Spacer(1,10)]
    wins=sum(r['gain']>0 for r in a['rows']);ties=len(a['rows'])-wins
    graph=Drawing(730,48)
    for y,label,value,col in [(29,'Melhorou',wins,colors.HexColor('#19786A')),(8,'Empatou',ties,colors.HexColor('#64748B'))]:
        graph.add(String(0,y,label,fontSize=9));graph.add(Rect(70,y-2,550*value/max(1,len(a['rows'])),12,fillColor=col,strokeColor=None))
        graph.add(String(630,y,str(value),fontSize=9))
    story.extend([graph,Spacer(1,8)])
    headers=['Caso','C/10','ALNS\nmelhor','ALNS\nmedia','Hibrido\nmelhor','Hibrido\nmedia','Melhora\nN','ALNS\ns medio','Total\ns medio']
    table=[headers]
    for case in sorted(p['cases']):
        rows=[r for r in a['rows'] if r['case']==case];n=len(rows)
        best=lambda k:str(min(r[k] for r in rows)) if rows else '-'
        mean=lambda k:f'{statistics.mean(r[k] for r in rows):.2f}' if n==10 else '-'
        table.append([case,f'{n}/10',best('alns_cost'),mean('alns_cost'),best('final_cost'),mean('final_cost'),
                      str(sum(r['gain']>0 for r in rows)),mean('alns_seconds'),mean('total_seconds')])
    t=Table(table,colWidths=[116,40,73,77,73,77,55,80,80],repeatRows=1,hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#17324D')),
                          ('TEXTCOLOR',(0,0),(-1,0),colors.white),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
                          ('FONTSIZE',(0,0),(-1,-1),8),('LEADING',(0,0),(-1,-1),10),
                          ('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4),
                          ('ALIGN',(1,0),(-1,-1),'RIGHT'),('VALIGN',(0,0),(-1,-1),'MIDDLE'),
                          ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#EDF2F6')])]))
    story.extend([t,Spacer(1,10),Paragraph('Melhor = minimo observado entre completas. Traco = media de dez indisponivel. '
                    'Cada bundle incluido teve hashes, logs, sementes, iteracoes, custos, cobertura, rotas e tempos conferidos. '
                    'Auditoria final do lote pendente enquanto houver casos incompletos. '
                    'O artigo anuncia 60 configuracoes, mas apenas 59 foram identificadas; nao foi inventado um caso adicional.',styles['Normal'])])
    PDF.parent.mkdir(parents=True,exist_ok=True);temp=PDF.with_suffix('.tmp.pdf')
    def footer(canvas,doc):
        canvas.setFont('Helvetica',8);canvas.setFillColor(colors.HexColor('#475569'))
        canvas.drawString(30,18,'CTP | acompanhamento exploratorio | '+stamp)
        canvas.drawRightString(810,18,f'Pagina {doc.page}')
    SimpleDocTemplate(str(temp),pagesize=landscape(A4),leftMargin=30,rightMargin=30,topMargin=25,bottomMargin=32).build(story,onFirstPage=footer,onLaterPages=footer)
    temp.replace(PDF)
    a['pdf_sha256']=sha(PDF);a['generated_at']=stamp
    path=OUT/'audit_snapshot.json';temp=path.with_suffix('.json.tmp');temp.write_text(json.dumps(a,indent=2)+'\n');temp.replace(path)
    print(f"{a['status']} {a['complete']}/590 {PDF}")


if __name__=='__main__':
    with (OUT/'report.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:sys.exit(0)
        p,a=audit();render(p,a)
