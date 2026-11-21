#!/usr/bin/env python3
"""LotoScan 1.02: auditoría independiente de PDFs oficiales de Navidad.
No calcula premios publicables. No altera el histórico.
"""
import argparse, collections, datetime, hashlib, json, pathlib, re, urllib.parse, urllib.request
import fitz

BASE='https://www.loteriasyapuestas.es'
DRAW={2024:'1259409102',2025:'1295909102'}
PAT=re.compile(r'(?<!\d)(\d{5})\s*(?:\.\s*){0,5}([act])?\s*(?:\.\s*){0,5}(\d{3,9})(?!\d)')

def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; LotoScanAudit/1.02)','Accept':'application/pdf,application/json,*/*'})
    with urllib.request.urlopen(req,timeout=35) as r: return r.read()

def source(year, dest):
    local=pathlib.Path(f'lista_oficial_navidad_{year}.pdf')
    if local.is_file(): return local.read_bytes(),'archivo_local'
    endpoint=f'{BASE}/servicios/resultados2?idsorteo={DRAW[year]}'
    try:
        data=fetch(endpoint).decode('utf-8-sig').strip()
        data=re.sub(r'^\s*\w+\s*\(','',data).rstrip(');') if not data.startswith(('{','[')) else data
        obj=json.loads(data)
        if isinstance(obj,list): obj=obj[0]
        link=obj.get('urlListadoOficial','')
        if link: return fetch(urllib.parse.urljoin(BASE,urllib.parse.quote(link,safe='/:?=&%'))),'json_oficial'
    except Exception as e: print('Aviso: consulta JSON:',str(e)[:180])
    url=f'{BASE}/f/loterias/documentos/Loter%C3%ADa%20Nacional/listas%20de%20premios/SM_LISTAOFICIAL.A{year}.S102.pdf'
    return fetch(url),'ruta_oficial_pdf'

def analyze(year,raw,out):
    doc=fitz.open(stream=raw,filetype='pdf')
    entries=[]; lines=[]; odd=[]
    for p, page in enumerate(doc,1):
        # Dos extracciones independientes: texto geométrico y texto ordenado por contenido.
        for mode in ['sort','native']:
            txt=page.get_text('text',sort=(mode=='sort'))
            (out/f'navidad_{year}_pagina_{p}_{mode}.txt').write_text(txt,encoding='utf-8')
            matches=list(PAT.finditer(txt))
            lines.append({'pagina':p,'modo':mode,'coincidencias':len(matches)})
            for m in matches:
                number,mark,amount=m.groups()
                if int(amount)>100000000: continue
                entries.append({'numero':number,'marca':mark or '', 'euros_billete':int(amount),'pagina':p,'modo':mode,'contexto':txt[max(0,m.start()-35):m.end()+35].replace('\n',' ')})
        # Las palabras originales conservan posición para examinar omisiones.
        for x0,y0,x1,y1,word,*_ in page.get_text('words',sort=True):
            if re.fullmatch(r'\d{5}',word):
                odd.append({'numero':word,'pagina':p,'x':round(x0,1),'y':round(y0,1)})
    bymode={mode:[r for r in entries if r['modo']==mode] for mode in ['sort','native']}
    groups={mode:collections.Counter((r['numero'],r['marca'],r['euros_billete']) for r in rs) for mode,rs in bymode.items()}
    only={mode:[{'numero':k[0],'marca':k[1],'euros_billete':k[2],'veces':n} for k,n in (groups[mode]-groups['native' if mode=='sort' else 'sort']).items()] for mode in groups}
    marks={mode:dict(collections.Counter(r['marca'] or 'sin_letra' for r in rs)) for mode,rs in bymode.items()}
    candidates={mode:sorted(set(r['numero'] for r in rs if not r['marca'] and r['euros_billete']==1000)) for mode,rs in bymode.items()}
    words=collections.Counter((r['numero'],r['pagina']) for r in odd)
    parsed=set((r['numero'],r['pagina']) for r in entries)
    missing=[{'numero':n,'pagina':p,'apariciones':count} for (n,p),count in words.items() if (n,p) not in parsed]
    summary={'version':'1.02','anio':year,'paginas':len(doc),'sha256_pdf':hashlib.sha256(raw).hexdigest(),
        'referencia_pedreas_extracciones':1794,'metodos':lines,'marcas_por_metodo':marks,
        'candidatos_sin_marca_1000_por_metodo':{k:len(v) for k,v in candidates.items()},
        'diferencia_referencia':{k:1794-len(v) for k,v in candidates.items()},
        'discrepancias_entre_metodos':{k:len(v) for k,v in only.items()},
        'palabras_cinco_cifras_no_reconocidas':len(missing),
        'advertencia':'1794 es numero de extracciones, no necesariamente numeros distintos. Los registros sin letra NO se certifican como pedrea.',
        'publicable':False,'historico_modificado':False}
    (out/f'diagnostico_pdf_{year}_102.json').write_text(json.dumps({'resumen':summary,'solo_en_metodo':only,'numeros_cinco_cifras_sin_parsear':missing,'muestras_entradas':entries[:50]},ensure_ascii=False,indent=2),encoding='utf-8')
    (out/f'candidatos_{year}_102.json').write_text(json.dumps({'anio':year,'estado':'NO_VALIDADO','candidatos_por_metodo':candidates},ensure_ascii=False,indent=2),encoding='utf-8')
    return summary

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--salida',default='salida_lotoscan_102');args=ap.parse_args()
    out=pathlib.Path(args.salida);out.mkdir(parents=True,exist_ok=True)
    report={'version':'1.02','generado_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'publicable':False,'historico_modificado':False,'sorteos':{},'errores':{}}
    for year in DRAW:
        try:
            pdf,origin=source(year,out)
            if not pdf.startswith(b'%PDF'): raise ValueError('Respuesta no es PDF')
            (out/f'lista_oficial_navidad_{year}.pdf').write_bytes(pdf)
            report['sorteos'][str(year)]={'origen':origin,**analyze(year,pdf,out)}
            print(year,report['sorteos'][str(year)]['candidatos_sin_marca_1000_por_metodo'])
        except Exception as e:
            report['errores'][str(year)]=str(e);print('ERROR',year,e)
    (out/'informe_navidad_102.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if report['errores']: raise SystemExit(1)
if __name__=='__main__':main()
