#!/usr/bin/env python3
"""Auditoria pasiva de JavaScript publico SELAE. No comprueba premios ni modifica datos."""
import datetime as dt
import hashlib
import json
import re
import urllib.request
import urllib.error
from pathlib import Path
from urllib.parse import urljoin, urlparse

OUT = Path('informes/087v')
OUT.mkdir(parents=True, exist_ok=True)
BASE = 'https://www.loteriasyapuestas.es'
PAGES = [BASE + '/es/loteria-nacional/tablas-y-alambres', BASE + '/f/loterias/resultados/lnac.html?game_id=LNAC&fecha_sorteo=20261114']
JS = [BASE + '/f/loterias/estaticos/js/utils-json-lnac.js']
PAT = re.compile(r'(?i)extracci[oó]n|terminaci[oó]n|alambre|centena|premioDecimo|fecha2|servicios/|LNAC|\.json\b|ajax\s*\(|fetch\s*\(|jsonp')
URLPAT = re.compile(r'''(?:(?:https?:)?//[^\s"'<>\\]{5,220}|/[\w./?=&%+-]{5,220})''')


def allowed(url):
    p = urlparse(url)
    return p.scheme == 'https' and p.hostname in {'www.loteriasyapuestas.es', 'cds.loteriasyapuestas.es'}


def fetch(url):
    info = {'url': url, 'status': None, 'bytes': 0, 'error': None, 'sha256': None}
    if not allowed(url):
        info['error'] = 'dominio_no_permitido'
        return info, ''
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; LotoScanResearch/0.87V)', 'Accept': 'text/javascript,text/html,application/json,*/*'})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read(1_500_001)
            info['status'] = resp.status
            info['content_type'] = resp.headers.get('Content-Type', '')
            info['truncado'] = len(raw) > 1_500_000
            raw = raw[:1_500_000]
    except urllib.error.HTTPError as e:
        info['status'] = e.code
        raw = e.read(4096)
    except Exception as e:
        raw = b''
        info['error'] = f'{type(e).__name__}: {e}'[:250]
    info['bytes'] = len(raw)
    if raw:
        info['sha256'] = hashlib.sha256(raw).hexdigest()
    return info, raw.decode('utf-8', errors='replace')


def snippets(source, max_count=80):
    lines = source.splitlines()
    matches = []
    for n, line in enumerate(lines, 1):
        if PAT.search(line):
            for fragment in re.findall(r'.{0,140}(?:extracci[oó]n|terminaci[oó]n|alambre|centena|premioDecimo|fecha2|servicios/|LNAC|\.json\b|ajax\s*\(|fetch\s*\(|jsonp).{0,180}', line, re.I):
                matches.append({'linea': n, 'fragmento': fragment[:360]})
                if len(matches) >= max_count:
                    return matches
    return matches


def main():
    report = {'version': '0.87V', 'fecha_utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'objetivo': 'Inspeccionar referencias JavaScript oficiales de LNAC sin inferir endpoints', 'recursos': [], 'endpoints_confirmados_con_extracciones': [], 'premios_publicados': 0, 'historico_modificado': False}
    pages = {}
    for url in PAGES:
        info, body = fetch(url)
        info['tipo'] = 'pagina'
        if info['status'] == 200:
            scripts = re.findall(r'<script\b[^>]*\bsrc\s*=\s*["\']([^"\']+)', body, re.I)
            info['scripts'] = [urljoin(url, s) for s in scripts if allowed(urljoin(url, s))]
            info['fragmentos_relevantes'] = snippets(body, 35)
            pages[url] = body
            (OUT / ('pagina_tablas_fragmentos.txt' if 'tablas-y-alambres' in url else 'pagina_terceros_fragmentos.txt')).write_text('\n'.join(str(x) for x in info['fragmentos_relevantes']), encoding='utf-8')
        report['recursos'].append(info)
    # Only inspect the identified first-party LNAC JS and page scripts with LNAC in filename.
    for body in pages.values():
        for src in re.findall(r'<script\b[^>]*\bsrc\s*=\s*["\']([^"\']+)', body, re.I):
            u = urljoin(BASE, src)
            if allowed(u) and ('lnac' in u.lower() or 'nacional' in u.lower()) and u not in JS:
                JS.append(u)
    for i, url in enumerate(JS[:8]):
        info, body = fetch(url)
        info['tipo'] = 'javascript'
        if info['status'] == 200:
            info['fragmentos_relevantes'] = snippets(body, 100)
            info['referencias_url'] = list(dict.fromkeys(URLPAT.findall(body)))[:100]
            (OUT / f'javascript_{i+1}_fragmentos.txt').write_text('\n'.join(f"L{x['linea']}: {x['fragmento']}" for x in info['fragmentos_relevantes']), encoding='utf-8')
            # Save source of relevant small script for reproducibility; never execute it.
            if len(body) <= 350_000:
                (OUT / f'javascript_{i+1}_fuente.js').write_text(body, encoding='utf-8')
        report['recursos'].append(info)
    report['conclusion'] = 'Auditoria de referencias; ninguna ruta se considera fuente completa sin respuesta real con numeros de extracciones.'
    (OUT / 'informe_js_lnac_087v.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print('0.87V: recursos consultados:', len(report['recursos']))
    for r in report['recursos']:
        print(r['tipo'], r['status'], r['bytes'], r['url'], 'coincidencias', len(r.get('fragmentos_relevantes', [])))
    print('Informe:', OUT / 'informe_js_lnac_087v.json')

if __name__ == '__main__':
    main()
