#!/usr/bin/env python3
"""LotoScan 0.86D: lectura de premios PDF SELAE; diagnóstico, nunca publicable.
Depende del archivo existente scripts/probar_notas_selae_085m.py.
Usa 12 URLs de prueba históricas, no descubrimiento diario.
"""
import datetime as dt
import importlib.util
import json
import re
from collections import Counter
from io import BytesIO
from pathlib import Path
from pypdf import PdfReader

BASE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('selae085m', BASE / 'probar_notas_selae_085m.py')
if not SPEC.origin or not Path(SPEC.origin).exists():
    raise SystemExit('Falta scripts/probar_notas_selae_085m.py')
OLD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(OLD)
GAMES = ['euromillones','primitiva','bonoloto','gordo-primitiva','eurodreams',
         'loteria-nacional-lista','loteria-nacional-mayores',
         'loteria-nacional-lista','loteria-nacional-mayores',
         'quinigol','lototurf','quintuple-plus']
MONTHS = dict(zip('enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre'.split(), range(1,13)))
MONTHS['setiembre'] = 9
NUM_AMOUNT = r'(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d{2})?'
PAIR = re.compile(r'(?<!\d)(\d{5})\.{3,}\s*([\d.]+)(?!\d)')
TERM = re.compile(r'(?<!\d)(\d{1,4})\.{3,}\s*([\d.]+)(?!\d)')


def date(text):
    m = re.search(r'\b(\d{1,2})\s+de\s+('+'|'.join(MONTHS)+r')\s+de\s+(20\d{2})\b',text,re.I)
    if m:
        try: return dt.date(int(m[3]),MONTHS[m[2].lower()],int(m[1])).isoformat()
        except ValueError: pass
    m = re.search(r'\b(?:FECHA\s*:\s*)?(\d{1,2})/(\d{1,2})/(\d{2,4})\b',text,re.I)
    if m:
        year=int(m[3]); year += 2000 if year<100 else 0
        try: return dt.date(year,int(m[2]),int(m[1])).isoformat()
        except ValueError: pass
    return None


def money(s):
    return s.strip().replace('.','').replace(',','.')


def prize_table(text):
    m = re.search(r'REPARTO DE PREMIOS',text,re.I)
    if not m: return [],['No se encuentra REPARTO DE PREMIOS']
    segment = text[m.end():]
    rows=[]
    for line in segment.splitlines():
        if len(rows)>0 and not line.strip():
            # Un salto simple no siempre termina la tabla.
            continue
        # Categoría / acertantes / importe: dos o más espacios entre columnas.
        parts = [p.strip() for p in re.split(r'\s{2,}',line.strip()) if p.strip()]
        if len(parts)<3: continue
        category, winners, amount = parts[0],parts[-2],parts[-1]
        if not re.fullmatch(r'[\d.]+',winners): continue
        if not re.fullmatch(NUM_AMOUNT+r'|BOTE|EUROBOTE|PLUSBOTE',amount,re.I): continue
        if not re.search(r'CATEGOR[IÍ]A|Aciertos|Reintegro|Especial|^\d+[ªº]|^\d+ª',category,re.I): continue
        rows.append({'categoria':category,'acertantes':int(winners.replace('.','')),
                     'premio_unitario_eur':money(amount) if re.fullmatch(NUM_AMOUNT,amount) else None,
                     'estado_premio':amount if not re.fullmatch(NUM_AMOUNT,amount) else None})
        if len(rows)>=25: break
    return rows,([] if rows else ['No se han interpretado filas de premios'])


def national_major(text):
    result={'fecha':date(text),'sorteo':None,'primer_premio':None,'segundo_premio':None,'reintegros':None,'advertencias':[]}
    m=re.search(r'SORTEO\s*:\s*(\d{1,3}/\d{2})',text,re.I)
    if m: result['sorteo']=m[1]
    for title,key in [('PRIMER PREMIO','primer_premio'),('SEGUNDO PREMIO','segundo_premio')]:
        m=re.search(title+r'\s+PREMIO DE\s+([\d.]+)\s+EUROS AL N[ÚU]MERO\s+([\d.]+)',text,re.I)
        if m: result[key]={'numero':m[2].replace('.','').zfill(5),'euros_por_billete':int(m[1].replace('.',''))}
        else: result['advertencias'].append(f'{key} no reconocido')
    m=re.search(r'REINTEGROS\s+([0-9])\s+([0-9])\s+([0-9])',text,re.I)
    if m: result['reintegros']=[int(x) for x in m.groups()]
    else: result['advertencias'].append('Reintegros no reconocidos')
    return result


def national_list(text):
    """Lista acumulada: pares número/importe por billete y terminaciones.
    NO se suman terminaciones a importes acumulados (evita doble conteo).
    """
    section = re.split(r'ESTE SORTEO PONE EN JUEGO',text, maxsplit=1, flags=re.I)[0]
    full={}
    for m in PAIR.finditer(section):
        key=m[1]; value=int(m[2].replace('.',''))
        if key in full and full[key]!=value:
            raise ValueError('Número con dos importes distintos: '+key)
        full[key]=value
    terms={}
    for m in TERM.finditer(section):
        if len(m[1])==5: continue
        terms[m[1]]=int(m[2].replace('.',''))
    return {'fecha':date(text),'premios_acumulados_por_billete':full,
            'terminaciones_informativas':terms,
            'numero_entradas':len(full),
            'advertencias':['La lista puede ser parcial: no inferir premios de números ausentes',
                             'Importes por billete completo (10 décimos); no sumar terminaciones otra vez']}


def generic(text,game):
    rows,warnings=prize_table(text)
    result={'fecha':date(text),'categorias':rows,'advertencias':warnings}
    if game=='quinigol':
        matches=[]
        for line in text.splitlines():
            m=re.match(r'^\s*([1-6])\s+(.+?)\s{2,}(\d+)\s+(\d+)\s+(.+?)\s{2,}([012M]{2})\s*$',line)
            if m: matches.append({'partido':int(m[1]),'local':m[2].strip(),'goles_local':int(m[3]),'goles_visitante':int(m[4]),'visitante':m[5].strip(),'pronostico':m[6]})
        result['partidos']=matches
        if len(matches)!=6: warnings.append('Partidos de Quinigol incompletos')
    if game=='primitiva':
        joker=re.search(r'JOKER\s*:\s*(\d{7})',text,re.I)
        result['joker']=joker[1] if joker else None
    return result


def main():
    if len(OLD.SEED_PDFS)!=len(GAMES): raise SystemExit('Cantidad de URLs inesperada')
    output=Path('diagnostico_pdf_086d');output.mkdir(exist_ok=True)
    report={'version':'0.86D','generado_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
            'publicable':False,'solo_lectura':True,'fuente':'PDF oficiales SELAE, URLs históricas 0.85M',
            'documentos':[],'validaciones_cruzadas':[]}
    for i,(url,game) in enumerate(zip(OLD.SEED_PDFS,GAMES),1):
        entry={'indice':i,'juego':game,'url':url,'error':None,'validado':False}
        try:
            meta,raw=OLD.fetch(url)
            entry['http']=meta.get('http')
            if entry['http']!=200 or not raw.startswith(b'%PDF-'): raise ValueError('Descarga PDF inválida')
            pdf=PdfReader(BytesIO(raw))
            if pdf.is_encrypted or not pdf.pages: raise ValueError('PDF sin páginas legibles')
            text='\n'.join(p.extract_text(extraction_mode='layout') or '' for p in pdf.pages)
            if len(text.strip())<100: raise ValueError('PDF sin texto suficiente')
            (output/f'{i:02d}_{game}.txt').write_text(text,encoding='utf-8')
            if game=='loteria-nacional-lista': data=national_list(text)
            elif game=='loteria-nacional-mayores': data=national_major(text)
            else: data=generic(text,game)
            entry['datos']=data;entry['paginas']=len(pdf.pages)
            if not data.get('fecha'): data['advertencias'].append('Fecha no reconocida')
        except Exception as exc: entry['error']=f'{type(exc).__name__}: {exc}'
        report['documentos'].append(entry)
        print(f'{i:02d} {game}: {entry["error"] or "extraído (no validado)"}',flush=True)
    for a,b in ((5,6),(7,8)):
        lista=report['documentos'][a]; mayores=report['documentos'][b]
        check={'documentos':[a+1,b+1],'fecha_coincide':False,'premios_mayores_coinciden':False,'detalles':[]}
        if not lista['error'] and not mayores['error']:
            ld=lista['datos']; md=mayores['datos']
            check['fecha_coincide']=ld['fecha']==md['fecha']
            matches=[]
            for key in ('primer_premio','segundo_premio'):
                p=md.get(key)
                if p:
                    actual=ld['premios_acumulados_por_billete'].get(p['numero'])
                    matches.append(actual==p['euros_por_billete'])
                    check['detalles'].append({'premio':key,'numero':p['numero'],
                                               'importe_lista':actual,'importe_mayores':p['euros_por_billete']})
            check['premios_mayores_coinciden']=len(matches)==2 and all(matches)
        report['validaciones_cruzadas'].append(check)
    Path('informe_pdf_086d.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['LotoScan 0.86D — DIAGNÓSTICO, NO PUBLICABLE','']
    for item in report['documentos']:
        d=item.get('datos',{})
        lines.append(f'{item["indice"]:02d} {item["juego"]} | fecha={d.get("fecha")} | filas premios={len(d.get("categorias",[]))} | entradas lotería={d.get("numero_entradas")} | advertencias={d.get("advertencias")} | error={item["error"]}')
    for check in report['validaciones_cruzadas']:
        lines.append('Comprobación Nacional: '+json.dumps(check,ensure_ascii=False))
    Path('informe_pdf_086d.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    if any(x['error'] for x in report['documentos']): raise SystemExit('Errores en documentos: consultar informe')

if __name__=='__main__': main()
