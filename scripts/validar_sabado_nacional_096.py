#!/usr/bin/env python3
"""LotoScan 0.96: contraste económico sábado 14/11/2026. NO publicable.

Tarifas derivadas tomadas de la lista oficial SM_LISTAOFICIAL.A2026.S092.pdf.
Valida seis importes independientes de la tabla oficial; no extrapolar a otros sorteos.
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
# Valores en céntimos por décimo: aproximaciones 1000/554 EUR; centenas 30 EUR; terminaciones 3 y 2 cifras 30/12 EUR.
DERIVED={'aproximacion_primero':100000,'aproximacion_segundo':55400,
         'centena_primero':3000,'centena_segundo':3000,
         'terminacion_3_primero':3000,'terminacion_2_primero':1200}


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
        for width in (3,2):
            if number.endswith(first[-width:]):add('terminacion_%d_primero'%width,DERIVED['terminacion_%d_primero'%width])
        for field in FIELDS:
            for item in d[field]:
                if number.endswith(item['decimo']):add(field+':'+item['decimo'],item['prize'])
    total=sum(x['centimos'] for x in parts)
    return {'numero':number,'componentes':parts,'total_centimos_calculado':total,
            'total_euros_calculado':str((Decimal(total)/100).quantize(Decimal('0.01'))),
            'contraste_documental_parcial':True,'publicable':False}


def fixture():
    d={'drawIdSorteo':'1328609092','tipoSorteo':'X','tipoSorteoGeneral':'S','fechaSorteo':'2026-11-14T13:00:00.000Z',
       'precioDecimo':6,'premioEspecial':None,'tercerosPremios':[],'cuartosPremios':[],'quintosPremios':[],
       'primerPremio':{'decimo':'75409','prize':6000000},'segundoPremio':{'decimo':'38422','prize':1200000}}
    values={'extraccionesDeCuatroCifras':'2004 2888 4896 8274',
            'extraccionesDeTresCifras':'249 491 594 624 640 655 781 824 863 924',
            'extraccionesDeDosCifras':'06 07 14 21 38 48 50 76 98','reintegros':'0 4 9'}
    for k,v in values.items():d[k]=[{'decimo':n,'prize':FIELDS[k][2]} for n in v.split()]
    return d


# Importes de la tabla de números de la lista oficial SELAE del 14/11/2026,
# transcritos por décimo (importe impreso por billete / 10).
# Fuente: SM_LISTAOFICIAL.A2026.S092.pdf, descargada en la auditoría 0.95.
OFFICIAL_CASES={'75409':60000,'38422':12000,'75408':1030,
                '75410':1036,'38421':596,'38423':584}


def tests():
    d=fixture();cases=[]
    def test(name,condition):cases.append({'prueba':name,'ok':bool(condition)})
    test('estructura_referencia_093',not validate(d))
    for number,euros in OFFICIAL_CASES.items():
        test('tabla_oficial_'+number,calculate(d,number)['total_centimos_calculado']==euros*100)
    test('extraccion_4_y_reintegro',calculate(d,'02004')['total_centimos_calculado']==15600)
    test('extraccion_3_y_reintegro',calculate(d,'00249')['total_centimos_calculado']==3600)
    test('extraccion_2',calculate(d,'00006')['total_centimos_calculado']==1200)
    test('reintegro',calculate(d,'00000')['total_centimos_calculado']==600)
    test('sin_premio',calculate(d,'11111')['total_centimos_calculado']==0)
    test('centena_primero_30eur',any(x['categoria']=='centena_primero' and x['centimos']==3000 for x in calculate(d,'75408')['componentes']))
    test('centena_segundo_30eur',any(x['categoria']=='centena_segundo' and x['centimos']==3000 for x in calculate(d,'38423')['componentes']))
    test('aproximacion_primero_1000eur',any(x['categoria']=='aproximacion_primero' and x['centimos']==100000 for x in calculate(d,'75410')['componentes']))
    test('aproximacion_segundo_554eur',any(x['categoria']=='aproximacion_segundo' and x['centimos']==55400 for x in calculate(d,'38421')['componentes']))
    test('primer_premio_sin_reintegro_adicional',len(calculate(d,'75409')['componentes'])==1)
    test('segundo_premio_sin_otras_categorias',len(calculate(d,'38422')['componentes'])==1)
    test('rechazo_modalidad',bool(validate(dict(d,tipoSorteoGeneral='J'))))
    bad=json.loads(json.dumps(d));bad['reintegros']=[]
    test('rechazo_incompleto',bool(validate(bad)))
    test('no_publicable',not calculate(d,'75409')['publicable'])
    return cases


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--informe',default='informes/lnac_096/validacion_sabado_096.json')
    ap.add_argument('--sin-red',action='store_true')
    args=ap.parse_args()
    report={'version':'0.96','fecha_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
      'alcance':'Solo sábado 14/11/2026 (ID 1328609092); NO generalizable ni publicable',
      'evidencia_oficial':'SELAE SM_LISTAOFICIAL.A2026.S092.pdf; importes por billete divididos entre diez',
      'publicable':False,'historico_modificado':False,'tests':tests(),'errores':[],'fuente':'fixture_local_093'}
    d=fixture()
    if not args.sin_red:
        try:
            d=fetch();report['fuente']='SELAE_resultados2'
        except (urllib.error.URLError,TimeoutError,ValueError,json.JSONDecodeError) as e:
            report['errores'].append('Consulta SELAE fallida; se usa fixture de referencia: '+str(e)[:250])
    report['validacion_datos']=validate(d)
    if not report['validacion_datos']:
        sample=list(OFFICIAL_CASES)+['02004','00249','00006','00000','11111']
        report['muestras']=[calculate(d,n) for n in sample]
        report['contraste_oficial']=[{'numero':n,'esperado_euros':euros,
            'calculado_euros':calculate(d,n)['total_euros_calculado'],
            'coincide':calculate(d,n)['total_centimos_calculado']==euros*100}
            for n,euros in OFFICIAL_CASES.items()]
    else:report['errores'].append('JSON no admitido; no se calculan muestras')
    report['pruebas_superadas']=sum(t['ok'] for t in report['tests'])
    report['pruebas_totales']=len(report['tests'])
    report['estado']='contraste_parcial_superado' if (not report['validacion_datos']
        and all(x['coincide'] for x in report['contraste_oficial'])
        and report['pruebas_superadas']==report['pruebas_totales']) else 'requiere_revision'
    report['pendiente']='Validar el resto de categorías y acumulaciones con más números y sorteos; Navidad requiere perfil propio'
    dest=pathlib.Path(args.informe);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'estado':report['estado'],'pruebas':f"{report['pruebas_superadas']}/{report['pruebas_totales']}",
        'fuente':report['fuente'],'informe':str(dest)},ensure_ascii=False))
    return 0 if report['estado']=='contraste_parcial_superado' else 1

if __name__=='__main__':raise SystemExit(main())
