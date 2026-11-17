#!/usr/bin/env python3
"""Diagnóstico de páginas RTVE para LotoScan; solo lectura, sin publicación."""
import datetime as dt
import html
from html.parser import HTMLParser
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = 'https://www.rtve.es/loterias/'
GAMES = {'lototurf': ('lototurf',), 'quinigol': ('quinigol',), 'quintuple_plus': ('quíntuple', 'quintuple', 'quíntuple plus', 'quintuple plus')}
MAX_PAGES = 18

class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links=[]; self.text=[]; self.href=None; self.anchor=[]
        self.skip=0
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag in ('script','style','noscript'): self.skip+=1
        if tag=='a': self.href=a.get('href');self.anchor=[]
    def handle_endtag(self,tag):
        if tag in ('script','style','noscript'): self.skip=max(0,self.skip-1)
        if tag=='a' and self.href:
            self.links.append((self.href,' '.join(self.anchor).strip()[:120]));self.href=None;self.anchor=[]
    def handle_data(self,data):
        if not self.skip:
            value=' '.join(data.split())
            if value: self.text.append(value)
            if self.href: self.anchor.append(data.strip())

def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; LotoScanDiagnostics/0.85B)','Accept':'text/html,application/xhtml+xml'})
    with urllib.request.urlopen(req,timeout=18) as r:
        raw=r.read(900000)
        encoding=r.headers.get_content_charset() or 'utf-8'
        return r.status,r.url,r.headers.get('Content-Type',''),raw.decode(encoding,'replace')

def relevant_links(page,base):
    result=[]
    for href,label in page.links:
        full=urllib.parse.urljoin(base,href)
        p=urllib.parse.urlparse(full)
        if p.hostname not in ('www.rtve.es','rtve.es') or p.scheme!='https': continue
        full=urllib.parse.urlunparse(p._replace(fragment='',query=''))
        if any(t in urllib.parse.unquote(full+' '+label).lower() for terms in GAMES.values() for t in terms):
            result.append({'url':full,'texto':label})
    return result

def snippets(text, terms, radius=190, limit=6):
    out=[];lower=text.lower()
    for term in terms:
        for match in list(re.finditer(re.escape(term),lower))[:limit]:
            s=max(0,match.start()-radius);e=min(len(text),match.end()+radius)
            fragment=text[s:e]
            if fragment not in out:out.append(fragment)
    return out[:limit]

def main():
    report={'generado_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'objetivo':'Diagnóstico de accesibilidad y estructura; no verifica premios ni publica datos','paginas':[],'candidatos':{},'limites':['HTTP 200 no confirma que el resultado sea actual','Coincidencia textual no demuestra que exista una tabla de premios','Revisar manualmente cada sorteo y sus importes antes de integrar']}
    queue=[ROOT];seen=set()
    while queue and len(seen)<MAX_PAGES:
        url=queue.pop(0)
        if url in seen:continue
        seen.add(url);item={'url':url}
        try:
            status,final,ctype,body=fetch(url)
            page=Page();page.feed(body)
            text=' '.join(page.text)
            links=relevant_links(page,final)
            item.update({'http':status,'url_final':final,'content_type':ctype,'tamano_html':len(body),'enlaces_candidatos':links[:30],'juegos':{}})
            for game,terms in GAMES.items():
                found=any(t in text.lower() for t in terms)
                item['juegos'][game]={'mencionado_en_texto':found,'fragmentos':snippets(text,terms) if found else []}
            item['indicadores']={'premios':bool(re.search(r'premios?',text,re.I)),'acertantes':bool(re.search(r'acertantes?',text,re.I)),'euros':bool(re.search(r'\d[\d.,]*\s*€',text)),'fechas':list(dict.fromkeys(re.findall(r'\b\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}\b',text)))[:12]}
            for link in links:
                target=link['url']
                if target not in seen and target not in queue and len(queue)<35:queue.append(target)
            print(f'{status} {url} ({len(links)} enlaces candidatos)')
        except Exception as e:
            item['error']=f'{type(e).__name__}: {e}'[:350]
            print(f'ERROR {url}: {item["error"]}')
        report['paginas'].append(item)
        time.sleep(.3)
    for game,terms in GAMES.items():
        report['candidatos'][game]=[{'url':p['url'],'http':p.get('http'),'indicios_premios':p.get('indicadores',{}).get('premios'),'indicios_euros':p.get('indicadores',{}).get('euros')} for p in report['paginas'] if p.get('juegos',{}).get(game,{}).get('mencionado_en_texto')]
    with open('informe_rtve_085b.json','w',encoding='utf-8') as f:json.dump(report,f,ensure_ascii=False,indent=2)
    with open('informe_rtve_085b.txt','w',encoding='utf-8') as f:
        f.write('LotoScan 0.85B — Diagnóstico RTVE (sin publicación)\n')
        f.write(f'Páginas examinadas: {len(report["paginas"])}\n')
        for game,items in report['candidatos'].items():
            f.write(f'\n{game}: {len(items)} páginas con mención textual\n')
            for item in items:f.write(f'  HTTP {item["http"]} {item["url"]}\n')
        f.write('\nAVISO: El informe identifica páginas candidatas, NO acredita extracción fiable de resultados y premios.\n')

if __name__=='__main__':main()
