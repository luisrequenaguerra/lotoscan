#!/usr/bin/env python3
"""LotoScan 0.87Q: auditoría conservadora de La Primitiva (sin publicación).

Prueba correspondencia aciertos/categorías y detecta las reglas económicas
que requieren confirmación; no presume que el premio Especial sea acumulable.
"""
import json
import re
import sys
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HISTORY = ROOT / 'datos/selae_provisional/historico_provisional.json'
OUTPUT = ROOT / 'informe_primitiva_087q.json'


def money(value):
    if isinstance(value, bool) or value is None:
        raise ValueError('importe ausente')
    raw = str(value).strip().replace(' ', '').replace('\u00a0', '')
    if ',' in raw:
        raw = raw.replace('.', '').replace(',', '.')
    try:
        result = Decimal(raw)
    except InvalidOperation as exc:
        raise ValueError('importe no numérico') from exc
    if not result.is_finite() or result < 0:
        raise ValueError('importe inválido')
    return result


def parse_draw(draw):
    if draw.get('game_id') != 'LAPR':
        raise ValueError('no es La Primitiva')
    match = re.fullmatch(r'\s*(\d{1,2}(?:\s*-\s*\d{1,2}){5})\s+C\((\d{1,2})\)\s+R\((\d)\)\s*', str(draw.get('combinacion', '')))
    if not match:
        raise ValueError('combinación incompleta')
    nums = [int(v.strip()) for v in match.group(1).split('-')]
    comp, refund = int(match.group(2)), int(match.group(3))
    if len(set(nums)) != 6 or any(not 1 <= n <= 49 for n in nums) or not 1 <= comp <= 49 or comp in nums:
        raise ValueError('números oficiales inválidos')
    rows = draw.get('escrutinio')
    if not isinstance(rows, list):
        raise ValueError('escrutinio ausente')
    by_cat = {}
    for row in rows:
        cat = row.get('categoria')
        if type(cat) is not int or cat in by_cat or cat not in range(1, 8):
            raise ValueError('categoría duplicada o inválida')
        try:
            winners = int(row['ganadores'])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError('ganadores inválidos') from exc
        if winners < 0:
            raise ValueError('ganadores negativos')
        by_cat[cat] = {'tipo': row.get('tipo'), 'ganadores': winners, 'premio': money(row.get('premio'))}
    if set(by_cat) != set(range(1, 8)):
        raise ValueError('faltan categorías de escrutinio')
    return nums, comp, refund, by_cat


def evaluate(draw, ticket):
    nums, comp, refund, rows = parse_draw(draw)
    chosen = ticket.get('numeros')
    reintegro = ticket.get('reintegro')
    if not isinstance(chosen, list) or len(chosen) != 6 or any(type(n) is not int or not 1 <= n <= 49 for n in chosen) or len(set(chosen)) != 6:
        raise ValueError('apuesta inválida')
    if type(reintegro) is not int or not 0 <= reintegro <= 9:
        raise ValueError('reintegro inválido')
    hits = len(set(chosen) & set(nums))
    has_comp = comp in chosen
    refund_hit = reintegro == refund
    cat = ({6: 1 if refund_hit else 2, 5: 3 if has_comp else 4, 4: 5, 3: 6}).get(hits)
    concepts = []
    if cat is not None:
        row = rows[cat]
        concepts.append({'categoria': cat, 'tipo': row['tipo'], 'ganadores_oficiales': row['ganadores'], 'importe_unitario_oficial': str(row['premio'])})
    if refund_hit:
        row = rows[7]
        concepts.append({'categoria': 7, 'tipo': row['tipo'], 'ganadores_oficiales': row['ganadores'], 'importe_unitario_oficial': str(row['premio'])})
    # El escrutinio de un sorteo real no demuestra que un boleto sintético exista.
    # En 6+R, no sumamos ni sustituimos la categoría Especial sin confirmar el reglamento.
    needs_rule = (cat == 1 and refund_hit)
    return {
        'aciertos': hits, 'complementario': has_comp, 'reintegro': refund_hit,
        'categoria_principal': cat, 'conceptos_observados': concepts,
        'estado': 'pendiente_regla_especial_6_mas_reintegro' if needs_rule else 'simulacion_no_pagadera',
        'premio_total_pagadero_eur': None,
        'advertencias': (['Confirmar si premio Especial incluye o acumula primera categoría y reintegro'] if needs_rule else []) +
                        ['Las apuestas sintéticas no prueban existencia de boleto ni derecho al cobro']
    }


def load_history():
    if not HISTORY.exists():
        return []
    data = json.loads(HISTORY.read_text(encoding='utf-8'))
    if isinstance(data, dict):
        for key in ('registros', 'sorteos', 'resultados'):
            if isinstance(data.get(key), list):
                return data[key]
    if isinstance(data, list):
        return data
    raise ValueError('formato del histórico no reconocido')


def unwrap(record):
    if record.get('game_id') == 'LAPR':
        return record
    for key in ('resultado', 'datos', 'sorteo', 'respuesta'):
        if isinstance(record.get(key), dict) and record[key].get('game_id') == 'LAPR':
            return record[key]
    versions = record.get('revisiones')
    if isinstance(versions, list) and versions:
        return unwrap(versions[-1])
    return None


def cases(draw):
    nums, comp, refund, _ = parse_draw(draw)
    other = [x for x in range(1, 50) if x not in nums and x != comp]
    bad_r = (refund + 1) % 10
    specs = [
        ('especial_6_R', nums, refund, 1),
        ('primera_6', nums, bad_r, 2),
        ('segunda_5_C', nums[:5] + [comp], bad_r, 3),
        ('tercera_5', nums[:5] + [other[0]], bad_r, 4),
        ('cuarta_4', nums[:4] + other[:2], bad_r, 5),
        ('quinta_3', nums[:3] + other[:3], bad_r, 6),
        ('solo_reintegro', other[:6], refund, None),
        ('sin_premio', other[:6], bad_r, None),
    ]
    out = []
    for name, selected, r, expected in specs:
        result = evaluate(draw, {'numeros': selected, 'reintegro': r})
        ok = result['categoria_principal'] == expected and (result['reintegro'] == (r == refund)) and result['premio_total_pagadero_eur'] is None
        out.append({'caso': name, 'superado': ok, 'resultado': result})
    return out


def main():
    draws = []
    for record in load_history():
        if not isinstance(record, dict):
            continue
        draw = unwrap(record)
        if draw is not None:
            draws.append(draw)
    # Muestra histórica oficial conservada en el script 0.87P, si está disponible.
    try:
        sys.path.insert(0, str(ROOT / 'scripts'))
        from probar_millon_joker_087p import fixture
        reference = fixture('LAPR')
        if not any(str(d.get('id_sorteo')) == str(reference.get('id_sorteo')) for d in draws):
            draws.append(reference)
    except (ImportError, ValueError, KeyError) as exc:
        print('Muestra de 0.87P no disponible:', exc)
    report = {'version': '0.87Q', 'fecha_utc': datetime.now(timezone.utc).isoformat(),
              'modo': 'solo_diagnostico', 'historico_modificado': False, 'publicables': 0,
              'sorteos': [], 'resumen': {'sorteos': 0, 'casos': 0, 'superados': 0, 'fallidos': 0, 'errores': 0},
              'pendiente_reglamentario': ['Determinar tratamiento económico de Especial (6+R) y posible acumulación',
                                         'Confirmar condiciones de acumulación del reintegro con otras categorías',
                                         'Validar con boletos reales y tablas oficiales antes de publicar']}
    for draw in draws:
        entry = {'id_sorteo': draw.get('id_sorteo'), 'fecha_sorteo': draw.get('fecha_sorteo')}
        try:
            entry['casos'] = cases(draw)
            report['resumen']['casos'] += len(entry['casos'])
            report['resumen']['superados'] += sum(c['superado'] for c in entry['casos'])
            report['resumen']['fallidos'] += sum(not c['superado'] for c in entry['casos'])
        except Exception as exc:
            entry['error'] = f'{type(exc).__name__}: {exc}'
            report['resumen']['errores'] += 1
        report['sorteos'].append(entry)
    report['resumen']['sorteos'] = len(draws)
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report['resumen'], ensure_ascii=False))
    if not draws or report['resumen']['fallidos'] or report['resumen']['errores']:
        raise SystemExit(1)

if __name__ == '__main__':
    main()
