#!/usr/bin/env python3
"""LotoScan 0.87I: archivo PROVISIONAL de resultados SELAE; nunca publica premios.

Requiere scripts/actualizar_resultados_selae_087f.py y
scripts/validar_resultados_selae_087h.py. Escribe exclusivamente
 datos/selae_provisional/historico_provisional.json.
"""
import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'datos' / 'selae_provisional' / 'historico_provisional.json'


def load(name, filename):
    path = ROOT / 'scripts' / filename
    if not path.is_file():
        raise RuntimeError(f'Dependencia ausente: {path}')
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def canonical(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def digest(obj):
    return hashlib.sha256(canonical(obj).encode('utf-8')).hexdigest()


def initial():
    return {'esquema': 1, 'tipo': 'archivo_provisional_no_publicable', 'registros': []}


def read_store(path):
    if not path.exists():
        return initial()
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict) or data.get('esquema') != 1 or not isinstance(data.get('registros'), list):
        raise RuntimeError('Histórico provisional incompatible: no se sobrescribe')
    keys = set()
    for r in data['registros']:
        if not isinstance(r, dict) or not all(k in r for k in ('juego', 'id_sorteo', 'fecha', 'revisiones')):
            raise RuntimeError('Registro provisional mal formado: no se sobrescribe')
        key = (r['juego'], r['id_sorteo'])
        if key in keys or not isinstance(r['revisiones'], list) or not r['revisiones']:
            raise RuntimeError('Duplicado o revisiones inválidas: no se sobrescribe')
        keys.add(key)
    return data


def apply(store, item, code, day, warnings, now):
    key = (code, str(item['id_sorteo']))
    sha = digest(item)
    for row in store['registros']:
        if (row['juego'], row['id_sorteo']) == key:
            if row['fecha'] != day.isoformat():
                return 'conflicto_identidad'
            if row['revisiones'][-1]['sha256'] == sha:
                return 'sin_cambios'
            # Conserva revisiones anteriores: un cambio de SELAE no borra la evidencia.
            row['revisiones'].append({'sha256': sha, 'detectado_utc': now, 'datos_oficiales': item,
                                      'advertencias': warnings, 'publicable': False})
            return 'revision_nueva'
    store['registros'].append({'juego': code, 'id_sorteo': key[1], 'fecha': day.isoformat(),
                               'revisiones': [{'sha256': sha, 'detectado_utc': now,
                                              'datos_oficiales': item, 'advertencias': warnings,
                                              'publicable': False}]})
    return 'nuevo'


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--dias', type=int, default=4)
    p.add_argument('--fecha-fin', default='', help='AAAAMMDD; por defecto hoy en España')
    p.add_argument('--escribir', action='store_true', help='Persistir SOLO histórico provisional')
    p.add_argument('--offline-dir', default='', help='Directorio con JSON oficiales para prueba sin red')
    args = p.parse_args()
    if not 1 <= args.dias <= 14:
        p.error('El intervalo debe ser 1-14 días')
    try:
        end = dt.datetime.strptime(args.fecha_fin, '%Y%m%d').date() if args.fecha_fin else dt.datetime.now(ZoneInfo('Europe/Madrid')).date()
    except ValueError:
        p.error('Fecha incorrecta')
    sondeo = load('lotoscan_sondeo_087f', 'actualizar_resultados_selae_087f.py')
    audit = load('lotoscan_auditoria_087h', 'validar_resultados_selae_087h.py')
    store = read_store(DEST)
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    report = {'version': '0.87I', 'inicio_utc': now, 'escritura_provisional_habilitada': args.escribir,
              'historico_publico_modificado': False, 'validacion_premios_definitiva': False,
              'consultas': [], 'resumen': {}}
    counts = {}
    offline = Path(args.offline_dir) if args.offline_dir else None
    for offset in range(args.dias):
        day = end - dt.timedelta(days=offset)
        for _, code in sondeo.GAMES:
            endpoint = 'fecha2' if code == 'LNAC' else 'fechav3'
            url = f'{sondeo.BASE}/servicios/{endpoint}?' + urlencode({'game_id': code, 'fecha_sorteo': day.strftime('%Y%m%d')})
            if offline:
                f = offline / f'{day:%Y%m%d}_{code}.json'
                if not f.exists():
                    continue
                raw = f.read_bytes()
                net = {'http': 200, 'modo': 'offline'}
            else:
                net, raw = sondeo.get(url)
            result = {'juego': code, 'fecha': day.isoformat(), 'http': net.get('http')}
            if raw is None or net.get('http') != 200:
                result['estado'] = 'error_red'
            else:
                status, item, issues = sondeo.evaluate(raw, code, day)
                if item is None:
                    result['estado'] = status
                elif issues:
                    result.update(estado='rechazado_basico', errores=issues)
                else:
                    errors, warnings, evidence = audit.validate(item, code, day)
                    if errors:
                        result.update(estado='rechazado_auditoria', errores=errors)
                    else:
                        result['estado'] = apply(store, item, code, day, warnings, now)
                        result['id_sorteo'] = str(item['id_sorteo'])
                        result['publicable'] = False
            counts[result['estado']] = counts.get(result['estado'], 0) + 1
            report['consultas'].append(result)
            print(f"{result['fecha']} {code}: {result['estado']}")
    store['registros'].sort(key=lambda x: (x['fecha'], x['juego'], x['id_sorteo']))
    report['resumen'] = {'estados': counts, 'registros_provisionales': len(store['registros']),
                         'revisiones_totales': sum(len(x['revisiones']) for x in store['registros'])}
    Path('informe_selae_087i.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    Path('informe_selae_087i.txt').write_text('LotoScan 0.87I — archivo PROVISIONAL, NO PUBLICABLE\n' +
        json.dumps(report['resumen'], ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if args.escribir:
        DEST.parent.mkdir(parents=True, exist_ok=True)
        tmp = DEST.with_suffix('.json.tmp')
        tmp.write_text(json.dumps(store, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        os.replace(tmp, DEST)
        print(f'Actualizado únicamente {DEST.relative_to(ROOT)}')
    else:
        print('Simulación: ningún archivo persistente modificado')


if __name__ == '__main__':
    main()
