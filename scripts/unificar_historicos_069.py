"""Unificación conservadora LotoScan: incorpora únicamente datos ausentes y compatibles.

No descarga resultados, no valida premios de Joker y nunca cambia un dato existente.
Ante conflicto, no escribe el histórico. Mantiene historico_nuevos.json intacto.
"""
import json
import os
import tempfile
from pathlib import Path

MAIN = Path('datos_revision/historico.json')
LEGACY = Path('datos_revision/historico_nuevos.json')
GAMES = ('euromillones','primitiva','bonoloto','loteria_nacional','gordo_primitiva','eurodreams','quiniela','quinigol','lototurf','quintuple_plus')
IDENTITY = ('fecha','numero_sorteo','numeros','estrellas','complementario','reintegro','joker','el_millon','combinacion')
# Campos de premios permitidos para enriquecimiento; nunca se añaden metadatos de verificación automáticamente.
PRIZE_FIELDS = ('categorias','premios_parciales','premios_completos','joker_categorias','joker_premios','joker_premios_validados')


def merge_missing(old, new, path):
    """Une valores ausentes, pero no cambia valores no nulos ni acepta discrepancias."""
    if old is None:
        return new, True
    if new is None or old == new:
        return old, False
    if isinstance(old, dict) and isinstance(new, dict):
        result = dict(old)
        changed = False
        for key, value in new.items():
            if key not in result:
                result[key] = value
                changed = True
            else:
                result[key], updated = merge_missing(result[key], value, path + '.' + key)
                changed |= updated
        return result, changed
    raise ValueError(f'Conflicto en {path}: se conservan los datos anteriores')


def merge_record(game, day, old, new):
    if not isinstance(old, dict) or not isinstance(new, dict):
        raise ValueError(f'Registro inválido {game}/{day}')
    # Comprobar la identidad antes de incorporar cualquier premio.
    for field in IDENTITY:
        if field in old and field in new and old[field] != new[field]:
            raise ValueError(f'Identidad incompatible {game}/{day}/{field}')
    # Exigir identidad compartida suficiente; fecha sola no basta.
    shared = [f for f in IDENTITY if f != 'fecha' and f in old and f in new]
    if not shared:
        raise ValueError(f'Identidad insuficiente {game}/{day}')
    merged = dict(old)
    changed = False
    for field in PRIZE_FIELDS:
        if field not in new:
            continue
        # No aceptar categorías Joker sin señal explícita de validación en la fuente nueva.
        if field in ('joker_categorias','joker_premios') and new.get('joker_premios_validados') is not True:
            continue
        if field == 'joker_premios_validados' and new[field] is not True:
            continue
        if field not in merged:
            merged[field] = new[field]
            changed = True
        elif field == 'joker_premios_validados' and merged[field] is False and new[field] is True:
            # Solo activar validación si se ha incorporado una tabla de premios Joker.
            if any(k in merged for k in ('joker_categorias','joker_premios')):
                merged[field] = True
                changed = True
        elif field != 'joker_premios_validados':
            merged[field], updated = merge_missing(merged[field], new[field], f'{game}/{day}/{field}')
            changed |= updated
    return merged, changed


def main():
    if not MAIN.exists():
        raise SystemExit('Falta historico.json; no se crea uno vacío')
    base = json.loads(MAIN.read_text(encoding='utf-8'))
    if base.get('version') != '0.49' or base.get('publicable') is not False or set(base.get('juegos', {})) != set(GAMES):
        raise SystemExit('Formato principal inesperado')
    if not LEGACY.exists():
        print('Histórico secundario ausente; sin cambios')
        return
    extra = json.loads(LEGACY.read_text(encoding='utf-8'))
    if extra.get('version') != '0.60' or extra.get('publicable') is not False or not isinstance(extra.get('juegos'), dict):
        raise SystemExit('Formato secundario inesperado')
    added = enriched = 0
    for game, draws in extra['juegos'].items():
        if game not in GAMES or not isinstance(draws, dict):
            raise SystemExit('Juego desconocido en histórico secundario')
        for day, record in draws.items():
            old = base['juegos'][game].get(day)
            if old is None:
                base['juegos'][game][day] = record
                added += 1
            else:
                merged, changed = merge_record(game, day, old, record)
                if changed:
                    base['juegos'][game][day] = merged
                    enriched += 1
    if added or enriched:
        MAIN.parent.mkdir(parents=True, exist_ok=True)
        fd, temp = tempfile.mkstemp(prefix='.historico-', suffix='.json', dir=MAIN.parent)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as output:
                json.dump(base, output, ensure_ascii=False, indent=2, sort_keys=True)
                output.write('\n')
            os.replace(temp, MAIN)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)
    print(f'Unificación: {added} sorteos añadidos; {enriched} enriquecidos; secundario conservado')


if __name__ == '__main__':
    main()
