#!/usr/bin/env python3
"""LotoScan 0.87Q2: contraste reglamentario y cálculo teórico de La Primitiva.
No acredita resguardos ni publica premios. Requiere 0.87Q y 0.87P.
"""
import json
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from auditar_primitiva_087q import parse_draw, evaluate, load_history, unwrap
from probar_millon_joker_087p import fixture

OUT = ROOT / 'informe_acumulacion_primitiva_087q2.json'
NORMATIVA = 'https://www.loteriasyapuestas.es/f/loterias/documentos/normativa/normativa%20SELAE/8-ACUERDO_Y_NORMAS_PRIMITIVA_OCT_2018.pdf'
FUENTE_EJEMPLO = 'https://www.loteriasyapuestas.es/es/resultados?drawId=1328414091'


def calcular(draw, ticket):
    """Importe matemático por apuesta simple, nunca importe cobrado verificado.

    La Especial y Primera son fondos diferentes: el acertante 6+R tiene
    derecho a ambas categorías. El reintegro es un premio independiente.
    La ausencia de ganadores oficiales impide convertir la simulación en
    un pago real, aunque se conserva el cálculo hipotético.
    """
    base = evaluate(draw, ticket)
    _, _, _, rows = parse_draw(draw)
    cat = base['categoria_principal']
    categorias = ([1, 2] if cat == 1 else ([cat] if cat is not None else []))
    if base['reintegro']:
        categorias.append(7)
    partes = []
    for category in categorias:
        row = rows[category]
        partes.append({
            'categoria': category,
            'ganadores_oficiales': row['ganadores'],
            'importe_unitario_eur': f"{row['premio']:.2f}",
            'sin_acertantes_oficiales': row['ganadores'] == 0,
        })
    total = sum((rows[c]['premio'] for c in categorias), Decimal('0.00'))
    contradiccion = any(rows[c]['ganadores'] == 0 for c in categorias)
    return {
        'aciertos': base['aciertos'], 'reintegro_coincide': base['reintegro'],
        'categoria_principal': cat, 'componentes': partes,
        'total_matematico_hipotetico_eur': f'{total:.2f}',
        'estado': 'simulacion_contraria_al_escrutinio' if contradiccion else 'simulacion_no_verifica_resguardo',
        'importe_pagadero_verificado_eur': None,
        'publicable': False,
    }


def pruebas(draw):
    nums, comp, reintegro, rows = parse_draw(draw)
    otros = [n for n in range(1, 50) if n not in nums and n != comp]
    malo = (reintegro + 1) % 10
    casos = [
        ('especial_6_R', nums, reintegro, [1, 2, 7]),
        ('primera_6_sin_R', nums, malo, [2]),
        ('segunda_5_C_con_R', nums[:5] + [comp], reintegro, [3, 7]),
        ('tercera_5_sin_R', nums[:5] + otros[:1], malo, [4]),
        ('cuarta_4_con_R', nums[:4] + otros[:2], reintegro, [5, 7]),
        ('quinta_3_sin_R', nums[:3] + otros[:3], malo, [6]),
        ('solo_R', otros[:6], reintegro, [7]),
        ('sin_premio', otros[:6], malo, []),
    ]
    resultados = []
    for nombre, seleccion, r, esperadas in casos:
        result = calcular(draw, {'numeros': seleccion, 'reintegro': r})
        cats = [p['categoria'] for p in result['componentes']]
        esperado_total = sum((rows[c]['premio'] for c in esperadas), Decimal('0'))
        ok = (cats == esperadas and Decimal(result['total_matematico_hipotetico_eur']) == esperado_total
              and result['importe_pagadero_verificado_eur'] is None and not result['publicable'])
        resultados.append({'caso': nombre, 'aprobado': ok, 'resultado': result})
    return resultados


def main():
    draws = []
    for item in load_history():
        if isinstance(item, dict):
            draw = unwrap(item)
            if draw:
                draws.append(draw)
    ref = fixture('LAPR')
    if not any(str(d.get('id_sorteo')) == str(ref.get('id_sorteo')) for d in draws):
        draws.append(ref)
    report = {
        'version': '0.87Q2', 'generado_utc': datetime.now(timezone.utc).isoformat(),
        'fuentes_reglamentarias': [NORMATIVA, FUENTE_EJEMPLO],
        'reglas': {
            'especial': '6+R: premio Especial + premio Primera + reintegro por coincidencia del resguardo',
            'primera': '6 aciertos sin reintegro: premio Primera',
            'otras_categorias': 'Premio de la categoria aplicable y, si coincide, reintegro adicional',
            'sin_acertantes': 'Una apuesta sintética incompatible con los ganadores oficiales nunca acredita un pago',
            'sin_doble_conteo': 'No se vuelve a sumar el bote: ya está reflejado en el premio unitario oficial Especial',
        },
        'historico_modificado': False, 'publicables': 0,
        'sorteos': [], 'resumen': {'sorteos': 0, 'casos': 0, 'aprobados': 0, 'fallidos': 0, 'errores': 0},
    }
    for draw in draws:
        entry = {'id_sorteo': draw.get('id_sorteo'), 'fecha_sorteo': draw.get('fecha_sorteo')}
        try:
            entry['pruebas'] = pruebas(draw)
            report['resumen']['casos'] += len(entry['pruebas'])
            report['resumen']['aprobados'] += sum(x['aprobado'] for x in entry['pruebas'])
            report['resumen']['fallidos'] += sum(not x['aprobado'] for x in entry['pruebas'])
        except Exception as exc:
            entry['error'] = f'{type(exc).__name__}: {exc}'
            report['resumen']['errores'] += 1
        report['sorteos'].append(entry)
    report['resumen']['sorteos'] = len(draws)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report['resumen'], ensure_ascii=False))
    if not draws or report['resumen']['fallidos'] or report['resumen']['errores']:
        raise SystemExit(1)

if __name__ == '__main__':
    main()
