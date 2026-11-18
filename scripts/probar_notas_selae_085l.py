
#!/usr/bin/env python3
"""LotoScan 0.85L: prueba de acceso a notas oficiales SELAE, solo lectura."""
import argparse
import datetime as dt
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from bs4 import BeautifulSoup
from pypdf import PdfReader
from io import BytesIO

BASE = 'https://www.loteriasyapuestas.es'
PAGES = [BASE + '/es/resultados', BASE + '/es/resultados/euromillones']
OUT = Path('informe_selae_085l.json')
HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; LotoScanDiagnostic/0.85L)', 'Accept': 'text/html,application/pdf,*/*'}
KEYWORDS = re.compile(r'nota\s+de\s+prensa|nota[-_ ]?prensa|press|comunicado|\.pdf(?:$|[?#])', re.I)

def fetch(url):
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=25) as res:
            data = res.read(6_000_000)
            return {'http': res.status, 'final_url': res.url, 'content_type': res.headers.get('Content-Type', ''), 'bytes': len(data)}, data
    except urllib.error.HTTPError as exc:
        return {'http': exc.code, 'final_url': exc.url, 'error': str(exc)}, b''
    except Exception as exc:
        return {'error': f'{type(exc).__name__}: {exc}'}, b''

def inspect(url, depth=0):
    meta, data = fetch(url)
    item = {'requested_url': url, **meta, 'links_candidates': [], 'sample': '', 'format': 'unknown'}
    if not data:
        return item
    is_pdf = data.startswith(b'%PDF-') or 'application/pdf' in meta.get('content_type', '').lower()
    if is_pdf:
        item['format'] = 'pdf'
        try:
            pdf = PdfReader(BytesIO(data))
            item['pages'] = len(pdf.pages)
            extracted = '\n'.join((p.extract_text() or '') for p in pdf.pages[:3])
            item['characters_extracted'] = len(extracted)
            item['sample'] = extracted[:3000]
            item['possible_prize_table'] = bool(re.search(r'categor[ií]as?|acertantes|premio', extracted, re.I))
        except Exception as exc:
            item['pdf_error'] = f'{type(exc).__name__}: {exc}'
    elif b'<html' in data[:3000].lower() or 'html' in meta.get('content_type', '').lower():
        item['format'] = 'html'
        soup = BeautifulSoup(data, 'html.parser')
        for a in soup.find_all('a', href=True):
            label = ' '.join(a.get_text(' ', strip=True).split())
            href = urllib.parse.urljoin(meta.get('final_url', url), a['href'])
            if KEYWORDS.search(label + ' ' + href) and href.startswith(('https://', 'http://')):
                item['links_candidates'].append({'text': label[:160], 'url': href})
        item['links_candidates'] = item['links_candidates'][:30]
        item['sample'] = ' '.join(soup.get_text(' ', strip=True).split())[:1200]
    else:
        item['format'] = 'other'
    return item

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--nota-url', default='', help='URL exacta de nota oficial obtenida desde SELAE; opcional')
    args = parser.parse_args()
    targets = PAGES[:]
    if args.nota_url:
        parsed = urllib.parse.urlparse(args.nota_url)
        if parsed.scheme != 'https' or parsed.hostname not in ('loteriasyapuestas.es', 'www.loteriasyapuestas.es'):
            parser.error('La URL manual debe ser HTTPS y pertenecer a loteriasyapuestas.es')
        targets.insert(0, args.nota_url)
    report = {'version': '0.85L-SELAE', 'utc': dt.datetime.now(dt.timezone.utc).isoformat(),
              'read_only': True, 'published': False, 'checks': []}
    seen = set()
    for url in targets:
        if url in seen: continue
        seen.add(url)
        result = inspect(url)
        report['checks'].append(result)
        print(f"{result['requested_url']}: HTTP={result.get('http','ERROR')} tipo={result['format']} candidatos={len(result['links_candidates'])}")
        # Probe at most three discovered official-site candidates to avoid broad crawling.
        for link in result['links_candidates'][:3]:
            candidate = link['url']
            host = urllib.parse.urlparse(candidate).hostname
            if candidate not in seen and host in ('loteriasyapuestas.es', 'www.loteriasyapuestas.es'):
                seen.add(candidate)
                child = inspect(candidate)
                report['checks'].append(child)
                print(f"  {candidate}: HTTP={child.get('http','ERROR')} tipo={child['format']}")
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    lines = ['LotoScan 0.85L - prueba SELAE (SOLO DIAGNOSTICO)', 'No se han modificado historicos ni boletos.', '']
    for item in report['checks']:
        lines.append(f"{item['requested_url']} | HTTP {item.get('http','ERROR')} | {item['format']} | PDF texto {item.get('characters_extracted','-')} | error {item.get('error', item.get('pdf_error','ninguno'))}")
    lines.append('Un acceso correcto a un documento NO demuestra cobertura de los diez juegos.')
    Path('informe_selae_085l.txt').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print('\n'.join(lines))

if __name__ == '__main__':
    main()
