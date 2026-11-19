#!/usr/bin/env python3
"""LotoScan 0.87B. Diagnostico de URL directas oficiales. Solo lectura.
No evade restricciones ni publica resultados. Las URL candidatas NO son fuentes
validadas hasta confirmar PDF, fecha y juego en su contenido.
"""
import argparse, hashlib, io, json, re, unicodedata
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit, urlunsplit
import requests
from pypdf import PdfReader

SEEDS = [{'juego': 'euromillones', 'url': 'https://www.loteriasyapuestas.es/f/loterias/documentos/Euromillones/Notas de prensa/NOTA_DE_PRENSA_EUROMILLONES_17_11_26.pdf'}, {'juego': 'primitiva', 'url': 'https://www.loteriasyapuestas.es/f/loterias/documentos/La Primitiva/Notas de prensa/NOTA_DE_PRENSA_LA_PRIMITIVA_LUNES_16_11_26.pdf'}, {'juego': 'bonoloto', 'url': 'https://www.loteriasyapuestas.es/f/loterias/documentos/Bonoloto/Notas de prensa/NOTA_DE_PRENSA_BONOLOTO_17_11_26.pdf'}, {'juego': 'gordo-primitiva', 'url': 'https://www.loteriasyapuestas.es/f/loterias/documentos/El Gordo/Notas de prensa/NOTA_DE_PRENSA_EL_GORDO_DE_LA_PRIMITIVA_15_11_26.pdf'}, {'juego': 'eurodreams', 'url': 'https://www.loteriasyapuestas.es/f/loterias/documentos/EuroDrems/Notas de prensa/NOTA_DE_PRENSA_EURODREAMS_16_11_26.pdf'}, {'juego': 'loteria-nacional', 'url': 'https://www.loteriasyapuestas.es/f/loterias/documentos/Lotería Nacional/listas de premios/SM_LISTAOFICIAL.A2026.S091.pdf'}, {'juego': 'loteria-nacional', 'url': 'https://www.loteriasyapuestas.es/f/loterias/documentos/Lotería Nacional/notas de prensa/PREMIOS_MAYORES_DEL_SORTEO_DE_LOTERIA_NACIONAL_JUEVES_12_11_26.pdf'}, {'juego': 'loteria-nacional', 'url': 'https://www.loteriasyapuestas.es/f/loterias/documentos/Lotería Nacional/listas de premios/SM_LISTAOFICIAL.A2026.S092.pdf'}, {'juego': 'loteria-nacional', 'url': 'https://www.loteriasyapuestas.es/f/loterias/documentos/Lotería Nacional/notas de prensa/PREMIOS_MAYORES_DEL_SORTEO_DE_LOTERIA_NACIONAL_SÁBADO_14_11_26.pdf'}, {'juego': 'quinigol', 'url': 'https://www.loteriasyapuestas.es/f/loterias/documentos/El Quinigol/Notas de prensa/NOTA_DE_PRENSA_EL_QUINIGOL_17_11_26.pdf'}, {'juego': 'lototurf', 'url': 'https://www.loteriasyapuestas.es/f/loterias/documentos/Lototurf/Notas de prensa/NOTA_DE_PRENSA_LOTOTURF_15_11_26.pdf'}, {'juego': 'quintuple-plus', 'url': 'https://www.loteriasyapuestas.es/f/loterias/documentos/Quíntuple Plus/Notas de prensa/NOTA_DE_PRENSA_QUÍNTUPLE_PLUS_15_11_26.pdf'}]
OUT=Path('diagnostico_selae_087b')
MONTHS={'enero':1,'febrero':2,'marzo':3,'abril':4,'mayo':5,'junio':6,'julio':7,'agosto':8,'septiembre':9,'octubre':10,'noviembre':11,'diciembre':12}
ALIASES={'euromillones':['euro millones','euromillones'],'primitiva':['primitiva'],'bonoloto':['bonoloto'],'gordo-primitiva':['gordo de la primitiva'],'eurodreams':['eurodreams','euro dreams'],'loteria-nacional':['loteria nacional'],'quinigol':['quinigol'],'lototurf':['lototurf'],'quintuple-plus':['quintuple plus','quintupleplus'],'quiniela':['quiniela']}

def norm(s):
    return ''.join(c for c in unicodedata.normalize('NFKD',s.lower()) if not unicodedata.combining(c))

def pdf_date(text):
    s=norm(text)
    m=re.search(r'\b(\d{1,2})\s+de\s+([a-z]+)\s+de\s+(20\d\d)\b',s)
    if m and m[2] in MONTHS:
        try: return date(int(m[3]),MONTHS[m[2]],int(m[1])).isoformat()
        except ValueError: pass
    m=re.search(r'\b(?:fecha\s*:\s*)?(\d{1,2})/(\d{1,2})/(\d{2,4})\b',s)
    if m:
        try:
            y=int(m[3]); y=y+2000 if y<100 else y
            return date(y,int(m[2]),int(m[1])).isoformat()
        except ValueError: pass
    return None

def official_url(url):
    p=urlsplit(url)
    return p.scheme=='https' and p.hostname=='www.loteriasyapuestas.es' and p.path.startswith('/f/loterias/documentos/')

def url_encode(url):
    p=urlsplit(url)
    return urlunsplit((p.scheme,p.netloc,quote(unquote(p.path),safe='/'),p.query,''))

def get_pdf(session,url):
    if not official_url(url): raise ValueError('URL no permitida')
    r=session.get(url_encode(url),timeout=(12,35),stream=True,allow_redirects=True)
    status=r.status_code
    if status!=200:
        r.close(); return {'http':status,'estado':'no_disponible'}
    if not official_url(r.url):
        r.close(); return {'http':status,'estado':'redireccion_no_oficial'}
    data=bytearray()
    try:
        for chunk in r.iter_content(65536):
            data.extend(chunk)
            if len(data)>10_000_000: raise ValueError('PDF demasiado grande')
    finally: r.close()
    b=bytes(data)
    if not b.startswith(b'%PDF-'): return {'http':200,'estado':'respuesta_no_pdf'}
    reader=PdfReader(io.BytesIO(b))
    text='\n'.join((p.extract_text() or '') for p in reader.pages)
    return {'http':200,'estado':'pdf_leido','fecha_documento':pdf_date(text),'paginas':len(reader.pages),'sha256':hashlib.sha256(b).hexdigest(),'texto_inicio':text[:750]}

def candidate_url(seed,target):
    """Sustituye SOLO la fecha final de un nombre de prensa ya observado."""
    url=seed['url']; path=unquote(urlsplit(url).path)
    m=re.search(r'_(\d\d)_(\d\d)_(\d\d)\.pdf$',path,re.I)
    if not m: return None
    new=target.strftime('_%d_%m_%y.pdf')
    return url[:len(url)-len(m.group(0))]+new

def game_matches(game,text):
    s=norm(text[:1600]); return any(alias in s for alias in ALIASES[game])

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--fecha',help='YYYY-MM-DD; por defecto fecha UTC actual')
    p.add_argument('--dias',type=int,default=3,help='ventana hacia atras, maximo 7')
    args=p.parse_args()
    target=date.fromisoformat(args.fecha) if args.fecha else datetime.now(timezone.utc).date()
    if not 1<=args.dias<=7: p.error('--dias entre 1 y 7')
    OUT.mkdir(exist_ok=True)
    sess=requests.Session(); sess.headers.update({'User-Agent':'LotoScan/0.87B (verificacion de documentos publicos)','Accept':'application/pdf,*/*;q=0.8'})
    records=[]; seen=set()
    def probe(game,url,kind,expected=None):
        if url in seen: return
        seen.add(url)
        item={'juego':game,'tipo':kind,'url':url,'fecha_esperada':expected}
        try:
            data=get_pdf(sess,url)
            item.update(data)
            if data['estado']=='pdf_leido':
                matches=game_matches(game,data['texto_inicio'])
                item['juego_coincide']=matches
                item['fecha_coincide']=(expected is None or data['fecha_documento']==expected)
                item['candidato_confirmado']=bool(matches and data['fecha_documento'] and item['fecha_coincide'])
                if not item['candidato_confirmado']: item['estado']='pdf_no_confirmado'
                item.pop('texto_inicio',None)
        except Exception as exc:
            item.update(estado='error',error=f'{type(exc).__name__}: {str(exc)[:220]}')
        records.append(item)
        print(f"{game:19} {kind:13} {item['estado']:21} {expected or '-'}")
    # 12 URL reales observadas en 0.86A, para distinguir bloqueo de HTML vs PDF.
    for seed in SEEDS: probe(seed['juego'],seed['url'],'control')
    # Quiniela: patron del nombre observado en los tres PDF aportados por el usuario;
    # la ruta remota es HIPOTESIS, no URL confirmada.
    quiniela={'juego':'quiniela','url':'https://www.loteriasyapuestas.es/f/loterias/documentos/La Quiniela/Notas de prensa/NOTA_DE_PRENSA_LA_QUINIELA_15_11_26.pdf'}
    templates=[s for s in SEEDS if re.search(r'_\d\d_\d\d_\d\d\.pdf$',unquote(s['url']),re.I)]+[quiniela]
    # No adivinar codigos de listas oficiales de Nacional: no son fechas.
    for i in range(args.dias):
        day=target-timedelta(days=i)
        for seed in templates:
            url=candidate_url(seed,day)
            if url: probe(seed['juego'],url,'hipotesis',day.isoformat())
    summary={'controles':sum(x['tipo']=='control' for x in records),'controles_pdf':sum(x['tipo']=='control' and x['estado']=='pdf_leido' for x in records),'hipotesis_probadas':sum(x['tipo']=='hipotesis' for x in records),'hipotesis_confirmadas':sum(x.get('candidato_confirmado',False) and x['tipo']=='hipotesis' for x in records)}
    report={'version':'0.87B','generado_utc':datetime.now(timezone.utc).isoformat(),'fecha_referencia':target.isoformat(),'solo_lectura':True,'publicable':False,'advertencia':'Las URL inferidas son hipotesis; solo confirmar con fecha y juego extraidos del PDF. No se infieren enlaces de listas oficiales de Nacional.','resumen':summary,'documentos':records}
    (OUT/'informe_087b.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/'informe_087b.txt').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n\n'+'\n'.join(f"{x['juego']} | {x['tipo']} | {x['estado']} | {x.get('http','-')} | {x['url']}" for x in records),encoding='utf-8')
    print('RESUMEN:',summary)
    # Diagnostico: no fallar por 403 o 404, pero sí por fallos del propio script.

if __name__=='__main__': main()
