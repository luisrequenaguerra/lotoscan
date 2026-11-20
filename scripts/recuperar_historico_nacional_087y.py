#!/usr/bin/env python3
"""LotoScan 0.87Y: descarga de prueba, SOLO lectura, desde SELAE resultados2.
No calcula premios, no publica, no modifica el histórico existente.
"""
import argparse, datetime as dt, hashlib, json, pathlib, re, sys, time, urllib.error, urllib.request
BASE='https://www.loteriasyapuestas.es/servicios/resultados2?idsorteo='
FIELDS={'extraccionesDeCuatroCifras':4,'extraccionesDeTresCifras':3,'extraccionesDeDosCifras':2,'extraccionesDeCincoCifras':5,'reintegros':1}

def descargar(draw_id):
    req=urllib.request.Request(BASE+str(draw_id),headers={'User-Agent':'LotoScan/0.87Y (auditoria de resultados publicos)','Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=25) as resp:
        raw=resp.read(1500000)
        if resp.status!=200: raise ValueError('HTTP '+str(resp.status))
    return json.loads(raw),hashlib.sha256(raw).hexdigest()

def normalizar(obj,esperado,sha):
    problemas=[]
    real=str(obj.get('drawIdSorteo',''))
    if real!=str(esperado): problemas.append('ID devuelto distinto del solicitado')
    fecha=str(obj.get('fechaSorteo',''))[:10]
    try: dt.date.fromisoformat(fecha)
    except ValueError: problemas.append('Fecha de sorteo invalida')
    nums={}
    for field,width in FIELDS.items():
        value=obj.get(field)
        if not isinstance(value,list): problemas.append(field+' no es lista');value=[]
        entries=[]
        for i,item in enumerate(value):
            if not isinstance(item,dict): problemas.append(field+f'[{i}] no es objeto');continue
            numero=item.get('decimo')
            premio=item.get('prize')
            if not isinstance(numero,str) or not re.fullmatch(r'\d{'+str(width)+r'}',numero):
                problemas.append(field+f'[{i}] numero no valido');continue
            if not isinstance(premio,(int,float)) or isinstance(premio,bool) or premio<0:
                problemas.append(field+f'[{i}] importe no valido');continue
            entries.append({'numero':numero,'premio_fuente':premio,'tipo':item.get('prizeType')})
        nums[field]=entries
    principales={}
    for key in ['primerPremio','segundoPremio','premioEspecial']:
        value=obj.get(key)
        if value is not None:
            if not isinstance(value,dict): problemas.append(key+' no es objeto')
            else: principales[key]={'numero':value.get('decimo'),'premio_fuente':value.get('prize'),'tipo':value.get('prizeType')}
    menores=sum(len(nums[k]) for k in ['extraccionesDeCuatroCifras','extraccionesDeTresCifras','extraccionesDeDosCifras'])
    if menores==0: problemas.append('Sin extracciones menores: posible sorteo no celebrado')
    if not principales.get('primerPremio'): problemas.append('Primer premio ausente')
    if not principales.get('segundoPremio'): problemas.append('Segundo premio ausente')
    if not nums['reintegros']: problemas.append('Reintegros ausentes')
    return {'id_sorteo':real,'fecha_sorteo':fecha,'tipo_sorteo':obj.get('tipoSorteo'),'nombre_sorteo':obj.get('nombreDelSorteo'),'id_anterior':str(obj.get('drawIdSorteoAnterior') or ''),'id_siguiente':str(obj.get('drawIdSorteoSiguiente') or ''),'precio_decimo_fuente':obj.get('precioDecimo'),'principales':principales,'extracciones':nums,'cantidad_extracciones_menores':menores,'sha256_respuesta':sha,'validacion':{'estructura_minima_completa':not problemas,'incidencias':problemas},'nota_importes':'prize conserva unidades originales de SELAE; no convertir a euros sin validar la escala por sorteo y categoria','publicable':False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--ancla',default='1329109093')
    p.add_argument('--cantidad',type=int,default=5)
    p.add_argument('--salida',default='informes/lnac_087y')
    args=p.parse_args()
    if not 1<=args.cantidad<=12: p.error('cantidad entre 1 y 12')
    out=pathlib.Path(args.salida);out.mkdir(parents=True,exist_ok=True)
    resumen={'version':'0.87Y','origen':'SELAE /servicios/resultados2','ancla':args.ancla,'fecha_auditoria_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'consultas':[],'validos':0,'no_validos':0,'historico_modificado':False,'publicables':0,'limitaciones':['Auditoria de estructura, no validacion de premios totales','No confirma autorizacion de reutilizacion comercial','No garantiza disponibilidad futura del servicio','No presupone que las reglas sean iguales en sorteos extraordinarios']}
    vistos=set();actual=args.ancla
    for idx in range(args.cantidad):
        if not re.fullmatch(r'\d+',actual) or actual in vistos:
            resumen['detencion']='ID invalido o ciclo de identificadores';break
        vistos.add(actual)
        try:
            obj,sha=descargar(actual)
            if not isinstance(obj,dict):raise ValueError('JSON no es objeto')
            normal=normalizar(obj,actual,sha)
            if normal['validacion']['estructura_minima_completa']:
                resumen['validos']+=1
            else:resumen['no_validos']+=1
            (out/('sorteo_'+actual+'.json')).write_text(json.dumps(normal,ensure_ascii=False,indent=2),encoding='utf-8')
            resumen['consultas'].append({'solicitado':actual,'recibido':normal['id_sorteo'],'fecha':normal['fecha_sorteo'],'extracciones_menores':normal['cantidad_extracciones_menores'],'valido':normal['validacion']['estructura_minima_completa'],'incidencias':normal['validacion']['incidencias']})
            if normal['id_sorteo']!=actual:
                resumen['detencion']='ID no coincidente';break
            actual=normal['id_anterior']
            if not actual:resumen['detencion']='Sin identificador anterior';break
        except Exception as exc:
            resumen['no_validos']+=1
            resumen['consultas'].append({'solicitado':actual,'error':str(exc),'valido':False})
            resumen['detencion']='Error de consulta';break
        time.sleep(.3)
    (out/'informe_087y.json').write_text(json.dumps(resumen,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'validos':resumen['validos'],'no_validos':resumen['no_validos'],'consultas':resumen['consultas']},ensure_ascii=False,indent=2))
    return 0 if resumen['validos'] else 1
if __name__=='__main__':sys.exit(main())
