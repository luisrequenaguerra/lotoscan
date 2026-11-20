#!/usr/bin/env python3
"""LotoScan 0.87N: integración prudente de categorías y cálculo sintético.
No verifica boletos reales, no publica ni escribe históricos.
Requiere scripts/comprobar_premios_087l.py y scripts/clasificar_premios_087m.py.
"""
import argparse
import importlib.util
import json
import re
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name, filename):
    path = ROOT / 'scripts' / filename
    spec = importlib.util.spec_from_file_location(name, path)
    if not path.is_file() or not spec or not spec.loader:
        raise RuntimeError(f'Dependencia ausente: {path}')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def inspect_case(draw, ticket, engine, categories):
    """El cálculo original es orientativo; nunca autoriza un importe pagadero."""
    game = draw['game_id']
    base = engine.check(draw, ticket)
    rows = draw.get('escrutinio', [])
    classified = [categories.classify(r, game) for r in rows]
    outcome = {
        'estado': 'prueba_hipotetica_no_publicable',
        'aciertos': base.get('aciertos'),
        'resultado_motor_previo': base.get('estado'),
        'premio_pagadero_eur': None,
        'categorias_implicadas': [],
        'advertencias': [],
    }
    if base.get('estado') != 'calculado_en_pruebas':
        outcome['advertencias'].append('Motor incompleto: ' + str(base.get('motivo', base.get('estado'))))
        return outcome

    # Resolver la categoría a partir de la salida anterior sin asumir que el importe cero es pagadero.
    parts = base.get('componentes', [])
    if game == 'QGOL':
        cat = base.get('categoria')
        if cat is not None:
            matches = [r for r in classified if r['categoria'] == cat]
            if len(matches) != 1:
                outcome['advertencias'].append('Categoría ambigua o ausente')
            else:
                outcome['categorias_implicadas'].append(matches[0])
    else:
        for p in parts:
            label = str(p.get('concepto', '')).strip()
            matches = [r for r in classified if r['tipo'].strip() == label]
            if len(matches) == 1:
                outcome['categorias_implicadas'].append(matches[0])
            elif label == 'El Millón':
                outcome['advertencias'].append('El Millón: requiere comprobación independiente de código y escrutinio')
            else:
                outcome['advertencias'].append('Concepto no identificado unívocamente: ' + label)

    if not outcome['categorias_implicadas'] and not parts and game != 'QGOL':
        outcome['advertencias'].append('Sin categoría principal reconocida; revisar reintegros y premios complementarios')
    for r in outcome['categorias_implicadas']:
        if r['estado'] == 'sin_acertantes_en_ambito_reportado':
            outcome['advertencias'].append('Apuesta contrafactual: categoría sin acertantes oficiales')
        elif r['estado'] == 'acertantes_con_importe_cero_requiere_regla':
            outcome['advertencias'].append('Importe cero con acertantes: requiere regla específica')
    if game == 'EMIL':
        outcome['advertencias'].append('El Millón no se considera validado mediante apuestas sintéticas')
    if game == 'LAPR':
        outcome['advertencias'].append('Joker y acumulación de especial/reintegro pendientes')
    return outcome


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--historico', default=str(ROOT / 'datos/selae_provisional/historico_provisional.json'))
    ap.add_argument('--muestras-dir', default='', help='Carpeta opcional de muestras JSON')
    args = ap.parse_args()
    engine = load('lotoscan_087l', 'comprobar_premios_087l.py')
    categories = load('lotoscan_087m', 'clasificar_premios_087m.py')
    if args.muestras_dir:
        draws = []
        for path in sorted(Path(args.muestras_dir).glob('*.json')):
            draws.extend(engine.records(json.loads(path.read_text(encoding='utf-8'))))
    else:
        path = Path(args.historico)
        if not path.is_file():
            raise SystemExit(f'No existe histórico: {path}')
        draws = list(engine.records(json.loads(path.read_text(encoding='utf-8'))))
    report = {'version': '0.87N', 'fecha_utc': datetime.now(timezone.utc).isoformat(),
              'modo': 'SIMULACION_NO_PUBLICABLE', 'historico_modificado': False,
              'publicables': 0, 'sorteos': [], 'errores': []}
    for draw in draws:
        game = draw.get('game_id')
        item = {'juego': game, 'id_sorteo': draw.get('id_sorteo'), 'casos': []}
        try:
            if game not in engine.SUPPORTED:
                item['estado'] = 'motor_pendiente'
            else:
                for name, ticket in engine.synthetic(draw):
                    item['casos'].append({'nombre': name, 'resultado': inspect_case(draw, ticket, engine, categories)})
                item['estado'] = 'simulado'
        except Exception as exc:
            item['estado'] = 'error'
            item['error'] = str(exc)
            report['errores'].append({'juego': game, 'id_sorteo': draw.get('id_sorteo'), 'error': str(exc)})
        report['sorteos'].append(item)
    report['resumen'] = {
        'sorteos': len(draws),
        'motores_simulados': sum(x['estado'] == 'simulado' for x in report['sorteos']),
        'motores_pendientes': sum(x['estado'] == 'motor_pendiente' for x in report['sorteos']),
        'errores': len(report['errores']), 'publicables': 0,
    }
    Path('informe_premios_087n.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    Path('informe_premios_087n.txt').write_text(json.dumps(report['resumen'], ensure_ascii=False, indent=2) + '\nNO PUBLICABLE. Pruebas sintéticas contrafactuales.\n', encoding='utf-8')
    print(json.dumps(report['resumen'], ensure_ascii=False))
    if report['errores']:
        raise SystemExit(1)

if __name__ == '__main__':
    main()
