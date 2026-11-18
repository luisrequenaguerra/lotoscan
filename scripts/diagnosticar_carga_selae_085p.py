
#!/usr/bin/env python3
"""LotoScan 0.85P: investigate SELAE dynamic result/document loading.
Read-only diagnostic. Does not publish or change historical data.
"""
import datetime as dt
import json
import re
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path
from bs4 import BeautifulSoup

ROOT = 'https://www.loteriasyapuestas.es'
SLUGS = ['quiniela','bonoloto','euromillones','primitiva','eurodreams',
         'gordo-primitiva','loteria-nacional','quinigol','lototurf','quintuple-plus']
HEADERS = {'User-Agent':'Mozilla/5.0 (compatible; LotoScanResearch/0.85P)',
           'Accept':'text/html,application/javascript,*/*'}
PAT = re.compile(r'nota.{0,35}prensa|\.pdf\b|resultad|sorteo|drawId|documentos/|api/|ajax|historico', re.I)
URLS = re.compile(r'''(?:(?:https?:)?//|/)[\w./%?=&:#-]{8,}''')
MAX_JS = 8

def get(url, cap=1_500_000):
    p = urllib.parse.urlsplit(url)
    if p.scheme != 'https' or p.hostname not in ('www.loteriasyapuestas.es','loteriasyapuestas.es'):
        raise ValueError('URL outside official SELAE host')
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=25) as response:
        final = urllib.parse.urlsplit(response.url)
        if final.hostname not in ('www.loteriasyapuestas.es','loteriasyapuestas.es'):
            raise ValueError('Redirect outside SELAE')
        body = response.read(cap+1)
        if len(body) > cap:
            raise ValueError('Response too large')
        return {'http':response.status,'final_url':response.url,'bytes':len(body),
                'content_type':response.headers.get('Content-Type','')},body.decode('utf-8','replace')

def snippets(source, limit=12):
    return [' '.join(source[max(0,m.start()-110):m.end()+160].split())[:320]
            for m in list(PAT.finditer(source))[:limit]]

def main():
    report={'version':'0.85P','utc':dt.datetime.now(dt.timezone.utc).isoformat(),
            'read_only':True,'published':False,'pages':[],'javascript':[]}
    scripts={}
    for slug in SLUGS:
        url=ROOT+'/es/resultados/'+slug
        item={'game':slug,'url':url,'scripts':[],'candidate_links':[]}
        try:
            meta,html=get(url)
            item.update(meta)
            soup=BeautifulSoup(html,'html.parser')
            item['html_hits']=snippets(html)
            for tag in soup.find_all(['script','a','iframe'], limit=1500):
                attr='src' if tag.name in ('script','iframe') else 'href'
                raw=tag.get(attr)
                if not raw: continue
                absolute=urllib.parse.urljoin(meta['final_url'],raw)
                if tag.name=='script' and urllib.parse.urlsplit(absolute).hostname in ('www.loteriasyapuestas.es','loteriasyapuestas.es'):
                    scripts.setdefault(absolute,set()).add(slug)
                    item['scripts'].append(absolute)
                elif PAT.search(raw+' '+tag.get_text(' ',strip=True)):
                    item['candidate_links'].append(absolute)
            item['scripts']=item['scripts'][:35]
            item['candidate_links']=item['candidate_links'][:20]
            item['inline_script_hits']=[]
            for tag in soup.find_all('script',src=False):
                item['inline_script_hits'].extend(snippets(tag.get_text(),4))
            item['inline_script_hits']=item['inline_script_hits'][:15]
        except Exception as exc:
            item['error']=f'{type(exc).__name__}: {exc}'
        report['pages'].append(item)
        print(slug,item.get('http','ERROR'),'scripts',len(item['scripts']))
    # Inspect bounded number of common JS bundles. No speculative API requests.
    ordered=sorted(scripts, key=lambda url: (not bool(re.search(r'result|sorte|app|main',url,re.I)),url))
    for url in ordered[:MAX_JS]:
        entry={'url':url,'used_by':sorted(scripts[url])}
        try:
            meta,js=get(url,cap=3_000_000)
            entry.update(meta)
            entry['hits']=snippets(js,25)
            candidates=[]
            for raw in URLS.findall(js):
                if PAT.search(raw) and raw not in candidates:
                    candidates.append(raw[:300])
            entry['path_candidates']=candidates[:30]
        except Exception as exc:
            entry['error']=f'{type(exc).__name__}: {exc}'
        report['javascript'].append(entry)
        print('JS',entry.get('http','ERROR'),url[:120])
    Path('informe_selae_085p.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['LotoScan 0.85P — diagnóstico de carga dinámica (SOLO LECTURA)','']
    for item in report['pages']:
        lines.append(f"{item['game']}: HTTP={item.get('http','ERROR')} scripts={len(item['scripts'])} enlaces={len(item['candidate_links'])} error={item.get('error','-')}")
    lines.append(f"Scripts JS inspeccionados: {len(report['javascript'])}")
    for entry in report['javascript']:
        lines.append(f"{entry['url']}: HTTP={entry.get('http','ERROR')} coincidencias={len(entry.get('hits',[]))} error={entry.get('error','-')}")
    lines.append('Candidatos NO verificados; este diagnóstico no identifica aún una API confirmada.')
    Path('informe_selae_085p.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')

if __name__=='__main__':
    main()
