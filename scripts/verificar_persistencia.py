
"""LotoScan 0.50: verifica el historico en revision antes de guardarlo.
No convierte resultados de terceros en resultados oficiales ni publicables.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from almacenar_resultados import GAMES, STORE, SUMMARY, valid_em

OUT = Path('informe-lotoscan-050.json')


def main():
    report = {'version': '0.50', 'fecha_utc': datetime.now(timezone.utc).isoformat(),
              'publica_resultados': False, 'estado': 'rechazado'}
    try:
        archive = json.loads(STORE.read_text(encoding='utf-8'))
        summary = json.loads(SUMMARY.read_text(encoding='utf-8'))
        if archive.get('version') != '0.49' or archive.get('publicable') is not False:
            raise ValueError('Formato o indicador publicable no esperado')
        if summary.get('conflictos') or summary.get('rechazados'):
            raise ValueError('Conflictos o resultados rechazados; requiere revision')
        games = archive.get('juegos')
        if not isinstance(games, dict) or set(games) != set(GAMES):
            raise ValueError('Lista de juegos inesperada')
        total = 0
        for game, draws in games.items():
            if not isinstance(draws, dict):
                raise ValueError('Almacen de juego no es objeto: ' + game)
            if game != 'euromillones' and draws:
                raise ValueError('Juego sin validador especifico: ' + game)
            for key, record in draws.items():
                if key != record.get('fecha') or not valid_em({
                    **record,
                    'categorias': {k: {'importe_centimos': v} for k, v in record.get('categorias', {}).items()},
                    'datos_validos': True,
                }):
                    raise ValueError('Registro incorrecto: ' + str(key))
                if record.get('estado') != 'pendiente_verificacion_independiente':
                    raise ValueError('Estado no permitido: ' + str(key))
                total += 1
        report.update(estado='valido_para_revision', sorteos_almacenados=total,
                      nuevos=summary.get('nuevos', []), sin_cambios=summary.get('sin_cambios', []),
                      nota='Persistencia de datos NO verificados; no conectar al comprobador de premios.')
    except Exception as exc:
        report['error'] = str(exc)
        raise
    finally:
        OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()

