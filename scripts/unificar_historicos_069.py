"""Unificación conservadora: no borra el histórico secundario ni sobreescribe registros."""
import json
from pathlib import Path

MAIN = Path('datos_revision/historico.json')
LEGACY = Path('datos_revision/historico_nuevos.json')
GAMES = ('euromillones','primitiva','bonoloto','loteria_nacional','gordo_primitiva','eurodreams','quiniela','quinigol','lototurf','quintuple_plus')

def main():
    if not MAIN.exists():
        raise SystemExit('Falta historico.json: no se crea uno vacío para evitar pérdida de datos')
    base = json.loads(MAIN.read_text(encoding='utf-8'))
    if base.get('version') != '0.49' or base.get('publicable') is not False or not isinstance(base.get('juegos'),dict):
        raise SystemExit('Formato principal inesperado')
    if set(base['juegos']) != set(GAMES):
        raise SystemExit('La lista de juegos del histórico principal no coincide')
    if not LEGACY.exists():
        print('Histórico secundario ausente; el principal ya es la única fuente')
        return
    extra = json.loads(LEGACY.read_text(encoding='utf-8'))
    if extra.get('version') != '0.60' or extra.get('publicable') is not False or not isinstance(extra.get('juegos'),dict):
        raise SystemExit('Formato del histórico secundario inesperado')
    added=0
    for game, draws in extra['juegos'].items():
        if game not in GAMES or not isinstance(draws,dict):
            raise SystemExit('Juego desconocido en histórico secundario')
        for day, record in draws.items():
            old=base['juegos'][game].get(day)
            if old is None:
                base['juegos'][game][day]=record
                added+=1
            elif old == record or (isinstance(old,dict) and old.get('combinacion')==record.get('combinacion') and record.get('combinacion') is not None):
                pass
            else:
                raise SystemExit(f'Conflicto {game} {day}: no se ha escrito ningún archivo')
    if added:
        MAIN.write_text(json.dumps(base,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(f'Unificación: {added} sorteos añadidos; histórico secundario conservado')

if __name__=='__main__':
    main()
