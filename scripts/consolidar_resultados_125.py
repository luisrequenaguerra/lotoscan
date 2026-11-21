#!/usr/bin/env python3
"""LotoScan 1.25 reutiliza extractor 0.85W: resultados candidatos SELAE, SOLO LECTURA.
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


# 1.25: orquestación incremental, fuente oficial y cuarentena para resultados parciales.
import argparse, hashlib, os, tempfile, urllib.parse, urllib.request
from pypdf import PdfReader
MONTHS = {'enero':1,'febrero':2,'marzo':3,'abril':4,'mayo':5,'junio':6,'julio':7,'agosto':8,'septiembre':9,'octubre':10,'noviembre':11,'diciembre':12}
def cents(s):
    if s.upper() == 'BOTE': return None
    return int(s.replace('.','').replace(',',''))

def parse_quiniela_pdf(path):
    reader = PdfReader(str(path))
    if not reader.pages: raise ValueError('PDF sin páginas')
    raw = '\n'.join(p.extract_text(extraction_mode='layout') or '' for p in reader.pages)
    # Layout PDF extraction may differ by library. Normalize whitespace but preserve order.
    compact = re.sub(r'\s+', ' ', raw)
    dm = re.search(r'(\d{1,2})\s+de\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\s+de\s+(20\d{2})',compact,re.I)
    if not dm: raise ValueError('Fecha ausente')
    day = date(int(dm.group(3)), MONTHS[dm.group(2).lower()], int(dm.group(1))).isoformat()
    sm = re.search(r'(?<![A-Z0-9])([12X](?:\s*-\s*[12X]){13})(?![A-Z0-9])', compact, re.I)
    if not sm: raise ValueError('No se encuentran los 14 signos')
    signs = re.findall('[12X]',sm.group(1).upper())
    pm = re.search(r'Pleno\s+al\s+quince\s*-?\s*([012M])\s*([012M])\s*-?', compact, re.I)
    if not pm:
        # Some PDFs place the plenary header after the combination.
        vicinity = compact[sm.end():sm.end()+130]
        pm = re.search(r'-\s*([012M])\s*([012M])\s*-',vicinity,re.I)
    if not pm: raise ValueError('Pleno al 15 ausente')
    pleno = (pm.group(1)+pm.group(2)).upper()
    # Locate prize rows by label rather than relying on column order.
    rows=[]
    for label in ['Pleno al 15','14 Aciertos','13 Aciertos','12 Aciertos','11 Aciertos','10 Aciertos']:
        pat = re.compile(re.escape(label)+r'\s+([\d.]+)\s+(BOTE|[\d.]+,\d{2})',re.I)
        m = pat.search(compact)
        if not m: raise ValueError('Categoría no recuperada: '+label)
        rows.append({'categoria':label,'acertantes':int(m.group(1).replace('.','')),'premio_centimos':cents(m.group(2))})
    em = re.search(r'REPARTO DE PREMIOS Elige8.*?\b8\s+([\d.]+)\s+([\d.]+,\d{2})',compact,re.I)
    if not em: raise ValueError('Elige8 no recuperado')
    return {'fecha':day,'signos':signs,'pleno_15':pleno,'categorias':rows,'elige8':{'acertantes':int(em.group(1).replace('.','')),'premio_centimos':cents(em.group(2))},'fuente':path.name}



OFFICIAL_HOSTS={'www.loteriasyapuestas.es','loteriasyapuestas.es'}
RESULTADOS1='https://www.loteriasyapuestas.es/servicios/resultados1'
QUINIELA_PAGE='https://www.loteriasyapuestas.es/es/resultados/quiniela'

def fetch_official(url, limit=5_000_000):
    p=urllib.parse.urlsplit(url)
    if p.scheme!='https' or p.hostname not in OFFICIAL_HOSTS:
        raise ValueError('Solo se admiten URLs HTTPS de SELAE')
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (LotoScan/1.25)','Accept':'application/json,text/html,application/pdf,*/*'})
    with urllib.request.urlopen(req,timeout=40) as r:
        final=urllib.parse.urlsplit(r.url)
        if r.status!=200 or final.scheme!='https' or final.hostname not in OFFICIAL_HOSTS:
            raise ValueError('Respuesta o redireccion fuera de SELAE')
        data=r.read(limit+1)
        if len(data)>limit: raise ValueError('Respuesta excesiva')
        return data

def save_incremental(path, payload):
    path.parent.mkdir(parents=True,exist_ok=True)
    blob=json.dumps(payload,ensure_ascii=False,sort_keys=True,indent=2)+'\n'
    if path.exists():
        prev=json.loads(path.read_text(encoding='utf-8'))
        if prev==payload:return 'ya_archivado'
        return 'conflicto_sin_sobrescribir'
    path.write_text(blob,encoding='utf-8')
    return 'nuevo_archivado'

def q_from_html(soup):
    # Diagnostico de la pagina actual; NO deducir resultados a partir de textos sueltos.
    candidates=[]
    for a in soup.find_all('a',href=True):
        href=urllib.parse.urljoin(QUINIELA_PAGE,a['href'])
        if urllib.parse.urlsplit(href).hostname not in OFFICIAL_HOSTS:continue
        label=' '.join(a.get_text(' ',strip=True).split())
        if ('quiniela' in (href+' '+label).lower() and ('.pdf' in href.lower() or 'nota' in label.lower())):
            candidates.append({'url':href,'texto':label[:120]})
    return candidates[:30]

def main125():
    ap=argparse.ArgumentParser()
    ap.add_argument('--out',default='salida_125')
    ap.add_argument('--historico',default='datos/lotoscan/historico_125')
    ap.add_argument('--quiniela-pdf-url',default='',help='PDF oficial SELAE de Quiniela/Elige8, opcional')
    ap.add_argument('--solo-lectura',action='store_true',help='No escribir historico')
    args=ap.parse_args()
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    history=Path(args.historico)
    report={'version':'1.25','fecha_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
      'fuentes':{'ultimos':'https://www.loteriasyapuestas.es/es/resultados','nacional':RESULTADOS1,'quiniela':QUINIELA_PAGE},
      'juegos':{},'quiniela':{},'publicable':False,'premios_certificados':False,'errores_globales':[]}
    # Reutiliza el extractor real 0.85W para nueve juegos. Sus errores se preservan.
    try:
        html=fetch_official(URL)
        (out/'fuente_resultados_sha256.txt').write_text(hashlib.sha256(html).hexdigest()+'\n')
        soup=BeautifulSoup(html,'html.parser')
        for game,code in CODES.items():
            try:
                result=parse(soup,game,code)
                result['fuente']='SELAE /es/resultados (extractor reutilizado 0.85W)'
                report['juegos'][game]=result
                if result.get('fecha') and not args.solo_lectura:
                    date=dt.datetime.strptime(result['fecha'],'%d/%m/%Y').date().isoformat()
                    dest=history/game/(date+'.json')
                    result['historico_estado']=save_incremental(dest,{k:v for k,v in result.items() if k!='historico_estado'})
                else:result['historico_estado']='sin_fecha_o_solo_lectura'
            except Exception as e:
                report['juegos'][game]={'error':str(e),'publicable':False}
    except Exception as e:report['errores_globales'].append('Pagina nueve juegos: '+str(e))
    # resultados1 fue verificado en 0.87Z para LNAC; no se atribuye a todos los juegos.
    try:
        raw=fetch_official(RESULTADOS1)
        obj=json.loads(raw)
        report['resultados1']={'sha256':hashlib.sha256(raw).hexdigest(),
          'tipo':type(obj).__name__,'id_sorteo':obj.get('drawIdSorteo') if isinstance(obj,dict) else None,
          'fecha':obj.get('fechaSorteo') if isinstance(obj,dict) else None,
          'claves':list(obj)[:45] if isinstance(obj,dict) else [],'publicable':False}
        if isinstance(obj,dict) and obj.get('drawIdSorteo') and not args.solo_lectura:
            sid=str(obj['drawIdSorteo'])
            if re.fullmatch(r'[0-9]{5,20}',sid):
                report['resultados1']['historico_estado']=save_incremental(history/'loteria_nacional'/(sid+'.resultados1.json'),
                    {'origen':RESULTADOS1,'sha256':hashlib.sha256(raw).hexdigest(),'respuesta':obj})
    except Exception as e:report['resultados1']={'error':str(e),'publicable':False}
    # La Quiniela: reutiliza parser de notas oficiales 0.86L, con Elige8.
    # No inventa un PDF ni un resultado si no se localiza fuente utilizable.
    try:
        qhtml=fetch_official(QUINIELA_PAGE)
        report['quiniela']['pagina_sha256']=hashlib.sha256(qhtml).hexdigest()
        report['quiniela']['enlaces_pdf_candidatos']=q_from_html(BeautifulSoup(qhtml,'html.parser'))
    except Exception as e:report['quiniela']['error_pagina']=str(e)
    if args.quiniela_pdf_url:
        try:
            raw=fetch_official(args.quiniela_pdf_url,limit=12_000_000)
            if not raw.startswith(b'%PDF'):raise ValueError('El recurso no es PDF')
            with tempfile.TemporaryDirectory() as tmp:
                path=Path(tmp)/'quiniela.pdf';path.write_bytes(raw)
                result=parse_quiniela_pdf(path)
            result['juego']='la_quiniela';result['modalidades']=['quiniela','pleno_15','elige8']
            result['sha256_pdf']=hashlib.sha256(raw).hexdigest()
            result['url_pdf']=args.quiniela_pdf_url
            result['publicable']=False
            report['quiniela']['resultado_pdf']=result
            if not args.solo_lectura:
                report['quiniela']['historico_estado']=save_incremental(history/'la_quiniela'/(result['fecha']+'.json'),result)
        except Exception as e:report['quiniela']['error_pdf']=str(e)
    else:report['quiniela']['estado']='PDF no aportado; solo descubrimiento de enlaces'
    (out/'diagnostico_125.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    lines=['LotoScan 1.25 — recuperación de extractores históricos','Fuente nueve juegos: SELAE /es/resultados',
      'Fuente LNAC: SELAE /servicios/resultados1','Quiniela/Elige8: parser de notas oficiales 0.86L']
    for game in CODES:
        r=report['juegos'].get(game,{})
        lines.append(f"{game}: fecha={r.get('fecha')} categorias={len(r.get('premios',[]))} incidencias={len(r.get('errores',[]))} archivo={r.get('historico_estado')}")
    lines.append('Quiniela: '+str(report['quiniela'].get('historico_estado') or report['quiniela'].get('estado') or report['quiniela'].get('error_pdf') or 'pagina examinada'))
    lines.append('No se publican premios. Conflictos de histórico no se sobrescriben.')
    (out/'resumen_125.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('\n'.join(lines))

if __name__=='__main__':main125()
