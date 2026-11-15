
"""LotoScan 0.52: validación de histórico en revisión, sin publicación."""
import json
from datetime import datetime, timezone
from pathlib import Path
from almacenar_resultados import GAMES, STORE, SUMMARY, CATS, OTHER_CATS, valid_em, valid_other

OUT = Path('informe-lotoscan-050.json')


def main():
    report = {'version': '0.52', 'fecha_utc': datetime.now(timezone.utc).isoformat(),
              'publica_resultados': False, 'estado': 'rechazado'}
    try:
        archive = json.loads(STORE.read_text(encoding='utf-8'))
        summary = json.loads(SUMMARY.read_text(encoding='utf-8'))
        if archive.get('version') != '0.49' or archive.get('publicable') is not False:
            raise ValueError('Formato de historico inesperado')
        if summary.get('version') != '0.52' or summary.get('conflictos') or summary.get('rechazados'):
            raise ValueError('Informe con conflictos, rechazos o version incorrecta')
        games = archive.get('juegos')
        if not isinstance(games, dict) or set(games) != set(GAMES):
            raise ValueError('Lista de juegos incorrecta')
        totals = {}
        for game, draws in games.items():
            if not isinstance(draws, dict):
                raise ValueError('Datos no estructurados: ' + game)
            if game not in ('euromillones', 'bonoloto', 'primitiva') and draws:
                raise ValueError('Juego sin validador: ' + game)
            for key, record in draws.items():
                if not isinstance(record, dict) or key != record.get('fecha'):
                    raise ValueError('Clave/fecha incorrecta: ' + game + '/' + key)
                if record.get('estado') != 'pendiente_verificacion_independiente':
                    raise ValueError('Estado publicable no autorizado')
                if game == 'euromillones':
                    payload = {**record,
                               'categorias': {k: {'importe_centimos': v}
                                              for k, v in record.get('categorias', {}).items()},
                               'datos_validos': True}
                    if not valid_em(payload):
                        raise ValueError('Euromillones invalido: ' + key)
                else:
                    payload = {**record, 'datos_validos': True}
                    if not valid_other(game, payload):
                        raise ValueError('Sorteo invalido: ' + game + '/' + key)
                    if game == 'primitiva' and record.get('joker_premios_validados') is not False:
                        raise ValueError('Premios Joker no validados')
            totals[game] = len(draws)
        report.update(estado='valido_para_revision', sorteos_por_juego=totals,
                      nuevos=summary.get('nuevos', []), sin_cambios=summary.get('sin_cambios', []),
                      consultas_fallidas=summary.get('consultas_fallidas', []),
                      nota='Resultados no contrastados; no usar para declarar premios.')
    except Exception as exc:
        report['error'] = str(exc)
        raise
    finally:
        OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()

