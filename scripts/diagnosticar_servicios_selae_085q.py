
#!/usr/bin/env python3
"""LotoScan 0.85Q: locate official result loaders, without publishing data."""
import datetime as dt
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path
from bs4 import BeautifulSoup

BASE = 'https://www.loteriasyapuestas.es'
HOSTS = {'www.loteriasyapuestas.es', 'loteriasyapuestas.es'}
GAMES = ['gordo-primitiva', 'quiniela', 'bonoloto', 'euromillones',
         'primitiva', 'eurodreams', 'loteria-nacional', 'quinigol',
         'lototurf', 'quintuple-plus']
KEY = re.compile(r'nota.{0,30}prensa|\.pdf\b|drawId|resultado|historico|/servicios/|ajax|\.load\(|\.getJSON\(|fetch\(|reparto|premio', re.I)
PATH = re.compile(r'''["']([^"'\n]{4,240}(?:resultad|sorteo|draw|prensa|servicio|\.pdf)[^"'\n]{0,120})["']''', re.I)
HEADERS = {'User-Agent': 'Mozilla/5.0 (LotoScan/0.85Q research)', 'Accept': 'text/html,application/javascript,*/*'}

def download(url, limit=3_000_000):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname not in HOSTS:
        raise ValueError('Only official SELAE HTTPS URLs are allowed')
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=25) as response:
        final = response.url
        if urllib.parse.urlsplit(final).hostname not in HOSTS:
            raise ValueError('Redirect outside SELAE')
        data = response.read(limit + 1)
        if len(data) > limit:
            raise ValueError('Response too large')
        return {'http': response.status, 'final_url': final, 'bytes': len(data)}, data.decode('utf-8', 'replace')

def evidence(text, max_items=35):
    found = []
    for match in KEY.finditer(text):
        snippet = ' '.join(text[max(0, match.start()-180):match.end()+230].split())[:450]
        if snippet not in found:
            found.append(snippet)
        if len(found) >= max_items:
            break
    return found

def main():
    report = {'version':'0.85Q', 'utc':dt.datetime.now(dt.timezone.utc).isoformat(),
              'read_only':True, 'publishable':False, 'pages':[], 'scripts':[]}
    js_refs = {}
    for game in GAMES:
        url = BASE + '/es/resultados/' + game
        page = {'game':game, 'url':url}
        try:
            meta, html = download(url)
            page.update(meta)
            soup = BeautifulSoup(html, 'html.parser')
            page['html_evidence'] = evidence(html, 18)
            page['inline_evidence'] = []
            for tag in soup.find_all('script'):
                src = tag.get('src')
                if src:
                    absolute = urllib.parse.urljoin(meta['final_url'], src)
                    if urllib.parse.urlsplit(absolute).hostname in HOSTS:
                        js_refs.setdefault(absolute, set()).add(game)
                else:
                    page['inline_evidence'].extend(evidence(tag.get_text() or '', 8))
            page['inline_evidence'] = page['inline_evidence'][:25]
            page['script_count'] = len(soup.find_all('script', src=True))
            page['html_paths'] = list(dict.fromkeys(PATH.findall(html)))[:35]
        except Exception as exc:
            page['error'] = f'{type(exc).__name__}: {exc}'
        report['pages'].append(page)
        print(game, page.get('http', 'ERROR'), page.get('script_count', 0))

    # Inspect every unique first-party JS script (not just the first eight).
    # Prioritize result-specific scripts, then inspect the remainder up to a bounded cap.
    ranked = sorted(js_refs, key=lambda u: (0 if re.search(r'result|sorte|quiniel|gordo|histor|ajax',u,re.I) else 1, u))
    for url in ranked[:70]:
        entry = {'url':url, 'games':sorted(js_refs[url])}
        try:
            meta, code = download(url)
            entry.update(meta)
            entry['evidence'] = evidence(code, 45)
            entry['path_candidates'] = list(dict.fromkeys(PATH.findall(code)))[:70]
        except Exception as exc:
            entry['error'] = f'{type(exc).__name__}: {exc}'
        report['scripts'].append(entry)
        print('JS', entry.get('http','ERROR'), url)
    report['total_unique_scripts'] = len(js_refs)
    report['inspected_scripts'] = len(report['scripts'])
    Path('informe_selae_085q.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    lines = ['LotoScan 0.85Q - servicios de resultados SELAE (SOLO DIAGNOSTICO)',
             'No se consultan endpoints inferidos ni se modifica historico.json.', '']
    for page in report['pages']:
        lines.append(f"{page['game']}: HTTP={page.get('http','ERROR')}, scripts={page.get('script_count',0)}, inline={len(page.get('inline_evidence',[]))}, error={page.get('error','-')}")
    lines.append(f"Scripts unicos: {len(js_refs)}; inspeccionados: {len(report['scripts'])}")
    for entry in report['scripts']:
        if entry.get('evidence') or entry.get('path_candidates'):
            lines.append(f"{entry['url']}: HTTP={entry.get('http','ERROR')}, evidencias={len(entry.get('evidence',[]))}, rutas={len(entry.get('path_candidates',[]))}")
            for candidate in entry.get('path_candidates', [])[:5]:
                lines.append('  posible ruta: ' + candidate[:180])
    lines.append('Las rutas son candidatas; no se ha verificado una API de notas de prensa.')
    Path('informe_selae_085q.txt').write_text('\n'.join(lines)+'\n', encoding='utf-8')

if __name__ == '__main__':
    main()

