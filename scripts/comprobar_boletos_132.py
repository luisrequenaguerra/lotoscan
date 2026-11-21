#!/usr/bin/env python3
"""LotoScan 1.32: comprobación experimental de aciertos sobre JSON normalizado.
No publica premios ni modifica históricos. Navidad se trata por separado.
"""
import argparse, json, re
from pathlib import Path

GAMES={'EMIL','LAPR','BONO','ELGR','EDMS','LNAC','LAQU','QGOL','LOTU','QUPL'}
NUMBER_GAMES={'BONO':(6,49),'LAPR':(6,49),'EMIL':(5,50),'EDMS':(6,40),'ELGR':(5,54),'LOTU':(6,49)}

def verify_bet(draw, bet):
    game=draw['game_id']; comb=draw.get('combinacion') or {}
    base={'game_id':game,'id_sorteo':draw['id_sorteo'],'estado':'no_comprobable','aciertos':None,
          'premio_eur':None,'categoria':None,'publicable':False,'motivo':None}
    if draw.get('estado_datos')=='pendiente' or not comb:
        base['motivo']='resultado_pendiente';return base
    if game in NUMBER_GAMES:
        count,maxnum=NUMBER_GAMES[game]
        nums=bet.get('numeros'); win=comb.get('numeros')
        if not isinstance(nums,list) or len(nums)!=count or any(type(n)!=int or n<1 or n>maxnum for n in nums) or len(set(nums))!=count:
            base['motivo']='apuesta_numerica_invalida';return base
        if not isinstance(win,list) or len(win)<count:
            base['motivo']='combinacion_oficial_incompleta';return base
        if game=='EMIL':
            stars=bet.get('estrellas')
            if not isinstance(stars,list) or len(stars)!=2 or any(type(n)!=int or not 1<=n<=12 for n in stars) or len(set(stars))!=2 or len(win)<7:
                base['motivo']='estrellas_invalidas_o_ausentes';return base
            base['aciertos']={'numeros':len(set(nums)&set(win[:5])),'estrellas':len(set(stars)&set(win[5:7]))}
        elif game=='EDMS':
            dream=bet.get('numero_sueno')
            if type(dream)!=int or not 1<=dream<=5:
                base['motivo']='numero_sueno_ausente_o_invalido';return base
            base['aciertos']={'numeros':len(set(nums)&set(win[:6])),'sueno':int(dream==comb.get('complementario'))}
        else:
            base['aciertos']={'numeros':len(set(nums)&set(win[:count]))}
            if game in ('BONO','LAPR'):
                base['aciertos']['complementario']=int(comb.get('complementario') in nums) if comb.get('complementario') is not None else None
                refund=bet.get('reintegro')
                if type(refund)==int and 0<=refund<=9 and comb.get('reintegro_o_clave') is not None:
                    base['aciertos']['reintegro']=int(refund==comb['reintegro_o_clave'])
            if game=='ELGR':
                clave=bet.get('clave')
                if type(clave)!=int or not 0<=clave<=9:
                    base['motivo']='clave_ausente_o_invalida';return base
                base['aciertos']['clave']=int(clave==comb.get('reintegro_o_clave'))
            if game=='LOTU':
                caballo=bet.get('caballo')
                if type(caballo)!=int or caballo<1:
                    base['motivo']='caballo_ausente_o_invalido';return base
                base['aciertos']['caballo']=int(caballo==comb.get('reintegro_o_clave'))
    elif game=='LAQU':
        signs=bet.get('signos'); official=comb.get('signos')
        if not isinstance(signs,list) or len(signs)!=14 or any(s not in ('1','X','2') for s in signs):
            base['motivo']='14_signos_invalidos';return base
        if not isinstance(official,list) or len(official)<15:
            base['motivo']='quiniela_oficial_incompleta';return base
        base['aciertos']={'partidos_1_a_14':sum(a==b for a,b in zip(signs,official[:14]))}
        # Pleno al 15 y Elige8 requieren apuesta específica; nunca se infieren.
        base['motivo']='pleno_al_15_y_elige8_no_evaluados'
    elif game=='QGOL':
        signs=bet.get('pronosticos'); official=comb.get('signos')
        if not isinstance(signs,list) or len(signs)!=6 or not isinstance(official,list) or len(official)<6:
            base['motivo']='pronosticos_incompletos';return base
        if any(not isinstance(s,str) or not re.fullmatch(r'[012M]{2}',s) for s in signs):
            base['motivo']='pronosticos_invalidos';return base
        base['aciertos']={'partidos':sum(a==b for a,b in zip(signs,official[:6]))}
    else:
        base['motivo']='reglas_especificas_pendientes';return base
    base['estado']='aciertos_experimentales'
    base['motivo']=base['motivo'] or 'premios_y_categoria_sin_validar'
    return base

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--normalizados',default='datos/lotoscan/resultados_normalizados')
    p.add_argument('--informe',default='salida_132')
    p.add_argument('--apuestas',help='JSON con lista de {game_id,id_sorteo,...}; opcional')
    a=p.parse_args(); root=Path(a.normalizados); out=Path(a.informe);out.mkdir(parents=True,exist_ok=True)
    stats={'version':'1.32','archivos':0,'por_juego':{},'pendientes':0,'errores':[],
           'apuestas_evaluadas':0,'premios_verificados':False,'publicable':False}
    index={}
    for f in sorted(root.glob('*/*.json')):
        try:
            d=json.loads(f.read_text(encoding='utf-8'))
            if d.get('game_id') not in GAMES or f.parent.name!=d['game_id'] or f.stem!=str(d.get('id_sorteo')):
                raise ValueError('identidad de sorteo inconsistente')
            stats['archivos']+=1;stats['por_juego'][d['game_id']]=stats['por_juego'].get(d['game_id'],0)+1
            stats['pendientes']+=d.get('estado_datos')=='pendiente';index[(d['game_id'],str(d['id_sorteo']))]=d
        except (ValueError,KeyError,TypeError,OSError,json.JSONDecodeError) as e:
            stats['errores'].append({'archivo':str(f),'error':str(e)})
    checks=[]
    if a.apuestas:
        bets=json.loads(Path(a.apuestas).read_text(encoding='utf-8'))
        if not isinstance(bets,list): raise ValueError('apuestas debe ser una lista JSON')
        for bet in bets:
            if not isinstance(bet,dict):raise ValueError('apuesta no es objeto')
            key=(bet.get('game_id'),str(bet.get('id_sorteo')))
            if key not in index:
                checks.append({'game_id':key[0],'id_sorteo':key[1],'estado':'no_comprobable',
                               'motivo':'sorteo_no_encontrado','premio_eur':None,'publicable':False})
            else: checks.append(verify_bet(index[key],bet))
        stats['apuestas_evaluadas']=len(checks)
    (out/'informe_132.json').write_text(json.dumps(stats,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    (out/'comprobaciones_132.json').write_text(json.dumps(checks,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(stats,ensure_ascii=False))
    if stats['errores']:raise SystemExit(1)
if __name__=='__main__':main()
