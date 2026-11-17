
#!/usr/bin/env python3
"""LotoScan 0.85H: auditoría conservadora por fecha; NUNCA publica ni modifica históricos."""
import datetime as dt
import json
import re
import urllib.request
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from bs4 import BeautifulSoup

SOURCES = {
    'quinigol': {
        'rtve': 'https://www.rtve.es/loterias/quinigol/',
        'elpais': 'https://servicios.elpais.com/sorteos/quinigol/',
        'eldecimo_2026-10-28': 'https://eldecimo.com/quinigol/2026-10-28/',
    },
    'lototurf': {'rtve': 'https://www.rtve.es/loterias/lototurf/'},
    'quintuple_plus': {'rtve': 'https://www.rtve.es/loterias/quintuple-plus/'},
}
TARGET_DATES = {
    'quinigol': ['2026-10-28', '2026-09-16'],
    'lototurf': ['2026-11-15'],
    'quintuple_plus': ['2026-11-15'],
}
EXPECTED_STANDARD = {'quinigol': 5, 'lototurf': 8, 'quintuple_plus': 5}
MONTHS = {'ene':1,'feb':2,'mar':3,'abr':4,'may':5,'jun':6,'jul':7,'ago':8,'sep':9,'oct':10,'nov':11,'dic':12,
          'enero':1,'febrero':2,'marzo':3,'abril':4,'mayo':5,'junio':6,'julio':7,'agosto':8,
          'septiembre':9,'setiembre':9,'octubre':10,'noviembre':11,'diciembre':12}
DATE_PATTERNS = [
    re.compile(r'(?<!\d)(20\d{2})-(\d{1,2})-(\d{1,2})(?!\d)', re.I),
    re.compile(r'(?<!\d)(\d{1,2})[/.](\d{1,2})[/.](20\d{2})(?!\d)', re.I),
    re.compile(r'(?<!\d)(\d{1,2})\s+(?:de\s+)?('+'|'.join(MONTHS)+r')\s+(?:de\s+)?(20\d{2})(?!\d)', re.I),
]

def clean(value):
    return ' '.join(value.split())

def find_dates(text):
    found = set()
    for index, regex in enumerate(DATE_PATTERNS):
        for match in regex.finditer(text):
            a,b,c = match.groups()
            try:
                if index == 0: year,month,day = int(a),int(b),int(c)
                elif index == 1: day,month,year = int(a),int(b),int(c)
                else: day,month,year = int(a),MONTHS[b.lower()],int(c)
                found.add(dt.date(year,month,day).isoformat())
            except (ValueError,KeyError):
                pass
    return sorted(found)

def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0 (compatible; LotoScan/0.85H; read-only)', 'Accept':'text/html'})
    with urllib.request.urlopen(req,timeout=30) as response:
        raw = response.read(3_000_000)
        return response.status,response.url,BeautifulSoup(raw.decode(response.headers.get_content_charset() or 'utf-8','replace'),'html.parser')

def parse_money(value):
    value = clean(value).replace('€','').replace('\u00a0','')
    if not re.fullmatch(r'(?:\d{1,3}(?:\.\d{3})*|\d+),\d{2}',value):
        return None
    try:
        return str(Decimal(value.replace('.','').replace(',','.')).quantize(Decimal('0.01')))
    except InvalidOperation:
        return None

def parse_count(value):
    value = clean(value)
    if re.fullmatch(r'\d{1,3}(?:\.\d{3})*|\d+',value):
        return int(value.replace('.',''))
    if re.search(r'sin\s+(?:ganadores|acertantes)',value,re.I):
        return 0
    return None

def rows(table):
    return [[clean(c.get_text(' ',strip=True)) for c in tr.find_all(['th','td'],recursive=False)]
            for tr in table.find_all('tr') if tr.find_all(['th','td'],recursive=False)]

def category(label):
    label=clean(label)
    m=re.match(r'^(Especial|Reintegro|[1-9]\s*[ªº])(?=\s|$|\()',label,re.I)
    if m:
        return re.sub(r'\s+','',m.group(1)).lower()
    return None

def isolate(game,source,url):
    item={'juego':game,'fuente':source,'url':url,'solo_diagnostico':True,'registros':[]}
    try:
        status,final,soup=fetch(url)
        item.update({'http':status,'url_final':final})
        main=soup.find('main') or soup
        for tag in main(['script','style','noscript','nav','footer']): tag.decompose()
        # Associate each table with a nearby date only if a single target date is
        # visible in a bounded preceding text window. Ambiguity => no association.
        previous=[]
        for node in main.descendants:
            if getattr(node,'name',None)=='table':
                rr=rows(node)
                if not rr or not any(re.search(r'categor|acertant|ganador|premio|cuant', ' '.join(r),re.I) for r in rr[:2]):
                    continue
                context=clean(' '.join(previous[-80:]))[-1000:]
                dates=find_dates(context)
                candidate=[d for d in dates if d in TARGET_DATES[game]]
                # A date appearing elsewhere on the page is insufficient proof.
                # For a dated permalink, use its URL as a stronger anchor.
                permalink=[d for d in TARGET_DATES[game] if d in final]
                if len(permalink)==1:
                    chosen=permalink[0]; association='fecha_en_url'
                elif len(candidate)==1 and len(dates)==1:
                    chosen=candidate[0]; association='fecha_unica_en_contexto'
                else:
                    chosen=None; association='sin_asociacion_segura'
                prizes=[]
                for row in rr:
                    if not row: continue
                    code=category(row[0])
                    if not code: continue
                    count=parse_count(row[1]) if len(row)>1 else None
                    amount=parse_money(row[2]) if len(row)>2 else None
                    prizes.append({'categoria':code,'descripcion':row[0], 'acertantes':count,
                                   'importe_publicado':amount,'fila_original':row})
                if prizes:
                    item['registros'].append({'fecha':chosen,'asociacion':association,
                        'categorias':prizes,'categorias_reconocidas':len(prizes),
                        'muestra_contexto':context[-350:], 'publicable':False})
            elif getattr(node,'name',None) is None and isinstance(node,str):
                if not node.find_parent('table'):
                    value=clean(str(node))
                    if value: previous.append(value[:250])
        item['tablas_con_categorias']=len(item['registros'])
    except Exception as exc:
        item['error']=f'{type(exc).__name__}: {exc}'
    return item

def main():
    report={'version':'0.85H','generado_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
            'solo_lectura':True,'publicable':False,'fuentes':[], 'comparaciones':[],
            'nota':'No se certifican importes; la asociación por contexto requiere revisión humana.'}
    for game,sources in SOURCES.items():
        for source,url in sources.items():
            result=isolate(game,source,url)
            report['fuentes'].append(result)
            print(game,source,result.get('http','ERROR'), 'tablas',result.get('tablas_con_categorias',0),result.get('error',''))
    for game,dates in TARGET_DATES.items():
        for date in dates:
            candidates=[]
            for source in report['fuentes']:
                if source['juego']!=game:continue
                for record in source.get('registros',[]):
                    if record['fecha']==date:
                        candidates.append({'fuente':source['fuente'],'asociacion':record['asociacion'],
                            'categorias':record['categorias']})
            # Compare ONLY exact same game/date/category/count, never by table index.
            agreements=[];discrepancies=[]
            by_code=defaultdict(list)
            for cand in candidates:
                for prize in cand['categorias']:
                    if prize['importe_publicado'] is not None and prize['acertantes'] is not None:
                        by_code[prize['categoria']].append((cand['fuente'],prize['acertantes'],prize['importe_publicado']))
            for code,entries in by_code.items():
                if len({e[0] for e in entries})<2:continue
                distinct={(e[1],e[2]) for e in entries}
                record={'categoria':code,'fuentes':entries}
                (agreements if len(distinct)==1 else discrepancies).append(record)
            report['comparaciones'].append({'juego':game,'fecha':date,'fuentes_con_tablas':len(candidates),
                'coincidencias':agreements,'discrepancias':discrepancies,
                'verificado':False,'publicable':False,
                'nota':'Las coincidencias son indicios, no certificación: revisar asociación y cobertura de categorías.'})
    Path('informe_premios_085h.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['LotoScan 0.85H - aislamiento y contraste (NO PUBLICABLE)','']
    for source in report['fuentes']:
        associated=sum(bool(r['fecha']) for r in source.get('registros',[]))
        lines.append(f"{source['juego']} / {source['fuente']}: HTTP {source.get('http','ERROR')}; tablas={source.get('tablas_con_categorias',0)}; asociadas={associated}; error={source.get('error','ninguno')}")
    lines.append('')
    for item in report['comparaciones']:
        lines.append(f"{item['juego']} {item['fecha']}: fuentes={item['fuentes_con_tablas']} coincidencias={len(item['coincidencias'])} discrepancias={len(item['discrepancias'])}")
    lines.append('NINGUN IMPORTE CERTIFICADO. Revisar JSON antes de desarrollar integración.')
    Path('informe_premios_085h.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('\n'.join(lines))

if __name__=='__main__': main()
