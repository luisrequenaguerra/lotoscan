
"""LotoScan 0.47: diagnóstico estructurado, NO publica ni modifica premios.
Consulta 3 páginas con intervalo entre solicitudes; respeta robots.txt.
No interpreta la accesibilidad como autorización de reutilización.
"""
import json
import re
import time
import urllib.request
import urllib.robotparser
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

DATES = ('2026-11-13', '2026-11-10', '2026-11-06')
BASE = 'https://comprobarloteria.com/euromillones/{}/'
UA = 'LotoScan-diagnostic/0.47'
CATEGORIES = [(5,2),(5,1),(5,0),(4,2),(4,1),(3,2),(4,0),(2,2),(3,1),(3,0),(1,2),(2,1),(2,0)]

class Page(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts=[]; self.rows=[]; self.row=None; self.cell=None; self.skip=0
    def handle_starttag(self, tag, attrs):
        if tag in ('script','style','noscript'): self.skip+=1
        if self.skip: return
        if tag=='tr': self.row=[]
        if tag in ('td','th') and self.row is not None: self.cell=[]
    def handle_endtag(self, tag):
        if tag in ('script','style','noscript'):
            self.skip=max(0,self.skip-1); return
        if self.skip: return
        if tag in ('td','th') and self.cell is not None and self.row is not None:
            self.row.append(' '.join(' '.join(self.cell).split())); self.cell=None
        if tag=='tr' and self.row is not None:
            self.rows.append(self.row); self.row=None
    def handle_data(self, data):
        if self.skip or not data.strip(): return
        self.parts.append(data.strip())
        if self.cell is not None: self.cell.append(data.strip())

def request(url):
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'text/html'})
    with urllib.request.urlopen(req,timeout=20) as response:
        return response.status,response.geturl(),response.headers.get('Content-Type',''),response.read(500000).decode('utf-8','replace')

def parse_amount(value):
    value=value.replace('\u00a0',' ').strip()
    if 'sin acertantes' in value.casefold(): return None
    match=re.search(r'(\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2})\s*€',value)
    if not match: return None
    return int(match.group(1).replace('.','').replace(',','')) # centimos

def extract(date, page):
    text=' '.join(' '.join(page.parts).split())
    result={'fecha':date,'datos_validos':False,'filas_tabla':page.rows[:20]}
    # Solo interpreta secuencia si está junto al encabezado del resultado.
    m=re.search(r'Resultado de Euromillones\s*·?\s*Sorteo\s*\d+\s+.{0,65}?\s((?:\d{1,2}\s+){5})Estrellas\s+(\d{1,2})\s+(\d{1,2})\s+El Mill[oó]n\s+([A-Z]{3}\d{5})',text,re.I)
    if m:
        numbers=list(map(int,m.group(1).split()))
        stars=[int(m.group(2)),int(m.group(3))]
        if len(set(numbers))==5 and all(1<=x<=50 for x in numbers) and len(set(stars))==2 and all(1<=x<=12 for x in stars):
            result.update(numeros=sorted(numbers),estrellas=sorted(stars),el_millon=m.group(4))
    prizes={}
    for row in page.rows:
        joined=' '.join(row)
        cat=re.search(r'(?<!\d)([1-5])\s*\+\s*([012])(?!\d)',joined)
        if not cat: continue
        key=(int(cat.group(1)),int(cat.group(2)))
        if key not in CATEGORIES: continue
        amount=parse_amount(joined)
        if amount is None and 'sin acertantes' not in joined.casefold(): continue
        name=f'{key[0]}+{key[1]}'
        if name in prizes: result.setdefault('advertencias',[]).append('Categoría duplicada '+name)
        prizes[name]={'importe_centimos':amount,'fila':row}
    result['categorias']=prizes
    result['categorias_encontradas']=len(prizes)
    result['datos_validos']=bool('numeros' in result and len(prizes)==13 and not result.get('advertencias'))
    result['estado']='estructura_completa_sin_verificacion_independiente' if result['datos_validos'] else 'incompleto_revisar'
    return result

def main():
    report={'version':'0.47','fecha_utc':datetime.now(timezone.utc).isoformat(),'publica_resultados':False,'resultados':[]}
    for i,date in enumerate(DATES):
        url=BASE.format(date); p=urlsplit(url)
        item={'fecha':date,'url':url,'datos_validos':False}
        try:
            robots_url=f'{p.scheme}://{p.netloc}/robots.txt'
            status,_,_,rules=request(robots_url) if i==0 else (200,'','','')
            if i==0:
                rp=urllib.robotparser.RobotFileParser(); rp.parse(rules.splitlines())
                main.robots=rp
            if not main.robots.can_fetch(UA,url):
                item['estado']='prohibido_por_robots'
            else:
                if i: time.sleep(2)
                status,final,ct,html=request(url)
                item.update(http=status,url_final=final)
                if status==200 and 'html' in ct.lower():
                    parser=Page();parser.feed(html)
                    item.update(extract(date,parser))
                else: item['estado']='respuesta_no_html'
        except Exception as exc:
            item['estado']='error';item['detalle']=str(exc)[:200]
        report['resultados'].append(item)
    report['nota']='Diagnóstico solamente. No publicar como premios verificados sin contraste independiente y autorización de reutilización.'
    Path('informe-lotoscan-047.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Informe generado. Fechas completas:',sum(x.get('datos_validos',False) for x in report['resultados']))

if __name__=='__main__': main()

