#!/usr/bin/env python3
"""Auditoria acotada de recursos oficiales LNAC; no valida premios ni publica datos."""
import datetime as dt, hashlib, json, pathlib, re, urllib.error, urllib.parse, urllib.request
BASE='https://www.loteriasyapuestas.es'
OUT=pathlib.Path('informes/087w'); OUT.mkdir(parents=True,exist_ok=True)
PATHS=[
 '/f/loterias/estaticos/json/configuracionLNAC.json',
 '/f/loterias/estaticos/json/estadoCelebracionLNAC.json',
 '/f/loterias/estaticos/json/TempJSONResultadosLNAC_I.json',
 '/f/loterias/estaticos/json/TempJSONRepartidoEnLNAC_I.json',
 '/servicios/resultados1', '/servicios/resultados2',
 '/servicios/escrutinio1',
]
# Solo parametros documentados por el flujo conocido; no fuerza ni adivina credenciales.
TESTS=[(p,{}) for p in PATHS]
for p in ['/servicios/resultados1','/servicios/resultados2']:
 for date in ('20261112','20261114'):
  TESTS.append((p,{'game_id':'LNAC','fecha_sorteo':date}))
HEADERS={'User-Agent':'LotoScan-Research/0.87W (public-data audit)','Accept':'application/json,text/plain,*/*'}

def inspect(value, depth=0, prefix='$'):
 out=[]
 if depth>9 or len(out)>100:return out
 if isinstance(value,dict):
  for k,v in list(value.items())[:120]:
   p=f'{prefix}.{k}';
   if re.search(r'extracc|alambre|termin|premiad|resultado|numero|cifra|tabla',str(k),re.I):
    out.append({'ruta':p,'tipo':type(v).__name__,'elementos':len(v) if isinstance(v,(list,dict)) else None})
   out+=inspect(v,depth+1,p)
 elif isinstance(value,list):
  for i,v in enumerate(value[:3]):out+=inspect(v,depth+1,f'{prefix}[{i}]')
 return out[:100]

rows=[]
for idx,(path,params) in enumerate(TESTS,1):
 url=BASE+path+('?' + urllib.parse.urlencode(params) if params else '')
 row={'id':idx,'url':url,'status':None,'content_type':None,'bytes':0,'json_valido':False,'campos_candidatos':[],'error':None}
 try:
  req=urllib.request.Request(url,headers=HEADERS)
  with urllib.request.urlopen(req,timeout=18) as res:
   row['status']=res.status;row['content_type']=res.headers.get('Content-Type',''); data=res.read(2_000_001)
  row['bytes']=len(data);row['truncado']=len(data)>2_000_000;row['sha256']=hashlib.sha256(data).hexdigest()
  if len(data)<=2_000_000:
   text=data.decode('utf-8-sig',errors='replace')
   try:
    obj=json.loads(text);row['json_valido']=True;row['tipo_raiz']=type(obj).__name__;row['campos_candidatos']=inspect(obj)
    # Guardar respuestas oficiales para analisis posterior, sin modificar historico.
    (OUT/f'respuesta_{idx:02}.json').write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
   except json.JSONDecodeError:
    row['muestra_texto']=text[:350]
 except urllib.error.HTTPError as e:
  row['status']=e.code;row['error']=f'HTTP {e.code}'
 except Exception as e:row['error']=f'{type(e).__name__}: {str(e)[:200]}'
 rows.append(row);print(f"{idx:02} HTTP {row['status']} JSON={row['json_valido']} {url}")
report={'version':'0.87W','fecha_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'objetivo':'Localizar extracciones LNAC en servicios publicos citados en utils-json-lnac.js','limites':'GET sin autenticacion; respuestas 2 MB maximo; no prueba permisos de reutilizacion comercial; no prueba ausencia de otros endpoints','consultas':rows,'json_validos':sum(x['json_valido'] for x in rows),'candidatos_detectados':sum(len(x['campos_candidatos']) for x in rows),'historico_modificado':False,'publicables':0}
(OUT/'informe_servicios_lnac_087w.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('Informe guardado. JSON validos:',report['json_validos'],'campos candidatos:',report['candidatos_detectados'])
