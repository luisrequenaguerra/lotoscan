#!/usr/bin/env python3
"""Read-only RTVE extraction probe; NEVER writes the LotoScan historical database."""
import datetime as dt
import json
import re
import urllib.request
from pathlib import Path
from bs4 import BeautifulSoup

PAGES = {
    'lototurf': 'https://www.rtve.es/loterias/lototurf/',
    'quinigol': 'https://www.rtve.es/loterias/quinigol/',
    'quintuple_plus': 'https://www.rtve.es/loterias/quintuple-plus/',
}
HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; LotoScanSourceProbe/0.85C)', 'Accept': 'text/html'}
OUT = Path('informe_rtve_085c.json')

def clean(s):
    return ' '.join(s.split())

def probe(game, url):
    result = {'juego': game, 'url': url, 'validado': False, 'solo_diagnostico': True}
    try:
        request = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(request, timeout=25) as response:
            result['http'] = response.status
            result['url_final'] = response.url
            raw = response.read(1_500_000)
            charset = response.headers.get_content_charset() or 'utf-8'
        soup = BeautifulSoup(raw.decode(charset, errors='replace'), 'html.parser')
        for el in soup(['script', 'style', 'noscript', 'nav', 'footer']): el.decompose()
        main = soup.find('main') or soup
        text = clean(main.get_text(' ', strip=True))
        result['texto_inicio'] = text[:5500]
        result['fechas_visibles'] = list(dict.fromkeys(re.findall(r'\b\d{1,2}\s+(?:ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)\s+20\d{2}\b', text, re.I)))[:8]
        result['tablas'] = []
        for table in main.find_all('table')[:12]:
            rows = []
            for tr in table.find_all('tr')[:30]:
                cells = [clean(td.get_text(' ', strip=True)) for td in tr.find_all(['th', 'td'], recursive=False)]
                if cells: rows.append(cells)
            if rows: result['tablas'].append(rows)
        # Some RTVE pages use CSS grids rather than HTML tables.
        for phrase in ('Categoría premio', 'N. acertantes', 'Cuantías', 'Recaudación', 'Premios:'):
            match = re.search(re.escape(phrase), text, re.I)
            if match:
                result.setdefault('fragmentos_premios', {})[phrase] = text[max(0,match.start()-80):match.start()+1400]
        result['indicios'] = {
            'tiene_fecha': bool(result['fechas_visibles']),
            'tiene_tablas_html': bool(result['tablas']),
            'menciona_acertantes': bool(re.search('acertantes?', text, re.I)),
            'menciona_cuantias': bool(re.search('cuant[ií]as', text, re.I)),
            'tiene_euros': bool(re.search(r'\d[\d.,]*\s*€', text)),
        }
        result['observacion'] = 'Requiere verificar manualmente fecha, combinación y cada categoría antes de publicar.'
    except Exception as exc:
        result['error'] = f'{type(exc).__name__}: {exc}'
    return result

def main():
    report = {
        'version': '0.85C', 'generado_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'objetivo': 'Extraer muestras estructurales de resultados y premios RTVE',
        'advertencia': 'No verifica premios, no actualiza historico.json, no publica datos.',
        'juegos': {game: probe(game, url) for game, url in PAGES.items()},
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    lines = ['LotoScan 0.85C - Diagnóstico RTVE', 'NO PUBLICABLE / NO MODIFICA HISTÓRICO', '']
    for game, item in report['juegos'].items():
        lines.extend([f'{game}: HTTP {item.get("http", "ERROR")}',
                      f'  fechas: {item.get("fechas_visibles", [])}',
                      f'  tablas: {len(item.get("tablas", []))}',
                      f'  indicadores: {item.get("indicios", {})}',
                      f'  error: {item.get("error", "ninguno")}', ''])
    Path('informe_rtve_085c.txt').write_text('\n'.join(lines), encoding='utf-8')
    print('\n'.join(lines))

if __name__ == '__main__':
    main()
