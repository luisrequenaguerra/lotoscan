
#!/usr/bin/env python3
"""LotoScan 0.85K: contraste conservador, solo lectura. No publica premios."""
import datetime as dt
import json
import re
import urllib.request
from decimal import Decimal, InvalidOperation
from pathlib import Path
from bs4 import BeautifulSoup

DATES = ['2026-11-15', '2026-10-28', '2026-09-16']
GAMES = {
    'lototurf': {'dates': ['2026-11-15'], 'rtve': 'https://www.rtve.es/loterias/lototurf/', 'slug': 'lototurf'},
    'quintuple_plus': {'dates': ['2026-11-15'], 'rtve': 'https://www.rtve.es/loterias/quintuple-plus/', 'slug': 'quintuple-plus'},
    'quinigol': {'dates': ['2026-10-28', '2026-09-16'], 'rtve': 'https://www.rtve.es/loterias/quinigol/', 'slug': 'quinigol'},
}


def clean(s):
    return ' '.join(str(s).replace('\xa0', ' ').split())


def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; LotoScanAudit/0.85K)', 'Accept': 'text/html'})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read(3_000_000)
        charset = r.headers.get_content_charset() or 'utf-8'
        final = r.url
    return final, BeautifulSoup(raw.decode(charset, 'replace'), 'html.parser')


def count(s):
    s = clean(s)
    if re.search(r'sin\s+(ganadores|acertantes)', s, re.I):
        return 0
    if re.fullmatch(r'\d{1,3}(?:\.\d{3})*|\d+', s):
        return int(s.replace('.', ''))
    return None


def money(s):
    s = clean(s).replace('€', '').strip()
    if re.fullmatch(r'(?:\d{1,3}(?:\.\d{3})*|\d+),\d{2}', s):
        try:
            return str(Decimal(s.replace('.', '').replace(',', '.')).quantize(Decimal('0.01'))), 'dos_decimales'
        except InvalidOperation:
            pass
    if re.fullmatch(r'(?:\d{1,3}(?:\.\d{3})*|\d+)', s):
        return None, 'sin_decimales'
    return None, 'no_interpretable'


def cat(s):
    s = clean(s).lower()
    if s.startswith('especial'):
        return 'especial'
    if s.startswith('reintegro'):
        return 'reintegro'
    m = re.match(r'([1-9])\s*[ªº]', s)
    return m.group(1) if m else None


def tables(soup):
    root = soup.find('main') or soup
    result = []
    for table in root.find_all('table'):
        rows = []
        for tr in table.find_all('tr'):
            cells = [clean(td.get_text(' ', strip=True)) for td in tr.find_all(['th', 'td'], recursive=False)]
            if cells:
                rows.append(cells)
        parsed = []
        for row in rows:
            if not row:
                continue
            code = cat(row[0])
            if not code:
                continue
            # Some sources place 'Sin ganadores: bote' in one cell only.
            n = count(row[1]) if len(row) > 1 else None
            if n == 0 and len(row) == 2:
                amount, precision = None, 'sin_acertantes'
            else:
                amount, precision = money(row[2]) if len(row) > 2 else (None, 'sin_importe')
            parsed.append({'categoria': code, 'descripcion': row[0], 'acertantes': n,
                           'importe': amount, 'precision': precision, 'fila': row})
        if parsed:
            result.append(parsed)
    return result


def compare(dated, rtve_tables):
    # A matching prize fingerprint is evidence, but not proof that RTVE's table
    # belongs to the requested date. Never promote this to certified.
    matches = []
    for index, table in enumerate(rtve_tables):
        a = {p['categoria']: p for p in dated}
        b = {p['categoria']: p for p in table}
        if set(a) != set(b):
            continue
        if not all(a[k]['acertantes'] is not None and a[k]['acertantes'] == b[k]['acertantes'] for k in a):
            continue
        matches.append({'indice_tabla_rtve': index, 'categorias': len(a),
                        'coinciden_acertantes': True})
    return matches


def main():
    report = {'version': '0.85K', 'utc': dt.datetime.now(dt.timezone.utc).isoformat(),
              'solo_lectura': True, 'publicable': False, 'resultados': []}
    for game, cfg in GAMES.items():
        try:
            rtve_url, rtve_soup = get(cfg['rtve'])
            rtve = tables(rtve_soup)
            rtve_error = None
        except Exception as exc:
            rtve_url, rtve, rtve_error = None, [], f'{type(exc).__name__}: {exc}'
        for date in cfg['dates']:
            url = f"https://eldecimo.com/{cfg['slug']}/{date}/"
            item = {'juego': game, 'fecha': date, 'fuente_fechada': url,
                    'rtve_url': rtve_url, 'tablas_rtve': len(rtve),
                    'error_rtve': rtve_error, 'verificado': False, 'publicable': False}
            try:
                final, soup = get(url)
                item['url_final'] = final
                # Date in final URL is necessary but not sufficient for exact validation.
                item['fecha_en_url'] = date in final
                dated_tables = tables(soup)
                item['tablas_fuente_fechada'] = len(dated_tables)
                if not item['fecha_en_url'] or len(dated_tables) != 1:
                    item['estado'] = 'pendiente_fecha_o_tablas'
                    item['muestras'] = dated_tables[:2]
                else:
                    prizes = dated_tables[0]
                    item['premios'] = prizes
                    item['coincidencias_rtve_por_acertantes'] = compare(prizes, rtve)
                    item['estado'] = ('contraste_estructural_provisional' if len(item['coincidencias_rtve_por_acertantes']) == 1
                                      else 'pendiente_contraste')
                    item['advertencia'] = ('No se ha probado la fecha de la tabla RTVE ni contrastado los céntimos '
                                           'con otra fuente exacta; importes NO certificados.')
            except Exception as exc:
                item['estado'] = 'error_fuente'
                item['error'] = f'{type(exc).__name__}: {exc}'
            report['resultados'].append(item)
            print(game, date, item['estado'], 'RTVE', item['tablas_rtve'])
    Path('informe_premios_085k.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    lines = ['LotoScan 0.85K — contraste conservador (NO PUBLICABLE)', '']
    for item in report['resultados']:
        lines.append(f"{item['juego']} {item['fecha']}: {item['estado']}; tablas RTVE={item['tablas_rtve']}; "
                     f"coincidencias={len(item.get('coincidencias_rtve_por_acertantes', []))}; "
                     f"error={item.get('error', item.get('error_rtve') or 'ninguno')}")
    lines.append('Ningún importe certificado ni publicado; revisar el JSON antes de integrar.')
    Path('informe_premios_085k.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
