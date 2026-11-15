
"""LotoScan 0.52: almacén de revisión; conserva registros existentes 0.49."""
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path

INPUT = Path('informe-lotoscan-048.json')
STORE = Path('datos_revision/historico.json')
SUMMARY = Path('informe-lotoscan-049.json')
GAMES = ('euromillones', 'primitiva', 'bonoloto', 'loteria_nacional',
         'gordo_primitiva', 'eurodreams', 'quiniela', 'quinigol', 'lototurf', 'quintuple_plus')
CATS = {f'{a}+{b}' for a, b in [(5,2),(5,1),(5,0),(4,2),(4,1),(3,2),(4,0),(2,2),(3,1),(3,0),(1,2),(2,1),(2,0)]}
OTHER_CATS = {'bonoloto': {'6', '5+C', '5', '4', '3', 'R'},
              'primitiva': {'6+R', '6', '5+C', '5', '4', '3', 'R'}}
DAYS = {'euromillones': (1,4), 'bonoloto': tuple(range(7)), 'primitiva': (0,3,5)}


def valid_date(value, game):
    d = date.fromisoformat(value)
    return date(2026, 1, 1) <= d <= datetime.now(timezone.utc).date() and d.weekday() in DAYS[game]


def valid_numbers(nums, count, max_number):
    return (isinstance(nums, list) and len(nums) == count and
            all(type(n) is int and 1 <= n <= max_number for n in nums) and len(set(nums)) == count)


def valid_em(item):
    try:
        cats = item['categorias']
        return (valid_date(item['fecha'], 'euromillones') and
                valid_numbers(item['numeros'], 5, 50) and
                valid_numbers(item['estrellas'], 2, 12) and
                bool(re.fullmatch(r'[A-Z]{3}\d{5}', item['el_millon'])) and
                set(cats) == CATS and
                all(isinstance(v, dict) and
                    (v.get('importe_centimos') is None or
                     (type(v['importe_centimos']) is int and v['importe_centimos'] >= 0))
                    for v in cats.values()) and item.get('datos_validos') is True)
    except (KeyError, ValueError, TypeError):
        return False


def valid_other(game, item):
    try:
        if not (valid_date(item['fecha'], game) and
                valid_numbers(item['numeros'], 6, 49) and
                type(item['complementario']) is int and 1 <= item['complementario'] <= 49 and
                item['complementario'] not in item['numeros'] and
                type(item['reintegro']) is int and 0 <= item['reintegro'] <= 9 and
                type(item['numero_sorteo']) is int and item['numero_sorteo'] > 0):
            return False
        if game == 'primitiva' and not re.fullmatch(r'\d{7}', item['joker']):
            return False
        cats = item['categorias']
        if not isinstance(cats, dict) or set(cats) != OTHER_CATS[game]:
            return False
        for prize in cats.values():
            if not isinstance(prize, dict):
                return False
            winners, amount = prize['acertantes'], prize['importe_centimos']
            if type(winners) is not int or winners < 0:
                return False
            if winners == 0 and amount is not None:
                return False
            if winners > 0 and (type(amount) is not int or amount < 0):
                return False
        return item.get('datos_validos') is True
    except (KeyError, ValueError, TypeError):
        return False


def normalize(game, item):
    if game == 'euromillones':
        return {'fecha': item['fecha'], 'numeros': sorted(item['numeros']),
                'estrellas': sorted(item['estrellas']), 'el_millon': item['el_millon'],
                'categorias': {k: item['categorias'][k]['importe_centimos'] for k in sorted(CATS)},
                'estado': 'pendiente_verificacion_independiente',
                'fuente': 'comprobarloteria.com (informe 0.48)'}
    record = {'fecha': item['fecha'], 'numero_sorteo': item['numero_sorteo'],
              'numeros': sorted(item['numeros']), 'complementario': item['complementario'],
              'reintegro': item['reintegro'],
              'categorias': {k: {'acertantes': item['categorias'][k]['acertantes'],
                                'importe_centimos': item['categorias'][k]['importe_centimos']}
                             for k in sorted(OTHER_CATS[game])},
              'estado': 'pendiente_verificacion_independiente',
              'fuente': 'comprobarloteria.com (informe 0.52)'}
    if game == 'primitiva':
        record['joker'] = item['joker']
        record['joker_premios_validados'] = False
    return record


def main():
    source = json.loads(INPUT.read_text(encoding='utf-8'))
    if source.get('version') != '0.52' or source.get('publica_resultados') is not False:
        raise ValueError('Informe de monitor incompatible')
    if STORE.exists():
        archive = json.loads(STORE.read_text(encoding='utf-8'))
        if archive.get('version') != '0.49' or archive.get('publicable') is not False:
            raise ValueError('Historico incompatible')
        if set(archive.get('juegos', {})) != set(GAMES):
            raise ValueError('Juegos historicos inesperados')
    else:
        archive = {'version': '0.49', 'publicable': False, 'juegos': {g: {} for g in GAMES}}
    summary = {'version': '0.52', 'fecha_utc': datetime.now(timezone.utc).isoformat(),
               'publica_resultados': False, 'nuevos': [], 'sin_cambios': [],
               'conflictos': [], 'rechazados': [], 'consultas_fallidas': []}
    for game in ('euromillones', 'bonoloto', 'primitiva'):
        entry = source.get('juegos', {}).get(game, {})
        if entry.get('estado') not in ('comprobado', 'sin_sorteos_pendientes'):
            summary['consultas_fallidas'].append(game + ': ' + str(entry.get('estado')))
        for item in entry.get('sorteos', []):
            day = item.get('fecha', 'desconocida')
            key = game + '/' + day
            if item.get('estado') in ('error_consulta', 'no_permitido_por_robots', 'respuesta_no_valida'):
                summary['consultas_fallidas'].append(key + ': ' + item['estado'])
                continue
            valid = valid_em(item) if game == 'euromillones' else valid_other(game, item)
            if not valid:
                summary['rechazados'].append(key)
                continue
            record = normalize(game, item)
            old = archive['juegos'][game].get(day)
            if old is None:
                archive['juegos'][game][day] = record
                summary['nuevos'].append(key)
            elif old == record:
                summary['sin_cambios'].append(key)
            else:
                summary['conflictos'].append(key)
    # Ante cualquier conflicto o estructura inválida, no escribir ni modificar el histórico.
    if not summary['conflictos'] and not summary['rechazados']:
        STORE.parent.mkdir(parents=True, exist_ok=True)
        STORE.write_text(json.dumps(archive, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False))
    if summary['conflictos'] or summary['rechazados']:
        raise SystemExit('Datos conflictivos o incompletos: historico sin modificar')


if __name__ == '__main__':
    main()

