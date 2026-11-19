#!/usr/bin/env python3
"""LotoScan 0.87F: sondeo oficial SELAE, solo lectura y sin publicación.

Consulta cada fecha del intervalo para evitar asumir calendarios fijos o
confundir un día sin sorteo con un resultado sin premio.
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
from zoneinfo import ZoneInfo

BASE = 'https://www.loteriasyapuestas.es'
GAMES = [('euromillones','EMIL'),('primitiva','LAPR'),('bonoloto','BONO'),
         ('gordo-primitiva','ELGR'),('eurodreams','EDMS'),('loteria-nacional','LNAC'),
         ('quiniela','LAQU'),('quinigol','QGOL'),('lototurf','LOTU'),
         ('quintuple-plus','QUPL')]
HEADERS = {'User-Agent':'LotoScan/0.87F (diagnostico de resultados oficiales)',
           'Accept':'application/json, text/javascript, */*;q=0.8'}
OUTPUT = pathlib.Path('diagnostico_selae_087f')
MAX_BYTES = 2_000_000


def get(url, retries=2):
    last = None
    for attempt in range(retries+1):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=18) as response:
                raw = response.read(MAX_BYTES+1)
                if len(raw)>MAX_BYTES:
                    return {'http':response.status,'error':'respuesta_mayor_2mb'}, None
                return {'http':response.status,'content_type':response.headers.get('Content-Type',''),
                        'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}, raw
        except urllib.error.HTTPError as exc:
            last = {'http':exc.code,'error':f'HTTP_{exc.code}'}
            if exc.code not in (429,500,502,503,504):
                break
        except (OSError, TimeoutError) as exc:
            last = {'http':None,'error':type(exc).__name__}
        if attempt<retries:
            time.sleep(1.5*(attempt+1))
    return last or {'http':None,'error':'sin_respuesta'}, None


def evaluate(raw, game, day):
    """Validate identity and minimal structure; never claim prize completeness."""
    try:
        payload = json.loads(raw.decode('utf-8-sig'))
    except (UnicodeError, ValueError):
        return 'respuesta_no_json', None, ['no_json']
    if not isinstance(payload,list) or not payload:
        return 'sin_resultado', None, ['lista_vacia_o_error']
    candidates=[]
    for item in payload:
        if not isinstance(item,dict):
            continue
        if item.get('game_id')!=game:
            continue
        date_string=str(item.get('fecha_sorteo') or '')
        if date_string[:10]!=day.isoformat():
            continue
        candidates.append(item)
    if not candidates:
        return 'sin_resultado_para_fecha', None, ['identidad_o_fecha_no_coincide']
    if len(candidates)!=1:
        return 'ambiguo', None, ['multiples_resultados_misma_fecha']
    item=candidates[0]
    issues=[]
    draw_id=str(item.get('id_sorteo') or '')
    if not re.fullmatch(r'\d{6,20}',draw_id):
        issues.append('id_sorteo_invalido')
    combination=item.get('combinacion')
    if game=='LNAC':
        if not isinstance(combination,dict) or not combination.get('primer_premio') or not combination.get('Segundo_premio'):
            issues.append('premios_mayores_ausentes')
        if not isinstance(item.get('reintegros'),list) or not item['reintegros']:
            issues.append('reintegros_ausentes')
    elif not isinstance(combination,str) or not combination.strip():
        issues.append('combinacion_ausente')
    if not isinstance(item.get('escrutinio'),list) or not item['escrutinio']:
        issues.append('escrutinio_ausente')
    # No se interpreta un escrutinio presente como escrutinio completo.
    return ('candidato' if not issues else 'incompleto'), item, issues


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--dias',type=int,default=4,help='Dias naturales a consultar, incluido hoy (1-14)')
    parser.add_argument('--fecha-fin',default='',help='Fecha local final AAAAMMDD, vacio=hoy Madrid')
    parser.add_argument('--espera',type=float,default=0.25,help='Pausa entre consultas (0.2-3 s)')
    args=parser.parse_args()
    if not 1<=args.dias<=14: parser.error('--dias debe estar entre 1 y 14')
    if args.fecha_fin:
        try: end=dt.datetime.strptime(args.fecha_fin,'%Y%m%d').date()
        except ValueError: parser.error('Fecha final incorrecta (AAAAMMDD)')
    else:
        end=dt.datetime.now(ZoneInfo('Europe/Madrid')).date()
    OUTPUT.mkdir(exist_ok=True)
    report={'version':'0.87F','origen':'SELAE /servicios/fechav3 y /servicios/fecha2',
            'generado_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
            'fecha_fin':end.isoformat(),'dias':args.dias,
            'publicable':False,'historico_modificado':False,'consultas':[], 'candidatos':[]}
    seen={}
    for offset in range(args.dias):
        day=end-dt.timedelta(days=offset)
        for name,code in GAMES:
            endpoint='fecha2' if code=='LNAC' else 'fechav3'
            url=f'{BASE}/servicios/{endpoint}?'+urllib.parse.urlencode({'game_id':code,'fecha_sorteo':day.strftime('%Y%m%d')})
            net,raw=get(url)
            status, item, issues=('error_red',None,[net.get('error','sin_respuesta')])
            if raw is not None and net.get('http')==200:
                status,item,issues=evaluate(raw,code,day)
            entry={'juego':name,'game_id':code,'fecha_solicitada':day.isoformat(),
                   'endpoint':endpoint,'url':url,'estado':status,'incidencias':issues,**net}
            if item is not None:
                draw_id=str(item.get('id_sorteo'))
                entry['id_sorteo']=draw_id
                entry['fecha_sorteo']=item.get('fecha_sorteo')
                key=(code,draw_id)
                if key in seen:
                    entry['estado']='duplicado';entry['incidencias'].append('id_ya_visto')
                else:
                    seen[key]=day.isoformat()
                    # Guardar candidato completo en artefacto, nunca en historico.json.
                    filename=f'{day:%Y%m%d}_{code}_{draw_id}.json'
                    (OUTPUT/filename).write_text(json.dumps(item,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
                    entry['archivo']=filename
                    report['candidatos'].append({'juego':name,'game_id':code,'id_sorteo':draw_id,
                                                  'fecha':day.isoformat(),'estado':status,'archivo':filename,
                                                  'validacion_premios_completa':False})
            report['consultas'].append(entry)
            print(f'{day} {code:4} HTTP={str(net.get("http")):>4} {entry["estado"]}')
            time.sleep(max(0.2,min(args.espera,3)))
    statuses={}
    for e in report['consultas']:
        statuses[e['estado']]=statuses.get(e['estado'],0)+1
    report['resumen']={'consultas':len(report['consultas']),'http_200':sum(e.get('http')==200 for e in report['consultas']),
                       'estados':statuses,'candidatos_unicos':len(report['candidatos']),
                       'juegos_con_candidatos':sorted(set(c['juego'] for c in report['candidatos'])),
                       'publicados':0}
    pathlib.Path('informe_selae_087f.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    lines=['LotoScan 0.87F — Sondeo diario oficial (SOLO DIAGNOSTICO)',
           f'Periodo: {end-dt.timedelta(days=args.dias-1)} a {end}',
           json.dumps(report['resumen'],ensure_ascii=False,indent=2),
           'Ningun candidato se considera validado para premios ni publicable.',
           'No se modifica historico.json.', '']
    lines += [f'{e["fecha_solicitada"]} {e["game_id"]}: HTTP {e.get("http")} / {e["estado"]} / {",".join(e["incidencias"])}' for e in report['consultas']]
    pathlib.Path('informe_selae_087f.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('RESUMEN:',json.dumps(report['resumen'],ensure_ascii=False))

if __name__=='__main__':main()
