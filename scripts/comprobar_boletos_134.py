#!/usr/bin/env python3
"""LotoScan 1.34: pruebas reproducibles con apuestas reales derivadas de sorteos archivados.
No calcula ni certifica importes. No modifica archivos fuente. Navidad queda fuera.
"""
import argparse, json, re
from pathlib import Path
from collections import Counter


# Apuestas de control derivadas exclusivamente de la combinación oficial normalizada.
# La prueba no valida por sí sola que la normalización ni las reglas de premio sean correctas.

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


def make_bet(draw):
    g=draw['game_id']; c=draw.get('combinacion') or {}; n=c.get('numeros') or []
    b={'game_id':g,'id_sorteo':draw['id_sorteo']}
    if g in ('BONO','LAPR','EMIL','EDMS','ELGR','LOTU'):
        count={'EMIL':5,'ELGR':5}.get(g,6)
        if len(n)<count or any(type(x)!=int for x in n[:count]): return None,'numeros_ausentes'
        b['numeros']=n[:count]
        if g=='EMIL':
            if len(n)<7:return None,'estrellas_ausentes'
            b['estrellas']=n[5:7]
        elif g=='EDMS':
            if type(c.get('complementario'))!=int:return None,'sueno_ausente'
            b['numero_sueno']=c['complementario']
        elif g=='ELGR':
            if type(c.get('reintegro_o_clave'))!=int:return None,'clave_ausente'
            b['clave']=c['reintegro_o_clave']
        elif g=='LOTU':
            if type(c.get('reintegro_o_clave'))!=int:return None,'caballo_ausente'
            b['caballo']=c['reintegro_o_clave']
        elif g in ('BONO','LAPR') and type(c.get('reintegro_o_clave'))==int:
            b['reintegro']=c['reintegro_o_clave']
    elif g=='LAQU':
        signs=c.get('signos') or []
        if len(signs)!=15:return None,'signos_incompletos'
        b['signos']=signs[:14]
        # El pleno al 15 y Elige8 se dejan expresamente sin verificar en 1.33.
    elif g=='QGOL':
        signs=c.get('signos') or []
        if len(signs)!=6:return None,'pronosticos_incompletos'
        b['pronosticos']=signs
    else:
        return None,'reglas_no_implementadas'
    return b,None

def run(root,output):
    output.mkdir(parents=True,exist_ok=True)
    report={'version':'1.33','archivos_leidos':0,'juegos':{},'controles_generados':0,
            'controles_correctos':0,'controles_fallidos':0,'omitidos':[], 'errores':[],
            'premios_verificados':False,'publicable':False}
    results=[]
    for path in sorted(root.glob('*/*.json')):
        try:
            d=json.loads(path.read_text(encoding='utf-8'))
            g=d.get('game_id'); sid=str(d.get('id_sorteo'))
            if g not in GAMES or path.parent.name!=g or path.stem!=sid:
                raise ValueError('identidad del sorteo inconsistente')
            report['archivos_leidos']+=1
            row=report['juegos'].setdefault(g,{'leidos':0,'probados':0,'omitidos':0})
            row['leidos']+=1
            if d.get('estado_datos')=='pendiente':
                row['omitidos']+=1;report['omitidos'].append({'juego':g,'id':sid,'razon':'pendiente'});continue
            bet,why=make_bet(d)
            if bet is None:
                row['omitidos']+=1;report['omitidos'].append({'juego':g,'id':sid,'razon':why});continue
            check=verify_bet(d,bet)
            report['controles_generados']+=1;row['probados']+=1
            expected=({'numeros':len(bet['numeros'])} if 'numeros' in bet else
                      {'partidos_1_a_14':14} if g=='LAQU' else {'partidos':6})
            valid=check['estado']=='aciertos_experimentales' and all(check['aciertos'].get(k)==v for k,v in expected.items()) and check['premio_eur'] is None and not check['publicable']
            report['controles_correctos']+=int(valid)
            report['controles_fallidos']+=int(not valid)
            results.append({'juego':g,'id_sorteo':sid,'apuesta_control':bet,'resultado':check,'control_superado':valid})
        except (OSError,ValueError,TypeError,KeyError,json.JSONDecodeError) as e:
            report['errores'].append({'archivo':str(path),'error':str(e)})
    (output/'informe_133.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (output/'controles_133.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    if not report['archivos_leidos'] or report['errores'] or report['controles_fallidos'] or not report['controles_generados']:
        raise SystemExit(1)



def test_cases(draw, bet):
    """Casos positivos, negativos y de entrada inválida; sin certificar premios."""
    import copy
    game=draw['game_id']
    baseline=verify_bet(draw,bet)
    cases=[]
    def add(name, modified, expected, reason=None):
        result=verify_bet(draw,modified)
        actual=result.get('aciertos') or {}
        ok=(result['estado']==('no_comprobable' if expected is None else 'aciertos_experimentales')
            and result['premio_eur'] is None and result['publicable'] is False)
        if expected is not None: ok=ok and all(actual.get(k)==v for k,v in expected.items())
        if reason: ok=ok and result.get('motivo')==reason
        cases.append({'caso':name,'correcto':ok,'aciertos':actual,'motivo':result['motivo']})
    if baseline['estado']!='aciertos_experimentales': return cases
    # Las entradas inválidas nunca deben considerarse apuestas comprobadas.
    if 'numeros' in bet:
        bad=copy.deepcopy(bet);bad['numeros'][0]=bad['numeros'][1]
        add('duplicado_rechazado',bad,None,'apuesta_numerica_invalida')
        bad=copy.deepcopy(bet);bad['numeros'][0]=0
        add('fuera_de_rango_rechazado',bad,None,'apuesta_numerica_invalida')
        count,upper=NUMBER_GAMES[game]
        win=set(bet['numeros']); alternative=next((n for n in range(1,upper+1) if n not in win),None)
        if alternative is not None:
            bad=copy.deepcopy(bet);bad['numeros'][0]=alternative
            expected={'numeros':count-1}
            add('un_numero_fallado',bad,expected)
        if game=='EMIL':
            bad=copy.deepcopy(bet);bad['estrellas']=[bet['estrellas'][0]]*2
            add('estrellas_duplicadas_rechazadas',bad,None,'estrellas_invalidas_o_ausentes')
        if game=='EDMS':
            bad=copy.deepcopy(bet);bad['numero_sueno']=0
            add('sueno_invalido_rechazado',bad,None,'numero_sueno_ausente_o_invalido')
    elif game=='LAQU':
        bad=copy.deepcopy(bet);bad['signos'][0]=next(x for x in ('1','X','2') if x!=bad['signos'][0])
        add('un_signo_fallado',bad,{'partidos_1_a_14':13})
        bad=copy.deepcopy(bet);bad['signos']=bad['signos'][:-1]
        add('quiniela_incompleta_rechazada',bad,None,'14_signos_invalidos')
    elif game=='QGOL':
        bad=copy.deepcopy(bet);bad['pronosticos'][0]=next(x for x in ('00','11','22','MM') if x!=bad['pronosticos'][0])
        add('un_partido_fallado',bad,{'partidos':5})
        bad=copy.deepcopy(bet);bad['pronosticos'][0]='ZZ'
        add('pronostico_invalido_rechazado',bad,None,'pronosticos_invalidos')
    return cases


def run_134(root,output):
    output.mkdir(parents=True,exist_ok=True)
    report={'version':'1.34','archivos_leidos':0,'juegos':{},'casos':0,'superados':0,'fallidos':0,
            'omitidos':[],'errores':[],'premios_verificados':False,'publicable':False}
    details=[]
    for path in sorted(root.glob('*/*.json')):
        try:
            draw=json.loads(path.read_text(encoding='utf-8'))
            game=draw.get('game_id'); sid=str(draw.get('id_sorteo'))
            if game not in GAMES or path.parent.name!=game or path.stem!=sid:
                raise ValueError('identidad del sorteo inconsistente')
            report['archivos_leidos']+=1
            game_report=report['juegos'].setdefault(game,{'leidos':0,'casos':0,'superados':0})
            game_report['leidos']+=1
            if draw.get('estado_datos')=='pendiente':
                report['omitidos'].append({'juego':game,'id':sid,'razon':'pendiente'});continue
            bet,why=make_bet(draw)
            if bet is None:
                report['omitidos'].append({'juego':game,'id':sid,'razon':why});continue
            for case in test_cases(draw,bet):
                report['casos']+=1;game_report['casos']+=1
                report['superados']+=int(case['correcto']);game_report['superados']+=int(case['correcto'])
                report['fallidos']+=int(not case['correcto'])
                details.append({'juego':game,'id_sorteo':sid,**case})
        except (OSError,ValueError,TypeError,KeyError,json.JSONDecodeError) as exc:
            report['errores'].append({'archivo':str(path),'error':str(exc)})
    (output/'informe_134.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (output/'casos_134.json').write_text(json.dumps(details,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    if not report['archivos_leidos'] or not report['casos'] or report['errores'] or report['fallidos']:
        raise SystemExit(1)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--normalizados',default='datos/lotoscan/resultados_normalizados')
    parser.add_argument('--informe',default='salida_134')
    args=parser.parse_args()
    run_134(Path(args.normalizados),Path(args.informe))
