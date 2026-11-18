#!/usr/bin/env python3
"""LotoScan 0.85N: extracción diagnóstica de premios desde PDFs oficiales.
No modifica historico.json, ni publica resultados. Sin certificación automática.
"""
import datetime as dt
import io
import json
import re
import urllib.parse
import urllib.request
from decimal import Decimal
from pathlib import Path
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'fuentes_selae_085n.json'
OUT = Path('informe_selae_085n.json')
MAX_BYTES = 8_000_000
HEADERS = {'User-Agent': 'Mozilla/5.0 (LotoScanResearch/0.85N)', 'Accept': 'application/pdf'}
CATS = re.compile(r'^\s*(?P<cat>Especial|Reintegro|\d{1,2}\s*[ªº]|\d\s+Aciertos?)', re.I)
# Split columns on >= 2 spaces: PDF layout preserves aligned columns.
SPLIT = re.compile(r'\s{2,}')
EUROS = re.compile(r'^(?:\d{1,3}(?:\.\d{3})*|\d+),\d{2}$')
COUNT = re.compile(r'^\d{1,3}(?:\.\d{3})*$|^\d+$')
DATE = re.compile(r'\b(\d{1,2})\s+de\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\s+de\s+(20\d{2})\b',re.I)
MONTHS = {m:i for i,m in enumerate('enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre'.split(),1)}
GAMES = [('quintuple_plus','Quíntuple Plus'),('quinigol','El Quinigol'),('lototurf','Lototurf'),('euromillones','Euromillones'),('primitiva','La Primitiva'),('bonoloto','Bonoloto'),('gordo','El Gordo'),('eurodreams','EuroDrems'),('loteria_nacional','Lotería Nacional'),('quiniela','Quiniela')]

def game_from_url(url):
    path=urllib.parse.unquote(urllib.parse.urlsplit(url).path).lower()
    for game,marker in GAMES:
        if marker.lower() in path:return game
    return 'desconocido'

def safe_url(url):
    p=urllib.parse.urlsplit(url)
    if p.scheme!='https' or p.hostname not in ('www.loteriasyapuestas.es','loteriasyapuestas.es'):
        raise ValueError('URL fuera del dominio oficial SELAE')
    return urllib.parse.urlunsplit((p.scheme,p.netloc,urllib.parse.quote(urllib.parse.unquote(p.path),safe='/'),urllib.parse.quote(urllib.parse.unquote(p.query),safe='=&'),''))

def fetch_pdf(url):
    req=urllib.request.Request(safe_url(url),headers=HEADERS)
    with urllib.request.urlopen(req,timeout=35) as r:
        safe_url(r.url)
        data=r.read(MAX_BYTES+1)
        if len(data)>MAX_BYTES:raise ValueError('PDF demasiado grande')
        if not data.startswith(b'%PDF-'):raise ValueError('Respuesta no es PDF')
    return '\n'.join((page.extract_text(extraction_mode='layout') or '') for page in PdfReader(io.BytesIO(data)).pages[:10])

def extract_date(text):
    # Only a single unambiguous date in the document is acceptable.
    found=set()
    for day,month,year in DATE.findall(text):
        try:found.add(dt.date(int(year),MONTHS[month.lower()],int(day)).isoformat())
        except ValueError:pass
    return sorted(found)

def parse_table(text):
    if 'REPARTO DE PREMIOS' not in text.upper():return [],['sin_encabezado_reparto']
    section=text.upper().find('REPARTO DE PREMIOS')
    tail=text[section:].splitlines()
    entries=[]; issues=[];started=False
    for line in tail[1:]:
        if re.search(r'^\s*(?:En el sorteo|Al no existir|De Primera|De Segunda|Con el |Madrid,|DEPARTAMENTO)',line,re.I) and started:break
        parts=[p.strip() for p in SPLIT.split(line.strip()) if p.strip()]
        if len(parts)<2:continue
        m=CATS.match(parts[0])
        if not m:continue
        started=True
        if len(parts)<3:
            issues.append('fila_incompleta: '+line.strip()[:140]);continue
        count_raw=parts[-2].strip(); amount_raw=parts[-1].strip().replace('€','').strip()
        if not COUNT.fullmatch(count_raw):
            issues.append('acertantes_no_interpretables: '+line.strip()[:140]);continue
        count=int(count_raw.replace('.',''))
        if EUROS.fullmatch(amount_raw):
            amount=str(Decimal(amount_raw.replace('.','').replace(',','.')).quantize(Decimal('.01')))
            status='importe_exacto_publicado'
        elif amount_raw.upper() in ('BOTE','EUROBOTE','PLUSBOTE'):
            amount=None;status='sin_acertantes_bote' if count==0 else 'revisar_bote_con_acertantes'
        else:
            amount=None;status='importe_no_interpretable';issues.append('importe_no_interpretable: '+line.strip()[:140])
        entries.append({'categoria':m.group('cat').replace(' ','').lower(), 'descripcion':parts[0],
                        'acertantes':count,'premio_unitario_eur':amount,'estado':status,'fila_original':line.strip()})
    if not entries:issues.append('sin_categorias_extraidas')
    if len({x['categoria'] for x in entries})!=len(entries):issues.append('categorias_duplicadas')
    return entries,issues

def audit(url):
    item={'juego':game_from_url(url),'url_oficial':safe_url(url),'publicable':False,'validado':False}
    try:
        text=fetch_pdf(url)
        item['caracteres']=len(text)
        item['fechas_detectadas']=extract_date(text)
        item['categorias'],item['incidencias']=parse_table(text)
        if item['juego']=='loteria_nacional':
            item['incidencias'].append('loteria_nacional_requiere_extractor_especifico_de_lista_oficial')
        if len(item['fechas_detectadas'])!=1:item['incidencias'].append('fecha_no_univoca')
        item['estado']='extraido_para_revision' if item['categorias'] and not item['incidencias'] else 'revision_necesaria'
        item['extracto_encabezado']=text[:500]
    except Exception as exc:
        item['estado']='error_descarga_o_lectura';item['error']=f'{type(exc).__name__}: {exc}'
    return item

def main():
    sources=json.loads(SOURCE.read_text(encoding='utf-8'))
    results=[]
    for entry in sources:
        item=audit(entry['url']);results.append(item)
        print(item['juego'],item['estado'],len(item.get('categorias',[])),item.get('error',''))
    report={'version':'0.85N-SELAE','generado_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
            'solo_diagnostico':True,'publicable':False,'documentos':results}
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['LotoScan 0.85N - EXTRACCION OFICIAL DIAGNOSTICA (NO PUBLICAR)','']
    for x in results:
        lines.append(f"{x['juego']} | {x['estado']} | fechas={','.join(x.get('fechas_detectadas',[]))} | categorias={len(x.get('categorias',[]))} | incidencias={'; '.join(x.get('incidencias',[]))} | error={x.get('error','')}")
    Path('informe_selae_085n.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('\n'.join(lines))

if __name__=='__main__':main()
