#!/usr/bin/env python3
"""LotoScan 0.87M: auditoría de categorías sin acertantes y pruebas hipotéticas.
SOLO DIAGNÓSTICO. No verifica boletos reales ni publica premios.
"""
import argparse
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / 'datos/selae_provisional/historico_provisional.json'
GAMES = {'BONO','LAPR','EMIL','ELGR','EDMS','LNAC','LAQU','QGOL','LOTU','QUPL'}

def decimal_money(value):
    if isinstance(value, bool) or value is None:
        raise ValueError('importe no numérico')
    s = str(value).strip().replace(' ', '').replace('\u00a0','')
    if ',' in s:
        s = s.replace('.', '').replace(',', '.')
    try:
        n = Decimal(s)
    except InvalidOperation as exc:
        raise ValueError('importe ilegible') from exc
    if not n.is_finite() or n < 0:
        raise ValueError('importe negativo o no finito')
    return n

def integer_count(value):
    if isinstance(value, bool) or value is None:
        raise ValueError('recuento ausente')
    s = str(value).strip().replace('.', '').replace(' ', '')
    if not re.fullmatch(r'\d+', s):
        raise ValueError('recuento ilegible')
    return int(s)

def classify(row, game):
    label = str(row.get('tipo', '')).strip()
    prize = decimal_money(row['premio'])
    winners = integer_count(row['ganadores'])
    european = None
    if game == 'EMIL' and 'ganadores_eu' in row and row['ganadores_eu'] is not None:
        european = integer_count(row['ganadores_eu'])
    # Un cero no prueba por sí solo que exista bote o que sea un premio reglamentario cero.
    if winners == 0:
        state = 'sin_acertantes_en_ambito_reportado'
    elif prize == 0:
        state = 'acertantes_con_importe_cero_requiere_regla'
    else:
        state = 'importe_unitario_reportado'
    return {'categoria':row.get('categoria'), 'tipo':label, 'ganadores':winners,
            'ganadores_europeos':european, 'premio_unitario_eur':str(prize),
            'estado':state, 'importe_pagadero_para_boleto_hipotetico':False,
            'nota': ('El escrutinio describe apuestas realmente premiadas, no una apuesta inventada. '
                     'Si se crea una apuesta sintética de una categoría sin acertantes, es contrafactual.')}

def records(data):
    if isinstance(data,dict) and isinstance(data.get('registros'),list):
        for r in data['registros']:
            revisions = r.get('revisiones') or []
            if not revisions: continue
            item = revisions[-1].get('datos_oficiales')
            if isinstance(item,dict): yield item
    elif isinstance(data,list):
        for item in data:
            if isinstance(item,dict): yield item
    else:
        raise ValueError('formato de histórico incompatible')

def audit(draw):
    game = draw.get('game_id')
    if game not in GAMES: raise ValueError('juego desconocido')
    rows = draw.get('escrutinio')
    if not isinstance(rows,list) or not rows: raise ValueError('escrutinio ausente')
    result = []
    for idx,row in enumerate(rows):
        if not isinstance(row,dict): raise ValueError(f'fila {idx} no es objeto')
        try:
            result.append(classify(row,game))
        except (ValueError, KeyError) as exc:
            raise ValueError(f'fila {idx}: {exc}') from exc
    # No asumir que el escrutinio principal contiene todas las modalidades complementarias.
    return {'juego':game,'id_sorteo':draw.get('id_sorteo'), 'fecha':draw.get('fecha_sorteo'),
            'categorias':result,'resumen':{
                'categorias':len(result),
                'sin_acertantes':sum(r['estado']=='sin_acertantes_en_ambito_reportado' for r in result),
                'importe_cero_con_acertantes':sum(r['estado']=='acertantes_con_importe_cero_requiere_regla' for r in result),
                'premio_unitario_reportado':sum(r['estado']=='importe_unitario_reportado' for r in result)},
            'limitaciones':[
                'Las categorías sin acertantes no tienen premio pagadero demostrable con apuestas sintéticas',
                'Un premio cero con acertantes exige verificar reglas oficiales antes de interpretarlo',
                'Reintegros, categorías acumulables, Joker, El Millón y Elige8 requieren comprobación específica',
                'No autoriza comprobar boletos ni publicar resultados']}

def run(draws):
    report={'version':'0.87M','fecha_utc':datetime.now(timezone.utc).isoformat(),
            'modo':'AUDITORIA_NO_PUBLICABLE','historico_modificado':False,
            'publicables':0,'sorteos':[], 'errores':[]}
    seen=set()
    for d in draws:
        try:
            key=(d.get('game_id'),str(d.get('id_sorteo')))
            if key in seen: raise ValueError('sorteo duplicado')
            seen.add(key)
            report['sorteos'].append(audit(d))
        except Exception as exc:
            report['errores'].append({'juego':d.get('game_id'),'id_sorteo':d.get('id_sorteo'),'error':str(exc)})
    report['resumen']={'sorteos_auditados':len(report['sorteos']), 'errores':len(report['errores']),
                       'categorias_sin_acertantes':sum(s['resumen']['sin_acertantes'] for s in report['sorteos']),
                       'categorias_cero_con_acertantes':sum(s['resumen']['importe_cero_con_acertantes'] for s in report['sorteos']),
                       'publicables':0}
    return report

def selftest():
    cases=[({'tipo':'1ª','premio':'0','ganadores':'0'},'BONO','sin_acertantes_en_ambito_reportado'),
           ({'tipo':'10 aciertos','premio':'0,00','ganadores':'152115'},'LAQU','acertantes_con_importe_cero_requiere_regla'),
           ({'tipo':'1ª','premio':'1.533.262,18','ganadores':'1'},'BONO','importe_unitario_reportado'),
           ({'tipo':'1ª','premio':'0','ganadores':'0','ganadores_eu':'0'},'EMIL','sin_acertantes_en_ambito_reportado')]
    for row,game,expected in cases:
        assert classify(row,game)['estado']==expected
    for invalid in [{'tipo':'x','premio':'-1','ganadores':'2'}, {'tipo':'x','premio':'NaN','ganadores':'0'}, {'tipo':'x','premio':'2','ganadores':None}]:
        try: classify(invalid,'BONO')
        except (ValueError,KeyError): pass
        else: raise AssertionError('dato inválido aceptado')

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--historico',default=str(DEFAULT))
    parser.add_argument('--muestras-dir',default='')
    args=parser.parse_args()
    selftest()
    if args.muestras_dir:
        draws=[]
        for p in sorted(Path(args.muestras_dir).glob('*.json')):
            draws.extend(records(json.loads(p.read_text(encoding='utf-8'))))
    else:
        p=Path(args.historico)
        if not p.is_file(): raise SystemExit(f'Falta histórico: {p}')
        draws=list(records(json.loads(p.read_text(encoding='utf-8'))))
    report=run(draws)
    Path('informe_categorias_087m.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    Path('informe_categorias_087m.txt').write_text(json.dumps(report['resumen'],ensure_ascii=False,indent=2)+'\nAuditoría de categorías; no calcula premios de boletos.\n',encoding='utf-8')
    print(json.dumps(report['resumen'],ensure_ascii=False))
    if report['errores']: raise SystemExit(1)

if __name__=='__main__': main()
