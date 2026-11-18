#!/usr/bin/env python3
"""LotoScan 0.85N-10: inspección de páginas por juego y PDF oficiales.
Solo diagnóstico: nunca modifica históricos ni publica premios.
"""
import datetime as dt
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path
from bs4 import BeautifulSoup
from extraer_premios_selae_085n import audit, safe_url

ROOT = Path(__file__).resolve().parent
PAGES = {
    'quiniela':'quiniela', 'bonoloto':'bonoloto', 'euromillones':'euromillones',
    'primitiva':'primitiva', 'eurodreams':'eurodreams',
    'gordo':'gordo-primitiva', 'loteria_nacional':'loteria-nacional',
    'quinigol':'quinigol', 'lototurf':'lototurf', 'quintuple_plus':'quintuple-plus'
}
# Slugs are candidates; the report records failures rather than assuming they exist.
BASE='https://www.loteriasyapuestas.es/es/resultados/'
KEYWORDS=re.compile(r'nota\s+de\s+prensa|nota[_ -]*de[_ -]*prensa|\.pdf(?:$|[?#])|lista\s+oficial|lista[_ -]*oficial',re.I)
HEADERS={'User-Agent':'Mozilla/5.0 (LotoScanDiagnostic/0.85N-10)', 'Accept':'text/html,*/*'}

def discover(game,slug):
    url=BASE+slug
    item={'juego':game,'pagina':url,'candidatos_pdf':[]}
    try:
        req=urllib.request.Request(safe_url(url),headers=HEADERS)
        with urllib.request.urlopen(req,timeout=30) as r:
            final=r.url; safe_url(final)
            data=r.read(4_000_001)
            if len(data)>4_000_000: raise ValueError('HTML demasiado grande')
            item['http']=r.status;item['url_final']=final
            item['tipo']=r.headers.get('Content-Type','')
        soup=BeautifulSoup(data,'html.parser')
        item['titulo']=soup.title.get_text(' ',strip=True) if soup.title else ''
        seen=set()
        for tag in soup.find_all(['a','iframe','embed','object']):
            raw=tag.get('href') or tag.get('src') or tag.get('data')
            if not raw:continue
            label=' '.join(tag.get_text(' ',strip=True).split())
            candidate=urllib.parse.urljoin(final,raw)
            if not KEYWORDS.search(label+' '+candidate):continue
            try: candidate=safe_url(candidate)
            except ValueError:continue
            if candidate in seen:continue
            seen.add(candidate)
            item['candidatos_pdf'].append({'texto':label[:140],'url':candidate})
        item['total_candidatos']=len(item['candidatos_pdf'])
        item['candidatos_pdf']=item['candidatos_pdf'][:30]
        item['aviso']='Los enlaces HTML no garantizan cobertura histórica; otros resultados pueden cargarse dinámicamente.'
    except Exception as exc:
        item['error']=f'{type(exc).__name__}: {exc}'
    return item

def main():
    pages=[discover(g,s) for g,s in PAGES.items()]
    # Keep all 12 already-proven official URLs; add only links actually discovered.
    seed=json.loads((ROOT/'fuentes_selae_085n.json').read_text(encoding='utf-8'))
    urls={safe_url(x['url']) for x in seed}
    for page in pages:
        for link in page.get('candidatos_pdf',[]):
            if link['url'].lower().split('?')[0].endswith('.pdf'):
                urls.add(link['url'])
    # Bound the diagnostic to avoid unintentional bulk crawling.
    selected=sorted(urls)[:60]
    documents=[audit(url) for url in selected]
    # Don't mistake a PDF belonging to another game for Quiniela.
    quiniela=[d for d in documents if d['juego']=='quiniela']
    report={'version':'0.85N-10','utc':dt.datetime.now(dt.timezone.utc).isoformat(),
            'solo_diagnostico':True,'publicable':False,'paginas':pages,'documentos':documents,
            'quiniela_pdf_detectado':bool(quiniela),
            'advertencia':'No se certifican fechas, categorías ni importes automáticamente. No se publica histórico.'}
    Path('informe_selae_085n_10.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['LotoScan 0.85N - DIEZ JUEGOS - SOLO DIAGNOSTICO']
    for p in pages:lines.append(f"{p['juego']}: HTTP={p.get('http','ERROR')} enlaces={p.get('total_candidatos',0)} error={p.get('error','ninguno')}")
    lines.append(f'Documentos auditados: {len(documents)}')
    lines.append(f'PDF de Quiniela identificado: {bool(quiniela)}')
    for d in documents:lines.append(f"{d['juego']} | {d['estado']} | categorias={len(d.get('categorias',[]))} | {d.get('error','')}")
    Path('informe_selae_085n_10.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('\n'.join(lines))

if __name__=='__main__':main()
