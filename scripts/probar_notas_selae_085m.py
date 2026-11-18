
#!/usr/bin/env python3
"""LotoScan 0.85M: audita acceso y extracción de PDFs oficiales SELAE.
Solo lectura. Nunca modifica historico.json ni publica premios.
"""
import argparse
import datetime as dt
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from io import BytesIO
from pathlib import Path
from bs4 import BeautifulSoup
from pypdf import PdfReader

BASE = 'https://www.loteriasyapuestas.es'
SEED_PDFS = ['https://www.loteriasyapuestas.es/f/loterias/documentos/Euromillones/Notas de prensa/NOTA_DE_PRENSA_EUROMILLONES_17_11_26.pdf', 'https://www.loteriasyapuestas.es/f/loterias/documentos/La Primitiva/Notas de prensa/NOTA_DE_PRENSA_LA_PRIMITIVA_LUNES_16_11_26.pdf', 'https://www.loteriasyapuestas.es/f/loterias/documentos/Bonoloto/Notas de prensa/NOTA_DE_PRENSA_BONOLOTO_17_11_26.pdf', 'https://www.loteriasyapuestas.es/f/loterias/documentos/El Gordo/Notas de prensa/NOTA_DE_PRENSA_EL_GORDO_DE_LA_PRIMITIVA_15_11_26.pdf', 'https://www.loteriasyapuestas.es/f/loterias/documentos/EuroDrems/Notas de prensa/NOTA_DE_PRENSA_EURODREAMS_16_11_26.pdf', 'https://www.loteriasyapuestas.es/f/loterias/documentos/Lotería Nacional/listas de premios/SM_LISTAOFICIAL.A2026.S091.pdf', 'https://www.loteriasyapuestas.es/f/loterias/documentos/Lotería Nacional/notas de prensa/PREMIOS_MAYORES_DEL_SORTEO_DE_LOTERIA_NACIONAL_JUEVES_12_11_26.pdf', 'https://www.loteriasyapuestas.es/f/loterias/documentos/Lotería Nacional/listas de premios/SM_LISTAOFICIAL.A2026.S092.pdf', 'https://www.loteriasyapuestas.es/f/loterias/documentos/Lotería Nacional/notas de prensa/PREMIOS_MAYORES_DEL_SORTEO_DE_LOTERIA_NACIONAL_SÁBADO_14_11_26.pdf', 'https://www.loteriasyapuestas.es/f/loterias/documentos/El Quinigol/Notas de prensa/NOTA_DE_PRENSA_EL_QUINIGOL_17_11_26.pdf', 'https://www.loteriasyapuestas.es/f/loterias/documentos/Lototurf/Notas de prensa/NOTA_DE_PRENSA_LOTOTURF_15_11_26.pdf', 'https://www.loteriasyapuestas.es/f/loterias/documentos/Quíntuple Plus/Notas de prensa/NOTA_DE_PRENSA_QUÍNTUPLE_PLUS_15_11_26.pdf']
HEADERS = {'User-Agent': 'Mozilla/5.0 (LotoScanDiagnostic/0.85M)',
           'Accept': 'application/pdf,text/html,*/*'}
DATE_RE = re.compile(r'(?<!\d)(?:\d{2}[/-]\d{2}[/-]20\d{2}|20\d{2}[/-]\d{2}[/-]\d{2})(?!\d)')
PRIZE_RE = re.compile(r'categor[ií]a|acertantes|premio|reparto', re.I)

def safe_url(url):
    p = urllib.parse.urlsplit(url)
    if p.scheme != 'https' or p.hostname not in ('www.loteriasyapuestas.es', 'loteriasyapuestas.es'):
        raise ValueError('Solo se permiten URLs HTTPS oficiales SELAE')
    # Quote path, retaining valid %XX sequences, including accented filenames.
    return urllib.parse.urlunsplit((p.scheme, p.netloc,
        urllib.parse.quote(urllib.parse.unquote(p.path), safe='/'),
        urllib.parse.quote(urllib.parse.unquote(p.query), safe='=&'), ''))

def fetch(url):
    normalized = safe_url(url)
    req = urllib.request.Request(normalized, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=35) as response:
            final = response.url
            safe_url(final)  # reject redirects off the official domain
            data = response.read(8_000_001)
            if len(data) > 8_000_000:
                raise ValueError('Documento superior a 8 MB')
            return {'http': response.status, 'url_final': final,
                    'tipo': response.headers.get('Content-Type',''), 'bytes':len(data)}, data
    except urllib.error.HTTPError as e:
        return {'http':e.code, 'error':str(e)}, b''
    except Exception as e:
        return {'error':f'{type(e).__name__}: {e}'}, b''

def inspect_pdf(label,url):
    item={'etiqueta':label, 'url_original':url, 'url_codificada':safe_url(url),
          'publicable':False, 'premios_validados':False}
    meta, data=fetch(url)
    item.update(meta)
    if not data:return item
    if not data.startswith(b'%PDF-'):
        item['error_formato']='La respuesta no empieza por %PDF-'
        item['muestra_respuesta']=data[:160].decode('utf-8','replace')
        return item
    try:
        reader=PdfReader(BytesIO(data))
        texts=[p.extract_text(extraction_mode='layout') or '' for p in reader.pages[:8]]
        content='\n'.join(texts)
        item.update({'paginas':len(reader.pages), 'caracteres':len(content),
                     'fechas_en_texto':sorted(set(DATE_RE.findall(content)))[:20],
                     'indicadores_premios':bool(PRIZE_RE.search(content)),
                     'muestra_texto':content[:2800]})
    except Exception as e:
        item['error_pdf']=f'{type(e).__name__}: {e}'
    return item

def discover_quiniela():
    # Pages can be JS-driven: failure to find links does NOT mean no notes exist.
    urls=[BASE+'/es/resultados',BASE+'/es/resultados/quiniela']
    result=[]
    for url in urls:
        meta,data=fetch(url)
        item={'pagina':url,**meta,'candidatos':[]}
        if data and ('html' in meta.get('tipo','').lower() or b'<html' in data[:3000].lower()):
            soup=BeautifulSoup(data,'html.parser')
            for a in soup.find_all('a',href=True):
                label=' '.join(a.get_text(' ',strip=True).split())
                href=urllib.parse.urljoin(meta.get('url_final',url),a['href'])
                if re.search('quiniela',label+' '+href,re.I) and re.search('nota|prensa|pdf',label+' '+href,re.I):
                    try:
                        safe_url(href)
                        item['candidatos'].append({'texto':label[:140],'url':href})
                    except ValueError:pass
            item['candidatos']=item['candidatos'][:20]
        result.append(item)
    return result

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--quiniela-url',default='',help='URL exacta de nota de prensa de La Quiniela (opcional)')
    args=ap.parse_args()
    if args.quiniela_url:safe_url(args.quiniela_url)
    report={'version':'0.85M-SELAE','utc':dt.datetime.now(dt.timezone.utc).isoformat(),
            'solo_lectura':True,'publicable':False,'documentos':[],'busqueda_quiniela':[]}
    # Seed URLs were extracted from the 0.85L GitHub report, not invented.
    for i,url in enumerate(SEED_PDFS):
        item=inspect_pdf('enlace_085L_'+str(i+1),url)
        report['documentos'].append(item)
        print(item['etiqueta'],item.get('http','ERROR'),item.get('caracteres',0),item.get('error',''))
    report['busqueda_quiniela']=discover_quiniela()
    extra=[]
    for page in report['busqueda_quiniela']:
        extra += [x['url'] for x in page.get('candidatos',[])]
    if args.quiniela_url:extra.insert(0,args.quiniela_url)
    existing={x['url_codificada'] for x in report['documentos']}
    for url in extra[:5]:
        if safe_url(url) not in existing:
            existing.add(safe_url(url))
            report['documentos'].append(inspect_pdf('quiniela',url))
    Path('informe_selae_085m.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['LotoScan 0.85M - acceso a PDF oficiales (DIAGNOSTICO)',
           'No se han certificado ni publicado premios.','']
    for x in report['documentos']:
        lines.append(f"{x['etiqueta']} | HTTP={x.get('http','ERROR')} | paginas={x.get('paginas','-')} | texto={x.get('caracteres',0)} | error={x.get('error',x.get('error_pdf',x.get('error_formato','ninguno')))}")
    for x in report['busqueda_quiniela']:
        lines.append(f"Busqueda Quiniela {x['pagina']}: HTTP={x.get('http','ERROR')} candidatos={len(x['candidatos'])}")
    Path('informe_selae_085m.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('\n'.join(lines))

if __name__=='__main__':main()
