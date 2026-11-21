#!/usr/bin/env python3
"""LotoScan 1.03: catálogo auditable, NO publicable, de candidatos a pedrea."""
import argparse, collections, datetime, hashlib, json, pathlib, re, urllib.parse, urllib.request
import fitz

BASE='https://www.loteriasyapuestas.es'
DRAW={2024:'1259409102',2025:'1295909102'}
# Coincidencia deliberadamente estricta. La extracción geométrica se usa solo como contraste.
PAT=re.compile(r'(?<!\d)(\d{5})\s*(?:\.\s*){0,5}([act])?\s*(?:\.\s*){0,5}(\d{3,9})(?!\d)')

def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (LotoScanAudit/1.03)','Accept':'application/pdf,application/json,*/*'})
    with urllib.request.urlopen(req,timeout=50) as resp:return resp.read()

def pdf_source(year):
    local=pathlib.Path(f'lista_oficial_navidad_{year}.pdf')
    if local.is_file():return local.read_bytes(),'archivo_local'
    try:
        data=fetch(f'{BASE}/servicios/resultados2?idsorteo={DRAW[year]}').decode('utf-8-sig').strip()
        if not data.startswith(('{','[')):
            data=data[data.find('(')+1:data.rfind(')')]
        obj=json.loads(data)
        if isinstance(obj,list):obj=obj[0]
        link=obj.get('urlListadoOficial')
        if link:
            url=urllib.parse.urljoin(BASE,urllib.parse.quote(link,safe='/:?=&%'))
            return fetch(url),'enlace_json_oficial'
    except Exception as exc:print('Aviso JSON',year,str(exc)[:160])
    url=f'{BASE}/f/loterias/documentos/Loter%C3%ADa%20Nacional/listas%20de%20premios/SM_LISTAOFICIAL.A{year}.S102.pdf'
    return fetch(url),'ruta_pdf_oficial'

def extract(page,mode):
    txt=page.get_text('text',sort=(mode=='geometrico'))
    rows=[]
    for m in PAT.finditer(txt):
        num,mark,amount=m.groups()
        if int(amount)>100000000:continue
        rows.append({'numero':num,'marca':mark or '', 'euros_billete':int(amount),
                     'contexto':txt[max(0,m.start()-38):min(len(txt),m.end()+38)].replace('\n',' ')})
    return rows

def audit(year,raw,out):
    if not raw.startswith(b'%PDF'):raise ValueError('No se recibió un PDF')
    doc=fitz.open(stream=raw,filetype='pdf')
    bymode={'nativo':[],'geometrico':[]}; word_five=[]
    for page_no,page in enumerate(doc,1):
        for mode in bymode:
            for r in extract(page,mode):
                r['pagina']=page_no
                bymode[mode].append(r)
        for w in page.get_text('words',sort=True):
            if re.fullmatch(r'\d{5}',w[4]):word_five.append({'numero':w[4],'pagina':page_no,'x':round(w[0],1),'y':round(w[1],1)})
    native=bymode['nativo']
    geo=bymode['geometrico']
    n_native=collections.Counter(r['numero'] for r in native if r['marca']=='' and r['euros_billete']==1000)
    n_geo=set(r['numero'] for r in geo if r['marca']=='' and r['euros_billete']==1000)
    marked=collections.defaultdict(list)
    for r in native:
        if r['marca']:marked[r['numero']].append({'marca':r['marca'],'euros_billete':r['euros_billete'],'pagina':r['pagina']})
    main=set()
    for r in native:
        if r['euros_billete']>=100000 and not r['marca']:main.add(r['numero'])
    catalog=[]
    for num in sorted(n_native):
        originals=[r for r in native if r['numero']==num and not r['marca'] and r['euros_billete']==1000]
        catalog.append({'numero':num,'apariciones_nativas':n_native[num],
                        'paginas':sorted(set(r['pagina'] for r in originals)),
                        'tambien_en_extraccion_geometrica':num in n_geo,
                        'premios_marcados_mismo_numero':marked.get(num,[]),
                        'contexto_evidencia':originals[0]['contexto'],
                        'estado':'CANDIDATO_NO_CERTIFICADO'})
    suspicious=[r for r in native if r['euros_billete']==1000 and r['marca']=='' and (r['numero'] in main)]
    # La igualdad numérica NO valida los 1794 números; conservar las discrepancias.
    summary={'version':'1.03','anio':year,'id_sorteo':DRAW[year],
             'sha256_pdf':hashlib.sha256(raw).hexdigest(),'paginas_pdf':len(doc),
             'registros_nativos':len(native),'registros_geometricos':len(geo),
             'candidatos_nativos_distintos':len(n_native),'apariciones_nativas':sum(n_native.values()),
             'referencia_extracciones_pedrea':1794,
             'diferencia_vs_referencia':1794-sum(n_native.values()),
             'candidatos_repetidos_nativos':{n:c for n,c in n_native.items() if c>1},
             'candidatos_solo_nativo':len(set(n_native)-n_geo),
             'candidatos_solo_geometrico':len(n_geo-set(n_native)),
             'candidatos_con_premios_marcados':sum(bool(marked.get(n)) for n in n_native),
             'candidatos_coincidentes_con_premios_mayores':len(suspicious),
             'palabras_cinco_cifras_geometricas':len(word_five),
             'catalogo_validado':False,'publicable':False,'historico_modificado':False}
    (out/f'catalogo_candidatos_navidad_{year}_103.json').write_text(json.dumps({'resumen':summary,'candidatos':catalog},ensure_ascii=False,indent=2),encoding='utf-8')
    (out/f'auditoria_navidad_{year}_103.json').write_text(json.dumps({
        'resumen':summary,
        'solo_nativo':sorted(set(n_native)-n_geo),
        'solo_geometrico':sorted(n_geo-set(n_native)),
        'candidatos_duplicados':summary['candidatos_repetidos_nativos'],
        'candidatos_con_premios_marcados':[{'numero':n,'marcas':marked[n]} for n in sorted(n_native) if marked.get(n)],
        'coincidencias_premios_mayores':suspicious,
        'advertencias':['Un conteo de 1794 no certifica identidad ni integridad de la pedrea.',
          'Las diferencias entre métodos requieren revisión; no se sustituyen registros automáticamente.',
          'El catálogo no permite determinar premios pagaderos ni publicar resultados.']},ensure_ascii=False,indent=2),encoding='utf-8')
    return summary

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--salida',default='salida_lotoscan_103');args=parser.parse_args()
    out=pathlib.Path(args.salida);out.mkdir(parents=True,exist_ok=True)
    report={'version':'1.03','fecha_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'publicable':False,'historico_modificado':False,'catalogo_validado':False,'sorteos':{},'errores':{}}
    for year in DRAW:
        try:
            raw,origin=pdf_source(year)
            report['sorteos'][str(year)]={'origen':origin,**audit(year,raw,out)}
            print(year,report['sorteos'][str(year)]['candidatos_nativos_distintos'])
        except Exception as exc:
            report['errores'][str(year)]=str(exc)
            print('ERROR',year,exc)
    (out/'informe_navidad_103.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if report['errores']:raise SystemExit(1)
if __name__=='__main__':main()
