
#!/usr/bin/env python3
"""LotoScan 0.85D: audit all category tables against each dated draw. Read-only."""
import datetime as dt
import json
import re
import urllib.request
from decimal import Decimal, InvalidOperation
from pathlib import Path
from bs4 import BeautifulSoup

URLS = {'lototurf':'https://www.rtve.es/loterias/lototurf/', 'quinigol':'https://www.rtve.es/loterias/quinigol/', 'quintuple_plus':'https://www.rtve.es/loterias/quintuple-plus/'}
EXPECTED = {'lototurf':['1ª','2ª','3ª','4ª','5ª','6ª','7ª','Reintegro'], 'quinigol':['1ª','2ª','3ª','4ª','5ª'], 'quintuple_plus':['Especial','1ª','2ª','3ª','4ª']}
MONTHS = {'ENE':1,'FEB':2,'MAR':3,'ABR':4,'MAY':5,'JUN':6,'JUL':7,'AGO':8,'SEP':9,'OCT':10,'NOV':11,'DIC':12}
DATE_RE = re.compile(r'\b(?:Lunes|Martes|Miércoles|Miercoles|Jueves|Viernes|Sábado|Sabado|Domingo),\s*(\d{1,2})\s+(ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)\s+(20\d{2})\b', re.I)

def norm(s): return ' '.join(s.split())
def integer(s):
    if not re.fullmatch(r'\d{1,3}(?:\.\d{3})*|\d+', s.strip()): raise ValueError('acertantes no numérico')
    return int(s.replace('.',''))
def money(s):
    s=s.replace('€','').strip()
    if not re.fullmatch(r'\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2}',s): raise ValueError('importe no monetario exacto')
    return str(Decimal(s.replace('.','').replace(',','.')))
def get_page(url):
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (LotoScan/0.85D; diagnostic only)','Accept':'text/html'})
    with urllib.request.urlopen(req,timeout=30) as r:
        if r.status!=200: raise ValueError(f'HTTP {r.status}')
        raw=r.read(2500000); charset=r.headers.get_content_charset() or 'utf-8'
    soup=BeautifulSoup(raw.decode(charset,'replace'),'html.parser')
    for x in soup(['script','style','noscript','nav','footer']): x.decompose()
    return soup.find('main') or soup

def parse(game, main):
    # The page's chronological text is checked against its chronological prize tables.
    txt=norm(main.get_text(' ',strip=True))
    dates=[]
    for m in DATE_RE.finditer(txt):
        iso=f'{int(m.group(3)):04d}-{MONTHS[m.group(2).upper()]:02d}-{int(m.group(1)):02d}'
        dates.append((iso,m.start(),m.end()))
    tables=[]
    for table in main.find_all('table'):
        rows=[]
        for tr in table.find_all('tr'):
            cells=[norm(td.get_text(' ',strip=True)) for td in tr.find_all(['th','td'],recursive=False)]
            if cells:rows.append(cells)
        if rows and len(rows[0])>=3 and 'categor' in rows[0][0].lower():tables.append(rows)
    out={'juego':game,'fechas_detectadas':len(dates),'tablas_de_premios':len(tables),'sorteos':[],'advertencias':[]}
    if len(dates)!=len(tables):out['advertencias'].append('No coincide el número de fechas con el de tablas; NO SE PUBLICA NADA')
    for i,(iso,start,end) in enumerate(dates):
        record={'fecha':iso,'categorias':[],'completo':False,'errores':[]}
        if i>=len(tables):record['errores'].append('Falta tabla de premios');out['sorteos'].append(record);continue
        table=tables[i]
        labels=[]
        for row in table[1:]:
            if len(row)!=3:record['errores'].append('Fila de premios con número de columnas distinto de 3');continue
            label=row[0]; code=next((c for c in EXPECTED[game] if label.startswith(c+' ') or label==c or label.startswith(c+'(')),None)
            if code is None:record['errores'].append('Categoría inesperada: '+label);continue
            if code in labels:record['errores'].append('Categoría repetida: '+code);continue
            labels.append(code)
            try:
                winners=integer(row[1]);amount=money(row[2])
                record['categorias'].append({'codigo':code,'descripcion':label,'acertantes':winners,'importe_eur':amount,'sin_acertantes':winners==0,'importe_no_asignable':winners==0})
            except (ValueError,InvalidOperation) as exc:record['errores'].append(f'{code}: {exc}')
        if set(labels)!=set(EXPECTED[game]):record['errores'].append('Faltan o sobran categorías: '+str(sorted(set(EXPECTED[game])-set(labels))))
        # Extract combination from the isolated text before this draw's prize table.
        next_start=dates[i+1][1] if i+1<len(dates) else len(txt)
        segment=txt[end:next_start]
        before_prizes=segment.split('Categoría premio',1)[0]
        if game=='lototurf':
            m=re.search(r'\b((?:\d{2}\s+){5}\d{2})\s+R\s+(\d{2})\s+Caballo\s+(\d{2})\b',before_prizes)
            if m:record['resultado']={'numeros':m.group(1).split(),'reintegro':m.group(2),'caballo':m.group(3)}
            else:record['errores'].append('No se pudo aislar la combinación Lototurf')
        elif game=='quinigol':
            # Match six score tokens only when followed by team names: reject ambiguous text.
            scores=re.findall(r'(?<!\S)([0-2M]-[0-2M])(?=\s)',before_prizes)
            if len(scores)==6:record['resultado']={'marcadores':scores}
            else:record['errores'].append(f'Quinigol: {len(scores)} marcadores, se requieren 6')
        else:
            pairs=re.findall(r'Carrera\s+([1-5])(?:\s*\(2ª\))?\s+(\d{2})',before_prizes)
            if len(pairs)==6 and [x[0] for x in pairs]==['1','2','3','4','5','5']:
                record['resultado']={'caballos':[p[1] for p in pairs[:5]],'segundo_quinta':pairs[5][1]}
            else:record['errores'].append('Quíntuple Plus: no se reconocieron las seis posiciones')
        record['completo']=not record['errores'] and len(dates)==len(tables)
        out['sorteos'].append(record)
    out['todos_completos']=bool(out['sorteos']) and all(r['completo'] for r in out['sorteos'])
    return out

def main():
    report={'version':'0.85D','generado_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'solo_diagnostico':True,'publicable':False,'fuente':'RTVE','juegos':{}}
    for game,url in URLS.items():
        try: report['juegos'][game]=parse(game,get_page(url))
        except Exception as exc:report['juegos'][game]={'juego':game,'todos_completos':False,'error':str(exc)}
    Path('informe_rtve_085d.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['LotoScan 0.85D — auditoría de cobertura (NO PUBLICABLE)']
    for game,info in report['juegos'].items():
        lines.append(f"{game}: fechas={info.get('fechas_detectadas','?')} tablas={info.get('tablas_de_premios','?')} completos={sum(s['completo'] for s in info.get('sorteos',[]))}/{len(info.get('sorteos',[]))} error={info.get('error','ninguno')}")
        for s in info.get('sorteos',[]):
            if s['errores']:lines.append(f"  {s['fecha']}: {'; '.join(s['errores'])}")
    Path('informe_rtve_085d.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('\n'.join(lines))
if __name__=='__main__':main()
