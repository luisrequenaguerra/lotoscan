#!/usr/bin/env python3
"""LotoScan 0.87L: pruebas de cálculo de apuestas simples con JSON oficial.
No publica ni altera históricos. Los boletos de prueba son SINTÉTICOS.
"""
import argparse
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / 'datos/selae_provisional/historico_provisional.json'
SUPPORTED = {'BONO', 'LAPR', 'EMIL', 'ELGR', 'QGOL'}
ALL = {'BONO','LAPR','EMIL','ELGR','EDMS','LNAC','LAQU','QGOL','LOTU','QUPL'}


def amount(x):
    try:
        v = Decimal(str(x).replace('.', '').replace(',', '.'))
        if not v.is_finite() or v < 0: raise ValueError('importe negativo/no finito')
        return v
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f'importe inválido: {x!r}') from exc


def split_main(text, count):
    parts = str(text).split('C(')[0].split('R(')[0]
    values = [int(s.strip()) for s in parts.split('-')]
    if len(values) < count: raise ValueError('combinación incompleta')
    return values[:count]


def extra(text, label):
    m = re.search(r'\b' + re.escape(label) + r'\((\d+)\)', str(text))
    if not m: raise ValueError(f'falta {label}')
    return int(m.group(1))


def prizes(draw):
    rows = draw.get('escrutinio')
    if not isinstance(rows, list) or not rows: raise ValueError('escrutinio ausente')
    for r in rows:
        if not isinstance(r, dict) or 'premio' not in r: raise ValueError('categoría incompleta')
        amount(r['premio'])
    return rows


def row_by_category(rows, category):
    matches = [r for r in rows if r.get('categoria') == category]
    if len(matches) != 1: raise ValueError(f'categoría {category} ambigua o ausente')
    return matches[0]


def row_by_regex(rows, pattern):
    matches = [r for r in rows if re.search(pattern, str(r.get('tipo','')), re.I)]
    if len(matches) != 1: raise ValueError(f'categoría ambigua/ausente: {pattern}')
    return matches[0]


def check(draw, ticket):
    """Resultado de un boleto simple SINTÉTICO. No equivale a autorización para publicar."""
    code = draw['game_id']
    if code not in SUPPORTED: return {'estado':'no_implementado','motivo':'motor pendiente'}
    rows = prizes(draw)
    if code == 'QGOL':
        winning = [s.strip().upper() for s in draw['combinacion'].split('-')]
        guess = ticket['pronosticos']
        if len(winning)!=6 or len(guess)!=6 or any(not re.fullmatch(r'[012M]{2}', x.upper()) for x in winning+guess):
            raise ValueError('marcadores Quinigol inválidos')
        hits = sum(a == b.upper() for a,b in zip(winning,guess))
        category = {6:1,5:2,4:3,3:4,2:5}.get(hits)
        prize = amount(row_by_category(rows,category)['premio']) if category else Decimal(0)
        return {'estado':'calculado_en_pruebas','aciertos':hits,'categoria':category,'premio_eur':str(prize)}

    count = {'BONO':6,'LAPR':6,'EMIL':5,'ELGR':5}[code]
    win = split_main(draw['combinacion'], count)
    nums = ticket['numeros']
    limits = {'BONO':49,'LAPR':49,'EMIL':50,'ELGR':54}
    if len(win)!=count or len(set(win))!=count or any(x<1 or x>limits[code] for x in win):
        raise ValueError('combinación oficial inválida')
    if len(nums)!=count or len(set(nums))!=count or any(type(x) is not int or x<1 or x>limits[code] for x in nums):
        raise ValueError('apuesta inválida')
    hits = len(set(win)&set(nums))
    parts = []
    if code in ('BONO','LAPR'):
        comp, refund = extra(draw['combinacion'],'C'), extra(draw['combinacion'],'R')
        if comp in win or not (1<=comp<=49 and 0<=refund<=9): raise ValueError('extras oficiales inválidos')
        if type(ticket.get('reintegro')) is not int or not 0<=ticket['reintegro']<=9:
            raise ValueError('reintegro del boleto ausente/inválido')
        has_c = comp in nums
        cat = {6:1,5:2 if has_c else 3,4:4,3:5}.get(hits) if code=='BONO' else {6:2,5:3 if has_c else 4,4:5,3:6}.get(hits)
        if code=='LAPR' and hits==6 and ticket['reintegro']==refund: cat=1
        if cat:
            r=row_by_category(rows,cat);parts.append({'concepto':str(r['tipo']).strip(),'euros':str(amount(r['premio']))})
        if ticket['reintegro']==refund:
            r=row_by_regex(rows,r'^\s*Reintegro\s*$')
            # En Primitiva especial (6+R), no añadir un reintegro sin verificar acumulación reglamentaria.
            if code=='LAPR' and cat==1:
                return {'estado':'pendiente_regla_acumulacion','aciertos':hits,'motivo':'6+R: comprobar acumulación del reintegro'}
            parts.append({'concepto':'Reintegro','euros':str(amount(r['premio']))})
        if code=='LAPR' and ticket.get('participa_joker'):
            return {'estado':'pendiente_joker','aciertos':hits,'motivo':'Joker requiere evaluación separada de siete cifras'}
    elif code=='ELGR':
        key=extra(draw['combinacion'],'R')
        if not 0<=key<=9 or type(ticket.get('clave')) is not int or not 0<=ticket['clave']<=9:
            raise ValueError('clave ausente/inválida')
        same=ticket['clave']==key
        cat={(5,True):1,(5,False):2,(4,True):3,(4,False):4,(3,True):5,(3,False):6,(2,True):7,(2,False):8}.get((hits,same))
        if cat:
            r=row_by_category(rows,cat);parts.append({'concepto':r['tipo'].strip(),'euros':str(amount(r['premio']))})
        if hits<2 and same:
            r=row_by_regex(rows,r'^\s*Reintegro\s*$');parts.append({'concepto':'Reintegro','euros':str(amount(r['premio']))})
    else:  # EMIL
        winning_stars=split_main(draw['combinacion'],7)[5:7]
        stars=ticket.get('estrellas')
        if len(stars or [])!=2 or len(set(stars))!=2 or any(type(x) is not int or not 1<=x<=12 for x in stars):
            raise ValueError('estrellas inválidas')
        shits=len(set(winning_stars)&set(stars))
        pattern=rf'\b{hits}\s*\+\s*{shits}\s*$'
        found=[r for r in rows if re.search(pattern,str(r.get('tipo','')))]
        if len(found)>1: raise ValueError('categoría ambigua')
        if found: parts.append({'concepto':found[0]['tipo'].strip(),'euros':str(amount(found[0]['premio']))})
        million=draw.get('millon')
        if not isinstance(million,dict) or not million.get('combinacion'):
            return {'estado':'pendiente_el_millon','aciertos':hits,'motivo':'falta código oficial El Millón'}
        if not ticket.get('codigo_el_millon'):
            return {'estado':'pendiente_el_millon','aciertos':hits,'motivo':'falta código del resguardo'}
        if ticket['codigo_el_millon'].strip().upper()==million['combinacion'].strip().upper():
            if not isinstance(draw.get('escrutinio_millon'),list) or len(draw['escrutinio_millon'])!=1:
                raise ValueError('escrutinio El Millón incompleto')
            parts.append({'concepto':'El Millón','euros':str(amount(draw['escrutinio_millon'][0]['premio']))})
    total=sum((Decimal(x['euros']) for x in parts),Decimal(0))
    return {'estado':'calculado_en_pruebas','aciertos':hits,'componentes':parts,'premio_eur':str(total)}


def records(data):
    if isinstance(data,dict) and isinstance(data.get('registros'),list):
        for r in data['registros']:
            revisions=r.get('revisiones') or []
            if revisions and isinstance(revisions[-1].get('datos_oficiales'),dict):
                yield revisions[-1]['datos_oficiales']
    elif isinstance(data,list):
        for r in data:
            if isinstance(r,dict): yield r
    else: raise ValueError('histórico incompatible')


def synthetic(draw):
    code=draw['game_id']
    if code=='QGOL':
        win=[s.strip() for s in draw['combinacion'].split('-')]
        if len(win)!=6: raise ValueError('seis marcadores requeridos')
        lose=['00' if x!='00' else '11' for x in win]
        return [('pleno_sintetico',{'pronosticos':win}),('cero_sintetico',{'pronosticos':lose})]
    n={'BONO':6,'LAPR':6,'EMIL':5,'ELGR':5}[code]
    win=split_main(draw['combinacion'],n)
    base={'numeros':win}
    if code in ('BONO','LAPR'):base['reintegro']=extra(draw['combinacion'],'R')
    if code=='ELGR':base['clave']=extra(draw['combinacion'],'R')
    if code=='EMIL':
        base['estrellas']=split_main(draw['combinacion'],7)[5:7]
        base['codigo_el_millon']=draw['millon']['combinacion']
    return [('pleno_sintetico',base)]


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--historico',default=str(DEFAULT))
    ap.add_argument('--muestras-dir',default='',help='Carpeta opcional de JSON oficiales para pruebas locales')
    args=ap.parse_args()
    draws=[]
    if args.muestras_dir:
        for f in sorted(Path(args.muestras_dir).glob('*.json')):
            draws.extend(records(json.loads(f.read_text(encoding='utf-8'))))
    else:
        path=Path(args.historico)
        if not path.is_file(): raise SystemExit(f'Histórico no encontrado: {path}')
        draws=list(records(json.loads(path.read_text(encoding='utf-8'))))
    report={'version':'0.87L','fecha_utc':datetime.now(timezone.utc).isoformat(),
            'modo':'PRUEBAS_SINTETICAS_NO_PUBLICABLE','historico_modificado':False,
            'juegos_implementados_parcialmente':sorted(SUPPORTED),
            'juegos_pendientes':sorted(ALL-SUPPORTED),'pruebas':[]}
    failures=0
    for draw in draws:
        code=draw.get('game_id','?'); item={'juego':code,'id_sorteo':draw.get('id_sorteo'),'casos':[]}
        if code not in SUPPORTED:
            item['estado']='motor_pendiente';report['pruebas'].append(item);continue
        try:
            for name,ticket in synthetic(draw):
                item['casos'].append({'nombre':name,'resultado':check(draw,ticket)})
            item['estado']='ejecutado'
        except Exception as exc:
            failures+=1;item['estado']='error';item['error']=str(exc)
        report['pruebas'].append(item)
    report['resumen']={'sorteos':len(draws),'motores_ejecutados':sum(x['estado']=='ejecutado' for x in report['pruebas']),
                       'pendientes':sum(x['estado']=='motor_pendiente' for x in report['pruebas']), 'errores':failures,
                       'publicables':0}
    Path('informe_premios_087l.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    Path('informe_premios_087l.txt').write_text(json.dumps(report['resumen'],ensure_ascii=False,indent=2)+'\nNo publica ni modifica el histórico. Boletos sintéticos.\n',encoding='utf-8')
    print(json.dumps(report['resumen'],ensure_ascii=False))
    if failures: raise SystemExit(1)

if __name__=='__main__': main()
