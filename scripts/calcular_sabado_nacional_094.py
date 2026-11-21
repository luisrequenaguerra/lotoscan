#!/usr/bin/env python3
"""LotoScan 0.94: motor experimental de sábado. NO publicable.

Tarifas derivadas hipotéticas: duplicación del perfil jueves 93/26.
NO equivalen a validación oficial de premios acumulados de sábado.
"""
import argparse
import datetime as dt
import json
import pathlib
import re
import urllib.error
import urllib.request
from decimal import Decimal

URL='https://www.loteriasyapuestas.es/servicios/resultados2?idsorteo=1328609092'
FIELDS={'extraccionesDeCuatroCifras':(4,4,15000),'extraccionesDeTresCifras':(3,10,3000),
        'extraccionesDeDosCifras':(2,9,1200),'reintegros':(1,3,600)}
# HIPOTESIS: importes derivados de jueves multiplicados por dos. No validados con lista oficial del sábado.
DERIVED={'aproximacion_primero':240000,'aproximacion_segundo':149400,
         'centena_primero':6000,'centena_segundo':3000,
         'terminacion_4_primero':15000,'terminacion_3_primero':3000,'terminacion_2_primero':1200}


def fetch():
    req=urllib.request.Request(URL,headers={'User-Agent':'LotoScan-auditoria/0.94 (+consulta puntual)','Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=25) as response:
        raw=response.read(1_000_001)
        if len(raw)>1_000_000:raise ValueError('Respuesta excesiva')
        return json.loads(raw.decode('utf-8-sig'))


def validate(d):
    errors=[]
    if not isinstance(d,dict):return ['La respuesta no es objeto JSON']
    if str(d.get('drawIdSorteo'))!='1328609092':errors.append('ID inesperado')
    if d.get('tipoSorteoGeneral')!='S' or d.get('tipoSorteo')!='X':errors.append('Modalidad no admitida')
    if not str(d.get('fechaSorteo','')).startswith('2026-11-14'):errors.append('Fecha inesperada')
    if d.get('precioDecimo')!=6:errors.append('Precio décimo inesperado')
    for field,amount in [('primerPremio',6000000),('segundoPremio',1200000)]:
        item=d.get(field)
        if not isinstance(item,dict) or not re.fullmatch(r'\d{5}',str(item.get('decimo',''))):errors.append('Número inválido '+field)
        if not isinstance(item,dict) or item.get('prize')!=amount:errors.append('Importe inesperado '+field)
    for field,(width,count,amount) in FIELDS.items():
        items=d.get(field)
        if not isinstance(items,list) or len(items)!=count:
            errors.append('Cantidad inválida '+field);continue
        seen=set()
        for item in items:
            if not isinstance(item,dict):errors.append('Entrada inválida '+field);continue
            n=item.get('decimo')
            if not isinstance(n,str) or not re.fullmatch(r'\d{%s}'%width,n):errors.append('Número inválido '+field)
            if n in seen:errors.append('Número repetido '+field)
            seen.add(n)
            if item.get('prize')!=amount:errors.append('Importe inválido '+field)
    if d.get('premioEspecial') is not None:errors.append('Premio especial no soportado')
    if d.get('tercerosPremios') or d.get('cuartosPremios') or d.get('quintosPremios'):errors.append('Premios adicionales no soportados')
    return errors


def calculate(d,number):
    if not re.fullmatch(r'\d{5}',number):raise ValueError('Número inválido: deben ser 5 cifras')
    problems=validate(d)
    if problems:raise ValueError('; '.join(problems))
    first=d['primerPremio']['decimo'];second=d['segundoPremio']['decimo']
    parts=[]
    def add(category,cents):parts.append({'categoria':category,'centimos':cents})
    if number==first:add('primer_premio',d['primerPremio']['prize'])
    elif number==second:add('segundo_premio',d['segundoPremio']['prize'])
    else:
        if abs(int(number)-int(first))==1:add('aproximacion_primero',DERIVED['aproximacion_primero'])
        if abs(int(number)-int(second))==1:add('aproximacion_segundo',DERIVED['aproximacion_segundo'])
        if number[:3]==first[:3]:add('centena_primero',DERIVED['centena_primero'])
        if number[:3]==second[:3]:add('centena_segundo',DERIVED['centena_segundo'])
        for width in (4,3,2):
            if number.endswith(first[-width:]):add('terminacion_%d_primero'%width,DERIVED['terminacion_%d_primero'%width])
        for field in FIELDS:
            for item in d[field]:
                if number.endswith(item['decimo']):add(field+':'+item['decimo'],item['prize'])
    total=sum(x['centimos'] for x in parts)
    return {'numero':number,'componentes':parts,'total_centimos_hipotetico':total,
            'total_euros_hipotetico':str((Decimal(total)/100).quantize(Decimal('0.01'))),
            'validacion_normativa':False,'publicable':False}


def fixture():
    d={'drawIdSorteo':'1328609092','tipoSorteo':'X','tipoSorteoGeneral':'S','fechaSorteo':'2026-11-14T13:00:00.000Z',
       'precioDecimo':6,'premioEspecial':None,'tercerosPremios':[],'cuartosPremios':[],'quintosPremios':[],
       'primerPremio':{'decimo':'75409','prize':6000000},'segundoPremio':{'decimo':'38422','prize':1200000}}
    values={'extraccionesDeCuatroCifras':'2004 2888 4896 8274',
            'extraccionesDeTresCifras':'249 491 594 624 640 655 781 824 863 924',
            'extraccionesDeDosCifras':'06 07 14 21 38 48 50 76 98','reintegros':'0 4 9'}
    for k,v in values.items():d[k]=[{'decimo':n,'prize':FIELDS[k][2]} for n in v.split()]
    return d


def tests():
    d=fixture();cases=[]
    def test(name,condition):cases.append({'prueba':name,'ok':bool(condition)})
    test('estructura_referencia_093',not validate(d))
    test('primer_premio',calculate(d,'75409')['total_centimos_hipotetico']==6000000)
    test('segundo_premio',calculate(d,'38422')['total_centimos_hipotetico']==1200000)
    test('extraccion_4_y_reintegro',calculate(d,'02004')['total_centimos_hipotetico']==15600)
    test('extraccion_3',calculate(d,'00249')['total_centimos_hipotetico']==3600)
    test('extraccion_2',calculate(d,'00006')['total_centimos_hipotetico']==1200)
    test('reintegro',calculate(d,'00000')['total_centimos_hipotetico']==600)
    test('aproximacion_primero',any(x['categoria']=='aproximacion_primero' for x in calculate(d,'75408')['componentes']))
    test('centena_segundo',any(x['categoria']=='centena_segundo' for x in calculate(d,'38499')['componentes']))
    test('cero_inicial',any(x['categoria'].startswith('extraccionesDeDosCifras') for x in calculate(d,'00006')['componentes']))
    test('rechazo_modalidad',bool(validate(dict(d,tipoSorteoGeneral='J'))))
    bad=json.loads(json.dumps(d));bad['reintegros']=[]
    test('rechazo_incompleto',bool(validate(bad)))
    test('no_publicable',not calculate(d,'75409')['publicable'])
    return cases


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--informe',default='informes/lnac_094/analisis_sabado_094.json');ap.add_argument('--sin-red',action='store_true');args=ap.parse_args()
    report={'version':'0.94','fecha_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
      'alcance':'Sábado 14/11/2026; tarifas derivadas HIPOTETICAS (doble del jueves), no verificadas en lista oficial',
      'publicable':False,'historico_modificado':False,'tests':tests(),'errores':[],'fuente':'fixture_local_093'}
    d=fixture()
    if not args.sin_red:
        try:d=fetch();report['fuente']='SELAE_resultados2'
        except (urllib.error.URLError,TimeoutError,ValueError,json.JSONDecodeError) as e:
            report['errores'].append('Consulta SELAE fallida; se usa referencia local 0.93: '+str(e)[:250])
    report['validacion_datos']=validate(d)
    if not report['validacion_datos']:
        sample=['75409','38422','75408','75410','38421','38423','02004','00249','00006','00000','11111']
        report['muestras']=[calculate(d,n) for n in sample]
    else:report['errores'].append('JSON no admitido; no se calculan muestras')
    report['pruebas_superadas']=sum(t['ok'] for t in report['tests'])
    report['pruebas_totales']=len(report['tests'])
    report['pendiente_para_validar']='Contrastar importes acumulados del sábado con lista oficial independiente; verificar aproximaciones, centenas y terminaciones'
    report['estado']='diagnostico_experimental' if report['pruebas_superadas']==report['pruebas_totales'] and not report['validacion_datos'] else 'requiere_revision'
    dest=pathlib.Path(args.informe);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'estado':report['estado'],'pruebas':f"{report['pruebas_superadas']}/{report['pruebas_totales']}",'fuente':report['fuente'],'informe':str(dest)},ensure_ascii=False))
    return 0 if report['estado']=='diagnostico_experimental' else 1

if __name__=='__main__':raise SystemExit(main())
