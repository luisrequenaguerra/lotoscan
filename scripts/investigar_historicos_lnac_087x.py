#!/usr/bin/env python3
"""Prueba acotada de identificadores oficiales en servicios SELAE LNAC. Solo lectura."""
import datetime as dt, hashlib, json, pathlib, urllib.parse, urllib.request, urllib.error
BASE='https://www.loteriasyapuestas.es'; OUT=pathlib.Path('informes/087x');OUT.mkdir(parents=True,exist_ok=True)
# IDs tomados de enlaces anterior/siguiente del JSON oficial 0.87W y de fecha2 0.87R.
IDS=[('jueves_20261119','1329109093'),('jueves_anterior','1328609092'),('sabado_siguiente','1329309094')]
# No asumimos que los nombres de los parametros sean equivalentes; el error oficial de resultados2 cita idsorteo.
TESTS=[]
for label,sid in IDS:
 for path,params in [('/servicios/resultados2',{'idsorteo':sid}),('/servicios/resultados1',{'idsorteo':sid})]:
  TESTS.append((label,path,params))
# Dos consultas de control para verificar si resultados1 ignora el parametro idsorteo.
TESTS += [('control_resultados1','/servicios/resultados1',{}),('control_resultados2','/servicios/resultados2',{})]
HEADERS={'User-Agent':'LotoScan-Research/0.87X (public SELAE results)','Accept':'application/json,text/plain,*/*'}

def resumen(obj):
 if not isinstance(obj,dict):return {'tipo':type(obj).__name__,'mensaje':str(obj)[:220]}
 r={'tipo':'dict','claves':list(obj)[:35]}
 for k in ('drawIdSorteo','fechaSorteo','tipoSorteo','nombreDelSorteo','drawIdSorteoAnterior','drawIdSorteoSiguiente'):
  if k in obj:r[k]=obj[k]
 for k in ('primerPremio','segundoPremio','premioEspecial'):
  v=obj.get(k)
  if isinstance(v,dict):r[k]={'decimo':v.get('decimo'),'prize':v.get('prize')}
 for k in ('extraccionesDeCuatroCifras','extraccionesDeTresCifras','extraccionesDeDosCifras','extraccionesDeCincoCifras','reintegros'):
  v=obj.get(k)
  if isinstance(v,list):r[k]={'cantidad':len(v),'muestra':[{'decimo':x.get('decimo'),'prize':x.get('prize'),'prizeType':x.get('prizeType')} if isinstance(x,dict) else x for x in v[:3]]}
 return r
rows=[]
for idx,(label,path,params) in enumerate(TESTS,1):
 url=BASE+path+('?' + urllib.parse.urlencode(params) if params else '')
 row={'id':idx,'etiqueta':label,'url':url,'http':None,'json':False,'error':None}
 try:
  req=urllib.request.Request(url,headers=HEADERS)
  with urllib.request.urlopen(req,timeout=20) as res:
   row['http']=res.status;row['content_type']=res.headers.get('Content-Type');data=res.read(1_000_001)
  row['bytes']=len(data);row['sha256']=hashlib.sha256(data).hexdigest()
  if len(data)>1_000_000:row['error']='Respuesta supera 1 MB; no se analiza'
  else:
   try:
    obj=json.loads(data.decode('utf-8-sig'));row['json']=True;row['resumen']=resumen(obj)
    (OUT/f'respuesta_{idx:02}.json').write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
   except (ValueError,UnicodeError):row['muestra']=data[:250].decode('utf-8',errors='replace')
 except urllib.error.HTTPError as exc:row['http']=exc.code;row['error']=f'HTTP {exc.code}'
 except Exception as exc:row['error']=f'{type(exc).__name__}: {str(exc)[:180]}'
 rows.append(row);print(f"{idx:02} HTTP={row['http']} json={row['json']} draw={row.get('resumen',{}).get('drawIdSorteo')} {url}")
# Evitar confundir HTTP 200 con exito: exigir dict, ID coincidente y extracciones.
for row in rows:
 sid=urllib.parse.parse_qs(urllib.parse.urlsplit(row['url']).query).get('idsorteo',[None])[0]
 summary=row.get('resumen',{})
 row['id_coincidente']=bool(sid and str(summary.get('drawIdSorteo'))==sid)
 row['extracciones_disponibles']=sum(summary.get(k,{}).get('cantidad',0) for k in ('extraccionesDeCuatroCifras','extraccionesDeTresCifras','extraccionesDeDosCifras') if isinstance(summary.get(k),dict))
 row['historico_confirmado']=row['id_coincidente'] and row['extracciones_disponibles']>0
report={'version':'0.87X','fecha_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'objetivo':'Probar idsorteo oficial para resultados2 y resultados1 LNAC','limitaciones':'No prueba licencia de reutilizacion, exhaustividad de premios, ni historicos fuera de los IDs consultados. No altera historico.','consultas':rows,'historicos_confirmados':sum(r['historico_confirmado'] for r in rows if r['etiqueta']!='jueves_20261119'),'historico_modificado':False,'publicables':0}
(OUT/'informe_historicos_lnac_087x.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('Historicos confirmados:',report['historicos_confirmados'])
