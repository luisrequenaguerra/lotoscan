#!/usr/bin/env python3
"""LotoScan 1.27: exclusivamente SELAE /servicios/resultados1.
Conserva el JSON oficial íntegro y un histórico incremental con revisiones.
NO usa resultados2, HTML ni PDF. Navidad queda fuera de este proceso.
No certifica premios ni atribuye datos a juegos que la fuente no identifique.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import urllib.parse
import urllib.request

URL = 'https://www.loteriasyapuestas.es/servicios/resultados1'
GAMES = ('euromillones','primitiva','bonoloto','gordo-primitiva','eurodreams',
         'loteria-nacional','quiniela','quinigol','lototurf','quintuple-plus')
ALIASES = {
 'euromillones':('euromillones',), 'primitiva':('primitiva',),
 'bonoloto':('bonoloto',), 'gordo-primitiva':('gordo de la primitiva','el gordo','gordo-primitiva'),
 'eurodreams':('eurodreams','euro dreams'), 'loteria-nacional':('lotería nacional','loteria nacional'),
 'quiniela':('quiniela',), 'quinigol':('quinigol',), 'lototurf':('lototurf',),
 'quintuple-plus':('quíntuple plus','quintuple plus','quintuple-plus')}

def fetch(url):
    u=urllib.parse.urlsplit(url)
    if u.scheme!='https' or u.hostname!='www.loteriasyapuestas.es' or u.path!='/servicios/resultados1':
        raise ValueError('Solo se permite SELAE /servicios/resultados1')
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (LotoScan/1.26)',
                                           'Accept':'application/json,text/plain,*/*'})
    with urllib.request.urlopen(req,timeout=35) as resp:
        end=urllib.parse.urlsplit(resp.url)
        if end.scheme!='https' or end.hostname!='www.loteriasyapuestas.es' or end.path!='/servicios/resultados1':
            raise ValueError('Redirección fuera del endpoint autorizado')
        if resp.status!=200:raise ValueError(f'HTTP {resp.status}')
        raw=resp.read(5_000_001)
    if len(raw)>5_000_000:raise ValueError('JSON demasiado grande')
    return json.loads(raw),hashlib.sha256(raw).hexdigest()

def game_of(obj):
    if not isinstance(obj,dict):return None
    # Identificación explícita. No se infiere a partir de la fecha ni de números.
    labels=[str(obj.get(k) or '').lower() for k in
            ('nombreJuego','juego','game','nombreDelJuego','nombreDelSorteo','tipoJuego')]
    for game,aliases in ALIASES.items():
        if any(alias in label for label in labels for alias in aliases):return game
    # Esquema específico de Lotería Nacional observado en 0.87Z/1.25.
    if {'drawIdSorteo','primerPremio','segundoPremio','reintegros'} <= set(obj):
        return 'loteria-nacional'
    return None

def draw_id(obj):
    for key in ('drawIdSorteo','idSorteo','idsorteo','id_sorteo'):
        value=obj.get(key)
        if isinstance(value,(str,int)) and re.fullmatch(r'[A-Za-z0-9_-]{3,60}',str(value)):
            return str(value)
    return None

def date_of(obj):
    for key in ('fechaSorteo','fecha','drawDate'):
        v=obj.get(key)
        if isinstance(v,str):
            try:return dt.date.fromisoformat(v[:10]).isoformat()
            except ValueError:pass
    return None

def atomic_json(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    os.replace(tmp,path)

def store(base,game,sid,day,obj,read_only):
    if not sid or not day:return 'sin_identificador_o_fecha'
    if dt.date.fromisoformat(day)>dt.datetime.now(dt.timezone.utc).date():return 'fecha_futura_no_archivada'
    folder=base/game/sid
    canonical=folder/'actual.json'
    # Canonicalización evita cambios por orden de claves/espaciado del JSON.
    fingerprint=hashlib.sha256(json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    revision=folder/'revisiones'/(fingerprint+'.json')
    if canonical.exists():
        previous=json.loads(canonical.read_text(encoding='utf-8'))
        if previous.get('huella_contenido')==fingerprint:return 'sin_cambios'
        if read_only:return 'actualizacion_detectada_solo_lectura'
        atomic_json(revision,{'fuente':URL,'fecha_sorteo':day,'id_sorteo':sid,'huella_contenido':fingerprint,'respuesta':obj})
        atomic_json(canonical,{'fuente':URL,'fecha_sorteo':day,'id_sorteo':sid,'huella_contenido':fingerprint,'respuesta':obj,
                               'actualizado_utc':dt.datetime.now(dt.timezone.utc).isoformat()})
        return 'actualizado_con_revision'
    if read_only:return 'nuevo_detectado_solo_lectura'
    atomic_json(revision,{'fuente':URL,'fecha_sorteo':day,'id_sorteo':sid,'huella_contenido':fingerprint,'respuesta':obj})
    atomic_json(canonical,{'fuente':URL,'fecha_sorteo':day,'id_sorteo':sid,'huella_contenido':fingerprint,'respuesta':obj,
                           'actualizado_utc':dt.datetime.now(dt.timezone.utc).isoformat()})
    return 'nuevo_archivado'

# Códigos oficiales observados en el extractor 0.87F y sus respuestas archivadas.
CODES = {'euromillones':'EMIL','primitiva':'LAPR','bonoloto':'BONO',
         'gordo-primitiva':'ELGR','eurodreams':'EDMS','loteria-nacional':'LNAC',
         'quiniela':'LAQU','quinigol':'QGOL','lototurf':'LOTU','quintuple-plus':'QUPL'}

def identify(item):
    if not isinstance(item,dict):return None
    code=str(item.get('game_id') or item.get('gameId') or '').upper()
    for name, known in CODES.items():
        if code==known:return name
    return game_of(item)

def draw_id(item):
    for k in ('id_sorteo','drawIdSorteo','idSorteo','idsorteo'):
        v=item.get(k)
        if v is not None and re.fullmatch(r'[0-9]{6,20}',str(v)):return str(v)
    return None

def date_of(item):
    for k in ('fecha_sorteo','fechaSorteo','fecha','drawDate'):
        v=item.get(k)
        if isinstance(v,str):
            try:return dt.date.fromisoformat(v[:10]).isoformat()
            except ValueError:pass
    return None

def run(args):
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    report={'version':'1.27','fuente_exclusiva':URL,'consultas':[],
            'juegos':{g:{'estado':'pendiente'} for g in GAMES},
            'navidad':'tratamiento independiente no modificado',
            'premios_certificados':False,'errores':[],
            'advertencia':'El uso de game_id con resultados1 es una hipótesis que debe confirmarse con respuestas reales; los nueve juegos históricos fueron consultados mediante fechav3/fecha2.'}
    for game,code in CODES.items():
        # Un endpoint, diez consultas diferenciadas. No se consulta resultados2, fecha2, fechav3, HTML ni PDF.
        url=URL+'?'+urllib.parse.urlencode({'game_id':code})
        row={'juego':game,'game_id_solicitado':code,'url':url}
        try:
            if args.json_prueba_dir:
                path=Path(args.json_prueba_dir)/(code+'.json')
                if not path.exists():
                    row['estado']='sin_fixture';report['consultas'].append(row);continue
                obj=json.loads(path.read_text(encoding='utf-8'));sha=None
            else:obj,sha=fetch(url)
            entries=obj if isinstance(obj,list) else [obj]
            row.update(http=200,sha256=sha,elementos=len(entries),tipo=type(obj).__name__)
            matching=[x for x in entries if identify(x)==game]
            others=sorted(set(identify(x) for x in entries if identify(x) and identify(x)!=game))
            row['otros_juegos_recibidos']=others
            if not matching:
                row['estado']='sin_resultado_del_juego';report['juegos'][game]={'estado':row['estado']}
            else:
                states=[]
                for item in matching:
                    sid=draw_id(item);day=date_of(item)
                    state=store(Path(args.historico),game,sid,day,item,args.solo_lectura)
                    states.append({'id_sorteo':sid,'fecha':day,'estado':state,
                                   'campos':list(item)[:60],
                                   'elige8_detectado':('elige8' in json.dumps(item,ensure_ascii=False).lower()) if game=='quiniela' else None})
                row['estado']='recibido';row['sorteos']=states
                report['juegos'][game]={'estado':'recibido','sorteos':states}
        except Exception as exc:
            row['estado']='error';row['error']=str(exc)[:300]
            report['juegos'][game]={'estado':'error','detalle':row['error']}
            report['errores'].append(game+': '+row['error'])
        report['consultas'].append(row)
    atomic_json(out/'diagnostico_127.json',report)
    lines=['LotoScan 1.27 — solo resultados1; diez consultas diferenciadas',
           'Códigos de juego recuperados de 0.87F; compatibilidad de parámetros por confirmar.']
    lines += [g+': '+report['juegos'][g]['estado'] for g in GAMES]
    lines += ['Sin resultados2, fechav3, fecha2, HTML ni PDF. Navidad no modificada.',
              'La presencia de JSON no certifica premios ni modalidades complementarias.']
    (out/'resumen_127.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('\n'.join(lines))
    return 1 if report['errores'] else 0

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',default='salida_127')
    parser.add_argument('--historico',default='datos/lotoscan/historico_127')
    parser.add_argument('--solo-lectura',action='store_true')
    parser.add_argument('--json-prueba-dir',default='',help='Carpeta de JSON de prueba, uno por código')
    sys.exit(run(parser.parse_args()))
