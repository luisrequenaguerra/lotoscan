
#!/usr/bin/env python3
"""LotoScan 0.85E: independent, read-only RTVE audit. Never publishes results."""
import datetime as dt
import json
import re
import urllib.request
from decimal import Decimal
from pathlib import Path
from bs4 import BeautifulSoup

URLS = {'lototurf':'https://www.rtve.es/loterias/lototurf/', 'quinigol':'https://www.rtve.es/loterias/quinigol/', 'quintuple_plus':'https://www.rtve.es/loterias/quintuple-plus/'}
EXPECTED = {'lototurf':['1ª','2ª','3ª','4ª','5ª','6ª','7ª','Reintegro'], 'quinigol':['1ª','2ª','3ª','4ª','5ª'], 'quintuple_plus':['Especial','1ª','2ª','3ª','4ª']}
MONTHS = {'ENE':1,'FEB':2,'MAR':3,'ABR':4,'MAY':5,'JUN':6,'JUL':7,'AGO':8,'SEP':9,'OCT':10,'NOV':11,'DIC':12}
DATE_RE = re.compile(r'\b(?:Lunes|Martes|Miércoles|Miercoles|Jueves|Viernes|Sábado|Sabado|Domingo),\s*(\d{1,2})\s+(ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)\s+(20\d{2})\b', re.I)

def clean(s): return ' '.join(s.split())
def winners(s):
    s=s.strip()
    if not re.fullmatch(r'\d{1,3}(?:\.\d{3})*|\d+',s): raise ValueError('acertantes inválidos: '+s)
    return int(s.replace('.',''))
def amount(s):
    s=s.replace('€','').strip()
    if not re.fullmatch(r'(?:\d{1,3}(?:\.\d{3})*|\d+),\d{2}',s): raise ValueError('importe no exacto a dos decimales: '+s)
    return str(Decimal(s.replace('.','').replace(',','.')))
def get_page(url):
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; LotoScanAudit/0.85E)','Accept':'text/html'})
    with urllib.request.urlopen(req,timeout=30) as r:
        if r.status!=200: raise ValueError('HTTP '+str(r.status))
        raw=r.read(2500000);charset=r.headers.get_content_charset() or 'utf-8'
    soup=BeautifulSoup(raw.decode(charset,'replace'),'html.parser')
    for el in soup(['script','style','noscript','nav','footer']):el.decompose()
    return soup.find('main') or soup

def category_code(label,game):
    label=clean(label)
    for code in EXPECTED[game]:
        if label==code or label.startswith(code+' ') or label.startswith(code+'('):return code
    return None

def result_from_segment(game,segment):
    """Strict first pass; conservative fallback for markup variations."""
    head=re.split(r'Categor[ií]a\s+premio',segment,maxsplit=1,flags=re.I)[0]
    if game=='lototurf':
        m=re.search(r'\b((?:\d{1,2}\s+){5}\d{1,2})\s+R\s*(\d{1,2})\s+Caballo\s*(\d{1,2})\b',head,re.I)
        if not m:
            m=re.search(r'\b((?:\d{1,2}\s+){5}\d{1,2})\s+Reintegro\s*(\d{1,2})\s+Caballo(?:\s+ganador)?\s*(\d{1,2})\b',head,re.I)
        if m:
            nums=[int(x) for x in m.group(1).split()]
            if len(nums)==6 and len(set(nums))==6 and all(1<=x<=31 for x in nums):
                return {'numeros':[f'{x:02d}' for x in nums],'reintegro':f'{int(m.group(2)):02d}','caballo':f'{int(m.group(3)):02d}'},None
        return None,'No se identificó inequívocamente combinación, reintegro y caballo'
    if game=='quinigol':
        scores=re.findall(r'(?<![\w-])([012Mm]-[012Mm])(?![\w-])',head)
        scores=[s.upper() for s in scores]
        if len(scores)==6:return {'marcadores':scores},None
        return None,f'Se detectaron {len(scores)} marcadores; se necesitan exactamente 6'
    pairs=re.findall(r'Carrera\s+([1-5])(?:\s*\(2ª\))?\s+(\d{1,2})',head,re.I)
    if len(pairs)==6 and [p[0] for p in pairs]==['1','2','3','4','5','5']:
        return {'caballos':[f'{int(p[1]):02d}' for p in pairs[:5]],'segundo_quinta':f'{int(pairs[5][1]):02d}'},None
    return None,'No se detectaron seis posiciones inequívocas de Quíntuple Plus'

def audit(game,root):
    text=clean(root.get_text(' ',strip=True))
    dates=[(f'{int(m.group(3)):04d}-{MONTHS[m.group(2).upper()]:02d}-{int(m.group(1)):02d}',m.start(),m.end()) for m in DATE_RE.finditer(text)]
    tables=[]
    for table in root.find_all('table'):
        rows=[]
        for tr in table.find_all('tr'):
            cells=[clean(c.get_text(' ',strip=True)) for c in tr.find_all(['th','td'],recursive=False)]
            if cells:rows.append(cells)
        if rows and any('categor' in ' '.join(row).lower() for row in rows[:2]):tables.append(rows)
    result={'fechas':len(dates),'tablas':len(tables),'sorteos':[],'advertencias':[]}
    if len(dates)!=len(tables):result['advertencias'].append('Fechas y tablas no coinciden; asociación por índice NO validada')
    for i,(date,start,end) in enumerate(dates):
        next_start=dates[i+1][1] if i+1<len(dates) else len(text)
        segment=text[end:next_start]
        item={'fecha':date,'completo':False,'categorias':[],'resultado':None,'errores':[],'alertas':[]}
        parsed,err=result_from_segment(game,segment)
        item['resultado']=parsed
        if err:item['errores'].append(err)
        if i>=len(tables):item['errores'].append('Sin tabla asociada')
        else:
            seen=set()
            for row in tables[i]:
                if len(row)<3:continue
                code=category_code(row[0],game)
                if not code:continue
                if code in seen:item['errores'].append('Categoría duplicada: '+code);continue
                seen.add(code)
                try:
                    count=winners(row[1]);eur=amount(row[2])
                    item['categorias'].append({'codigo':code,'descripcion':row[0],'acertantes':count,'importe_eur_publicado':eur,'sin_acertantes':count==0})
                    if count>0 and Decimal(eur)%1==0:item['alertas'].append(code+': importe terminado en ,00; confirmar céntimos con otra fuente')
                    if count==0 and Decimal(eur)!=0:item['alertas'].append(code+': cero acertantes con importe no nulo; revisar')
                except ValueError as exc:item['errores'].append(code+': '+str(exc))
            missing=set(EXPECTED[game])-seen
            if missing:item['errores'].append('Categorías ausentes: '+', '.join(sorted(missing)))
        if len(dates)!=len(tables):item['errores'].append('Asociación fecha-tabla no demostrada')
        item['completo']=not item['errores']
        if not item['completo']:
            item['fragmento_diagnostico']=segment[:1800]
            if i<len(tables):item['filas_tabla_diagnostico']=tables[i][:12]
        result['sorteos'].append(item)
    result['completos']=sum(s['completo'] for s in result['sorteos'])
    result['sin_alertas_de_importe']=all(not s['alertas'] for s in result['sorteos'])
    result['apto_para_publicar']=False
    return result

def main():
    report={'version':'0.85E','generado_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'solo_lectura':True,'publicable':False,'advertencia':'Una tabla con ,00 no demuestra redondeo, pero requiere contraste externo para certificar céntimos. La completitud estructural no implica exactitud monetaria.','juegos':{}}
    for game,url in URLS.items():
        try:report['juegos'][game]=audit(game,get_page(url))
        except Exception as exc:report['juegos'][game]={'error':f'{type(exc).__name__}: {exc}','completos':0,'sorteos':[],'apto_para_publicar':False}
    Path('informe_rtve_085e.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['LotoScan 0.85E — auditoría en modo lectura','NO PUBLICABLE: los céntimos requieren contraste externo','']
    for game,r in report['juegos'].items():
        lines.append(f'{game}: {r.get("completos",0)}/{len(r.get("sorteos",[]))} completos; error={r.get("error","ninguno")}')
        for s in r.get('sorteos',[]):
            if s['errores']:lines.append(f'  {s["fecha"]}: '+ '; '.join(s['errores']))
        alerts=sum(len(s['alertas']) for s in r.get('sorteos',[]))
        lines.append(f'  importes terminados en ,00 u otras alertas: {alerts}')
    Path('informe_rtve_085e.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('\n'.join(lines))
if __name__=='__main__':main()
