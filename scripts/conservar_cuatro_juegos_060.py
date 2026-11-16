"""LotoScan 0.60: archivo de revisión separado, sin alterar historico.json."""
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path

INPUT = Path('informe-lotoscan-059.json')
OUTPUT = Path('datos_revision/historico.json')
GAMES = ('eurodreams', 'gordo_primitiva', 'loteria_nacional', 'quiniela')
SOURCE = 'https://comprobarloteria.com'


def valid_numbers(values, count, low, high):
    return (type(values) is list and len(values) == count
            and all(type(x) is int and low <= x <= high for x in values)
            and len(set(values)) == count)


def validate(game, record):
    if record.get('estado') != 'extraido_sin_verificacion_oficial':
        raise ValueError('Extracción incompleta')
    if any(record.get(k) is not False for k in ('publicable', 'validado_oficialmente', 'incorporar_historico')):
        raise ValueError('Indicadores de seguridad inesperados')
    source = record.get('fuente', '')
    if not isinstance(source, str) or not source.startswith(SOURCE + '/'):
        raise ValueError('Fuente inesperada')
    day = record.get('fecha')
    if not isinstance(day, str) or not re.fullmatch(r'20\d{2}-\d{2}-\d{2}', day):
        raise ValueError('Fecha incorrecta')
    parsed = date.fromisoformat(day)
    if parsed > datetime.now(timezone.utc).date():
        raise ValueError('Fecha futura')
    c = record.get('combinacion')
    if not isinstance(c, dict):
        raise ValueError('Falta combinación')
    if game == 'eurodreams':
        if not valid_numbers(c.get('numeros'), 6, 1, 40) or type(c.get('extra')) is not int or not 1 <= c['extra'] <= 5:
            raise ValueError('EuroDreams inválido')
    elif game == 'gordo_primitiva':
        if not valid_numbers(c.get('numeros'), 5, 1, 54) or type(c.get('extra')) is not int or not 0 <= c['extra'] <= 9:
            raise ValueError('Gordo inválido')
    elif game == 'loteria_nacional':
        if any(not isinstance(c.get(k), str) or not re.fullmatch(r'\d{5}', c[k]) for k in ('primer_premio','segundo_premio')):
            raise ValueError('Premios principales inválidos')
        if not valid_numbers(c.get('reintegros'), 3, 0, 9):
            raise ValueError('Reintegros inválidos')
    elif game == 'quiniela':
        signs = c.get('signos_14_derivados')
        pleno = c.get('pleno_15_derivado')
        matches = c.get('partidos')
        if not isinstance(signs, list) or len(signs) != 14 or any(s not in ('1','X','2') for s in signs):
            raise ValueError('Signos inválidos')
        if not isinstance(pleno, list) or len(pleno) != 2 or any(s not in ('0','1','2','M') for s in pleno):
            raise ValueError('Pleno inválido')
        if not isinstance(matches, list) or len(matches) != 15:
            raise ValueError('Partidos incompletos')
        for i, m in enumerate(matches, 1):
            if not isinstance(m, dict) or type(m.get('posicion')) is not int or m['posicion'] != i:
                raise ValueError('Posición de partido inválida')
            score = m.get('marcador')
            if not isinstance(score, list) or len(score) != 2 or any(type(x) is not int or x < 0 for x in score):
                raise ValueError('Marcador inválido')
            a, b = score
            if i <= 14 and signs[i-1] != ('1' if a > b else '2' if a < b else 'X'):
                raise ValueError('Signo y marcador incompatibles')
            if i == 15 and pleno != [str(x) if x <= 2 else 'M' for x in (a,b)]:
                raise ValueError('Pleno y marcador incompatibles')
    return day


def main():
    report = json.loads(INPUT.read_text(encoding='utf-8'))
    if report.get('version') != '0.59' or report.get('modifica_historico') is not False or report.get('publica_resultados') is not False:
        raise ValueError('Informe 0.59 inesperado')
    if not isinstance(report.get('juegos'), dict):
        raise ValueError('Sin juegos')
    if OUTPUT.exists():
        history = json.loads(OUTPUT.read_text(encoding='utf-8'))
        if history.get('version') != '0.49' or history.get('publicable') is not False:
            raise ValueError('Archivo de revisión existente incompatible')
    else:
        history = {'version':'0.49','publicable':False,
                   'juegos':{game:{} for game in ('euromillones','primitiva','bonoloto','loteria_nacional','gordo_primitiva','eurodreams','quiniela','quinigol','lototurf','quintuple_plus')}}
    if not isinstance(history.get('juegos'),dict) or not set(GAMES).issubset(history['juegos']):
        raise ValueError('Estructura del archivo incompatible')
    added = 0
    for game in GAMES:
        record = report['juegos'].get(game)
        if not isinstance(record, dict):
            print(game, 'omitido: no hay registro')
            continue
        try:
            day = validate(game, record)
        except (ValueError, TypeError, KeyError) as exc:
            print(game, 'omitido:', str(exc))
            continue
        item = {'fecha':day, 'fuente':record['fuente'], 'estado':'pendiente_verificacion_oficial',
                'validado_oficialmente':False,'publicable':False,
                'combinacion':record['combinacion']}
        existing = history['juegos'][game].get(day)
        if existing is None:
            history['juegos'][game][day] = item
            added += 1
            print(game, day, 'nuevo')
        elif existing == item or (isinstance(existing,dict) and existing.get('combinacion') == item['combinacion']):
            print(game, day, 'ya almacenado (se conservan los datos ampliados)')
        else:
            # Nunca sobrescribir un sorteo existente silenciosamente.
            raise ValueError(f'Conflicto de resultados: {game} {day}')
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(history, ensure_ascii=False, indent=2, sort_keys=True)+'\n', encoding='utf-8')
    print('Nuevos:', added, 'Archivo:', OUTPUT)


if __name__ == '__main__':
    main()
