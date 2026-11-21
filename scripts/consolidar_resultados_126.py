#!/usr/bin/env python3
"""LotoScan 1.26: exclusivamente SELAE /servicios/resultados1.
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

def run(args):
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    report={'version':'1.26','fuente_unica':URL,'momento_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
            'juegos':{g:{'estado':'sin_resultado_identificado_en_respuesta'} for g in GAMES},
            'navidad':'excluida: conservar tratamiento anterior','publicacion_premios':False,
            'notas':['La consulta sin parámetros de resultados1 fue verificada previamente para Lotería Nacional.',
                     'No se presupone que una sola respuesta incluya los diez juegos.'], 'errores':[]}
    try:
        obj,sha=(json.loads(Path(args.json_prueba).read_text(encoding='utf-8')),None) if args.json_prueba else fetch(URL)
        if not isinstance(obj,(dict,list)):raise ValueError('JSON no contiene objeto o lista')
        entries=obj if isinstance(obj,list) else [obj]
        report['respuesta']={'tipo':type(obj).__name__,'elementos':len(entries),
                             'sha256_bytes':sha,'claves_raiz':list(obj)[:45] if isinstance(obj,dict) else []}
        report['no_identificados']=[]
        for item in entries:
            game=game_of(item)
            if game is None:
                report['no_identificados'].append({'claves':list(item)[:25] if isinstance(item,dict) else [],
                                                    'motivo':'Juego no identificado sin ambigüedad'})
                continue
            sid=draw_id(item);day=date_of(item)
            state=store(Path(args.historico),game,sid,day,item,args.solo_lectura)
            report['juegos'][game]={'estado':state,'id_sorteo':sid,'fecha':day,
                                    'campos':list(item)[:70],'publicable':False}
        if not args.solo_lectura:
            # Diagnóstico de la respuesta completa, sin inferir sorteos adicionales.
            atomic_json(Path(args.historico)/'_captura_ultima.json',{'fuente':URL,'respuesta':obj})
    except Exception as exc:
        report['errores'].append(str(exc))
    atomic_json(out/'diagnostico_126.json',report)
    lines=['LotoScan 1.26 — resultados1 exclusivamente',f'Fuente: {URL}']
    lines += [f'{g}: {v["estado"]}'+(f' ({v.get("fecha")})' if v.get('fecha') else '') for g,v in report['juegos'].items()]
    lines += ['No se usan resultados2, HTML ni PDF. No se certifican premios.']
    lines += ['ERRORES: '+ '; '.join(report['errores'])] if report['errores'] else []
    (out/'resumen_126.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('\n'.join(lines))
    return 1 if report['errores'] else 0

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',default='salida_126')
    parser.add_argument('--historico',default='datos/lotoscan/historico_126')
    parser.add_argument('--solo-lectura',action='store_true')
    parser.add_argument('--json-prueba',default='',help='Archivo JSON local para prueba sin red')
    sys.exit(run(parser.parse_args()))
