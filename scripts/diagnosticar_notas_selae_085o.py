
#!/usr/bin/env python3
"""0.85O: diagnose where SELAE exposes PDF references; read-only, bounded."""
import argparse
import datetime as dt
import html
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path
from bs4 import BeautifulSoup

HOSTS={'www.loteriasyapuestas.es','loteriasyapuestas.es'}
BASE='https://www.loteriasyapuestas.es/es/resultados/'
GAMES=['quiniela','bonoloto','euromillones','primitiva','eurodreams','gordo-primitiva','loteria-nacional','quinigol','lototurf','quintuple-plus']
PAT=re.compile(r'\.pdf\b|nota.{0,25}prensa|lista.{0,20}oficial|documentos/|quiniela',re.I)
URLPAT=re.compile(r'(?:https?:)?//[^\s"\'<>]+|/f/loterias/[^"\'<>\s]+',re.I)
HEADERS={'User-Agent':'Mozilla/5.0 (LotoScanResearch/0.85O)','Accept':'text/html,*/*'}

def safe_url(url):
    p=urllib.parse.urlsplit(url)
    if p.scheme!='https' or p.hostname not in HOSTS or p.username or p.password:
        raise ValueError('Solo HTTPS del dominio SELAE')
    return urllib.parse.urlunsplit((p.scheme,p.netloc,urllib.parse.quote(urllib.parse.unquote(p.path),safe='/'),urllib.parse.quote(urllib.parse.unquote(p.query),safe='=&'),''))

def fetch(url,limit=3000000):
    req=urllib.request.Request(safe_url(url),headers=HEADERS)
    with urllib.request.urlopen(req,timeout=30) as r:
        final=safe_url(r.url)
        data=r.read(limit+1)
        if len(data)>limit: raise ValueError('Respuesta demasiado grande')
        return {'http':r.status,'url_final':final,'tipo':r.headers.get('Content-Type',''),'bytes':len(data)},data

def analyze(url):
    item={'url':url,'enlaces':[],'referencias':[],'scripts':[]}
    try:
        meta,data=fetch(url);item.update(meta)
        soup=BeautifulSoup(data,'html.parser')
        item['titulo']=soup.title.get_text(' ',strip=True) if soup.title else ''
        seen=set()
        for tag in soup.find_all(['a','iframe','embed','object','script']):
            raw=tag.get('href') or tag.get('src') or tag.get('data')
            if not raw: continue
            target=urllib.parse.urljoin(meta['url_final'],raw)
            if tag.name=='script':
                item['scripts'].append(target[:350]);continue
            if PAT.search(raw+' '+tag.get_text(' ',strip=True)):
                try:target=safe_url(target)
                except ValueError:continue
                if target not in seen:
                    seen.add(target);item['enlaces'].append(target)
        # Inspect inline scripts, attributes, JSON-LD and raw escaped text; do not
        # assume the page renders every result on the server.
        decoded=html.unescape(data.decode('utf-8','replace'))
        decoded=decoded.replace('\\/','/')
        matches=list(PAT.finditer(decoded))
        item['total_coincidencias']=len(matches)
        for m in matches[:35]:
            item['referencias'].append(' '.join(decoded[max(0,m.start()-150):m.end()+220].split())[:400])
        for raw in URLPAT.findall(decoded):
            if not PAT.search(raw):continue
            try:
                target=safe_url(urllib.parse.urljoin(meta['url_final'],raw.rstrip('),;')))
                if target not in seen:
                    seen.add(target);item['enlaces'].append(target)
            except ValueError:pass
        item['enlaces']=item['enlaces'][:40]
        item['scripts']=item['scripts'][:20]
        item['diagnostico']='La ausencia de referencias no prueba que no existan PDFs; pueden cargarse mediante peticiones dinámicas.'
    except Exception as exc:item['error']=f'{type(exc).__name__}: {exc}'
    return item

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--quiniela-url',default='',help='URL oficial exacta de nota o página de jornada (opcional)')
    args=p.parse_args()
    if args.quiniela_url:safe_url(args.quiniela_url)
    pages=[analyze(BASE+game) for game in GAMES]
    if args.quiniela_url:pages.append(analyze(args.quiniela_url))
    report={'version':'0.85O','fecha_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
            'solo_lectura':True,'publicable':False,'paginas':pages}
    Path('informe_selae_085o.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['LotoScan 0.85O - referencias de documentos SELAE (DIAGNOSTICO)','No se modifica historico.json ni se publican premios.','']
    for item in pages:
        lines.append(f"{item['url']} | HTTP={item.get('http','ERROR')} | referencias={item.get('total_coincidencias',0)} | enlaces={len(item['enlaces'])} | scripts={len(item['scripts'])} | error={item.get('error','ninguno')}")
        for link in item['enlaces'][:5]:lines.append('  candidato: '+link)
    lines.append('Los candidatos requieren verificacion manual; no se descargan ni validan PDFs en esta prueba.')
    Path('informe_selae_085o.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('\n'.join(lines))

if __name__=='__main__':main()
