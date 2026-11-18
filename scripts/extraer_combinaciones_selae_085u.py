
#!/usr/bin/env python3
"""LotoScan 0.85U: inspect winning-combination DOM alongside official notes.
Diagnostic only. Never writes historical data or claims validated results.
"""
import datetime as dt
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path
from bs4 import BeautifulSoup

URL = 'https://www.loteriasyapuestas.es/es/resultados'
HOSTS = {'www.loteriasyapuestas.es', 'loteriasyapuestas.es'}
GAMES = {'euromillones':r'euromillones','bonoloto':r'bonoloto',
 'primitiva':r'la primitiva|(?<!gordo de la )primitiva',
 'eurodreams':r'euro\s?dreams','gordo-primitiva':r'el gordo|gordo de la primitiva',
 'loteria-nacional':r'loter[ií]a nacional','quinigol':r'quinigol',
 'lototurf':r'lototurf','quintuple-plus':r'qu[ií]ntuple\s?plus|quintupleplus'}
DATE = re.compile(r'\b[0-3]?\d/[01]?\d/20\d{2}\b')
NOTE = re.compile(r'nota\s+de\s+prensa|listad[oa]\s+de\s+premios|\.pdf(?:\?|$)',re.I)
HEADERS = {'User-Agent':'Mozilla/5.0 (LotoScan diagnostic 0.85U)',
 'Accept':'text/html,application/xhtml+xml','Cache-Control':'no-cache','Pragma':'no-cache'}

def txt(tag):
    return ' '.join(tag.get_text(' ',strip=True).split())

def game_for(s):
    if re.search(GAMES['gordo-primitiva'],s,re.I): return 'gordo-primitiva'
    for name,pattern in GAMES.items():
        if name!='gordo-primitiva' and re.search(pattern,s,re.I): return name
    return None

def dom_outline(node, max_nodes=130):
    """Retain DOM evidence, including class and data attributes, without inventing balls."""
    result=[]
    for child in node.find_all(True,limit=max_nodes):
        if child.name in ('script','style','svg','path'): continue
        direct=' '.join(s.strip() for s in child.find_all(string=True,recursive=False) if s.strip())
        attrs={k:v for k,v in child.attrs.items() if k in ('class','id','title','aria-label','data-numero','data-value','data-id','alt')}
        if direct or attrs:
            result.append({'tag':child.name,'attrs':attrs,'direct_text':direct[:110]})
    return result[:90]

def main():
    report={'version':'0.85U','generated_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
        'source':URL,'read_only':True,'publishable':False,'games':{},'errors':[],
        'notice':'DOM evidence only. Numbers and prizes are not validated or published.'}
    try:
        req=urllib.request.Request(URL,headers=HEADERS)
        with urllib.request.urlopen(req,timeout=35) as response:
            final=urllib.parse.urlsplit(response.url)
            if final.scheme!='https' or final.hostname not in HOSTS:
                raise ValueError('Unexpected redirect')
            raw=response.read(5_000_001)
            if len(raw)>5_000_000: raise ValueError('HTML exceeds 5 MB')
            report['http']=response.status
            report['bytes']=len(raw)
        soup=BeautifulSoup(raw,'html.parser')
        for name in GAMES: report['games'][name]=[]
        seen=set()
        for link in soup.find_all('a',href=True):
            label=txt(link)
            href=link['href']
            if not NOTE.search(label+' '+href): continue
            absolute=urllib.parse.urljoin(URL,href)
            parsed=urllib.parse.urlsplit(absolute)
            if parsed.scheme!='https' or parsed.hostname not in HOSTS: continue
            game=game_for(label+' '+href)
            if not game: continue
            date=DATE.search(label)
            key=(game,date.group() if date else '',absolute)
            if key in seen:continue
            seen.add(key)
            ancestors=[]
            for parent in list(link.parents)[:14]:
                if parent.name not in ('article','section','li','div'):continue
                content=txt(parent)
                if len(content)>20000:break
                if len(content)<80:continue
                ancestors.append(parent)
            if not ancestors:continue
            # Prefer a result container including the official note and its prize table.
            with_table=[p for p in ancestors if p.find('table')]
            detail=min(with_table or ancestors,key=lambda p:len(txt(p)))
            # Larger ancestors may contain winning balls before the prize table.
            wider=next((p for p in ancestors if p is not detail and len(txt(p))>len(txt(detail))+50),detail)
            # A small snapshot of the immediately preceding siblings captures balls
            # when result header and prize detail share a parent.
            preceding=[]
            for sibling in list(detail.previous_siblings)[:5]:
                if getattr(sibling,'name',None):
                    preceding.append({'tag':sibling.name,'classes':sibling.get('class',[]),
                                      'text':txt(sibling)[:1100], 'dom':dom_outline(sibling,50)})
            record={'date_from_note':date.group() if date else None,
                    'document_url':absolute,'document_label':label[:180],
                    'detail_classes':detail.get('class',[]),
                    'wider_classes':wider.get('class',[]),
                    'wider_text':txt(wider)[:2300],
                    'wider_dom':dom_outline(wider),
                    'preceding_siblings':preceding,
                    'tables':[],'validated':False}
            for table in detail.find_all('table')[:3]:
                rows=[]
                for tr in table.find_all('tr')[:25]:
                    cells=[txt(c) for c in tr.find_all(['td','th'],recursive=False)]
                    if cells: rows.append(cells[:8])
                record['tables'].append(rows)
            report['games'][game].append(record)
        for game in report['games']:
            report['games'][game]=report['games'][game][:4]
    except Exception as exc:
        report['errors'].append(f'{type(exc).__name__}: {exc}')
    Path('informe_selae_085u.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['LotoScan 0.85U - evidence of winning combinations (READ ONLY)',
           f"HTTP: {report.get('http','ERROR')} | bytes: {report.get('bytes',0)}"]
    for game,records in report['games'].items():
        lines.append(f'{game}: {len(records)} candidate result sections; validated=NO')
    lines.extend('ERROR: '+e for e in report['errors'])
    lines.append('No historical data or app files modified.')
    Path('informe_selae_085u.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('\n'.join(lines),flush=True)
    if report['errors']:raise SystemExit(1)

if __name__=='__main__':main()
