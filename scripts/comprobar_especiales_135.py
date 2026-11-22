#!/usr/bin/env python3
"""LotoScan 1.35: validacion independiente de LNAC y QUPL con resultados oficiales.
Solo aciertos/categorias verificables; no certifica importes ni publica premios.
"""
import argparse
import json
import re
from pathlib import Path


def lnac(draw, numero):
    """Compara primer/segundo premio y reintegro; no calcula extracciones ni aproximaciones."""
    c = draw.get('combinacion') or {}
    first = c.get('primer_premio')
    second = c.get('Segundo_premio', c.get('segundo_premio'))
    refunds = draw.get('reintegros', c.get('reintegros'))
    if not isinstance(numero, str) or not re.fullmatch(r'\d{5}', numero):
        return {'estado': 'apuesta_invalida', 'motivo': 'numero_de_cinco_cifras_requerido'}
    if not isinstance(first, str) or not re.fullmatch(r'\d{5}', first) or not isinstance(second, str) or not re.fullmatch(r'\d{5}', second):
        return {'estado': 'no_comprobable', 'motivo': 'premios_principales_incompletos'}
    if not isinstance(refunds, list) or not refunds or any(not re.fullmatch(r'\d', str(x)) for x in refunds):
        return {'estado': 'no_comprobable', 'motivo': 'reintegros_incompletos'}
    return {'estado': 'aciertos_parciales_verificados', 'primer_premio': numero == first,
            'segundo_premio': numero == second, 'reintegro': numero[-1] in {str(x) for x in refunds},
            'alcance': 'No incluye extracciones, aproximaciones, centenas, terminaciones ni premios acumulables',
            'premio_eur': None, 'publicable': False}


def qupl(draw, apuesta):
    """Cinco ganadores de carrera + segundo de quinta; categorias 1-5 segun escrutinio."""
    c = draw.get('combinacion')
    if isinstance(c, dict):
        winners = c.get('numeros')
        second = c.get('complementario')
    elif isinstance(c, str):
        m = re.fullmatch(r'\s*(\d+)\s*-\s*(\d+)\s*-\s*(\d+)\s*-\s*(\d+)\s*-\s*(\d+)\s+C\((\d+)\)\s*', c)
        winners = list(map(int, m.groups()[:5])) if m else None
        second = int(m.group(6)) if m else None
    else:
        winners, second = None, None
    if not isinstance(winners, list) or len(winners) != 5 or any(type(x) != int or x < 1 for x in winners) or type(second) != int or second < 1:
        return {'estado': 'no_comprobable', 'motivo': 'combinacion_oficial_incompleta'}
    picks = apuesta.get('ganadores')
    runner_up = apuesta.get('segundo_quinta')
    if not isinstance(picks, list) or len(picks) != 5 or any(type(x) != int or x < 1 for x in picks) or type(runner_up) != int or runner_up < 1 or runner_up == picks[4]:
        return {'estado': 'apuesta_invalida', 'motivo': 'cinco_caballos_y_segundo_quinta_distinto_requeridos'}
    hits = sum(a == b for a, b in zip(picks, winners))
    hit_second = runner_up == second
    # Especial depende de que exista un unico resguardo ganador de primera categoria:
    # no puede inferirse de una apuesta individual.
    category = ('primera' if hits == 5 and hit_second else
                'segunda' if hits == 5 else
                'tercera' if hits == 4 and hit_second else
                'cuarta' if hits == 4 else None)
    return {'estado': 'aciertos_parciales_verificados', 'ganadores_acertados': hits,
            'segundo_quinta_acertado': hit_second, 'categoria_provisional': category,
            'especial_no_evaluable': True, 'premio_eur': None, 'publicable': False}


def run_case(game, draw, bet):
    return lnac(draw, bet['numero']) if game == 'LNAC' else qupl(draw, bet)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--historico', default='datos/lotoscan/historico_oficial')
    ap.add_argument('--informe', default='salida_135')
    args = ap.parse_args()
    output = Path(args.informe)
    output.mkdir(parents=True, exist_ok=True)
    records = []
    errors = []
    totals = {'LNAC': 0, 'QUPL': 0}
    for game in ('LNAC', 'QUPL'):
        for path in sorted(Path(args.historico).glob(f'{game}/*/actual.json')):
            try:
                draw = json.loads(path.read_text(encoding='utf-8'))
                if draw.get('game_id') != game:
                    raise ValueError('game_id no coincide')
                if game == 'LNAC':
                    c = draw.get('combinacion') or {}
                    winner = c.get('primer_premio')
                    if not isinstance(winner, str) or not re.fullmatch(r'\d{5}', winner):
                        raise ValueError('primer premio ausente')
                    bets = [('primer_premio', {'numero': winner}, 'primer_premio', True),
                            ('apuesta_invalida', {'numero': '1234'}, 'estado', 'apuesta_invalida')]
                else:
                    raw = draw.get('combinacion')
                    m = re.fullmatch(r'\s*(\d+)\s*-\s*(\d+)\s*-\s*(\d+)\s*-\s*(\d+)\s*-\s*(\d+)\s+C\((\d+)\)\s*', raw or '')
                    if not m:
                        raise ValueError('combinacion QUPL ausente')
                    wins = list(map(int, m.groups()[:5]))
                    second = int(m.group(6))
                    if wins[4] == second:
                        raise ValueError('resultado oficial contradictorio: ganador y segundo iguales')
                    bets = [('primera', {'ganadores': wins, 'segundo_quinta': second}, 'categoria_provisional', 'primera'),
                            ('segunda', {'ganadores': wins, 'segundo_quinta': max(wins[4], second) + 1}, 'categoria_provisional', 'segunda'),
                            ('apuesta_invalida', {'ganadores': wins[:4], 'segundo_quinta': second}, 'estado', 'apuesta_invalida')]
                for name, bet, field, expected in bets:
                    actual = run_case(game, draw, bet)
                    ok = actual.get(field) == expected
                    records.append({'juego': game, 'id_sorteo': str(draw.get('id_sorteo')),
                                    'caso': name, 'superado': ok, 'resultado': actual})
                    if not ok:
                        errors.append({'archivo': str(path), 'caso': name, 'error': 'resultado inesperado'})
                totals[game] += 1
            except (OSError, ValueError, TypeError, json.JSONDecodeError) as e:
                errors.append({'archivo': str(path), 'error': str(e)})
    report = {'version': '1.35', 'sorteos_por_juego': totals, 'casos': len(records),
              'superados': sum(x['superado'] for x in records), 'fallidos': len(errors),
              'errores': errors, 'premios_verificados': False, 'publicable': False,
              'alcance': 'LNAC primer/segundo/reintegro; QUPL categorias provisionales 1-4; no importes'}
    (output / 'informe_135.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (output / 'casos_135.json').write_text(json.dumps(records, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not sum(totals.values()) or errors:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
