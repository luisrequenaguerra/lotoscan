#!/usr/bin/env python3
"""LotoScan 0.87P: motor aislado de El Millón y Joker, pruebas históricas.
No comprueba titularidad, autenticidad ni derecho al cobro; no publica datos.
"""
import argparse
import base64
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re
import zlib

ROOT = Path(__file__).resolve().parents[1]
HISTORY = ROOT / 'datos/selae_provisional/historico_provisional.json'
OUT = ROOT / 'informe_especiales_087p.json'
# Muestras oficiales de 17/11/2026 (EMIL) y 16/11/2026 (LAPR),
# capturadas en LotoScan 0.87E. Se generan en el paquete de distribución.
FIXTURES = {'EMIL': {'sha256': 'a85c6f235ffc81439b520ff1eccb56f976d394704026666b0fadce22fb62019e', 'payload': 'eNqNlkuP0zAQgP9K1Cup8PiRR28rWARSFyEOXBZUuYlbLDl2lccitNr/zjjpK2ma0ENSj2fm88zEHj+/LnYq+y03lStr5RarBSU0WgIsIQ4orCBaEbIIF7lGFVVIK1GlkKhboVTnFztgNEkJJSnFib0s1EbnKH58+rJGgbR/T85xdChVod1m62rlhRFpfziR5dnJlTc6NKqqZYUixlkqCEdhqTLZ5DLTzqI8FlGUkqQv36imdAfll8oE55yBN8xcsdX2ZBgwESwDFvtHgg8e+Yf/R8A/6HmZLT5OGBfey87Z/LxyiM8rV1VWNrW2GsN8fl3U+tAm5WdDiJRB9xPd6133uhBQkbRJszJ3paqGY4znKCoag56NzvzEYmUbY97CM41O0OCaBoJDQsM4nqeyWSqboJJrKoWIQkjYPFTMQnkPyu8nFuKYhpQOmOKWCeksVExA+/lNSUiHyY1hJLvtdpimRj0qux9qgtBoAKV0hJpAPEuNJ2LtVVXQML2B0hFoG/80NOlB6f1QKQlhWFMa8bGyAhfz4HQix/3KRiEMc8x4Eo+ARdqeV9NgIBPkXp4B96sYkBPgI5lmsYD5HQT9swnuJzsN2bDCwNKI35IjiNl/kOlEmXvZjm93keCEs1syFUCi+bMK2AS6l24epnwYNE0oHTutUgH8Xql/oVgb43vOa9sW2664fnj60vYs0/VPbKSycplGw1P/A+haab9tff669me3p+ni4G0XK+iaEPbLrNYvrYPWztbK6txV35VpzdF55VdhXa0RVR0bVd0Yd1JB229tBoKHpnaFREWHvjqlDyePF61HEzxhdD6pO2aDXAWP2Hq7gFWFYxPgPQLF1r1oVWxL5QfHW0BTmmuX74/t9vheKrPsHC1ztVRXbnFs8HrixWe3ftC69QlXFqPxJXvGwaGxtas+qh/K1rIT5S5rCuXF3VgXcq/s2aBUe7SR1Se8UjSodp6QeyxEtdbbshO9vV33/c2pzpf2309P/3OC6719vka4Mld4f7m6TGAxfUzGNC9adh9Vj9qfKP5sMlmrvSvxwobzWGczOrfDUK5nRr/df7Q6+zY='}, 'LAPR': {'sha256': 'bc8e11bca0b51be9af39055a266712c48d64afe83468780435765525a02ec614', 'payload': 'eNqVk92O2jAQRl/FytWiBmn8G4e71ao3VaVW3NIV8iZm65bEyAmVKrTv3gkQ1glkVZCwxDg+Zzz5WB2SjS1+mnXjQ2t9skgYMDWndE4VYXQh2AIgSZPS4SO2MrXBR7b72jZYdOX7McqZ1iAo17jxaiq7diWWvz5+X2LB1H97Nv7aBVs5v37xre1OUg7dBzeKsuhR3aHd3jatabCkaJ4xnWMx2MLsS1M4Xw/qha9eXN3XQZM5gRwXmuHCBS6Cd4smTw8sn5HlA8wurXQKLkBL6LwbX5fv3QHnIFRX/+V/25AsDsfrnW/35duxp+1pDjgQ0/jCmfIyEgqnkQz7U4IrnnOsd5r1mUyPcwC8edG6P0dE8pYmtinCvnW1w8rqkLRu1219bnYWTVvyoMhj4WxofUM+keWMdDbT2lcfHL4t2l/yeJmcSQE0ZeL4lmpsNNjmLLqg6Y89gDExeUxlETXjPBN5muuPmKxnyrjbpzGXx91SnWuVig+5/Jo7ZoqIyYSkKfARERMUIUWPFJNIGSGlTkGNgFIoGSNlj+STSBUhr24MkMGgx6V1NR4NfgjJ4vGNe2IKOM7uOU5UH73V9ctvfWkassVv4TbBNLMhDwa56v/BPpS2XseJnYiBIrvgKotc4klX3Jht66r/tt12sYlo3OUSI9dtFZ+IzF2qLM47n1KJiSjdqYpnKCdUg9SqXsXuVGkZp1neVqlYlfWqs2joOWmuLZqN8n5Dk2Hi357/AUYoFx8='}}


def money(value):
    if value is None or isinstance(value, bool):
        raise ValueError('importe ausente')
    s = str(value).strip().replace(' ', '').replace('\u00a0', '')
    if ',' in s:
        s = s.replace('.', '').replace(',', '.')
    try:
        n = Decimal(s)
    except InvalidOperation as exc:
        raise ValueError('importe ilegible') from exc
    if not n.is_finite() or n < 0:
        raise ValueError('importe negativo/no finito')
    return n


def official_code(draw, game):
    if draw.get('game_id') != game:
        raise ValueError('juego oficial incorrecto')
    section = draw.get('millon' if game == 'EMIL' else 'joker')
    if not isinstance(section, dict):
        raise ValueError('modalidad no publicada en resultado oficial')
    code = str(section.get('combinacion', '')).strip().upper()
    pattern = r'[A-Z]{3}\d{5}' if game == 'EMIL' else r'\d{7}'
    if not re.fullmatch(pattern, code):
        raise ValueError('código ganador ausente o mal formado')
    return code


def find_prize(rows, category, *, joker=False):
    if not isinstance(rows, list) or not rows:
        raise ValueError('escrutinio especial ausente')
    matches = []
    for row in rows:
        if joker:
            if str(row.get('orden_escrutinio', '')).strip() == str(category):
                matches.append(row)
        elif str(row.get('tipo', '')).strip().lower() == 'el millón':
            matches.append(row)
    if len(matches) != 1:
        raise ValueError('categoría oficial ausente o duplicada')
    row = matches[0]
    prize = money(row.get('premio'))
    try:
        winners = int(str(row.get('ganadores', '')).strip())
    except ValueError as exc:
        raise ValueError('acertantes inválidos') from exc
    if winners < 0:
        raise ValueError('acertantes negativos')
    return {'premio_unitario_oficial_eur': str(prize), 'acertantes_reportados': winners,
            'categoria': category, 'tipo': row.get('tipo')}


def check_millon(draw, code):
    """Comparación informativa del código; no acredita que el resguardo sea válido."""
    winning = official_code(draw, 'EMIL')
    if code is None or not re.fullmatch(r'[A-Za-z]{3}\d{5}', str(code).strip()):
        return {'estado': 'pendiente_dato_boleto', 'motivo': 'código El Millón ilegible o ausente'}
    match = str(code).strip().upper() == winning
    if not match:
        return {'estado': 'sin_coincidencia_de_codigo', 'coincide': False,
                'premio_estimado': None, 'nota': 'No evalúa Euromillones principal'}
    row = find_prize(draw.get('escrutinio_millon'), 1)
    return {'estado': 'coincidencia_de_codigo_no_verifica_boleto', 'coincide': True,
            **row, 'premio_estimado': None,
            'nota': 'El pago requiere resguardo válido, sorteo correcto y verificación SELAE'}


def check_joker(draw, code):
    winning = official_code(draw, 'LAPR')
    if code is None or not re.fullmatch(r'\d{7}', str(code).strip()):
        return {'estado': 'pendiente_dato_boleto', 'motivo': 'número Joker de 7 cifras ilegible o ausente'}
    code = str(code).strip()
    # El Joker premia 7 cifras exactas o la mejor coincidencia por prefijo/sufijo.
    # Las categorías NO se suman entre sí; conservar ceros iniciales.
    if code == winning:
        category, matched = 1, 7
    else:
        matched = max((k for k in range(1, 7)
                       if code[:k] == winning[:k] or code[-k:] == winning[-k:]), default=0)
        category = 8 - matched if matched else None
    if category is None:
        return {'estado': 'sin_coincidencia_joker', 'categoria': None,
                'premio_estimado': None, 'nota': 'No evalúa La Primitiva principal'}
    row = find_prize(draw.get('escrutinio_joker'), category, joker=True)
    return {'estado': 'coincidencia_joker_no_verifica_boleto', 'cifras_coincidentes': matched,
            **row, 'premio_estimado': None,
            'nota': 'Importe oficial de categoría; no acredita derecho al cobro'}


def fixture(game):
    item = FIXTURES[game]
    raw = zlib.decompress(base64.b64decode(item['payload']))
    if hashlib.sha256(raw).hexdigest() != item['sha256']:
        raise ValueError('muestra histórica alterada')
    rows = json.loads(raw)
    if len(rows) != 1 or rows[0].get('game_id') != game:
        raise ValueError('muestra histórica incorrecta')
    return rows[0]


def history_records():
    if not HISTORY.exists():
        return []
    data = json.loads(HISTORY.read_text(encoding='utf-8'))
    if not isinstance(data, dict) or not isinstance(data.get('registros'), list):
        raise ValueError('formato de histórico provisional no reconocido')
    result = []
    for record in data['registros']:
        revisions = record.get('revisiones', [])
        if revisions and isinstance(revisions[-1].get('datos_oficiales'), dict):
            result.append(revisions[-1]['datos_oficiales'])
    return result


def run():
    report = {'version': '0.87P', 'generado_utc': datetime.now(timezone.utc).isoformat(),
              'solo_lectura': True, 'publicables': 0, 'historico_modificado': False,
              'pruebas': [], 'historico': [], 'resumen': {'aprobadas': 0, 'fallidas': 0}}
    emil, lapr = fixture('EMIL'), fixture('LAPR')
    million = official_code(emil, 'EMIL')
    joker = official_code(lapr, 'LAPR')
    # Casos sintéticos: aciertos, errores, ausencia de datos y prioridad de categoría.
    tests = [
        ('millon_exacto', lambda: check_millon(emil, million), 'coincidencia_de_codigo_no_verifica_boleto', 1),
        ('millon_distinto', lambda: check_millon(emil, 'AAA00000' if million != 'AAA00000' else 'BBB00000'), 'sin_coincidencia_de_codigo', None),
        ('millon_ilegible', lambda: check_millon(emil, None), 'pendiente_dato_boleto', None),
        ('joker_7', lambda: check_joker(lapr, joker), 'coincidencia_joker_no_verifica_boleto', 1),
    ]
    for n in range(6, 0, -1):
        # Fabricar coincidencia de prefijo de n dígitos, forzando que el siguiente difiera;
        # verificar también que no aparece coincidencia de sufijo más larga.
        candidate = None
        for x in range(10 ** (7 - n)):
            s = joker[:n] + str(x).zfill(7 - n)
            if s == joker:
                continue
            best = max((k for k in range(1, 7) if s[:k] == joker[:k] or s[-k:] == joker[-k:]), default=0)
            if best == n:
                candidate = s
                break
        if candidate is None:
            raise ValueError('no se puede construir muestra Joker')
        tests.append((f'joker_{n}_cifras', lambda s=candidate: check_joker(lapr, s),
                      'coincidencia_joker_no_verifica_boleto', 8 - n))
    tests += [
        ('joker_ilegible', lambda: check_joker(lapr, '123'), 'pendiente_dato_boleto', None),
        ('joker_no_coincide', lambda: check_joker(lapr, next(str(x).zfill(7) for x in range(10000000)
              if str(x).zfill(7)[0] != joker[0] and str(x).zfill(7)[-1] != joker[-1])),
         'sin_coincidencia_joker', None),
    ]
    for label, func, state, category in tests:
        try:
            got = func()
            ok = got['estado'] == state and got.get('categoria') == category
            report['pruebas'].append({'caso': label, 'aprobado': ok, 'resultado': got})
        except Exception as exc:
            ok = False
            report['pruebas'].append({'caso': label, 'aprobado': False, 'error': f'{type(exc).__name__}: {exc}'})
        report['resumen']['aprobadas' if ok else 'fallidas'] += 1
    for draw in history_records():
        game = draw.get('game_id')
        if game not in ('EMIL', 'LAPR'):
            continue
        try:
            code = official_code(draw, game)
            row = (check_millon(draw, code) if game == 'EMIL' else check_joker(draw, code))
            report['historico'].append({'game_id': game, 'id_sorteo': draw.get('id_sorteo'),
                                        'datos_especiales_presentes': True,
                                        'categoria_referencia': row.get('categoria'),
                                        'estado': 'auditoria_sintetica_no_publicable'})
        except Exception as exc:
            report['historico'].append({'game_id': game, 'id_sorteo': draw.get('id_sorteo'),
                                        'datos_especiales_presentes': False, 'error': str(exc)})
            report['resumen']['fallidas'] += 1
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"0.87P: {report['resumen']['aprobadas']} pruebas aprobadas, {report['resumen']['fallidas']} fallidas")
    print(f"Auditoría histórico: {len(report['historico'])} sorteos de Euromillones/Primitiva")
    print('No se ha publicado ni modificado el histórico.')
    return 1 if report['resumen']['fallidas'] else 0


if __name__ == '__main__':
    raise SystemExit(run())
