#!/usr/bin/env python3
"""LotoScan 1.30. Fuentes oficiales para terceros SELAE: fechav3/fecha2.
Histórico incremental de respuestas íntegras; NO certifica premios ni publica resultados.
La Lotería de Navidad conserva su tratamiento independiente.
"""
import argparse
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
from zoneinfo import ZoneInfo

BASE = 'https://www.loteriasyapuestas.es/servicios/'
GAMES = {'euromillones':'EMIL','primitiva':'LAPR','bonoloto':'BONO',
         'gordo-primitiva':'ELGR','eurodreams':'EDMS','loteria-nacional':'LNAC',
         'quiniela':'LAQU','quinigol':'QGOL','lototurf':'LOTU','quintuple-plus':'QUPL'}
HEADERS={'User-Agent':'Mozilla/5.0 (compatible; LotoScan/1.30; official-results-monitor)',
         'Accept':'application/json, text/javascript, */*;q=0.8'}
MAX_BYTES=2_000_000

def fetch(url, retries=2):
    for attempt in range(retries+1):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers=HEADERS),timeout=22) as response:
                data=response.read(MAX_BYTES+1)
                if len(data)>MAX_BYTES: return None,{'http':response.status,'error':'respuesta_excesiva'}
                return data,{'http':response.status,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
        except urllib.error.HTTPError as e:
            err={'http':e.code,'error':'HTTP_'+str(e.code)}
            if e.code not in (429,500,502,503,504): return None,err
        except (OSError,TimeoutError) as e:
            err={'http':None,'error':type(e).__name__}
        if attempt<retries: time.sleep(attempt+1)
    return None,err

def candidates(raw,code,day):
    try: payload=json.loads(raw.decode('utf-8-sig'))
    except (UnicodeError,ValueError): return [],'no_json'
    if not isinstance(payload,list): return [],'respuesta_no_lista'
    out=[]
    for item in payload:
        if not isinstance(item,dict) or item.get('game_id')!=code: continue
        date=str(item.get('fecha_sorteo') or '')[:10]
        if date!=day.isoformat(): continue
        draw_id=str(item.get('id_sorteo') or '')
        if not re.fullmatch(r'\d{6,20}',draw_id): continue
        out.append(item)
    return out,('coincidencias' if out else 'sin_sorteo_para_fecha')

def quality(item,code):
    issues=[]
    if not item.get('combinacion'): issues.append('combinacion_no_disponible')
    if not isinstance(item.get('escrutinio'),list) or not item['escrutinio']:
        issues.append('escrutinio_no_disponible')
    # No asumir que una tabla de escrutinio presente tiene todos los premios.
    if code=='LAQU':
        text=json.dumps(item,ensure_ascii=False).lower()
        if not any(term in text for term in ('elige8','elige 8','elige_8')):
            issues.append('elige8_no_identificado_en_json')
        if not any(term in text for term in ('pleno','partido15','partido_15')):
            issues.append('pleno_al_15_no_identificado_en_json')
    return issues

def write_json(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    os.replace(tmp,path)

def update(history,code,item):
    draw_id=str(item['id_sorteo'])
    base=history/code/draw_id
    canonical=json.dumps(item,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
    digest=hashlib.sha256(canonical).hexdigest()
    revision=base/'revisiones'/f'{digest}.json'
    current=base/'actual.json'
    if current.exists():
        old=json.loads(current.read_text(encoding='utf-8'))
        oldhash=hashlib.sha256(json.dumps(old,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        if oldhash==digest: return 'sin_cambios',digest
        # Guardar revisión previa incluso si el histórico precede a esta versión.
        oldrev=base/'revisiones'/f'{oldhash}.json'
        if not oldrev.exists(): write_json(oldrev,old)
        action='revisado'
    else: action='nuevo'
    if not revision.exists(): write_json(revision,item)
    write_json(current,item)
    return action,digest

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--dias',type=int,default=8,help='Días naturales, incluido hoy (1-21)')
    p.add_argument('--fecha-fin',default='',help='AAAAMMDD, zona Europe/Madrid')
    p.add_argument('--solo-lectura',action='store_true')
    p.add_argument('--espera',type=float,default=0.25)
    p.add_argument('--historico',default='datos/lotoscan/historico_oficial')
    p.add_argument('--salida',default='salida_130')
    args=p.parse_args()
    if not 1<=args.dias<=21: p.error('--dias debe estar entre 1 y 21')
    if not 0<=args.espera<=5: p.error('--espera debe estar entre 0 y 5')
    try: end=dt.datetime.strptime(args.fecha_fin,'%Y%m%d').date() if args.fecha_fin else dt.datetime.now(ZoneInfo('Europe/Madrid')).date()
    except ValueError: p.error('--fecha-fin debe ser AAAAMMDD')
    out=Path(args.salida);out.mkdir(parents=True,exist_ok=True)
    history=Path(args.historico)
    report={'version':'1.30','fuente':'SELAE fechav3/fecha2','fecha_fin':end.isoformat(),
            'generado_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
            'solo_lectura':args.solo_lectura,'publicable':False,
            'validacion_premios_completa':False,'consultas':[],'sorteos':[]}
    seen={}; stats={'nuevo':0,'revisado':0,'sin_cambios':0,'candidato':0,'error':0,'sin_sorteo':0}
    for offset in range(args.dias):
        day=end-dt.timedelta(days=offset)
        for name,code in GAMES.items():
            endpoint='fecha2' if code=='LNAC' else 'fechav3'
            url=BASE+endpoint+'?'+urllib.parse.urlencode({'game_id':code,'fecha_sorteo':day.strftime('%Y%m%d')})
            raw,net=fetch(url)
            row={'juego':name,'game_id':code,'fecha_consultada':day.isoformat(),'endpoint':endpoint,**net}
            if raw is None:
                row['estado']='error_red';stats['error']+=1
            else:
                found,state=candidates(raw,code,day)
                row['estado']=state;row['encontrados']=len(found)
                if state in ('no_json','respuesta_no_lista'):
                    stats['error']+=1
                elif state=='sin_sorteo_para_fecha':
                    stats['sin_sorteo']+=1
                for item in found:
                    draw_id=str(item['id_sorteo']);key=(code,draw_id)
                    if key in seen:
                        row.setdefault('duplicados_en_ventana',[]).append(draw_id)
                        continue
                    seen[key]=True
                    issues=quality(item,code)
                    if day > dt.datetime.now(ZoneInfo('Europe/Madrid')).date():
                        issues.append('fecha_futura')
                        continue
                    if args.solo_lectura:
                        action='candidato';stats[action]+=1
                        # Copia íntegra solo en artefacto de diagnóstico, no histórico.
                        write_json(out/'candidatos'/code/f'{draw_id}.json',item)
                    else:
                        action,digest=update(history,code,item)
                        stats[action]+=1
                    report['sorteos'].append({'juego':name,'game_id':code,'id_sorteo':draw_id,
                        'fecha_sorteo':item.get('fecha_sorteo'),'accion':action,
                        'incidencias':issues,'publicable':False,'premios_verificados':False})
            report['consultas'].append(row)
            print(f"{day} {code} HTTP={net.get('http')} {row['estado']}",flush=True)
            time.sleep(args.espera)
    report['resumen']={'consultas':len(report['consultas']),'http_200':sum(x.get('http')==200 for x in report['consultas']),
        'sorteos_unicos':len(report['sorteos']),'juegos_con_sorteos':sorted(set(x['juego'] for x in report['sorteos'])),
        'acciones':stats,'publicados':0,'errores_reales':stats['error'],'dias_sin_sorteo':stats['sin_sorteo']}
    write_json(out/'informe_130.json',report)
    (out/'resumen_130.txt').write_text('LotoScan 1.30 — fuentes SELAE fechav3 / fecha2\n'+
        json.dumps(report['resumen'],ensure_ascii=False,indent=2)+'\n'+
        'Los datos archivados NO están certificados para calcular premios.\n',encoding='utf-8')
    print('RESUMEN',json.dumps(report['resumen'],ensure_ascii=False))
    # Fallar cuando absolutamente ninguna consulta tiene JSON coincidente, para no confundir HTTP 200 con éxito.
    if not report['sorteos']: raise SystemExit('No se obtuvo ningún sorteo identificable; revisar informe_130.json')
    if stats['error']:
        raise SystemExit(f'Consultas con errores reales: {stats["error"]}; consultar informe_130.json')

if __name__=='__main__': main()
