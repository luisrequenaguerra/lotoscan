#!/usr/bin/env python3
"""LotoScan 0.87O: cinco motores adicionales en simulación, nunca publicables.
Lee el histórico provisional y genera casos sintéticos. No modifica datos.
"""
import argparse
import json
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HISTORY = ROOT / 'datos/selae_provisional/historico_provisional.json'
GAMES = {'EDMS','LNAC','LAQU','LOTU','QUPL'}

def number(x):
    try:
        v=Decimal(str(x).replace('.','').replace(',','.'))
        if not v.is_finite() or v<0: raise ValueError('importe inválido')
        return v
    except (InvalidOperation,ValueError,TypeError) as exc: raise ValueError(f'importe inválido: {x!r}') from exc

def rows(draw):
    out=draw.get('escrutinio')
    if not isinstance(out,list) or not out: raise ValueError('escrutinio ausente')
    return out

def award(draw,category=None,label=None):
    r=rows(draw)
    hits=[x for x in r if (x.get('categoria')==category if category is not None else str(x.get('tipo','')).strip().lower()==label.lower())]
    if len(hits)!=1: return {'estado':'pendiente_categoria_ambigua','categoria':category,'coincidencias':len(hits),'premio_eur':None}
    x=hits[0]; prize=number(x.get('premio'))
    try: winners=int(x['ganadores'])
    except (KeyError,ValueError,TypeError): return {'estado':'pendiente_ganadores','premio_eur':None}
    if winners<0: raise ValueError('ganadores negativos')
    if winners==0: state='categoria_sin_ganadores_apuesta_hipotetica'
    elif prize==0: state='importe_cero_requiere_regla'
    else: state='importe_unitario_oficial_no_pagadero_en_simulacion'
    return {'estado':state,'categoria':category,'tipo':x.get('tipo'),'ganadores':winners,
            'importe_unitario_reportado_eur':str(prize),'premio_eur':None}

def ints(text,count):
    raw=str(text).split('C(')[0].split('R(')[0]
    a=[int(v.strip()) for v in raw.split('-')]
    if len(a)!=count: raise ValueError('longitud de combinación incorrecta')
    return a

def extra(text,tag):
    m=re.search(r'\b'+re.escape(tag)+r'\((\d+)\)',str(text))
    if not m: raise ValueError('falta extra '+tag)
    return int(m.group(1))

def check(draw,ticket):
    game=draw['game_id']; combination=draw.get('combinacion')
    if game=='EDMS':
        win=ints(combination,6); dream=extra(combination,'C')
        nums=ticket['numeros']; t_dream=ticket['sueno']
        if len(set(win))!=6 or any(not 1<=v<=40 for v in win) or not 1<=dream<=5: raise ValueError('resultado EuroDreams inválido')
        if len(nums)!=6 or len(set(nums))!=6 or any(type(v)!=int or not 1<=v<=40 for v in nums) or type(t_dream)!=int or not 1<=t_dream<=5: raise ValueError('boleto EuroDreams inválido')
        h=len(set(nums)&set(win)); d=int(t_dream==dream)
        category={(6,1):1,(6,0):2}.get((h,d),{5:3,4:4,3:5,2:6}.get(h))
        return {'aciertos':h,'sueno':d,'categoria':category,'premio':award(draw,label=next((x['tipo'] for x in rows(draw) if re.search(r'\b'+str(h)+r'\s*\+\s*'+(str(d) if h==6 else '0/1')+r'\b',str(x.get('tipo','')))),'')) if category else None}
    if game=='LOTU':
        win=ints(combination,6); horse=extra(combination,'C'); refund=extra(combination,'R')
        nums=ticket['numeros']; th=ticket['caballo']; tr=ticket['reintegro']
        if len(set(win))!=6 or any(not 1<=x<=49 for x in win) or not 1<=horse<=99 or not 0<=refund<=9: raise ValueError('resultado Lototurf inválido')
        if len(nums)!=6 or len(set(nums))!=6 or any(type(x)!=int or not 1<=x<=49 for x in nums) or type(th)!=int or not 1<=th<=99 or type(tr)!=int or not 0<=tr<=9: raise ValueError('boleto Lototurf inválido')
        h=len(set(win)&set(nums)); match=horse==th
        cat={(6,True):1,(6,False):2,(5,True):3,(5,False):4,(4,True):5,(4,False):6,(3,True):7}.get((h,match))
        return {'aciertos':h,'caballo':match,'categoria':cat,'premio':award(draw,cat) if cat else None,'reintegro':award(draw,8) if tr==refund else None,'nota':'La acumulación de categorías requiere contrastar el reglamento'}
    if game=='QUPL':
        win=ints(combination,5); second=extra(combination,'C'); guess=ticket['caballos']; tsecond=ticket['segundo_quinta']
        if len(win)!=5 or any(not 1<=v<=99 for v in win) or not 1<=second<=99: raise ValueError('resultado Quíntuple inválido')
        if len(guess)!=5 or any(type(v)!=int or not 1<=v<=99 for v in guess) or type(tsecond)!=int or not 1<=tsecond<=99: raise ValueError('boleto Quíntuple inválido')
        h=sum(a==b for a,b in zip(win,guess)); extra_hit=second==tsecond
        cat={(5,True):2,(5,False):3,(4,True):4,(4,False):5}.get((h,extra_hit))
        return {'aciertos':h,'segundo_quinta':extra_hit,'categoria':cat,'premio':award(draw,cat) if cat else None,'especial':'pendiente_regla_especial' if cat==2 else None}
    if game=='LAQU':
        win=[v.strip().upper() for v in str(combination).split('-')]
        guess=ticket['signos']; pleno=ticket.get('pleno')
        if len(win)!=15 or any(x not in ('1','X','2') for x in win[:14]) or not re.fullmatch(r'[012M]{2}',win[14]): raise ValueError('resultado Quiniela inválido')
        if len(guess)!=14 or any(x not in ('1','X','2') for x in guess): raise ValueError('boleto Quiniela inválido')
        h=sum(a==b for a,b in zip(win[:14],guess)); full=(h==14 and pleno==win[14]); cat=1 if full else {14:2,13:3,12:4,11:5,10:6}.get(h)
        return {'aciertos':h,'pleno':full,'categoria':cat,'premio':award(draw,cat) if cat else None,'elige8':'pendiente_motor_independiente' if ticket.get('elige8') else 'no_solicitado','nota':'Pleno al 15 y acumulación de categorías pendientes de contraste reglamentario'}
    if game=='LNAC':
        if not isinstance(combination,dict): raise ValueError('combinación Nacional no es objeto')
        first=str(combination.get('primer_premio','')).zfill(5); second=str(combination.get('Segundo_premio','')).zfill(5)
        ticket_num=str(ticket['numero']).zfill(5)
        if not all(re.fullmatch(r'\d{5}',x) for x in (first,second,ticket_num)): raise ValueError('número Nacional inválido')
        if ticket_num==first: result=award(draw,label='Primer Premio')
        elif ticket_num==second: result=award(draw,label='Segundo Premio')
        else: result={'estado':'pendiente_lista_completa_de_premios','premio_eur':None}
        return {'numero':ticket_num,'coincidencia_principal':ticket_num in (first,second),'premio':result,'estado_global':'PENDIENTE_PREMIOS_COMPLEMENTARIOS','nota':'No declarar sin premio: faltan extracciones, aproximaciones, centenas, terminaciones, reintegros y condiciones de serie/fracción'}
    raise ValueError('juego no implementado')

def examples(draw):
    game=draw['game_id']; comb=draw['combinacion']
    if game=='EDMS':
        w=ints(comb,6); d=extra(comb,'C');return [{'numeros':w,'sueno':d},{'numeros':w,'sueno':d%5+1}]
    if game=='LOTU':
        w=ints(comb,6);return [{'numeros':w,'caballo':extra(comb,'C'),'reintegro':extra(comb,'R')},{'numeros':w,'caballo':99,'reintegro':(extra(comb,'R')+1)%10}]
    if game=='QUPL':
        w=ints(comb,5);return [{'caballos':w,'segundo_quinta':extra(comb,'C')},{'caballos':w,'segundo_quinta':99}]
    if game=='LAQU':
        w=[v.strip() for v in comb.split('-')];return [{'signos':w[:14],'pleno':w[14]},{'signos':w[:14],'pleno':'00'}]
    if game=='LNAC':return [{'numero':comb['primer_premio']},{'numero':comb['Segundo_premio']},{'numero':'00000'}]
    return []

def records(obj):
    if isinstance(obj,list):
        for x in obj: yield from records(x)
    elif isinstance(obj,dict):
        if 'game_id' in obj and 'combinacion' in obj: yield obj
        elif 'registros' in obj: yield from records(obj['registros'])
        elif 'sorteos' in obj: yield from records(obj['sorteos'])
        elif 'resultado' in obj: yield from records(obj['resultado'])
        elif 'datos' in obj: yield from records(obj['datos'])
        elif 'revisiones' in obj:
            r=obj['revisiones']; yield from records(r[-1:] if isinstance(r,list) else r)
        elif 'datos_oficiales' in obj: yield from records(obj['datos_oficiales'])
        else:
            for v in obj.values():
                if isinstance(v,(dict,list)): yield from records(v)

def main():
    p=argparse.ArgumentParser();p.add_argument('--historico',default=str(HISTORY));p.add_argument('--muestras-dir',default='');a=p.parse_args()
    if a.muestras_dir:
        draws=[]
        for f in sorted(Path(a.muestras_dir).glob('*.json')): draws+=list(records(json.loads(f.read_text(encoding='utf-8'))))
    else: draws=list(records(json.loads(Path(a.historico).read_text(encoding='utf-8'))))
    report={'version':'0.87O','generado_utc':datetime.now(timezone.utc).isoformat(),'modo':'SIMULACION_NO_PUBLICABLE','publicables':0,'historico_modificado':False,'sorteos':[],'resumen':{'candidatos':0,'casos':0,'errores':0,'juegos':[]}}
    seen=set()
    for d in draws:
        if d.get('game_id') not in GAMES:continue
        key=(d.get('game_id'),d.get('id_sorteo'))
        if key in seen:continue
        seen.add(key)
        item={'juego':key[0],'id_sorteo':key[1],'casos':[]};report['resumen']['candidatos']+=1
        for t in examples(d):
            try: item['casos'].append({'boleto_sintetico':t,'resultado':check(d,t)})
            except Exception as exc:
                report['resumen']['errores']+=1;item['casos'].append({'boleto_sintetico':t,'error':f'{type(exc).__name__}: {exc}'})
            report['resumen']['casos']+=1
        report['sorteos'].append(item)
    report['resumen']['juegos']=sorted(set(x['juego'] for x in report['sorteos']))
    Path('informe_motores_087o.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    Path('informe_motores_087o.txt').write_text(json.dumps(report['resumen'],ensure_ascii=False,indent=2)+'\nNO PUBLICABLE. Apuestas sintéticas.\n',encoding='utf-8')
    print(report['resumen'])
    if report['resumen']['errores']: raise SystemExit(1)

if __name__=='__main__': main()
