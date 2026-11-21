#!/usr/bin/env python3
"""LotoScan 1.31: normaliza histórico oficial SELAE SIN calcular premios.
Fuente exclusiva: archivos actual.json creados por 1.30.1 (fechav3/fecha2).
No modifica históricos ni el tratamiento independiente de Navidad.
"""
import argparse
import datetime as dt
import json
import re
from pathlib import Path

GAMES={'EMIL','LAPR','BONO','ELGR','EDMS','LNAC','LAQU','QGOL','LOTU','QUPL'}

def money(value):
    if value is None or isinstance(value,bool): return None
    s=str(value).strip().replace('€','').replace(' ','')
    if not s or s.lower() in ('none','null','-'): return None
    if ',' in s: s=s.replace('.','').replace(',','.')
    try:
        from decimal import Decimal, InvalidOperation
        d=Decimal(s)
        if not d.is_finite() or d<0: return None
        return format(d,'f')
    except (InvalidOperation,ValueError): return None

def category(rows):
    if not isinstance(rows,list): return []
    out=[]
    for row in rows:
        if not isinstance(row,dict): continue
        out.append({'categoria':row.get('categoria'), 'tipo':row.get('tipo'),
                    'premio_eur':money(row.get('premio')),
                    'ganadores':row.get('ganadores'),
                    'ganadores_eu':row.get('ganadores_eu')})
    return out

def numbers(text):
    if not isinstance(text,str): return None
    return [int(n) for n in re.findall(r'\d+',text)]

def combination(item,game):
    c=item.get('combinacion')
    if game=='LNAC':
        if not isinstance(c,dict): return None
        return {'primer_premio':c.get('primer_premio'),'segundo_premio':c.get('Segundo_premio'),
                'reintegros':item.get('reintegros')}
    if not isinstance(c,str) or not c.strip(): return None
    if game in ('LAQU','QGOL'):
        return {'signos': [x.strip() for x in c.split('-')], 'partidos':item.get('partidos')}
    core=c.split('C(')[0].split('R(')[0]
    main=[int(x) for x in re.findall(r'\d+',core)]
    complement=re.search(r'C\((\d+)\)',c)
    refund=re.search(r'R\((\d+)\)',c)
    return {'numeros':main,'complementario':int(complement.group(1)) if complement else None,
            'reintegro_o_clave':int(refund.group(1)) if refund else None,'texto_original':c}

def normalize(item,folder):
    if not isinstance(item,dict): raise ValueError('no es objeto JSON')
    game=item.get('game_id'); draw=str(item.get('id_sorteo',''))
    if game not in GAMES or game!=folder: raise ValueError('game_id no coincide con carpeta')
    if not re.fullmatch(r'\d{6,20}',draw): raise ValueError('id_sorteo inválido')
    date=str(item.get('fecha_sorteo',''))
    try: dt.datetime.strptime(date[:10],'%Y-%m-%d')
    except ValueError: raise ValueError('fecha_sorteo inválida')
    comb=combination(item,game)
    escr=category(item.get('escrutinio'))
    extras={}
    if game=='EMIL':
        extras={'el_millon':item.get('millon'),'escrutinio_el_millon':category(item.get('escrutinio_millon'))}
    if game=='LAPR':
        extras={'joker':item.get('joker'),'escrutinio_joker':category(item.get('escrutinio_joker'))}
    if game=='LAQU':
        extras={'jornada':item.get('jornada'),'temporada':item.get('temporada'),
                'elige8':item.get('elige8'),'escrutinio_elige8':category(item.get('escrutinioElige8'))}
    if game=='EDMS': extras={'numero_sueno_incluido_en_combinacion':comb is not None}
    if game in ('QGOL','QUPL'): extras.update({'jornada':item.get('jornada'),'temporada':item.get('temporada')})
    problems=[]
    if comb is None: problems.append('combinacion_ausente_o_no_interpretable')
    if not escr: problems.append('escrutinio_ausente')
    if game=='LAQU' and (not extras['elige8'] or not extras['escrutinio_elige8']): problems.append('elige8_incompleto')
    if game=='LNAC': problems.append('premios_loteria_nacional_no_calculados')
    if game in ('EMIL','LAPR') and not extras.get('el_millon',extras.get('joker')):
        problems.append('juego_asociado_no_disponible')
    return {'esquema':'lotoscan.resultado.normalizado.v1','game_id':game,'id_sorteo':draw,
            'fecha_sorteo':date,'combinacion':comb,'escrutinio':escr,'complementos':extras,
            'estado_datos':'pendiente' if problems else 'estructura_disponible',
            'incidencias':problems,'premios_verificados':False,'publicable':False,
            'fuente':'historico oficial SELAE fechav3/fecha2','origen':'actual.json'}

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--historico',default='datos/lotoscan/historico_oficial')
    p.add_argument('--salida',default='datos/lotoscan/resultados_normalizados')
    p.add_argument('--informe',default='salida_131')
    args=p.parse_args()
    hist=Path(args.historico);out=Path(args.salida);report=Path(args.informe)
    report.mkdir(parents=True,exist_ok=True)
    results={'version':'1.31','archivos':0,'normalizados':0,'sin_cambios':0,'errores':[], 'por_juego':{},
             'premios_verificados':False,'publicable':False}
    for file in sorted(hist.glob('*/[0-9]*/actual.json')):
        results['archivos']+=1
        try:
            normalized=normalize(json.loads(file.read_text(encoding='utf-8')),file.parent.parent.name)
            target=out/normalized['game_id']/(normalized['id_sorteo']+'.json')
            content=json.dumps(normalized,ensure_ascii=False,indent=2,sort_keys=True)+'\n'
            if target.exists() and target.read_text(encoding='utf-8')==content:
                results['sin_cambios']+=1
            else:
                target.parent.mkdir(parents=True,exist_ok=True);target.write_text(content,encoding='utf-8')
                results['normalizados']+=1
            g=results['por_juego'].setdefault(normalized['game_id'],{'total':0,'pendientes':0})
            g['total']+=1;g['pendientes']+=normalized['estado_datos']=='pendiente'
        except (ValueError,KeyError,TypeError,OSError,json.JSONDecodeError) as e:
            results['errores'].append({'archivo':str(file),'error':str(e)})
    (report/'informe_131.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(results,ensure_ascii=False,indent=2))
    if not results['archivos']: raise SystemExit('No hay archivos actual.json: verificar commit del histórico 1.30.1')
    if results['errores']: raise SystemExit('Algunos registros no pudieron normalizarse; revisar informe_131.json')

if __name__=='__main__': main()
