
#!/usr/bin/env python3
"""LotoScan 0.86B: estructura resultados de PDF oficiales de SELAE.

Usa las 12 URL de prueba de 0.85M. Solo lectura: NO modifica historico.json.
Los datos son candidatos para revisión, NO resultados publicables.
"""
import datetime as dt
import importlib.util
import json
import re
from io import BytesIO
from pathlib import Path
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent
OLD = ROOT / 'probar_notas_selae_085m.py'
if not OLD.exists():
    raise SystemExit('Falta scripts/probar_notas_selae_085m.py')
spec = importlib.util.spec_from_file_location('old085m', OLD)
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)

GAMES = ['euromillones','primitiva','bonoloto','gordo-primitiva',
         'eurodreams','loteria-nacional-lista','loteria-nacional-mayores',
         'loteria-nacional-lista','loteria-nacional-mayores',
         'quinigol','lototurf','quintuple-plus']
MONTHS = {'enero':1,'febrero':2,'marzo':3,'abril':4,'mayo':5,'junio':6,
          'julio':7,'agosto':8,'septiembre':9,'setiembre':9,'octubre':10,
          'noviembre':11,'diciembre':12}
DATE_WORDS = re.compile(r'(\d{1,2})\s+de\s+(' + '|'.join(MONTHS) + r')\s+de\s+(20\d{2})',re.I)
DATE_DIGITS = re.compile(r'\b(\d{1,2})/(\d{1,2})/(20\d{2}|\d{2})\b')
MONEY = r'(?:\d{1,3}(?:\.\d{3})*|\d+),\d{2}'
PRIZE_LINE = re.compile(r'^\s*(?P<category>(?:Especial|Reintegro|REINTEGRO|\d{1,2}[ªº]?\s*(?:CATEGOR[IÍ]A)?|\d+\s+Aciertos)[^\n]*?)\s{2,}(?P<winners>\d[\d.]*)\s{2,}(?P<prize>'+MONEY+r'|BOTE|EUROBOTE|PLUSBOTE)\s*$', re.I)


def find_date(text):
    m = DATE_WORDS.search(text)
    if m:
        try:
            return dt.date(int(m[3]), MONTHS[m[2].lower()], int(m[1])).isoformat()
        except ValueError: pass
    m = DATE_DIGITS.search(text)
    if m:
        y = int(m[3]); y = y + 2000 if y < 100 else y
        try: return dt.date(y,int(m[2]),int(m[1])).isoformat()
        except ValueError: pass
    return None


def numbers_after_phrase(text, phrase, count):
    m = re.search(phrase, text, re.I | re.S)
    if not m: return None
    line = text[m.end():].split('\n',1)[0]
    vals = re.findall(r'(?<!\d)\d{1,2}(?!\d)',line)
    return [int(v) for v in vals[:count]] if len(vals) >= count else None


def prize_rows(text):
    rows = []
    for line in text.splitlines():
        m = PRIZE_LINE.match(line)
        if m:
            rows.append({'categoria_texto':m['category'].strip(),
                         'acertantes':int(m['winners'].replace('.','')),
                         'premio_texto':m['prize']})
    return rows


def extract_main(text, game):
    out = {'fecha':find_date(text),'combinacion':None,
           'adicionales':{},'categorias':prize_rows(text),
           'advertencias':[]}
    # Solo la primera línea numérica después de la frase: evita mezclar recaudación y premios.
    if game in ('euromillones','eurodreams'):
        out['combinacion'] = numbers_after_phrase(text,r'N[uú]meros\s*:',5 if game=='euromillones' else 6)
    elif game in ('primitiva','bonoloto','gordo-primitiva','lototurf'):
        out['combinacion'] = numbers_after_phrase(text,r'los siguientes n[uú]meros\s*:',5 if game=='gordo-primitiva' else 6)
    if game=='euromillones':
        m=re.search(r'Estrellas\s*:\s*[-\s]*(\d{1,2})',text,re.I)
        # La disposición del PDF coloca las estrellas antes y después del rótulo.
        out['adicionales']['estrellas'] = None
        out['advertencias'].append('Estrellas: disposición PDF ambigua; revisar manualmente')
        code=re.search(r'C[ÓO]DIGO GANADOR\s*[\'“”]?El Mill[oó]n[\'“”]?\s*\n\s*([A-Z]{3}\d{5})',text,re.I)
        out['adicionales']['el_millon']=code[1] if code else None
    if game=='eurodreams':
        m=re.search(r'Sue[ñn]o\s*:\s*(\d)',text,re.I)
        out['adicionales']['numero_sueno']=int(m[1]) if m else None
    if game=='primitiva':
        m=re.search(r'JOKER\s*:\s*(\d{7})',text,re.I)
        out['adicionales']['joker']=m[1] if m else None
    if game in ('primitiva','bonoloto'):
        # La línea del PDF presenta los seis números, complementario y reintegro
        # antes de los rótulos, con guiones de maquetación entre medias.
        m=re.search(r'los siguientes n[uú]meros\s*:\s*\n([^\n]+)',text,re.I)
        if m:
            prefix=m[1].split('Complementario')[0]
            values=re.findall(r'(?<!\d)\d{1,2}(?!\d)',prefix)
            if len(values)>=8:
                out['adicionales']['complementario']=int(values[6])
                out['adicionales']['reintegro']=int(values[7])
            else:
                out['advertencias'].append('Complementario/reintegro: revisión necesaria')
    if game=='gordo-primitiva':
        m=re.search(r'los siguientes n[uú]meros\s*:\s*\n([^\n]+)',text,re.I)
        if m:
            nums=re.findall(r'(?<!\d)\d{1,2}(?!\d)',m[1].split('Número Clave')[0])
            out['adicionales']['clave']=int(nums[5]) if len(nums)>5 else None
    if game=='lototurf':
        m=re.search(r'Reintegro\s*:\s*(\d)',text,re.I)
        out['adicionales']['reintegro']=int(m[1]) if m else None
        # El caballo aparece ANTES de 'Caballo Ganador 4ª carrera'.
        m=re.search(r'los siguientes n[uú]meros\s*:\s*\n([^\n]+)',text,re.I)
        if m:
            vals=re.findall(r'(?<!\d)\d{1,2}(?!\d)',m[1].split('Reintegro')[0])
            out['adicionales']['caballo_cuarta']=int(vals[6]) if len(vals)>6 else None
    if game=='quinigol':
        matches=[]
        for line in text.splitlines():
            m=re.match(r'^\s*([1-6])\s+(.+?)\s{2,}(\d+)\s+(\d+)\s+(.+?)\s{2,}([012M]{2})\s*$',line)
            if m:
                matches.append({'partido':int(m[1]),'local':m[2].strip(),
                                'goles_local':int(m[3]),'goles_visitante':int(m[4]),
                                'visitante':m[5].strip(),'pronostico':m[6]})
        out['partidos']=matches
        out['advertencias'].append('Comprobar alineación de columnas y nombres de equipos')
    if game=='quintuple-plus':
        m=re.search(r'1[ªa]\s*Carrera\s*:\s*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)',text,re.I)
        m2=re.search(r'5[ªa]\s*Carrera\s*:\s*Primero\s*:\s*(\d+)\s*Segundo\s*:\s*(\d+)',text,re.I|re.S)
        out['adicionales']['caballos_carreras_1_a_4']=[int(x) for x in m.groups()] if m else None
        out['adicionales']['quinta_primero']=int(m2[1]) if m2 else None
        out['adicionales']['quinta_segundo']=int(m2[2]) if m2 else None
    return out


def national(text, kind):
    result={'fecha':find_date(text),'tipo':kind,'advertencias':[]}
    if kind=='mayores':
        for title,key in [('PRIMER PREMIO','primero'),('SEGUNDO PREMIO','segundo')]:
            m=re.search(title+r'.{0,200}?PREMIO DE\s*([\d.]+)\s+EUROS AL N[ÚU]MERO\s*([\d.]+)',text,re.I|re.S)
            result[key]={'numero':m[2].replace('.','').zfill(5),
                         'euros':int(m[1].replace('.',''))} if m else None
        m=re.search(r'REINTEGROS\s+([0-9])\s+([0-9])\s+([0-9])',text,re.I)
        result['reintegros']=[int(x) for x in m.groups()] if m else None
    else:
        # Lista oficial: las columnas son números y euros/billete; extraer
        # candidatos sin publicar ni asumir que se han capturado todas las filas.
        pairs=re.findall(r'(?<!\d)(\d{5})\.{3,}\s*([\d.]+)(?!\d)',text)
        result['entradas_candidatas']=[{'numero':a,'euros_billete':int(b.replace('.',''))} for a,b in pairs]
        result['advertencias'].append('Lista oficial: comprobar exhaustividad y totales antes de utilizar premios')
    return result


def main():
    report={'version':'0.86B','utc':dt.datetime.now(dt.timezone.utc).isoformat(),
            'solo_lectura':True,'publicable':False,'origen':'PDF SELAE',
            'documentos':[],'quiniela':'posterior'}
    for i,(url,game) in enumerate(zip(old.SEED_PDFS,GAMES),1):
        item={'indice':i,'juego':game,'url':url,'error':None,'publicable':False}
        try:
            meta,data=old.fetch(url)
            item['http']=meta.get('http')
            if meta.get('http')!=200 or not data.startswith(b'%PDF-'):
                raise RuntimeError('Descarga no válida: '+str(meta))
            reader=PdfReader(BytesIO(data))
            if reader.is_encrypted or not reader.pages:
                raise ValueError('PDF protegido o sin páginas')
            text='\n'.join(page.extract_text(extraction_mode='layout') or '' for page in reader.pages)
            if len(text.strip())<100: raise ValueError('Texto insuficiente')
            item['paginas']=len(reader.pages)
            item['datos']=national(text,'lista' if game.endswith('lista') else 'mayores') if game.startswith('loteria-nacional') else extract_main(text,game)
            if not item['datos'].get('fecha'):
                item['datos']['advertencias'].append('Fecha no reconocida')
            item['texto_muestra']=text[:1000]
        except Exception as exc:
            item['error']=f'{type(exc).__name__}: {exc}'
        report['documentos'].append(item)
        print(f"{i:02d} {game}: {'ERROR '+item['error'] if item['error'] else 'extraído (sin validar)'}",flush=True)
    Path('informe_pdf_086b.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['LotoScan 0.86B - resultados candidatos desde PDF SELAE','NO PUBLICABLE - historico.json sin cambios','']
    for item in report['documentos']:
        lines.append(f"{item['indice']:02d} {item['juego']} | fecha={item.get('datos',{}).get('fecha')} | categorias={len(item.get('datos',{}).get('categorias',[]))} | error={item['error']}")
        if 'datos' in item:
            lines.append('  datos: '+json.dumps(item['datos'],ensure_ascii=False)[:1600])
    Path('informe_pdf_086b.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    if any(x['error'] for x in report['documentos']):
        raise SystemExit('Algunos documentos fallaron: consultar informe_pdf_086b.json')

if __name__=='__main__':main()
