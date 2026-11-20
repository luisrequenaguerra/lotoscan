#!/usr/bin/env python3
"""LotoScan 0.89: coincidencias candidatas, NO premios liquidados ni importes en euros."""
import argparse, datetime as dt, json, pathlib, re, sys
FIELDS={'extraccionesDeCincoCifras':5,'extraccionesDeCuatroCifras':4,'extraccionesDeTresCifras':3,'extraccionesDeDosCifras':2,'reintegros':1}
TESTS=['51664','68523','02316','00017','00025','00004','11111','00000','99999']

def analizar(d,numero):
    if not re.fullmatch(r'\d{5}',numero): raise ValueError('Número de décimo inválido')
    hits=[]
    for key in ('primerPremio','segundoPremio'):
        item=d.get('principales',{}).get(key)
        if isinstance(item,dict) and item.get('numero')==numero:
            hits.append({'categoria_origen':key,'coincidencia':numero,'importe_fuente_sin_unidad':item.get('premio_fuente'),'tipo_fuente':item.get('tipo')})
    for field,width in FIELDS.items():
        for item in d.get('extracciones',{}).get(field,[]):
            if not isinstance(item,dict): continue
            suffix=item.get('numero')
            if isinstance(suffix,str) and re.fullmatch(r'\d{'+str(width)+r'}',suffix) and numero[-width:]==suffix:
                hits.append({'categoria_origen':field,'coincidencia':suffix,'importe_fuente_sin_unidad':item.get('premio_fuente'),'tipo_fuente':item.get('tipo')})
    return hits

def fixture():
    # Datos de prueba transcritos del JSON oficial del 19-11-2026, NO usados para publicar premios.
    ex={}
    vals={'extraccionesDeCincoCifras':([],0),'extraccionesDeCuatroCifras':(['2316','4388','7198','8580'],7500),'extraccionesDeTresCifras':(['017','379','448','545','684','725','904'],1500),'extraccionesDeDosCifras':(['25','27','28','55','70','72','78','82','87'],600),'reintegros':(['0','4','6'],300)}
    for k,(nums,amount) in vals.items():ex[k]=[{'numero':x,'premio_fuente':amount,'tipo':'PRUEBA'} for x in nums]
    return {'id_sorteo':'1329109093','fecha_sorteo':'2026-11-19','tipo_sorteo':'J','principales':{'primerPremio':{'numero':'51664','premio_fuente':3000000,'tipo':'G'},'segundoPremio':{'numero':'68523','premio_fuente':600000,'tipo':'Z'}},'extracciones':ex,'validacion':{'estructura_minima_completa':True},'publicable':False}

def selftest():
    d=fixture();cases={'51664':{'primerPremio','reintegros'},'68523':{'segundoPremio'},'02316':{'extraccionesDeCuatroCifras','reintegros'},'00017':{'extraccionesDeTresCifras'},'00025':{'extraccionesDeDosCifras'},'00004':{'reintegros'},'11111':set()}
    for number,expected in cases.items():
        got={h['categoria_origen'] for h in analizar(d,number)}
        if got!=expected:raise AssertionError(f'{number}: esperado {expected}, obtenido {got}')
    assert analizar(d,'00017')[0]['coincidencia']=='017'
    try: analizar(d,'1234');raise AssertionError('Se aceptó número inválido')
    except ValueError:pass
    return len(cases)+2

def main():
    p=argparse.ArgumentParser();p.add_argument('--historico',default='datos/loteria_nacional/historico');p.add_argument('--informe',default='informes/lnac_089/analisis.json');a=p.parse_args()
    report={'version':'0.89','momento_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'publicacion_premios':False,'calculo_premio_total_habilitado':False,'importe_en_euros_habilitado':False,'nota':'SOLO coincidencias directas de datos archivados; no se calculan aproximaciones, centenas, terminaciones adicionales, acumulación ni premios especiales. No equivale a premio cobrado.','sorteos':[],'errores':[]}
    try:report['pruebas_unitarias_superadas']=selftest()
    except Exception as e:report['errores'].append('Autopruebas: '+str(e))
    paths=sorted(pathlib.Path(a.historico).glob('sorteo_*.json'))
    if not paths:report['errores'].append('No hay archivos de histórico en el repositorio')
    for path in paths:
        try:
            d=json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(d,dict) or d.get('validacion',{}).get('estructura_minima_completa') is not True or d.get('publicable') is not False:raise ValueError('Archivo sin validación mínima o con marca publicable')
            sid=str(d.get('id_sorteo',''))
            if path.name!=f'sorteo_{sid}.json':raise ValueError('ID no coincide con nombre de archivo')
            if d.get('tipo_sorteo') not in ('J','S'):raise ValueError('Modalidad desconocida')
            entries=[{'numero':n,'coincidencias_directas':analizar(d,n)} for n in TESTS]
            report['sorteos'].append({'archivo':str(path),'id_sorteo':sid,'fecha_sorteo':d.get('fecha_sorteo'),'tipo_sorteo':d.get('tipo_sorteo'),'casos':entries,'avisos':['Coincidencias no equivalen a premios totales; importes fuente sin conversión verificada']})
        except Exception as e:report['errores'].append(str(path)+': '+str(e))
    report['estado']='revision_necesaria' if report['errores'] else 'coincidencias_directas_verificadas_sin_liquidacion'
    out=pathlib.Path(a.informe);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'estado':report['estado'],'sorteos':len(report['sorteos']),'autopruebas':report.get('pruebas_unitarias_superadas'),'errores':report['errores']},ensure_ascii=False))
    return int(bool(report['errores']))
if __name__=='__main__':sys.exit(main())
