#!/usr/bin/env python3
"""LotoScan 0.90: calibración monetaria y detección de categorías derivadas.
NO es un liquidador: no autoriza premio total ni publicación.
"""
import argparse, datetime as dt, json, pathlib, re, sys
from decimal import Decimal

CAMPOS={'extraccionesDeCincoCifras':5,'extraccionesDeCuatroCifras':4,'extraccionesDeTresCifras':3,'extraccionesDeDosCifras':2,'reintegros':1}
CASOS=['51664','68523','51663','51665','68522','68524','51600','68599','02316','00017','00025','00004','11111']

def euros_hipoteticos(valor):
    if isinstance(valor,bool) or not isinstance(valor,(int,float,str)):return None
    try:
        v=Decimal(str(valor))
        if not v.is_finite() or v<0:return None
        return str((v/Decimal(100)).quantize(Decimal('0.01')))
    except Exception:return None

def analizar(d,numero):
    if not re.fullmatch(r'\d{5}',numero):raise ValueError('Número inválido')
    directas=[];derivadas=[]
    for k in ('primerPremio','segundoPremio'):
        p=d.get('principales',{}).get(k)
        if not isinstance(p,dict):continue
        ganador=p.get('numero')
        if not isinstance(ganador,str) or not re.fullmatch(r'\d{5}',ganador):continue
        if numero==ganador:directas.append({'categoria':k,'importe_original':p.get('premio_fuente'),'euros_si_centimos':euros_hipoteticos(p.get('premio_fuente'))})
        if abs(int(numero)-int(ganador))==1:
            derivadas.append({'categoria':'aproximacion_'+k,'estado':'solo_coincidencia; cuantia y reglas pendientes'})
        if numero[:3]==ganador[:3] and numero!=ganador:
            derivadas.append({'categoria':'centena_'+k,'estado':'solo_coincidencia; cuantia y reglas pendientes'})
        if numero[-2:]==ganador[-2:] and numero!=ganador:
            derivadas.append({'categoria':'terminacion_2_'+k,'estado':'solo_coincidencia; cuantia y reglas pendientes'})
    for k,width in CAMPOS.items():
        for p in d.get('extracciones',{}).get(k,[]):
            if not isinstance(p,dict):continue
            n=p.get('numero')
            if isinstance(n,str) and re.fullmatch(r'\d{%d}'%width,n) and numero.endswith(n):
                directas.append({'categoria':k,'extraccion':n,'importe_original':p.get('premio_fuente'),'euros_si_centimos':euros_hipoteticos(p.get('premio_fuente'))})
    return {'numero':numero,'coincidencias_directas':directas,'coincidencias_derivadas_sin_importe':derivadas,'premio_total_euros':None,'publicable':False}

def autopruebas():
    d={'principales':{'primerPremio':{'numero':'51664','premio_fuente':3000000},'segundoPremio':{'numero':'68523','premio_fuente':600000}},'extracciones':{'reintegros':[{'numero':'4','premio_fuente':300}],'extraccionesDeCuatroCifras':[{'numero':'2316','premio_fuente':7500}]}}
    assert euros_hipoteticos(300)=='3.00'
    assert euros_hipoteticos(3000000)=='30000.00'
    assert euros_hipoteticos('abc') is None
    assert {x['categoria'] for x in analizar(d,'51664')['coincidencias_directas']}=={'primerPremio','reintegros'}
    assert 'aproximacion_primerPremio' in {x['categoria'] for x in analizar(d,'51663')['coincidencias_derivadas_sin_importe']}
    assert 'centena_primerPremio' in {x['categoria'] for x in analizar(d,'51600')['coincidencias_derivadas_sin_importe']}
    assert analizar(d,'02316')['coincidencias_directas'][0]['euros_si_centimos']=='75.00'
    assert analizar(d,'11111')['premio_total_euros'] is None
    try:analizar(d,'1234');raise AssertionError('Se aceptó número inválido')
    except ValueError:pass
    return 9

def main():
    a=argparse.ArgumentParser();a.add_argument('--historico',default='datos/loteria_nacional/historico');a.add_argument('--informe',default='informes/lnac_090/calibracion.json');args=a.parse_args()
    rep={'version':'0.90','generado_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'moneda':'EUR','unidad_original':'SIN_VERIFICAR','hipotesis_conversion':'importe_original / 100 (solo diagnóstico)','publicacion_premios':False,'liquidacion_habilitada':False,'aviso':'Las aproximaciones, centenas, terminaciones y acumulaciones requieren normativa y contrastes oficiales. No usar importes como premio a cobrar.','sorteos':[],'errores':[]}
    try:rep['autopruebas']=autopruebas()
    except Exception as e:rep['errores'].append('Autopruebas: '+str(e))
    paths=sorted(pathlib.Path(args.historico).glob('sorteo_*.json'))
    if not paths:rep['errores'].append('Histórico vacío o carpeta inexistente')
    for path in paths:
        try:
            d=json.loads(path.read_text(encoding='utf-8'))
            if d.get('validacion',{}).get('estructura_minima_completa') is not True or d.get('publicable') is not False:raise ValueError('Validación insuficiente o marcado publicable')
            sid=str(d.get('id_sorteo',''))
            if path.name!=f'sorteo_{sid}.json':raise ValueError('Identificador inconsistente')
            if d.get('tipo_sorteo') not in ('J','S'):raise ValueError('Tipo de sorteo no reconocido')
            casos=[analizar(d,n) for n in CASOS]
            rep['sorteos'].append({'archivo':str(path),'id_sorteo':sid,'fecha_sorteo':d.get('fecha_sorteo'),'tipo_sorteo':d.get('tipo_sorteo'),'casos':casos,'evidencia_conversion':{'reintegro_original_300_implicaria_euros_3':'compatible, NO prueba suficiente','precio_decimo_en_json_original':'no incluido en archivo normalizado; pendiente cotejo'}})
        except Exception as e:rep['errores'].append(f'{path}: {e}')
    rep['estado']='errores' if rep['errores'] else 'diagnostico_monetario_sin_liquidacion'
    p=pathlib.Path(args.informe);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(rep,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'estado':rep['estado'],'sorteos':len(rep['sorteos']),'autopruebas':rep.get('autopruebas'),'errores':rep['errores']},ensure_ascii=False))
    return 1 if rep['errores'] else 0
if __name__=='__main__':sys.exit(main())
