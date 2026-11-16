"""LotoScan 0.69: verifica el histórico unificado sin publicar resultados."""
import json
from datetime import date, datetime, timezone
from pathlib import Path
from almacenar_resultados import GAMES, STORE, SUMMARY, valid_em, valid_other

OUT = Path('informe-lotoscan-050.json')
ORIGINALES = {'euromillones', 'bonoloto', 'primitiva'}
ADICIONALES = {'eurodreams', 'gordo_primitiva', 'loteria_nacional', 'quiniela'}


def entero(valor, minimo, maximo):
    return type(valor) is int and minimo <= valor <= maximo


def numeros(valor, cantidad, maximo):
    return (isinstance(valor, list) and len(valor) == cantidad
            and all(entero(n, 1, maximo) for n in valor)
            and len(set(valor)) == cantidad)


def validar_adicional(juego, registro):
    """Validación estructural; NO equivale a contraste oficial ni a premios completos."""
    if registro.get('estado') != 'pendiente_verificacion_oficial':
        raise ValueError('Estado incorrecto: ' + juego)
    if registro.get('publicable') is not False or registro.get('validado_oficialmente') is not False:
        raise ValueError('Marcadores de validación incorrectos: ' + juego)
    combinacion = registro.get('combinacion')
    if not isinstance(combinacion, dict):
        raise ValueError('Combinación ausente: ' + juego)
    if juego == 'eurodreams':
        correcto = numeros(combinacion.get('numeros'), 6, 40) and entero(combinacion.get('extra'), 1, 5)
    elif juego == 'gordo_primitiva':
        correcto = numeros(combinacion.get('numeros'), 5, 54) and entero(combinacion.get('extra'), 0, 9)
    elif juego == 'loteria_nacional':
        primero = combinacion.get('primer_premio')
        segundo = combinacion.get('segundo_premio')
        reintegros = combinacion.get('reintegros')
        correcto = (isinstance(primero, str) and len(primero) == 5 and primero.isascii() and primero.isdigit()
                    and isinstance(segundo, str) and len(segundo) == 5 and segundo.isascii() and segundo.isdigit()
                    and primero != segundo and isinstance(reintegros, list)
                    and 1 <= len(reintegros) <= 3 and all(entero(x, 0, 9) for x in reintegros)
                    and len(set(reintegros)) == len(reintegros))
        parciales = registro.get('premios_parciales')
        if parciales is not None:
            if not isinstance(parciales, dict):
                correcto = False
            else:
                for campo in ('primer_premio_centimos', 'segundo_premio_centimos', 'reintegro_centimos'):
                    if campo in parciales and not entero(parciales[campo], 0, 10**12):
                        correcto = False
    elif juego == 'quiniela':
        partidos = combinacion.get('partidos')
        signos = combinacion.get('signos_14_derivados')
        pleno = combinacion.get('pleno_15_derivado')
        correcto = (isinstance(partidos, list) and len(partidos) == 15
                    and all(isinstance(p, dict) and p.get('posicion') == i
                            and isinstance(p.get('marcador'), list) and len(p['marcador']) == 2
                            and all(entero(n, 0, 99) for n in p['marcador'])
                            for i, p in enumerate(partidos, 1))
                    and isinstance(signos, list) and len(signos) == 14
                    and all(x in ('1', 'X', '2') for x in signos)
                    and isinstance(pleno, list) and len(pleno) == 2
                    and all(x in ('0', '1', '2', 'M') for x in pleno))
    else:
        raise ValueError('Juego adicional desconocido: ' + juego)
    if not correcto:
        raise ValueError('Datos inválidos: ' + juego + '/' + registro.get('fecha', '?'))


def main():
    report = {'version': '0.69', 'fecha_utc': datetime.now(timezone.utc).isoformat(),
              'publica_resultados': False, 'estado': 'rechazado'}
    try:
        archive = json.loads(STORE.read_text(encoding='utf-8'))
        summary = json.loads(SUMMARY.read_text(encoding='utf-8'))
        if archive.get('version') != '0.49' or archive.get('publicable') is not False:
            raise ValueError('Formato de histórico inesperado')
        if summary.get('version') != '0.52' or summary.get('conflictos') or summary.get('rechazados'):
            raise ValueError('Informe con conflictos, rechazos o versión incorrecta')
        games = archive.get('juegos')
        if not isinstance(games, dict) or set(games) != set(GAMES):
            raise ValueError('Lista de juegos incorrecta')
        totals = {}
        for game, draws in games.items():
            if not isinstance(draws, dict):
                raise ValueError('Datos no estructurados: ' + game)
            if game not in ORIGINALES | ADICIONALES and draws:
                raise ValueError('Juego sin validador: ' + game)
            for key, record in draws.items():
                try:
                    date.fromisoformat(key)
                except (ValueError, TypeError):
                    raise ValueError('Fecha inválida: ' + str(key))
                if not isinstance(record, dict) or key != record.get('fecha'):
                    raise ValueError('Clave/fecha incorrecta: ' + game + '/' + key)
                if game in ADICIONALES:
                    validar_adicional(game, record)
                    continue
                if record.get('estado') != 'pendiente_verificacion_independiente':
                    raise ValueError('Estado incorrecto: ' + game + '/' + key)
                if game == 'euromillones':
                    payload = {**record,
                               'categorias': {k: {'importe_centimos': v}
                                              for k, v in record.get('categorias', {}).items()},
                               'datos_validos': True}
                    if not valid_em(payload):
                        raise ValueError('Euromillones inválido: ' + key)
                else:
                    payload = {**record, 'datos_validos': True}
                    if not valid_other(game, payload):
                        raise ValueError('Sorteo inválido: ' + game + '/' + key)
                    if game == 'primitiva' and record.get('joker_premios_validados') is not False:
                        raise ValueError('Premios Joker no validados')
            totals[game] = len(draws)
        report.update(estado='valido_para_revision', sorteos_por_juego=totals,
                      nuevos=summary.get('nuevos', []), sin_cambios=summary.get('sin_cambios', []),
                      consultas_fallidas=summary.get('consultas_fallidas', []),
                      nota='Validación estructural, sin contraste oficial ni garantía de premios completos.')
    except Exception as exc:
        report['error'] = str(exc)
        raise
    finally:
        OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
