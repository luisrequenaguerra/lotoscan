
#!/usr/bin/env python3
"""LotoScan 0.85I: diagnóstico por bloques de fecha. No publica ni modifica históricos."""
import datetime as dt
import json
import re
import urllib.request
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from bs4 import BeautifulSoup, NavigableString

SOURCES = {
    'quinigol': {'rtve':'https://www.rtve.es/loterias/quinigol/',
                 'elpais':'https://servicios.elpais.com/sorteos/quinigol/',
                 'eldecimo':'https://eldecimo.com/quinigol/2026-10-28/'},
    'lototurf': {'rtve':'https://www.rtve.es/loterias/lototurf/'},
    'quintuple_plus': {'rtve':'https://www.rtve.es/loterias/quintuple-plus/'}
}
TARGETS = {'quinigol':['2026-10-28','2026-09-16'],
           'lototurf':['2026-11-15'],'quintuple_plus':['2026-11-15']}
MONTHS = {'ene':1,'feb':2,'mar':3,'abr':4,'may':5,'jun':6,'jul':7,'ago':8,'sep':9,'oct':10,'nov':11,'dic':12,
          'enero':1,'febrero':2,'marzo':3,'abril':4,'mayo':5,'junio':6,'julio':7,'agosto':8,
          'septiembre':9,'setiembre':9,'octubre':10,'noviembre':11,'diciembre':12}
DATE_RX = re.compile(r'(?<!\d)(20\d{2})-(\d{1,2})-(\d{1,2})(?!\d)|(?<!\d)(\d{1,2})[/.](\d{1,2})[/.](20\d{2})(?!\d)|(?<!\d)(\d{1,2})\s+(?:de\s+)?('+ '|'.join(MONTHS) +r')\s+(?:de\s+)?(20\d{2})(?!\d)',re.I)
CATEGORY_RX = re.compile(r'^(Especial|Reintegro|[1-9]\s*[ªº])(?=\s|$|\()',re.I)

def dates_with_positions(text):
    result=[]
    for m in DATE_RX.finditer(text):
        g=m.groups()
        try:
            if g[0]: y,mo,d=map(int,g[:3])
            elif g[3]: d,mo,y=map(int,g[3:6])
            else: d=int(g[6]);mo=MONTHS[g[7].lower()];y=int(g[8])
            result.append((m.start(),dt.date(y,mo,d).isoformat()))
        except (ValueError,KeyError): pass
    return result

def money(raw):
    s=' '.join(raw.replace('\u00a0',' ').split()).replace('€','').strip()
    if re.fullmatch(r'(?:\d{1,3}(?:\.\d{3})*|\d+),\d{2}',s):
        return str(Decimal(s.replace('.','').replace(',','.')).quantize(Decimal('.01'))),'dos_decimales'
    if re.fullmatch(r'(?:\d{1,3}(?:\.\d{3})*|\d+),\d',s):
        return str(Decimal(s.replace('.','').replace(',','.')).quantize(Decimal('.01'))),'un_decimal_publicado'
    if re.fullmatch(r'(?:\d{1,3}(?:\.\d{3})*|\d+)',s):
        return None,'sin_decimales_publicados'
    return None,'no_interpretable'

def count(raw):
    s=raw.strip()
    if re.fullmatch(r'\d{1,3}(?:\.\d{3})*|\d+',s):return int(s.replace('.',''))
    if re.search(r'sin\s+(?:ganadores|acertantes)',s,re.I):return 0
    return None

def table_rows(table):
    return [[' '.join(c.get_text(' ',strip=True).split()) for c in tr.find_all(['th','td'],recursive=False)]
            for tr in table.find_all('tr') if tr.find_all(['th','td'],recursive=False)]

def audit(game,source,url):
    out={'juego':game,'fuente':source,'url':url,'registros':[],'solo_diagnostico':True}
    try:
        req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (LotoScanAudit/0.85I)','Accept':'text/html'})
        with urllib.request.urlopen(req,timeout=30) as response:
            out['http']=response.status;out['url_final']=response.url
            raw=response.read(3000000);charset=response.headers.get_content_charset() or 'utf-8'
        soup=BeautifulSoup(raw.decode(charset,'replace'),'html.parser')
        root=soup.find('main') or soup
        for el in root(['script','style','noscript','nav','footer']):el.decompose()
        # Build an ordered stream. A table is associated with the LAST preceding
        # visible date, not any date somewhere in a 1000-character context window.
        stream=[]
        for node in root.descendants:
            if getattr(node,'name',None)=='table':
                rr=table_rows(node)
                if rr and any(re.search(r'categor|acertant|premio|cuant', ' '.join(row),re.I) for row in rr[:2]):
                    stream.append(('table',rr))
            elif isinstance(node,NavigableString) and not node.find_parent('table'):
                s=' '.join(str(node).split())
                if s:stream.append(('text',s))
        # The surrounding page may contain navigation dates. Only use the nearest
        # date immediately before a table, and flag every match as heuristic.
        text_buffer='';last_date=None;last_pos=-1
        permalink=[d for d in TARGETS[game] if d in out['url_final']]
        for kind,value in stream:
            if kind=='text':
                text_buffer+=' '+value
                for pos,date in dates_with_positions(text_buffer[max(0,len(text_buffer)-len(value)-130):]):
                    # Full buffer position not needed: last matching date is enough.
                    last_date=date;last_pos=len(text_buffer)
            else:
                rows=value
                prizes=[]
                for row in rows:
                    if not row:continue
                    m=CATEGORY_RX.match(row[0])
                    if not m:continue
                    code=re.sub(r'\s+','',m.group(1)).lower()
                    n=count(row[1]) if len(row)>1 else None
                    amount,precision=money(row[2]) if len(row)>2 else (None,'sin_columna_importe')
                    prizes.append({'categoria':code,'descripcion':row[0],'acertantes':n,
                                   'importe_eur':amount,'precision':precision,'fila_original':row})
                if not prizes:continue
                if len(permalink)==1:date=permalink[0];association='enlace_con_fecha'
                else:date=last_date;association='fecha_precedente_heuristica' if date else 'sin_fecha'
                out['registros'].append({'fecha':date,'asociacion':association,'categorias':prizes,
                                         'contexto':text_buffer[-450:],'publicable':False})
        out['tablas_con_premios']=len(out['registros'])
        out['asociadas_objetivo']=sum(r['fecha'] in TARGETS[game] for r in out['registros'])
    except Exception as exc:out['error']=f'{type(exc).__name__}: {exc}'
    return out

def main():
    report={'version':'0.85I','generado_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
            'solo_lectura':True,'publicable':False,'fuentes':[],'comparaciones':[],
            'advertencia':'Fechas precedentes son asociaciones heurísticas, NO prueba suficiente para publicar. RTVE puede redondear importes.'}
    for game,sources in SOURCES.items():
        for source,url in sources.items():
            r=audit(game,source,url);report['fuentes'].append(r)
            print(game,source,r.get('http','ERROR'),r.get('tablas_con_premios',0),r.get('asociadas_objetivo',0),r.get('error',''))
    for game,dates in TARGETS.items():
        for date in dates:
            candidates=[]
            for src in report['fuentes']:
                if src['juego']==game:
                    for rec in src.get('registros',[]):
                        if rec['fecha']==date:candidates.append((src['fuente'],rec))
            by_category=defaultdict(list)
            for source,rec in candidates:
                for prize in rec['categorias']:
                    if prize['importe_eur'] is not None and prize['acertantes'] is not None:
                        by_category[prize['categoria']].append({'fuente':source,'acertantes':prize['acertantes'],
                            'importe':prize['importe_eur'],'precision':prize['precision'],'asociacion':rec['asociacion']})
            matches=[];differences=[]
            for code,entries in by_category.items():
                if len(set(x['fuente'] for x in entries))<2:continue
                item={'categoria':code,'observaciones':entries}
                (matches if len(set((x['acertantes'],x['importe']) for x in entries))==1 else differences).append(item)
            report['comparaciones'].append({'juego':game,'fecha':date,'tablas_asociadas':len(candidates),
                'coincidencias_orientativas':matches,'discrepancias':differences,'certificado':False})
    Path('informe_premios_085i.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['LotoScan 0.85I - diagnóstico (NO PUBLICABLE)']
    for s in report['fuentes']:
        lines.append(f"{s['juego']} / {s['fuente']}: HTTP={s.get('http','ERROR')} tablas={s.get('tablas_con_premios',0)} objetivo={s.get('asociadas_objetivo',0)} error={s.get('error','ninguno')}")
    for c in report['comparaciones']:
        lines.append(f"{c['juego']} {c['fecha']}: tablas={c['tablas_asociadas']} coincidencias={len(c['coincidencias_orientativas'])} discrepancias={len(c['discrepancias'])}")
    lines.append('Ningún importe certificado. Revisar el JSON y confirmar asociaciones de fecha.')
    Path('informe_premios_085i.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('\n'.join(lines))

if __name__=='__main__':main()
