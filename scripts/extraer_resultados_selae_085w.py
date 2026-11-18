
#!/usr/bin/env python3
"""LotoScan 0.85W: resultados candidatos SELAE, SOLO LECTURA.
No altera historico.json ni publica resultados. Las validaciones son estructurales,
NO equivalen a verificacion de premios ni compatibilidad con el esquema de LotoScan.
"""
import datetime as dt
import json
import re
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path
from bs4 import BeautifulSoup

URL = 'https://www.loteriasyapuestas.es/es/resultados'
HEADERS = {'User-Agent':'Mozilla/5.0 (LotoScan diagnostic 0.85U)',
           'Accept':'text/html,application/xhtml+xml',
           'Cache-Control':'no-cache','Pragma':'no-cache'}
CODES = {'euromillones':'EMIL','bonoloto':'BONO','primitiva':'LAPR',
         'eurodreams':'EDMS','gordo-primitiva':'ELGR',
         'loteria-nacional':'LNACJ','quinigol':'QGOL',
         'lototurf':'LOTU','quintuple-plus':'QUPL'}
COUNTS = {'euromillones':(5,13),'bonoloto':(6,6),'primitiva':(6,7),
          'eurodreams':(6,6),'gordo-primitiva':(5,9),
          'loteria-nacional':(0,3),'quinigol':(6,5),
          'lototurf':(6,8),'quintuple-plus':(6,5)}
DATE = re.compile(r'(?<!\d)([0-3]?\d/[01]?\d/20\d{2})(?!\d)')
MONEY = re.compile(r'^\d[\d.]*,\d{2}\s*€$')

def text(el):
    return ' '.join(el.get_text(' ', strip=True).split()) if el else ''

def node(soup, identifier):
    # SELAE occasionally duplicates ids in hidden order-of-appearance variants.
    return soup.find(id=identifier)

def value(soup, identifier):
    return text(node(soup, identifier))

def balls(soup, identifier):
    ul=node(soup,identifier)
    if ul is None: return []
    return [text(x) for x in ul.find_all('li',recursive=False)]

def prize_rows(soup, game, code):
    # Anchor to the specific game's prize table; don't collect other games' rows.
    table=node(soup, ('qa_resultadoSorteo-escrutinio-' if game=='loteria-nacional' else 'qa_ultResult-'+code+'-escrutinio') + (code if game=='loteria-nacional' else ''))
    # The first variant already includes LNACJ in its prefix; fallback explicit ID.
    if game=='loteria-nacional': table=node(soup,'qa_resultadoSorteo-escrutinio-'+code)
    if not table: return []
    result=[]
    for tr in table.find_all('tr'):
        cells=[text(c) for c in tr.find_all(['th','td'],recursive=False)]
        if len(cells)>=3 and ('€' in ' '.join(cells) or 'al mes' in ' '.join(cells)):
            result.append(cells)
    return result

def parse(soup,game,code):
    prefix='qa_resultadoSorteo-' if game=='loteria-nacional' else 'qa_ultResult-'
    date=value(soup, ('qa_resultadoSorteo-fecha-' if game=='loteria-nacional' else 'qa_ultResult-'+code+'-fecha') + (code if game=='loteria-nacional' else ''))
    if game=='loteria-nacional':date=value(soup,'qa_resultadoSorteo-fecha-'+code)
    r={'juego':game,'fecha':date,'combinacion':[], 'adicionales':{},'premios':[], 'errores':[],'validado':False}
    if game in ('quinigol','quintuple-plus'):
        key='signoGanador' if game=='quinigol' else 'ganador'
        for i in range(1,7):
            cell=node(soup,f'qa_ultResult-{code}-{key}{i}')
            r['combinacion'].append(text(cell))
            if not text(cell):r['errores'].append(f'Falta resultado {i}')
    elif game=='loteria-nacional':
        r['adicionales']['primer_premio']=value(soup,f'qa_resultadoSorteo-premio-{code}-G1')
        r['adicionales']['segundo_premio']=value(soup,f'qa_resultadoSorteo-premio-{code}-Z2')
        r['adicionales']['reintegros']=[value(soup,f'qa_resultadoSorteo-reintegro-{code}-{i}') for i in range(1,4)]
        if not re.fullmatch(r'\d{5}',r['adicionales']['primer_premio']):r['errores'].append('Primer premio no válido')
        if not re.fullmatch(r'\d{5}',r['adicionales']['segundo_premio']):r['errores'].append('Segundo premio no válido')
        if any(not re.fullmatch(r'\d',x) for x in r['adicionales']['reintegros']):r['errores'].append('Reintegros incompletos')
        r['errores'].append('Lotería Nacional: resumen insuficiente para comprobar todas las terminaciones y aproximaciones')
    else:
        r['combinacion']=balls(soup,f'qa_ultResult-combination-mainNumbers-{code}')
        if game=='euromillones':r['adicionales']['estrellas']=balls(soup,f'qa_ultResult-combination-mainNumbers-{code}-stars')
        if game in ('bonoloto','primitiva','lototurf'):
            r['adicionales']['complementario']=value(soup,f'qa_ultResult-{code}-complementario')
            r['adicionales']['reintegro']=value(soup,f'qa_ultResult-{code}-reintegro')
        if game=='gordo-primitiva':
            # Avoid guessing the DOM identifier: report missing extra explicitly.
            r['errores'].append('Clave de El Gordo pendiente de selector confirmado')
        if game=='eurodreams':r['errores'].append('Número Sueño pendiente de selector confirmado')
        if game=='lototurf':r['errores'].append('Caballo ganador: revisar semántica del complementario')
        n=COUNTS[game][0]
        if len(r['combinacion'])!=n or any(not re.fullmatch(r'\d{1,2}',x) for x in r['combinacion']):
            r['errores'].append(f'Combinación incompleta: esperados {n}, recibidos {len(r["combinacion"])}')
        elif len(set(map(int,r['combinacion'])))!=n:r['errores'].append('Números duplicados')
        if game=='euromillones' and (len(r['adicionales']['estrellas'])!=2 or any(not re.fullmatch(r'\d{1,2}',x) for x in r['adicionales']['estrellas'])):
            r['errores'].append('Estrellas incompletas')
        if game in ('bonoloto','primitiva'):
            if not re.fullmatch(r'\d{1,2}',r['adicionales']['complementario']):r['errores'].append('Complementario inválido')
            if not re.fullmatch(r'\d',r['adicionales']['reintegro']):r['errores'].append('Reintegro inválido')
    match=DATE.search(date)
    r['fecha_original']=date
    r['fecha']=match.group(1) if match else None
    if not match:r['errores'].append('Fecha ausente o inválida')
    else:
        try:
            draw_date=dt.datetime.strptime(r['fecha'],'%d/%m/%Y').date()
            if draw_date>dt.datetime.now(dt.timezone.utc).date():r['errores'].append('Fecha futura')
        except ValueError:r['errores'].append('Fecha imposible')
    r['premios']=prize_rows(soup,game,code)
    expected=COUNTS[game][1]
    if len(r['premios'])!=expected:r['errores'].append(f'Categorías: esperadas {expected}, recibidas {len(r["premios"])}')
    # Non-monetary EuroDreams awards are preserved as text.
    if game in ('quinigol','quintuple-plus'):
        r['errores'].append('Validación semántica de pronósticos pendiente')
    if game=='euromillones':
        r['errores'].append('El Millón: código no incorporado aún')
    if game=='primitiva':
        r['errores'].append('Joker: premios independientes no incorporados aún')
    r['validado']=not r['errores']
    r['publicable']=False
    return r

def main():
    report={'version':'0.85W','fuente':URL,'generado_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
            'solo_lectura':True,'publicable':False,'resultados':[],'error':None,
            'aviso':'Validación estructural experimental; incluso los registros sin errores NO están aprobados para publicar ni calcular premios.'}
    try:
        req=urllib.request.Request(URL,headers=HEADERS)
        with urllib.request.urlopen(req,timeout=40) as response:
            parsed=urllib.parse.urlsplit(response.url)
            if response.status!=200 or parsed.scheme!='https' or parsed.hostname not in ('www.loteriasyapuestas.es','loteriasyapuestas.es'):
                raise RuntimeError('HTTP o destino inesperado')
            report['http']=response.status
            report['respuesta']={k:response.headers.get(k,'') for k in ('Content-Type','Age','Last-Modified','Server','Via')}
            raw=response.read(5_000_001)
            if len(raw)>5_000_000:raise RuntimeError('HTML demasiado grande')
        soup=BeautifulSoup(raw,'html.parser')
        report['http']=200
        report['resultados']=[parse(soup,g,c) for g,c in CODES.items()]
    except urllib.error.HTTPError as exc:
        report['http']=exc.code
        report['respuesta']={k:exc.headers.get(k,'') for k in ('Content-Type','Age','Last-Modified','Server','Via')}
        report['error']=f'HTTPError: HTTP {exc.code} {exc.reason}'
    except Exception as exc:report['error']=f'{type(exc).__name__}: {exc}'
    Path('informe_selae_085w.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=[f'LotoScan 0.85W | HTTP {report.get("http","ERROR")} | SOLO LECTURA']
    for r in report['resultados']:
        lines.append(f'{r["juego"]}: {r["fecha"]} | números={r["combinacion"]} | premios={len(r["premios"])} | validado={r["validado"]}')
        lines.extend('  PENDIENTE: '+e for e in r['errores'])
    if report.get('respuesta'):lines.append('Cabeceras de respuesta: '+json.dumps(report['respuesta'],ensure_ascii=False))
    if report['error']:lines.append('ERROR: '+report['error'])
    lines.append('No se ha escrito historico.json ni se ha modificado la aplicación.')
    Path('informe_selae_085w.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('\n'.join(lines))
    if report['error']:raise SystemExit(1)

if __name__=='__main__':main()
