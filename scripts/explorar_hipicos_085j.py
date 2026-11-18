
#!/usr/bin/env python3
"""LotoScan 0.85J: discovery of independent horse-lottery prize sources.
Read-only. Never modifies the app or historical results; never certifies prizes.
"""
import datetime as dt
import json
import re
import urllib.error
import urllib.request
from pathlib import Path
from bs4 import BeautifulSoup

DATE = '2026-11-15'
SOURCES = {
    'lototurf': {
        'rtve': 'https://www.rtve.es/loterias/lototurf/',
        'elpais': 'https://servicios.elpais.com/sorteos/lototurf/',
        'eldecimo': 'https://eldecimo.com/lototurf/2026-11-15/',
        '6aciertos': 'https://www.6aciertos.com/lototurf/',
    },
    'quintuple_plus': {
        'rtve': 'https://www.rtve.es/loterias/quintuple-plus/',
        'elpais': 'https://servicios.elpais.com/sorteos/quintuple-plus/',
        'eldecimo': 'https://eldecimo.com/quintuple-plus/2026-11-15/',
        '6aciertos': 'https://www.6aciertos.com/quintuple-plus/',
    },
}
MONEY = re.compile(r'(?<!\d)(?:\d{1,3}(?:\.\d{3})*|\d+),\d{2}\s*€?')
DATE_FORMS = ['2026-11-15', '15/11/2026', '15-11-2026', '15 de noviembre de 2026', '15 NOV 2026']


def compact(value):
    return ' '.join(value.split())


def inspect(game, name, url):
    result = {'juego': game, 'fuente': name, 'url': url,
              'fecha_objetivo': DATE, 'certificado': False, 'publicable': False}
    try:
        request = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; LotoScanResearch/0.85J)',
            'Accept': 'text/html'})
        with urllib.request.urlopen(request, timeout=25) as response:
            raw = response.read(2_000_000)
            result['http'] = response.status
            result['url_final'] = response.url
            charset = response.headers.get_content_charset() or 'utf-8'
        soup = BeautifulSoup(raw.decode(charset, 'replace'), 'html.parser')
        result['titulo'] = compact(soup.title.get_text(' ', strip=True)) if soup.title else ''
        for tag in soup(['script', 'style', 'noscript', 'nav', 'footer']):
            tag.decompose()
        root = soup.find('main') or soup
        text = compact(root.get_text(' ', strip=True))
        result['fecha_visible'] = any(f.lower() in text.lower() for f in DATE_FORMS)
        result['fecha_en_url_final'] = DATE in result['url_final']
        result['muestras_importes'] = MONEY.findall(text)[:25]
        result['tablas_candidatas'] = []
        for table in root.find_all('table'):
            rows = []
            for tr in table.find_all('tr'):
                cells = [compact(c.get_text(' ', strip=True))
                         for c in tr.find_all(['td', 'th'], recursive=False)]
                if cells:
                    rows.append(cells)
            if rows and re.search(r'categor|premio|acertant|ganador|importe|cuant',
                                  ' '.join(' '.join(r) for r in rows[:2]), re.I):
                result['tablas_candidatas'].append(rows[:14])
        result['total_tablas_candidatas'] = len(result['tablas_candidatas'])
        result['tablas_candidatas'] = result['tablas_candidatas'][:3]
        result['fragmentos_fecha'] = []
        for form in DATE_FORMS:
            match = re.search(re.escape(form), text, re.I)
            if match:
                result['fragmentos_fecha'].append(text[max(0, match.start()-120):match.end()+650])
        result['observacion'] = ('Solo se registra evidencia visible; HTTP 200, fechas y '
                                 'cantidades aisladas NO prueban que una tabla pertenezca '
                                 'al sorteo ni que los centimos sean exactos.')
    except Exception as exc:
        result['error'] = f'{type(exc).__name__}: {exc}'
    return result


def main():
    report = {'version': '0.85J', 'generado_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
              'modo': 'diagnostico_solo_lectura', 'publicable': False, 'resultados': []}
    for game, sources in SOURCES.items():
        for name, url in sources.items():
            item = inspect(game, name, url)
            report['resultados'].append(item)
            print(game, name, item.get('http', 'ERROR'),
                  item.get('total_tablas_candidatas', 0), item.get('error', ''))
    Path('informe_hipicos_085j.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    lines = ['LotoScan 0.85J - fuentes hipicas, SOLO DIAGNOSTICO',
             'Ningun importe certificado. No se modifica historico.json.', '']
    for item in report['resultados']:
        lines.append(f"{item['juego']} / {item['fuente']}: HTTP={item.get('http', 'ERROR')} "
                     f"tablas={item.get('total_tablas_candidatas', 0)} "
                     f"fecha_visible={item.get('fecha_visible', False)} "
                     f"fecha_url={item.get('fecha_en_url_final', False)} "
                     f"error={item.get('error', 'ninguno')}")
    Path('informe_hipicos_085j.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
