#!/usr/bin/env python3
"""0.87U: audita fuentes públicas SELAE para dos sorteos ordinarios LNAC.
Solo GET, sin navegador, sin proveedores externos, sin publicar premios.
"""
import datetime as dt
import html
import json
import re
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

OUT = Path('informes/087u')
OUT.mkdir(parents=True, exist_ok=True)
BASE = 'https://www.loteriasyapuestas.es'
FECHAS = [('jueves', '20261112'), ('sabado', '20261114')]
HEADERS = {'User-Agent': 'LotoScan/0.87U (auditoria publica de resultados)', 'Accept': 'application/json,text/html,*/*;q=0.5'}
PATRON = re.compile(r'(?i)extracci[oó]n|terminaci[oó]n|alambre|centena|reintegro|premio|LNAC')


def fetch(url):
    assert urlparse(url).hostname == 'www.loteriasyapuestas.es'
    req = urllib.request.Request(url, headers=HEADERS)
    result = {'url': url, 'http': None, 'content_type': None, 'bytes': 0, 'error': None}
    raw = b''
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            result['http'] = resp.status
            result['content_type'] = resp.headers.get('Content-Type', '').split(';')[0]
            raw = resp.read(2_000_001)
    except urllib.error.HTTPError as e:
        result['http'] = e.code
        result['content_type'] = e.headers.get('Content-Type', '').split(';')[0]
        raw = e.read(8192)
    except Exception as e:
        result['error'] = f'{type(e).__name__}: {e}'[:240]
    result['bytes'] = len(raw)
    result['truncado'] = len(raw) > 2_000_000
    return result, raw[:2_000_000]


def inspect_json(data):
    report = {'json_valido': True, 'campos_candidatos': [], 'numeros_extraccion_observados': 0}
    seen = set()
    def walk(x, path='', depth=0):
        if depth > 9 or len(seen) > 250:
            return
        if isinstance(x, dict):
            for k, v in x.items():
                key = str(k)
                loc = f'{path}.{key}' if path else key
                if PATRON.search(key) and loc not in seen:
                    seen.add(loc)
                    report['campos_candidatos'].append({'ruta': loc, 'tipo': type(v).__name__, 'elementos': len(v) if isinstance(v, (list, dict)) else None})
                walk(v, loc, depth + 1)
        elif isinstance(x, list):
            for i, v in enumerate(x[:30]):
                walk(v, f'{path}[{i}]', depth + 1)
    walk(data)
    return report


def inspect_html(body):
    s = body.decode('utf-8', 'replace')
    scripts = re.findall(r'<script[^>]+src=["\']([^"\']+)', s, flags=re.I)
    data_blocks = re.findall(r'<script[^>]*type=["\']application/(?:ld\+)?json["\'][^>]*>(.*?)</script>', s, flags=re.I|re.S)
    candidates = []
    for match in re.finditer(r'(?i).{0,65}(?:extracciones|alambres|terminaciones|/servicios/|\.json|LNAC).{0,90}', s):
        snippet = html.unescape(match.group(0)).strip()
        if snippet not in candidates:
            candidates.append(snippet[:170])
        if len(candidates) >= 30:
            break
    return {'html_analizado': True, 'scripts_encontrados': scripts[:40], 'bloques_json_incrustados': len(data_blocks), 'referencias_candidatas': candidates}


def main():
    consultas = []
    for dia, fecha in FECHAS:
        urls = [
            ('json_oficial_fecha2', f'{BASE}/servicios/fecha2?game_id=LNAC&fecha_sorteo={fecha}'),
            ('html_terceros', f'{BASE}/f/loterias/resultados/lnac.html?game_id=LNAC&fecha_sorteo={fecha}'),
        ]
        for fuente, url in urls:
            r, raw = fetch(url)
            r.update(dia=dia, fecha=fecha, fuente=fuente)
            if r['http'] == 200:
                try:
                    obj = json.loads(raw.decode('utf-8-sig'))
                    r.update(inspect_json(obj))
                    r['numero_registros'] = len(obj) if isinstance(obj, list) else 1
                    if fuente == 'json_oficial_fecha2':
                        (OUT / f'lnac_{dia}_fecha2.json').write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')
                except (ValueError, UnicodeDecodeError):
                    if b'<html' in raw[:2000].lower() or b'<!doctype' in raw[:2000].lower():
                        r.update(inspect_html(raw))
                    else:
                        r['formato_no_identificado'] = True
            consultas.append(r)
            print(f'{dia:7} {fuente:20} HTTP={r["http"]} bytes={r["bytes"]}')
    # Consulta una sola vez la página oficial de tablas, para comprobar si ofrece HTML estructurado.
    r, raw = fetch(f'{BASE}/es/loteria-nacional/tablas-y-alambres')
    r.update(dia='ambos', fecha=None, fuente='tablas_y_alambres')
    if r['http'] == 200:
        r.update(inspect_html(raw))
    consultas.append(r)
    report = {'version': '0.87U', 'fecha_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
              'objetivo': 'Comparar fuentes estructuradas oficiales para jueves y sabado de Loteria Nacional',
              'consultas': consultas,
              'extracciones_completas_confirmadas': False,
              'nota': 'La presencia de claves o texto no demuestra que se hayan obtenido todas las extracciones; se requiere cotejo independiente.',
              'historico_modificado': False, 'publicables': 0}
    (OUT/'informe_nacional_087u.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    lines = ['LotoScan 0.87U — jueves y sábado, SELAE', 'No se certifican extracciones completas automáticamente.', '']
    for x in consultas:
        lines.append(f'{x["dia"]}: {x["fuente"]}: HTTP {x["http"]}; bytes={x["bytes"]}; JSON={x.get("json_valido", False)}; campos candidatos={len(x.get("campos_candidatos", []))}; error={x["error"]}')
    lines.extend(['', 'Los HTTP 403 indican bloqueo de acceso desde GitHub, no ausencia de datos.', 'Histórico sin cambios. Publicación bloqueada.'])
    (OUT/'resumen_087u.txt').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print('\n'.join(lines))

if __name__ == '__main__':
    main()
