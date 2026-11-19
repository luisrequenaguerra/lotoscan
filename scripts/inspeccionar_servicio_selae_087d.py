#!/usr/bin/env python3
"""LotoScan 0.87D: inspeccion pasiva de HTML/JS publicos del servicio SELAE.
No ejecuta JS, no elude controles de acceso, no publica resultados.
"""
import argparse
import datetime as dt
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlparse
from urllib.request import Request, urlopen

BASE = 'https://www.loteriasyapuestas.es/f/loterias/resultados/'
JUEGOS = [
    ('euromillones','EMIL','euromillones.html','20261117'),
    ('primitiva','LAPR','primitiva.html','20261116'),
    ('bonoloto','BONO','bonoloto.html','20261117'),
    ('gordo-primitiva','ELGR','gordo.html','20261115'),
    ('eurodreams','EDMS','eurodreams.html','20261116'),
    ('loteria-nacional','LNAC','lnac.html','20261114'),
    ('quiniela','LAQU','quiniela.html','20261115'),
    ('quinigol','QGOL','quinigol.html','20261117'),
    ('lototurf','LOTU','lototurf.html','20261115'),
    ('quintuple-plus','QUPL','quintuple.html','20261115'),
]
OUT = Path('diagnostico_selae_087d')
HEADERS = {'User-Agent':'LotoScan/0.87D (inspeccion tecnica de recursos publicos)',
           'Accept':'text/html,application/javascript,text/javascript,*/*;q=0.5',
           'Accept-Language':'es-ES,es;q=0.9'}
MAX_BYTES = 600_000

class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.resources=[]; self.inline=[]; self._script=False; self._buf=[]
    def handle_starttag(self, tag, attrs):
        d=dict(attrs)
        if tag=='script':
            if d.get('src'): self.resources.append({'tag':tag,'attribute':'src','value':d['src']})
            else: self._script=True; self._buf=[]
        if tag in ('iframe','link','img','form','a'):
            key={'iframe':'src','link':'href','img':'src','form':'action','a':'href'}[tag]
            if d.get(key): self.resources.append({'tag':tag,'attribute':key,'value':d[key], 'rel':d.get('rel')})
    def handle_data(self,data):
        if self._script: self._buf.append(data)
    def handle_endtag(self,tag):
        if tag=='script' and self._script:
            self.inline.append(''.join(self._buf)); self._script=False; self._buf=[]

def get(url):
    info={'url':url,'status':None,'final_url':None,'content_type':None,'bytes':0,'sha256':None,'error':None,'truncated':False}
    data=b''
    try:
        with urlopen(Request(url,headers=HEADERS),timeout=18) as r:
            info.update(status=r.status,final_url=r.geturl(),content_type=r.headers.get('Content-Type',''))
            data=r.read(MAX_BYTES+1)
    except HTTPError as e:
        info.update(status=e.code,final_url=e.geturl(),content_type=e.headers.get('Content-Type',''),error=f'HTTP {e.code}')
    except (URLError,TimeoutError,OSError) as e: info['error']=f'{type(e).__name__}: {str(e)[:160]}'
    info['truncated']=len(data)>MAX_BYTES
    data=data[:MAX_BYTES]; info['bytes']=len(data)
    info['sha256']=hashlib.sha256(data).hexdigest() if data else None
    return info,data

def same_origin(url):
    p=urlparse(url)
    return p.scheme=='https' and p.hostname=='www.loteriasyapuestas.es' and p.port is None

def candidates(text,base):
    """Static URL hints only: no automatic requests to guessed API endpoints."""
    patterns=[r'''(?:fetch|axios\.(?:get|post)|\.open)\s*\(\s*['\"]([^'\"]{2,220})['\"]''',
              r'''(?:url|endpoint|action|src)\s*[:=]\s*['\"]([^'\"]{2,220})['\"]''',
              r'''['\"]((?:https?://|/)[^'\"\s]{3,220}(?:json|xml|resultados|sorteos|api)[^'\"\s]*)['\"]''']
    values=[]
    for p in patterns:
        for m in re.finditer(p,text,re.I):
            v=m.group(1); resolved=urljoin(base,v)
            if resolved not in values: values.append(resolved)
    return values[:60]

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--fecha',help='AAAAMMDD opcional, sustituye fechas historicas')
    p.add_argument('--max-scripts',type=int,default=8,help='Maximo de JS compartidos descargados (0-15)')
    a=p.parse_args()
    if a.fecha:
        try: dt.datetime.strptime(a.fecha,'%Y%m%d')
        except ValueError: p.error('Fecha invalida: usar AAAAMMDD')
    OUT.mkdir(exist_ok=True)
    entries=[]; js_urls=[]; js_results=[]
    for i,(name,code,filename,reference) in enumerate(JUEGOS,1):
        # Dos variantes para detectar si la fecha cambia el contenido realmente.
        for mode,date in [('actual',None),('historico',a.fecha or reference)]:
            params={'game_id':code}
            if date: params['fecha_sorteo']=date
            url=BASE+filename+'?'+urlencode(params)
            meta,raw=get(url)
            item={**meta,'juego':name,'variante':mode,'fecha_solicitada':date,
                  'scripts_externos':[],'recursos':[],'scripts_inline':[],'pistas_urls':[]}
            if meta['status']==200 and 'html' in (meta['content_type'] or '').lower():
                html=raw.decode('utf-8','replace')
                (OUT/f'{i:02d}_{name}_{mode}.html').write_text(html,encoding='utf-8')
                parser=Links(); parser.feed(html)
                item['recursos']=[{**r,'url_absoluta':urljoin(url,r['value'])} for r in parser.resources][:150]
                item['scripts_externos']=[r['url_absoluta'] for r in item['recursos'] if r['tag']=='script']
                item['scripts_inline']=[{'chars':len(s),'sha256':hashlib.sha256(s.encode()).hexdigest(),
                    'muestra':s[:900]} for s in parser.inline]
                item['pistas_urls']=candidates(html,url)
                for u in item['scripts_externos']:
                    if same_origin(u) and u not in js_urls: js_urls.append(u)
            entries.append(item)
            print(f'{name:19} {mode:9} HTTP {meta["status"]} {meta["bytes"]} bytes',flush=True)
            time.sleep(0.25)
    for idx,url in enumerate(js_urls[:max(0,min(a.max_scripts,15))],1):
        meta,raw=get(url)
        record={**meta,'pistas_urls':[]}
        if meta['status']==200:
            text=raw.decode('utf-8','replace')
            (OUT/f'script_{idx:02d}.js').write_text(text,encoding='utf-8')
            record['pistas_urls']=candidates(text,url)
            record['muestra_inicio']=text[:800]
        js_results.append(record)
        print(f'JS {idx}: HTTP {meta["status"]} {meta["bytes"]} bytes',flush=True)
        time.sleep(0.3)
    report={'version':'0.87D','fecha_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
        'origen':BASE,'publicable':False,'no_modifica_historico':True,
        'nota':'Inspeccion estatica; URLs detectadas no son API verificadas. HTTP 200 no valida resultados.',
        'html':entries,'js':js_results,
        'resumen':{'consultas_html':len(entries),'http_200_html':sum(x['status']==200 for x in entries),
                  'js_descargados':len(js_results),'js_http_200':sum(x['status']==200 for x in js_results),
                  'recursos_js_unicos':len(js_urls)}}
    (OUT/'informe_087d.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    lines=['LotoScan 0.87D - inspeccion HTML y JS de SELAE','NO publica resultados ni modifica historico.json','']
    for e in entries:
        lines += [f'{e["juego"]} / {e["variante"]}: HTTP {e["status"]}; {e["bytes"]} bytes; SHA {e["sha256"]}',
                  f'  Scripts: {e["scripts_externos"]}',f'  Pistas: {e["pistas_urls"]}']
    for e in js_results: lines += [f'JS {e["url"]}: HTTP {e["status"]}',f'  Pistas: {e["pistas_urls"]}']
    (OUT/'informe_087d.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('Informe creado. No se ha publicado ni modificado historico.json.')

if __name__=='__main__': main()
