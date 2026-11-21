#!/usr/bin/env python3
"""LotoScan 0.97: auditoría de disponibilidad JSON de Navidad (solo lectura)."""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = 'https://www.loteriasyapuestas.es'
OUT = Path(os.environ.get('LOTOSCAN_OUT', 'salida_097'))
OUT.mkdir(parents=True, exist_ok=True)
REPORT = {'version':'0.97', 'objetivo':'Localizar resultados oficiales de Navidad sin suponer que existen ni calcular premios',
          'fecha_utc':dt.datetime.now(dt.timezone.utc).isoformat(), 'solo_lectura':True,
          'publicable':False, 'consultas':[], 'candidatos_navidad':[], 'conclusiones':[]}

def request(path, tag):
    url=BASE+path
    entry={'etiqueta':tag,'url':url,'http':None,'error':None,'json_valido':False}
    try:
        req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; LotoScanResearch/0.97)', 'Accept':'application/json, text/plain, */*'})
        with urllib.request.urlopen(req,timeout=22) as resp:
            raw=resp.read(2_000_001)
            entry['http']=resp.status
            entry['content_type']=resp.headers.get('Content-Type','')
        if len(raw)>2_000_000: raise ValueError('Respuesta excede 2 MB')
        entry['sha256']=hashlib.sha256(raw).hexdigest()
        try:
            data=json.loads(raw.decode('utf-8-sig'))
            entry['json_valido']=True
            (OUT/(tag+'.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
            entry['tipo_raiz']=type(data).__name__
            entry['resumen']=summarize(data)
            return data
        except (ValueError,UnicodeDecodeError) as exc:
            entry['error']='No se pudo interpretar JSON: '+str(exc)[:180]
    except (urllib.error.HTTPError,urllib.error.URLError,TimeoutError,ValueError) as exc:
        entry['error']=str(exc)[:220]
        if isinstance(exc,urllib.error.HTTPError):entry['http']=exc.code
    finally:
        REPORT['consultas'].append(entry)
    return None

def summarize(data):
    if isinstance(data,dict):
        keys=['drawIdSorteo','fechaSorteo','nombreDelSorteo','tipoSorteo','tipoSorteoGeneral','precioDecimo','urlListadoOficial']
        s={k:data.get(k) for k in keys if k in data}
        for k in ['primerPremio','segundoPremio','tercerosPremios','cuartosPremios','quintosPremios','premioEspecial','extraccionesDeCincoCifras','extraccionesDeCuatroCifras','extraccionesDeTresCifras','extraccionesDeDosCifras','reintegros']:
            v=data.get(k)
            if isinstance(v,list):s[k+'_cantidad']=len(v)
            elif isinstance(v,dict):s[k+'_presente']=True
            elif v is None:s[k+'_presente']=False
        s['campos']=list(data)[:65]
        return s
    if isinstance(data,list):return {'cantidad':len(data),'primer_elemento':summarize(data[0]) if data and isinstance(data[0],dict) else str(data[:1])[:300]}
    return {'valor':str(data)[:300]}

def candidate_ids(obj):
    found=set()
    def walk(v,depth=0):
        if depth>5:return
        if isinstance(v,dict):
            for k,x in v.items():
                if k.lower() in ('drawidsorteo','idsorteo','id_sorteo') and re.fullmatch(r'\d{6,15}',str(x or '')):found.add(str(x))
                elif isinstance(x,(dict,list)):walk(x,depth+1)
        elif isinstance(v,list):
            for x in v[:30]:walk(x,depth+1)
    walk(obj)
    return sorted(found)

# El servicio fecha2 puede ignorar los filtros: nunca considerar confirmada una fecha por el parámetro enviado.
queries=[
 ('navidad_2025_fecha_sorteo','/servicios/fecha2?'+urllib.parse.urlencode({'game_id':'LNAC','fecha_sorteo':'20251222'})),
 ('navidad_2025_fecha','/servicios/fecha2?'+urllib.parse.urlencode({'game_id':'LNAC','fecha':'20251222'})),
 ('navidad_2024_fecha_sorteo','/servicios/fecha2?'+urllib.parse.urlencode({'game_id':'LNAC','fecha_sorteo':'20241222'})),
 ('ultimo_resultados1','/servicios/resultados1'),
]
ids=set()
for tag,path in queries:
    obj=request(path,tag)
    if obj is not None:
        for id_ in candidate_ids(obj):ids.add(id_)
    time.sleep(1.2)
# Consultar solo IDs explícitos hallados; evitar exploración masiva o IDs inventados.
for id_ in sorted(ids)[:5]:
    obj=request('/servicios/resultados2?'+urllib.parse.urlencode({'idsorteo':id_}), 'detalle_'+id_)
    if isinstance(obj,dict):
        iso=str(obj.get('fechaSorteo',''))
        nombre=str(obj.get('nombreDelSorteo',''))
        if iso.startswith(('2025-12-22','2024-12-22')) or 'NAVIDAD' in nombre.upper():
            REPORT['candidatos_navidad'].append({'id':id_,'fecha':iso,'nombre':nombre,'resumen':summarize(obj)})
    time.sleep(1.2)
if REPORT['candidatos_navidad']:
    REPORT['conclusiones'].append('Se encontraron candidatos navideños: comprobar integridad y premios especiales antes de implementar el motor.')
else:
    REPORT['conclusiones'].append('No se confirmó ningún JSON navideño completo. Los parámetros fecha podrían ignorarse; no asumir disponibilidad.')
REPORT['conclusiones'].append('La pedrea y los premios extraordinarios requieren verificación explícita; no deducir su existencia por el nombre del sorteo.')
REPORT['conclusiones'].append('No se modificó el histórico ni se calculó o publicó ningún premio.')
(OUT/'informe_navidad_097.json').write_text(json.dumps(REPORT,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'consultas':len(REPORT['consultas']),'candidatos_navidad':len(REPORT['candidatos_navidad']),'informe':str(OUT/'informe_navidad_097.json')},ensure_ascii=False))
