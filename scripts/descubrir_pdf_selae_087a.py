#!/usr/bin/env python3
"""LotoScan 0.87A: diagnóstico de descubrimiento de notas oficiales, solo lectura.
No publica resultados, no modifica historico.json y no supone que drawId sea dinámico.
"""
import argparse
import hashlib
import json
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse, unquote

import requests
from bs4 import BeautifulSoup

BASE = 'https://www.loteriasyapuestas.es'
DEFAULT = BASE + '/es/resultados?drawId=1328604137'
OUT = Path('diagnostico_selae_087a')
GAMES = {
    'euromillones': ('euromillones', 'euro millones'),
    'primitiva': ('la primitiva', 'primitiva'),
    'bonoloto': ('bonoloto',),
    'gordo-primitiva': ('el gordo', 'gordo de la primitiva'),
    'eurodreams': ('eurodreams', 'euro dreams'),
    'loteria-nacional': ('loteria nacional', 'listado de premios'),
    'quiniela': ('quiniela',),
    'quinigol': ('quinigol',),
    'lototurf': ('lototurf',),
    'quintuple-plus': ('quintuple plus', 'quintupleplus'),
}
MONTHS = {'enero':1,'febrero':2,'marzo':3,'abril':4,'mayo':5,'junio':6,
          'julio':7,'agosto':8,'septiembre':9,'setiembre':9,'octubre':10,
          'noviembre':11,'diciembre':12}
HEADERS = {'User-Agent':'LotoScan/0.87A (diagnostico de enlaces oficiales; sin publicacion)',
           'Accept':'text/html,application/pdf;q=0.9,*/*;q=0.7'}

def norm(s):
    return ''.join(c for c in unicodedata.normalize('NFKD', s.lower()) if not unicodedata.combining(c))

def game_for(label):
    s = norm(label)
    # Prioridad para evitar que 'gordo de la primitiva' se clasifique como Primitiva.
    for key in ('gordo-primitiva','quintuple-plus','quinigol','lototurf','eurodreams',
                'euromillones','bonoloto','loteria-nacional','quiniela','primitiva'):
        if any(alias in s for alias in GAMES[key]):
            return key
    return None

def date_for(label):
    m = re.search(r'(?<!\d)(\d{1,2})[/-](\d{1,2})[/-](20\d\d|\d\d)(?!\d)', label)
    if m:
        d, mo, y = map(int, m.groups())
        if y < 100: y += 2000
        try: return f'{y:04d}-{mo:02d}-{d:02d}' if datetime(y,mo,d) else None
        except ValueError: return None
    s = norm(label)
    m = re.search(r'\b(\d{1,2})\s+de\s+([a-z]+)\s+de\s+(20\d\d)\b',s)
    if m and m.group(2) in MONTHS:
        try: return datetime(int(m.group(3)), MONTHS[m.group(2)],int(m.group(1))).date().isoformat()
        except ValueError: pass
    return None

def safe_url(url):
    p=urlparse(url)
    return p.scheme == 'https' and (p.hostname == 'loteriasyapuestas.es' or (p.hostname or '').endswith('.loteriasyapuestas.es'))

def fetch(session,url,limit=12_000_000):
    with session.get(url, timeout=(12,35), allow_redirects=True, stream=True) as r:
        r.raise_for_status()
        if not safe_url(r.url): raise ValueError('Redireccion fuera del dominio oficial')
        data=bytearray()
        for part in r.iter_content(65536):
            data.extend(part)
            if len(data)>limit: raise ValueError('Documento supera limite de tamano')
        return r,bytes(data)

def links_from_html(html, page_url):
    soup=BeautifulSoup(html,'html.parser')
    links=[]
    seen=set()
    for a in soup.find_all('a',href=True):
        href=a.get('href','').strip()
        url=urljoin(page_url,href)
        if not safe_url(url): continue
        label=' '.join(a.stripped_strings)
        title=a.get('title','')
        context=' '.join(a.parent.stripped_strings)[:350] if a.parent else ''
        combined=' '.join((label,title,context,unquote(url)))
        pdf_hint=('.pdf' in url.lower() or 'nota de prensa' in norm(combined)
                  or 'listado de premios' in norm(combined))
        if not pdf_hint: continue
        key=(url,label)
        if key in seen: continue
        seen.add(key)
        links.append({'url':url,'texto':label[:180], 'titulo':title[:180],
                      'contexto':context,'juego_candidato':game_for(combined),
                      'fecha_candidata':date_for(combined),
                      'es_pdf_por_url':'.pdf' in urlparse(url).path.lower(),
                      'estado':'encontrado_no_verificado'})
    # Registrar URLs PDF visibles en scripts o datos embebidos, sin ejecutar JS.
    embedded=set(re.findall(r'(?:https?:)?//[^\s"\'<>]+?\.pdf(?:\?[^\s"\'<>]*)?|/[^\s"\'<>]+?\.pdf(?:\?[^\s"\'<>]*)?',html,re.I))
    for raw in sorted(embedded):
        url=urljoin(page_url,raw.replace('&amp;','&'))
        if safe_url(url) and not any(x['url']==url for x in links):
            links.append({'url':url,'texto':'URL embebida en HTML', 'titulo':'',
                          'contexto':'', 'juego_candidato':game_for(url),
                          'fecha_candidata':date_for(url),'es_pdf_por_url':True,
                          'estado':'encontrado_no_verificado'})
    return links

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--url',default=DEFAULT,help='URL oficial de la pagina de resultados')
    ap.add_argument('--verificar',action='store_true',help='Descarga PDFs candidatos y valida firma %PDF (no los publica)')
    args=ap.parse_args()
    if not safe_url(args.url): ap.error('Solo se permiten URLs HTTPS del dominio oficial SELAE')
    OUT.mkdir(exist_ok=True)
    session=requests.Session();session.headers.update(HEADERS)
    report={'version':'0.87A','fecha_utc':datetime.now(timezone.utc).isoformat(),
            'url_solicitada':args.url,'publicable':False,'modifica_historico':False,
            'paginas':[],'candidatos':[],'errores':[],'avisos':[]}
    # La URL sin drawId ayuda a observar si la pagina devuelve el indice actual.
    urls=list(dict.fromkeys([args.url,BASE+'/es/resultados']))
    for url in urls:
        page={'url':url}
        try:
            resp,body=fetch(session,url)
            ctype=resp.headers.get('Content-Type','')
            page.update({'http':resp.status_code,'url_final':resp.url,'content_type':ctype,
                         'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()})
            if 'pdf' in ctype or body.startswith(b'%PDF-'):
                page['aviso']='La URL corresponde a un PDF, no a una pagina de resultados'
            else:
                html=body.decode(resp.encoding or 'utf-8',errors='replace')
                candidates=links_from_html(html,resp.url)
                page['enlaces_candidatos']=len(candidates)
                report['candidatos'].extend(candidates)
                (OUT/('pagina_'+str(len(report['paginas'])+1)+'.html')).write_text(html,encoding='utf-8')
        except Exception as e:
            page['error']=f'{type(e).__name__}: {e}'
            report['errores'].append({'url':url,'error':page['error']})
        report['paginas'].append(page)
    # Desduplicacion por URL, no por fecha inferida.
    unique={}
    for item in report['candidatos']:
        unique.setdefault(item['url'],item)
    report['candidatos']=list(unique.values())
    if args.verificar:
        for item in report['candidatos']:
            try:
                resp,body=fetch(session,item['url'])
                item.update({'http':resp.status_code,'bytes':len(body),
                             'url_final':resp.url,'firma_pdf':body.startswith(b'%PDF-'),
                             'sha256':hashlib.sha256(body).hexdigest()})
                item['estado']='pdf_verificado' if body.startswith(b'%PDF-') else 'no_es_pdf'
            except Exception as e:
                item['estado']='error_verificacion';item['error']=f'{type(e).__name__}: {e}'
    found={x['juego_candidato'] for x in report['candidatos'] if x['juego_candidato']}
    report['resumen']={'paginas_consultadas':len(report['paginas']),
        'candidatos_unicos':len(report['candidatos']),
        'pdf_verificados':sum(x['estado']=='pdf_verificado' for x in report['candidatos']),
        'juegos_identificados':sorted(found),
        'juegos_sin_enlace_identificado':sorted(set(GAMES)-found),
        'errores_consulta':len(report['errores'])}
    if not report['candidatos']:
        report['avisos'].append('Sin enlaces identificados: puede requerirse JS, endpoints adicionales o cambios en el HTML.')
    report['avisos'].append('drawId se trata como identificador fijo de prueba; NO se inventan IDs ni se presume que la URL devuelve el ultimo sorteo.')
    report['avisos'].append('No encontrar un PDF no implica que el sorteo no exista ni que tenga premio cero.')
    (OUT/'informe_087a.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['LotoScan 0.87A - descubrimiento oficial SELAE (solo diagnostico)',
           'Fuente: '+args.url, 'Resumen: '+json.dumps(report['resumen'],ensure_ascii=False),
           'AVISOS:']+['- '+x for x in report['avisos']]+['CANDIDATOS:']
    lines += [f"- {x['juego_candidato'] or 'sin clasificar'} | {x['fecha_candidata'] or 'sin fecha'} | {x['estado']} | {x['url']}" for x in report['candidatos']]
    lines += ['ERRORES:']+[f"- {x['url']}: {x['error']}" for x in report['errores']]
    (OUT/'informe_087a.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('\n'.join(lines))
    # Solo falla por indisponibilidad total; no por no hallar PDF, para preservar diagnostico.
    return 1 if len(report['errores'])==len(urls) else 0

if __name__=='__main__': sys.exit(main())
