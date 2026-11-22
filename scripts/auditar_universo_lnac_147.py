#!/usr/bin/env python3
"""LotoScan 1.47: exhaustively enumerate 00000..99999 for compatible ordinary LNAC draws.
Production input: archived SELAE JSON only. PDF-transcribed sample references are test fixtures.
Enumeration is NOT an independent certification of every monetary outcome.
"""
import argparse
import collections
import json
import pathlib
import sys
from comprobar_premios_lnac_145 import ORACULOS, calc, validate

DEFAULT_ROOT = 'datos/lotoscan/loteria_nacional/historico_completo'

def inspect(path):
    d = json.loads(path.read_text(encoding='utf-8'))
    validate(d)
    sid = str(d['drawIdSorteo'])
    if path.parent.name != sid:
        raise ValueError('ID de sorteo distinto del nombre de carpeta')
    expected = ORACULOS.get(sid, {})
    failures = []
    for number, amount in expected.items():
        got = calc(d, number)['importe_centimos']
        if got != amount * 100:
            failures.append({'numero':number,'esperado_centimos':amount*100,'calculado_centimos':got})
    counts = collections.Counter()
    reasons = collections.Counter()
    amounts = collections.Counter()
    total_cents = 0
    zero = 0
    min_positive = None
    max_prize = 0
    for n in range(100000):
        number = f'{n:05d}'
        result = calc(d, number)
        prize = result['importe_centimos']
        parts = result['desglose']
        if prize != sum(p['centimos'] for p in parts):
            failures.append({'numero':number,'error':'desglose no suma total'})
        if prize < 0 or prize % 100:
            failures.append({'numero':number,'error':'importe negativo o no entero en euros'})
        if prize == 0:
            zero += 1
        else:
            min_positive = prize if min_positive is None else min(min_positive,prize)
        max_prize = max(max_prize,prize)
        total_cents += prize
        amounts[prize] += 1
        counts[len(parts)] += 1
        for p in parts:
            reasons[p['concepto']] += 1
        if len(failures) >= 30:
            break
    full = sum(amounts.values()) == 100000
    if not full:
        failures.append({'error':'universo incompleto'})
    if amounts[d['primerPremio']['prize']] < 1:
        failures.append({'error':'no aparece primer premio en histograma'})
    if amounts[d['segundoPremio']['prize']] < 1:
        failures.append({'error':'no aparece segundo premio en histograma'})
    return {
        'sorteo':sid,'fecha':d.get('fechaSorteo'),'archivo':str(path),
        'numeros_evaluados':sum(amounts.values()),'premiados':100000-zero,'sin_premio':zero,
        'importe_total_100000_decimos_eur':total_cents/100,
        'importe_maximo_decimo_eur':max_prize/100,
        'importe_minimo_positivo_eur':None if min_positive is None else min_positive/100,
        'distribucion_importes_eur':{str(k/100):v for k,v in sorted(amounts.items())},
        'coincidencias_por_numero':dict(sorted(counts.items())),
        'frecuencia_conceptos':dict(sorted(reasons.items())),
        'referencias_oficiales':len(expected),
        'referencias_correctas':len(expected)-sum('esperado_centimos' in x for x in failures),
        'errores':failures,'universo_completo':full,
        'premios_verificados':False,'publicable':False,
        'alcance':'Enumeración completa del algoritmo, no contraste independiente de los 100000 premios',
    }

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--raiz',default=DEFAULT_ROOT)
    parser.add_argument('--informe',default='salida_147')
    args=parser.parse_args()
    out=pathlib.Path(args.informe);out.mkdir(parents=True,exist_ok=True)
    paths=sorted(pathlib.Path(args.raiz).glob('*/original_resultados.json'))
    draws=[];errors=[]
    if not paths:
        errors.append('No se encontraron JSON de sorteos')
    for path in paths:
        try:
            draws.append(inspect(path))
        except Exception as exc:
            errors.append({'archivo':str(path),'error':str(exc)})
    report={'version':'1.47','fuente':'JSON SELAE archivado','pdf_en_produccion':False,
            'sorteos':draws,'errores':errors,
            'total_numeros_evaluados':sum(x['numeros_evaluados'] for x in draws),
            'total_referencias':sum(x['referencias_oficiales'] for x in draws),
            'total_referencias_correctas':sum(x['referencias_correctas'] for x in draws),
            'premios_verificados':False,'publicable':False,
            'limitacion':'Las referencias oficiales son muestras, no 100000 importes oficiales independientes. No incluye premio especial por serie/fraccion ni sorteos extraordinarios.'}
    (out/'informe_147.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    summary={'sorteos':len(draws),'numeros':report['total_numeros_evaluados'],
             'referencias':report['total_referencias_correctas'],
             'errores':len(errors)+sum(len(x['errores']) for x in draws)}
    print(json.dumps(summary,ensure_ascii=False))
    return 1 if errors or any(x['errores'] for x in draws) else 0

if __name__=='__main__':sys.exit(main())
