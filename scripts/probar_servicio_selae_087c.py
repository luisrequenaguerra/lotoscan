#!/usr/bin/env python3
"""LotoScan 0.87C: diagnostico de los HTML oficiales para medios de SELAE.
Solo lectura; no publica resultados ni modifica historico.json.
"""
import argparse
import datetime as dt
import hashlib
import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = 'https://www.loteriasyapuestas.es/f/loterias/resultados/'
# Fechas historicas conocidas, solo para diagnostico de acceso y contenido.
JUEGOS = [
    ('euromillones', 'EMIL', 'euromillones.html', '20261117'),
    ('primitiva', 'LAPR', 'primitiva.html', '20261116'),
    ('bonoloto', 'BONO', 'bonoloto.html', '20261117'),
    ('gordo-primitiva', 'ELGR', 'gordo.html', '20261115'),
    ('eurodreams', 'EDMS', 'eurodreams.html', '20261116'),
    ('loteria-nacional', 'LNAC', 'lnac.html', '20261114'),
    ('quiniela', 'LAQU', 'quiniela.html', '20261115'),
    ('quinigol', 'QGOL', 'quinigol.html', '20261117'),
    ('lototurf', 'LOTU', 'lototurf.html', '20261115'),
    ('quintuple-plus', 'QUPL', 'quintuple.html', '20261115'),
]


def pedir(url, timeout=16):
    request = urllib.request.Request(url, headers={
        'User-Agent': 'LotoScan/0.87C (+diagnostico de acceso a resultados publicos)',
        'Accept': 'text/html,application/xhtml+xml;q=0.9,*/*;q=0.7',
        'Accept-Language': 'es-ES,es;q=0.9',
    })
    result = {'url': url, 'estado': None, 'url_final': None, 'content_type': None,
              'bytes': 0, 'sha256': None, 'titulo': None, 'fecha_visible': False,
              'indicadores': [], 'muestra_texto': '', 'error': None}
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result['estado'] = response.status
            result['url_final'] = response.geturl()
            result['content_type'] = response.headers.get('Content-Type', '')
            raw = response.read(1_000_001)
            result['truncado'] = len(raw) > 1_000_000
            raw = raw[:1_000_000]
            result['bytes'] = len(raw)
            result['sha256'] = hashlib.sha256(raw).hexdigest()
            charset = response.headers.get_content_charset() or 'utf-8'
            page = raw.decode(charset, errors='replace')
            title = re.search(r'<title[^>]*>(.*?)</title>', page, re.I | re.S)
            if title:
                result['titulo'] = html.unescape(re.sub(r'\s+', ' ', title.group(1))).strip()
            cleaned = html.unescape(re.sub(r'<[^>]+>', ' ', re.sub(r'<(script|style)\b[^>]*>.*?</\1>', ' ', page, flags=re.I | re.S)))
            cleaned = re.sub(r'\s+', ' ', cleaned).strip()
            result['muestra_texto'] = cleaned[:550]
            markers = ('resultado', 'premio', 'sorteo', 'reintegro', 'pleno al 15', 'combinacion', 'combinación', 'acertantes')
            result['indicadores'] = [m for m in markers if m in cleaned.lower()]
            result['contenido_textual_caracteres'] = len(cleaned)
            result['posible_pagina_vacia'] = len(cleaned) < 120
    except urllib.error.HTTPError as exc:
        result['estado'] = exc.code
        result['url_final'] = exc.geturl()
        result['content_type'] = exc.headers.get('Content-Type', '')
        result['error'] = f'HTTP {exc.code} {exc.reason}'
    except Exception as exc:
        result['error'] = f'{type(exc).__name__}: {str(exc)[:250]}'
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fecha', help='AAAAMMDD para probar en todos los juegos; omitir para fechas historicas conocidas')
    parser.add_argument('--espera', type=float, default=0.5, help='Pausa entre peticiones, segundos')
    args = parser.parse_args()
    if args.fecha:
        try:
            dt.datetime.strptime(args.fecha, '%Y%m%d')
        except ValueError:
            parser.error('--fecha debe ser AAAAMMDD valido')
    out = Path('diagnostico_selae_087c')
    out.mkdir(exist_ok=True)
    entries = []
    for nombre, codigo, archivo, fecha_ref in JUEGOS:
        for variante, fecha in [('sin_fecha', None), ('con_fecha', args.fecha or fecha_ref)]:
            params = {'game_id': codigo}
            if fecha:
                params['fecha_sorteo'] = fecha
            url = BASE + archivo + '?' + urllib.parse.urlencode(params)
            response = pedir(url)
            response.update(juego=nombre, codigo=codigo, variante=variante, fecha_solicitada=fecha)
            entries.append(response)
            print(f'{nombre:19s} {variante:10s} HTTP {response["estado"]} bytes={response["bytes"]} error={response["error"] or "-"}', flush=True)
            time.sleep(max(0, min(args.espera, 3)))
    # Un 200 y una pagina titulada no prueban que existan datos de resultados.
    validos_http = sum(x['estado'] == 200 for x in entries)
    informe = {
        'version': '0.87C', 'origen': 'Servicio de resultados para medios de SELAE',
        'momento_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'solicitudes': len(entries), 'http_200': validos_http,
        'http_403': sum(x['estado'] == 403 for x in entries),
        'juegos': len(JUEGOS), 'publicable': False,
        'interpretacion': 'Diagnostico de accesibilidad y contenido. No valida combinaciones ni premios.',
        'resultados': entries,
    }
    (out / 'informe_087c.json').write_text(json.dumps(informe, indent=2, ensure_ascii=False), encoding='utf-8')
    lines = [f'LotoScan 0.87C | {len(entries)} solicitudes | HTTP 200: {validos_http}',
             'AVISO: HTTP 200 no significa resultados extraidos ni validados.', '']
    for x in entries:
        lines.append(f'{x["juego"]} [{x["variante"]}] HTTP {x["estado"]} {x["bytes"]} bytes | titulo={x["titulo"]!r} | error={x["error"]}')
        lines.append(f'  URL: {x["url"]}')
        lines.append(f'  Texto: {x["muestra_texto"][:220]}')
    (out / 'informe_087c.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f'Informe guardado en {out}/. No se ha modificado historico.json.')
    # El workflow debe subir el artefacto incluso cuando todos los accesos fallen.
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
