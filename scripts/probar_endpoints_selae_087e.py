#!/usr/bin/env python3
"""LotoScan 0.87E: diagnóstico de servicios de resultados oficiales SELAE.
Solo lectura; no modifica históricos ni publica resultados.
"""
import argparse
import datetime as dt
import hashlib
import json
import pathlib
import re
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = 'https://www.loteriasyapuestas.es'
JUEGOS = [
    ('euromillones','EMIL','20261117'),
    ('primitiva','LAPR','20261116'),
    ('bonoloto','BONO','20261117'),
    ('gordo-primitiva','ELGR','20261115'),
    ('eurodreams','EDMS','20261116'),
    ('loteria-nacional','LNAC','20261114'),
    ('quiniela','LAQU','20261115'),
    ('quinigol','QGOL','20261117'),
    ('lototurf','LOTU','20261115'),
    ('quintuple-plus','QUPL','20261115'),
]
HEADERS = {
    'User-Agent': 'LotoScan/0.87E (diagnostico de acceso a resultados oficiales)',
    'Accept': 'application/json, text/javascript, */*;q=0.8',
}

def request(url, timeout=20):
    req = urllib.request.Request(url, headers=HEADERS)
    result = {'url':url, 'http':None, 'final_url':None, 'content_type':None,
              'bytes':0, 'sha256':None, 'json_valido':False, 'error':None}
    raw = b''
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            result['http'] = response.status
            result['final_url'] = response.geturl()
            result['content_type'] = response.headers.get('Content-Type','')
            raw = response.read(2_000_001)
            if len(raw)>2_000_000:
                result['error'] = 'Respuesta mayor de 2 MB; truncada'
                raw = raw[:2_000_000]
    except urllib.error.HTTPError as exc:
        result['http'] = exc.code
        result['final_url'] = exc.geturl()
        result['content_type'] = exc.headers.get('Content-Type','')
        raw = exc.read(8192)
        result['error'] = f'HTTP {exc.code}'
    except Exception as exc:
        result['error'] = f'{type(exc).__name__}: {str(exc)[:300]}'
    result['bytes'] = len(raw)
    result['sha256'] = hashlib.sha256(raw).hexdigest() if raw else None
    return result, raw

def describe(obj):
    if isinstance(obj, list):
        return {'tipo':'lista', 'elementos':len(obj), 'primer_elemento':describe(obj[0]) if obj else None}
    if isinstance(obj, dict):
        return {'tipo':'objeto', 'claves':list(obj.keys())[:50],
                'tipos':{str(k):type(v).__name__ for k,v in list(obj.items())[:30]}}
    return {'tipo':type(obj).__name__, 'valor_corto':str(obj)[:120]}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--fecha',default='',help='AAAAMMDD opcional para todas las consultas históricas')
    ap.add_argument('--espera',type=float,default=0.35)
    args=ap.parse_args()
    if args.fecha:
        try: dt.datetime.strptime(args.fecha,'%Y%m%d')
        except ValueError: ap.error('--fecha debe ser AAAAMMDD válida')
    folder=pathlib.Path('diagnostico_selae_087e')
    folder.mkdir(exist_ok=True)
    informe={'version':'0.87E','origen':'Servicios observados en HTML oficial SELAE (0.87D)',
             'generado_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
             'publicable':False,'historico_modificado':False,'consultas':[]}
    for i,(name,code,historical) in enumerate(JUEGOS,1):
        endpoint='fecha2' if code=='LNAC' else 'fechav3'
        for tipo,fecha in [('ultimo',''),('historico',args.fecha or historical)]:
            params={'game_id':code}
            if fecha: params['fecha_sorteo']=fecha
            url=f'{BASE}/servicios/{endpoint}?{urllib.parse.urlencode(params)}'
            info,raw=request(url)
            info.update(juego=name,game_id=code,modo=tipo,fecha_solicitada=fecha,
                        endpoint=endpoint,fecha_respuesta=None,estructura=None,
                        datos_utiles_confirmados=False)
            if raw:
                filename=f'{i:02d}_{name}_{tipo}.respuesta.txt'
                # Archivar respuesta limitada para inspección; datos de resultados públicos.
                (folder/filename).write_bytes(raw)
                info['archivo_respuesta']=filename
                decoded=raw.decode('utf-8','replace').strip().lstrip('\ufeff')
                try:
                    obj=json.loads(decoded)
                    info['json_valido']=True
                    info['estructura']=describe(obj)
                    matches=re.findall(r'(?<!\d)(?:20\d{6}|20\d{2}-\d{2}-\d{2})(?!\d)',decoded)
                    info['fechas_en_contenido']=list(dict.fromkeys(matches))[:15]
                    # Sin validación semántica no se marca resultado publicable.
                except (ValueError,TypeError):
                    info['muestra_texto']=re.sub(r'\s+',' ',decoded[:250])
            informe['consultas'].append(info)
            print(f'{name:19} {tipo:9} HTTP={info["http"]} bytes={info["bytes"]} JSON={info["json_valido"]} error={info["error"]}')
            time.sleep(max(0,min(args.espera,3)))
    informe['resumen']={
        'consultas':len(informe['consultas']),
        'http_200':sum(x['http']==200 for x in informe['consultas']),
        'http_403':sum(x['http']==403 for x in informe['consultas']),
        'json_validos':sum(x['json_valido'] for x in informe['consultas']),
        'juegos_con_json':sorted({x['juego'] for x in informe['consultas'] if x['json_valido']}),
        'resultados_semanticamente_validados':0,
    }
    pathlib.Path('informe_selae_087e.json').write_text(json.dumps(informe,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['LotoScan 0.87E - Servicios oficiales SELAE','',json.dumps(informe['resumen'],ensure_ascii=False,indent=2),'',
           'NOTA: HTTP 200 y JSON válido no garantizan resultado correcto ni completo.','No se publica ni modifica historico.json.','']
    for x in informe['consultas']:
        lines.append(f'{x["juego"]} {x["modo"]}: HTTP {x["http"]}, {x["bytes"]} bytes, JSON={x["json_valido"]}, estructura={x["estructura"]}, error={x["error"]}')
    pathlib.Path('informe_selae_087e.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('RESUMEN',json.dumps(informe['resumen'],ensure_ascii=False))

if __name__=='__main__': main()
