
#!/usr/bin/env python3
"""LotoScan 0.85T: extraction candidates from SELAE homepage. READ ONLY.
No historical data is written. Candidates are NOT validated results.
"""
import datetime as dt
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path
from bs4 import BeautifulSoup

URL = 'https://www.loteriasyapuestas.es/es/resultados'
GAMES = {
    'euromillones': r'euromillones', 'bonoloto': r'bonoloto',
    'primitiva': r'(?<!gordo de la )primitiva', 'eurodreams': r'euro\s?dreams',
    'gordo-primitiva': r'el gordo|gordo de la primitiva',
    'loteria-nacional': r'loter[ií]a nacional', 'quinigol': r'quinigol',
    'lototurf': r'lototurf', 'quintuple-plus': r'qu[ií]ntuple plus',
}
DATE = re.compile(r'\b([0-3]?\d/[01]?\d/20\d{2})\b')
NUM = re.compile(r'\b\d{1,2}\b')
HEADERS = {'User-Agent':'Mozilla/5.0 (LotoScan diagnostic 0.85T)',
           'Accept':'text/html,application/xhtml+xml',
           'Cache-Control':'no-cache', 'Pragma':'no-cache'}

def clean(node):
    return ' '.join(node.get_text(' ', strip=True).split())

def download():
    with urllib.request.urlopen(urllib.request.Request(URL,headers=HEADERS),timeout=35) as r:
        if urllib.parse.urlsplit(r.url).hostname not in {'www.loteriasyapuestas.es','loteriasyapuestas.es'}:
            raise ValueError('Redirect to unexpected host')
        body=r.read(5_000_001)
        if len(body)>5_000_000: raise ValueError('HTML too large')
        return {'http':r.status,'bytes':len(body),'final_url':r.url},body

def game_of(label):
    label=label.lower()
    if re.search(GAMES['gordo-primitiva'],label): return 'gordo-primitiva'
    for game,pattern in GAMES.items():
        if game!='gordo-primitiva' and re.search(pattern,label,re.I): return game
    return None

def main():
    report={'version':'0.85T','generated_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
            'source':URL,'read_only':True,'publishable':False,'games':{},'notes':[],
            'warning':'Unverified candidates; no automated ticket checking from this report.'}
    try:
        meta,raw=download();report.update(meta)
        soup=BeautifulSoup(raw,'html.parser')
        # Official document links are reliably visible in the 0.85S HTML.
        for a in soup.find_all('a',href=True):
            label=clean(a); href=a['href']
            if not re.search(r'nota\s+de\s+prensa|listad[oa]\s+de\s+premios|\.pdf(?:\?|$)',label+' '+href,re.I):
                continue
            url=urllib.parse.urljoin(URL,href)
            if urllib.parse.urlsplit(url).hostname not in {'www.loteriasyapuestas.es','loteriasyapuestas.es'}:continue
            date=DATE.search(label)
            report['notes'].append({'game':game_of(label+' '+href),'date':date.group(1) if date else None,
                                    'label':label[:180],'url':url})
        # Collect candidate result sections, preserving HTML structure and tables.
        # No assumed CSS selectors: output evidence to inspect before writing a parser.
        for game,pattern in GAMES.items():
            notes=[x for x in report['notes'] if x['game']==game]
            samples=[]
            for note in notes[:4]:
                # Inspect the closest surrounding result block rather than page-wide text.
                link=soup.find('a',href=lambda h: bool(h) and urllib.parse.urljoin(URL,h)==note['url'])
                if not link:continue
                ancestors=[]
                for parent in list(link.parents)[:9]:
                    if parent.name not in ('div','section','article','li'):continue
                    txt=clean(parent)
                    if len(txt)<80 or len(txt)>14000:continue
                    tables=parent.find_all('table')
                    ancestors.append((len(txt),parent,txt,tables))
                if not ancestors:continue
                # Prefer smallest ancestor containing a table and draw date.
                candidates=[x for x in ancestors if x[3] and (not note['date'] or note['date'] in x[2])]
                chosen=min(candidates or ancestors,key=lambda x:x[0])
                _,parent,txt,tables=chosen
                sample={'date':note['date'],'document_url':note['url'],
                        'section_tag':parent.name,'section_classes':parent.get('class',[]),
                        'section_text_excerpt':txt[:2400], 'tables':[]}
                for table in tables[:3]:
                    rows=[]
                    for tr in table.find_all('tr')[:22]:
                        cells=[clean(c) for c in tr.find_all(['th','td'],recursive=False)]
                        if cells: rows.append(cells[:8])
                    sample['tables'].append(rows)
                samples.append(sample)
            report['games'][game]={'official_documents':len(notes),'candidates':samples,
                                   'validated':False}
        # No winner numbers are inferred from free text: game-specific selectors are required.
    except Exception as e:
        report['error']=f'{type(e).__name__}: {e}'
    Path('informe_selae_085t.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['LotoScan 0.85T - extraction evidence, NO PUBLICATION',
           f"HTTP: {report.get('http','ERROR')} | bytes: {report.get('bytes',0)}",
           f"Error: {report.get('error','none')}",f"Official document links: {len(report['notes'])}"]
    for g,x in report['games'].items():
        lines.append(f"{g}: documents={x['official_documents']} section_candidates={len(x['candidates'])} validated=NO")
    lines.append('No result or prize has been validated. No historical files changed.')
    Path('informe_selae_085t.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('\n'.join(lines),flush=True)

if __name__=='__main__': main()
