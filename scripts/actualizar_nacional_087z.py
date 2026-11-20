#!/usr/bin/env python3
"""LotoScan 0.87Z: captura incremental del ULTIMO sorteo LNAC. Sin calcular premios."""
import argparse, datetime as dt, hashlib, json, pathlib, re, sys, urllib.request
URL='https://www.loteriasyapuestas.es/servicios/resultados1'
WIDTHS={'extraccionesDeCuatroCifras':4,'extraccionesDeTresCifras':3,'extraccionesDeDosCifras':2,'extraccionesDeCincoCifras':5,'reintegros':1}
def fetch():
    req=urllib.request.Request(URL,headers={'User-Agent':'Mozilla/5.0 (compatible; LotoScan/0.87Z; lectura resultados publicos)','Accept':'application/json, text/plain, */*'})
    with urllib.request.urlopen(req,timeout=30) as r:
        if r.status!=200: raise ValueError('HTTP '+str(r.status))
        raw=r.read(1500001)
    if len(raw)>1500000: raise ValueError('Respuesta excesiva')
    return json.loads(raw),hashlib.sha256(raw).hexdigest()
def normalize(o,sha):
    errors=[]
    if not isinstance(o,dict):raise ValueError('La respuesta no es un objeto JSON')
    sid=str(o.get('drawIdSorteo') or '')
    if not re.fullmatch(r'[0-9]{5,20}',sid):errors.append('ID de sorteo ausente o incorrecto')
    fecha=str(o.get('fechaSorteo') or '')[:10]
    try:
        day=dt.date.fromisoformat(fecha)
        if day>dt.datetime.now(dt.timezone.utc).date()+dt.timedelta(days=1):errors.append('Fecha futura')
    except ValueError:errors.append('Fecha invalida');day=None
    kind=o.get('tipoSorteo')
    if kind not in ('J','S'):errors.append('Modalidad no ordinaria/no reconocida: requiere revision')
    prizes={}
    for key in ('primerPremio','segundoPremio','premioEspecial'):
        val=o.get(key)
        if val is None:
            if key!='premioEspecial':errors.append(key+' ausente')
            continue
        if not isinstance(val,dict):errors.append(key+' no es objeto');continue
        num=val.get('decimo'); amount=val.get('prize')
        if not isinstance(num,str) or not re.fullmatch(r'\d{5}',num):errors.append(key+' numero incorrecto')
        if not isinstance(amount,(int,float)) or isinstance(amount,bool) or amount<0:errors.append(key+' premio incorrecto')
        prizes[key]={'numero':num,'premio_fuente':amount,'tipo':val.get('prizeType')}
    extra={}
    for field,width in WIDTHS.items():
        val=o.get(field)
        if not isinstance(val,list):errors.append(field+' no es lista');val=[]
        entries=[];seen=set()
        for i,item in enumerate(val):
            if not isinstance(item,dict):errors.append(field+f'[{i}] no es objeto');continue
            num=item.get('decimo');amount=item.get('prize')
            if not isinstance(num,str) or not re.fullmatch(r'\d{'+str(width)+r'}',num):errors.append(field+f'[{i}] numero incorrecto');continue
            if not isinstance(amount,(int,float)) or isinstance(amount,bool) or amount<0:errors.append(field+f'[{i}] premio incorrecto');continue
            if num in seen:errors.append(field+f' numero repetido: '+num)
            seen.add(num)
            entries.append({'numero':num,'premio_fuente':amount,'tipo':item.get('prizeType')})
        extra[field]=entries
    # Control prudente: las cantidades conocidas son de sorteos ordinarios; nunca extrapolar a extraordinarios.
    if kind=='J' and [len(extra[k]) for k in ('extraccionesDeCuatroCifras','extraccionesDeTresCifras','extraccionesDeDosCifras','reintegros')]!=[4,7,9,3]:
        errors.append('Cantidades de extracciones distintas al jueves de referencia: revision manual')
    if kind=='S' and sum(len(extra[k]) for k in ('extraccionesDeCuatroCifras','extraccionesDeTresCifras','extraccionesDeDosCifras'))<20:
        errors.append('Sabado: menos de 20 extracciones menores, revision manual')
    if not extra['reintegros']:errors.append('Faltan reintegros')
    return {'version_esquema':'lnac-087z','id_sorteo':sid,'fecha_sorteo':fecha,'tipo_sorteo':kind,'nombre_sorteo':o.get('nombreDelSorteo'),'precio_decimo_fuente':o.get('precioDecimo'),'principales':prizes,'extracciones':extra,'sha256_respuesta':sha,'validacion':{'estructura_minima_completa':not errors,'incidencias':errors},'publicable':False,'nota':'Importes originales SELAE; sin conversion a euros ni calculo de premios; requiere validacion normativa.'}
def run(args):
    report={'version':'0.87Z','momento_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'endpoint':URL,'estado':'sin_cambios','historico_modificado':False,'publicacion_premios':False}
    try:
        obj,sha=fetch();norm=normalize(obj,sha)
        report.update({'id_sorteo':norm['id_sorteo'],'fecha_sorteo':norm['fecha_sorteo'],'incidencias':norm['validacion']['incidencias']})
        if not norm['validacion']['estructura_minima_completa']:
            report['estado']='pendiente_validacion'
        else:
            dest=pathlib.Path(args.historico)/('sorteo_'+norm['id_sorteo']+'.json')
            if dest.exists():
                old=json.loads(dest.read_text(encoding='utf-8'))
                # Comparar contenido relevante: una correccion SELAE nunca se pisa silenciosamente.
                keys=('fecha_sorteo','tipo_sorteo','principales','extracciones')
                if any(old.get(k)!=norm.get(k) for k in keys):
                    report['estado']='conflicto_requiere_revision';report['incidencias']=['Datos distintos para un sorteo ya archivado: no se sobrescribe']
                else:report['estado']='ya_archivado'
            elif not args.solo_lectura:
                dest.parent.mkdir(parents=True,exist_ok=True)
                dest.write_text(json.dumps(norm,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
                report['estado']='nuevo_archivado';report['historico_modificado']=True
            else:report['estado']='nuevo_detectado_solo_lectura'
    except Exception as exc:
        report['estado']='error_consulta';report['incidencias']=[str(exc)]
    out=pathlib.Path(args.informe);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 1 if report['estado'] in ('error_consulta','conflicto_requiere_revision') else 0
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--historico',default='datos/loteria_nacional/historico');p.add_argument('--informe',default='informes/lnac_087z/informe.json');p.add_argument('--solo-lectura',action='store_true');sys.exit(run(p.parse_args()))
