#!/usr/bin/env python3
"""LotoScan 0.93: auditoría de perfil SELAE sábado, solo lectura.

No calcula premios totales, no altera el histórico y no autoriza publicación.
"""
import argparse
import datetime as dt
import hashlib
import json
import pathlib
import re
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = 'https://www.loteriasyapuestas.es'
OUT = pathlib.Path('informes/093')
EXTRACTIONS = {
    'extraccionesDeCincoCifras': 5,
    'extraccionesDeCuatroCifras': 4,
    'extraccionesDeTresCifras': 3,
    'extraccionesDeDosCifras': 2,
    'reintegros': 1,
}
HEADERS = {'User-Agent': 'LotoScan/0.93 (auditoria tecnica de resultados publicos)',
           'Accept': 'application/json, text/plain, */*'}


def request_json(endpoint, params):
    url = BASE + endpoint + ('?' + urllib.parse.urlencode(params) if params else '')
    result = {'url': url, 'http': None, 'error': None}
    for attempt in range(2):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=25) as resp:
                result['http'] = resp.status
                result['content_type'] = resp.headers.get('Content-Type', '')
                raw = resp.read(1_000_001)
            if len(raw) > 1_000_000:
                raise ValueError('Respuesta demasiado grande')
            obj = json.loads(raw.decode('utf-8-sig'))
            if not isinstance(obj, dict):
                raise ValueError('JSON no es un objeto: ' + str(obj)[:120])
            result['sha256'] = hashlib.sha256(raw).hexdigest()
            return result, obj
        except urllib.error.HTTPError as e:
            result['http'] = e.code
            result['error'] = 'HTTP ' + str(e.code)
            if e.code not in (429, 500, 502, 503, 504) or attempt:
                break
        except (OSError, ValueError, UnicodeError) as e:
            result['error'] = type(e).__name__ + ': ' + str(e)[:200]
            break
        time.sleep(2)
    return result, None


def audit(obj, expected_id=None):
    issues = []
    general = obj.get('tipoSorteoGeneral')
    specific = obj.get('tipoSorteo')
    sid = str(obj.get('drawIdSorteo', ''))
    date = str(obj.get('fechaSorteo', ''))
    if expected_id and sid != expected_id:
        issues.append('ID distinto al solicitado')
    if general != 'S':
        issues.append('No es un sorteo de sábado (tipoSorteoGeneral != S)')
    if not re.match(r'^\d{4}-\d{2}-\d{2}T', date):
        issues.append('Fecha no reconocida')
    if not re.fullmatch(r'\d+', sid):
        issues.append('Identificador no válido')
    summary = {'id_sorteo': sid, 'fecha_sorteo': date, 'tipo_sorteo': specific,
               'tipo_sorteo_general': general, 'nombre_sorteo': obj.get('nombreDelSorteo'),
               'precio_decimo': obj.get('precioDecimo'), 'premios': {}, 'extracciones': {},
               'incidencias': issues, 'publicable': False}
    for key in ('primerPremio', 'segundoPremio', 'premioEspecial'):
        value = obj.get(key)
        if value is None:
            summary['premios'][key] = None
            if key in ('primerPremio', 'segundoPremio'):
                issues.append(key + ' ausente')
            continue
        if not isinstance(value, dict):
            issues.append(key + ' no es objeto')
            continue
        number = value.get('decimo')
        amount = value.get('prize')
        summary['premios'][key] = {'numero': number, 'importe_original': amount,
                                   'tipo_premio': value.get('prizeType')}
        if key != 'premioEspecial' and not (isinstance(number, str) and re.fullmatch(r'\d{5}', number)):
            issues.append(key + ' número no válido')
        if amount is not None and (type(amount) is not int or amount < 0):
            issues.append(key + ' importe no válido')
    for key, width in EXTRACTIONS.items():
        entries = obj.get(key, [])
        if not isinstance(entries, list):
            issues.append(key + ' no es lista')
            continue
        vals = []
        amounts = set()
        for idx, entry in enumerate(entries):
            if not isinstance(entry, dict):
                issues.append(key + ' elemento no es objeto')
                continue
            num = entry.get('decimo')
            amount = entry.get('prize')
            if not isinstance(num, str) or not re.fullmatch(r'\d{' + str(width) + r'}', num):
                issues.append(key + ' formato incorrecto en posición ' + str(idx))
            vals.append(num)
            if type(amount) is int and amount >= 0:
                amounts.add(amount)
            else:
                issues.append(key + ' importe inválido')
        if len(vals) != len(set(vals)):
            issues.append(key + ' números repetidos; revisar si el sorteo admite duplicidad')
        summary['extracciones'][key] = {'cantidad': len(entries), 'numeros': vals,
                                       'importes_originales_distintos': sorted(amounts)}
    summary['estructura_minima_coherente'] = not issues
    summary['validacion_normativa_completa'] = False
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--idsorteo', default='1328609092', help='ID de sábado conocido, 14/11/2026')
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    report = {'version': '0.93', 'fecha_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
              'objetivo': 'Caracterizar el JSON oficial de sábado sin extrapolar tarifas de jueves',
              'publicacion_premios': False, 'historico_modificado': False, 'consultas': [],
              'perfiles': [], 'advertencias': [
                  'La coherencia estructural no demuestra la exactitud del cálculo económico.',
                  'No se han validado aproximaciones, centenas, terminaciones, acumulación ni premios especiales.',
                  'Los importes se conservan en unidades originales; conversión y reglas pendientes de contraste oficial.'
              ]}
    tasks = [('sabado_historico', '/servicios/resultados2', {'idsorteo': args.idsorteo}, args.idsorteo),
             ('ultimo_disponible', '/servicios/resultados1', {}, None)]
    for label, endpoint, params, expected in tasks:
        info, obj = request_json(endpoint, params)
        info['etiqueta'] = label
        report['consultas'].append(info)
        if obj is None:
            continue
        (OUT / (label + '_original.json')).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')
        profile = audit(obj, expected)
        profile['fuente'] = label
        report['perfiles'].append(profile)
        print(label, 'id:', profile['id_sorteo'], 'tipo:', profile['tipo_sorteo_general'],
              'incidencias:', len(profile['incidencias']))
    # Contrastamos el sábado del 14/11 solo si SELAE ha devuelto ese sorteo concreto.
    known = next((x for x in report['perfiles'] if x['fuente'] == 'sabado_historico'
                  and x['id_sorteo'] == '1328609092'), None)
    if known:
        expected = {'primerPremio': ('75409', 6000000), 'segundoPremio': ('38422', 1200000)}
        checks = {}
        for name, (number, amount) in expected.items():
            prize = known['premios'].get(name) or {}
            checks[name] = prize.get('numero') == number and prize.get('importe_original') == amount
        report['contraste_sabado_14112026'] = {'referencia': 'Respuesta SELAE recuperada en 0.87X',
                                              'comprobaciones': checks, 'coincide': all(checks.values())}
    else:
        report['contraste_sabado_14112026'] = {'disponible': False,
                                              'motivo': 'No se obtuvo el JSON histórico correspondiente'}
    report['estado'] = 'datos_obtenidos' if report['perfiles'] else 'sin_datos_consultables'
    (OUT / 'auditoria_sabado_093.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Informe:', OUT / 'auditoria_sabado_093.json')
    # No forzamos fallo por HTTP 406 histórico: el informe permite analizar la incidencia.
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
