#!/usr/bin/env python3
"""LotoScan 1.04: motor EXPERIMENTAL de Navidad y auditoría independiente, no publicable."""
import argparse, collections, datetime, hashlib, json, pathlib, re, urllib.request, zipfile

DRAW={2024:'1259409102',2025:'1295909102'}
PAT=re.compile(r'(?<!\d)(\d{5})\s*(?:\.\s*){0,5}([act])?\s*(?:\.\s*){0,5}(\d{3,9})(?!\d)')

def fetch(url):
 req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Accept':'application/json,*/*'})
 with urllib.request.urlopen(req,timeout=35) as response:return response.read()

def load_json(year,source):
 p=pathlib.Path(f'navidad_{year}_json.json')
 if p.exists():return json.loads(p.read_text(encoding='utf-8')),'local'
 try:
  b=fetch(f'https://www.loteriasyapuestas.es/servicios/resultados2?idsorteo={DRAW[year]}').decode('utf-8-sig').strip()
  if not b.startswith(('{','[')):b=b[b.find('(')+1:b.rfind(')')]
  o=json.loads(b)
  if isinstance(o,list):o=o[0]
  if str(o.get('drawIdSorteo'))!=DRAW[year]:raise ValueError('ID inesperado')
  return o,'selae_json'
 except Exception as e:
  if source and f'navidad_{year}_json.json' in source.namelist():return json.loads(source.read(f'navidad_{year}_json.json')),'zip_referencia'
  raise RuntimeError(f'No disponible JSON {year}: {e}')

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--entrada',default='lotoscan-selae-103.zip');ap.add_argument('--salida',default='salida_104');args=ap.parse_args()
 out=pathlib.Path(args.salida);out.mkdir(parents=True,exist_ok=True)
 source=zipfile.ZipFile(args.entrada) if pathlib.Path(args.entrada).exists() else None
 import fitz
 reports={};failures=[]
 for year in DRAW:
  catname=f'catalogo_candidatos_navidad_{year}_103.json'
  if source and catname in source.namelist():catalog=json.loads(source.read(catname))
  else:
   p=pathlib.Path(catname)
   if not p.exists():raise RuntimeError('Falta catálogo 1.03: '+catname)
   catalog=json.loads(p.read_text(encoding='utf-8'))
  numbers=[c['numero'] for c in catalog['candidatos']]
  if len(numbers)!=1794 or len(set(numbers))!=1794:raise RuntimeError('Catálogo incompleto o duplicado')
  pdf=pathlib.Path(f'lista_oficial_navidad_{year}.pdf')
  if not pdf.exists():raise RuntimeError('Falta PDF original: '+str(pdf))
  raw=pdf.read_bytes();sha=hashlib.sha256(raw).hexdigest()
  expected=catalog['resumen'].get('sha256_pdf')
  if sha!=expected:raise RuntimeError(f'El PDF {year} no coincide con el catálogo 1.03')
  doc=fitz.open(stream=raw,filetype='pdf')
  records=collections.defaultdict(list)
  for pi,page in enumerate(doc,1):
   for match in PAT.finditer(page.get_text('text',sort=False)):
    n,mark,amount=match.groups();a=int(amount)
    if a>100000000:continue
    records[n].append({'marca':mark or '', 'euros_billete':a,'pagina':pi})
  official,origin=load_json(year,source)
  first=official['primerPremio']['decimo'];second=official['segundoPremio']['decimo'];third=official['tercerosPremios'][0]['decimo']
  fourth=[x['decimo'] for x in official['cuartosPremios']];fifth=[x['decimo'] for x in official['quintosPremios']]
  majors=[(first,400000),(second,125000),(third,50000)]+[(n,20000) for n in fourth]+[(n,6000) for n in fifth]
  ped=set(numbers)
  def compute(num):
   pieces=[]
   def add(k,v):
    if v:pieces.append({'categoria':k,'euros_decimo':v})
   major=dict(majors).get(num)
   if major is not None:add('premio_principal',major)
   if num in ped:add('pedrea',100)
   # Se conservan las marcas como categorías independientes según la lista, sin inferir reglas de tarifa no verificadas.
   for r in records.get(num,[]):
    if r['marca'] in ('a','c','t') and r['euros_billete']==1000:add('lista_'+r['marca'],100)
   # Reintegro: excluir el Gordo, que ya contiene su premio mayor.
   if num.endswith(first[-1]) and num!=first:add('reintegro',20)
   return {'numero':num,'componentes':pieces,'total_euros_decimo':sum(p['euros_decimo'] for p in pieces)}
  # Motor deliberadamente parcial: premios marcados de importes distintos a 1000 se excluyen y se notifican.
  ambiguous=[{'numero':n,'registro':r} for n,rs in records.items() for r in rs if r['marca'] and r['euros_billete']!=1000]
  checks=[]
  for n,v in majors:
   c=compute(n);official_entry=next(x for x in ([official['primerPremio'],official['segundoPremio']]+official['tercerosPremios']+official['cuartosPremios']+official['quintosPremios']) if x['decimo']==n)
   expected_amount=official_entry['prize']/100
   checks.append({'numero':n,'calculado':c['total_euros_decimo'],'json_oficial':expected_amount,'coincide':c['total_euros_decimo']==expected_amount,'componentes':c['componentes']})
  examples=sorted(set(numbers[:12]+[n for n in numbers if any(r['marca'] for r in records[n])][:12]+[first,second,third]+fourth+fifth+['00000','11111']))
  results=[compute(n) for n in examples]
  discrepancies=[x for x in checks if not x['coincide']]
  reports[str(year)]={'id_sorteo':DRAW[year],'origen_json':origin,'sha256_pdf':sha,'catalogo_1794':True,'premios_mayores_contrastados':len(checks),'coincidencias_json':len(checks)-len(discrepancies),'discrepancias':discrepancies,'registros_marcados_importe_no_1000':len(ambiguous),'ejemplos':results,'advertencias':['Motor experimental: las tarifas de las marcas se toman únicamente de filas de 1.000 euros por billete.','La lista PDF y el JSON pueden contener acumulaciones; no se debe publicar el cálculo sin contrastar todas las categorías.','No se certifican 100.000 números ni el catálogo de pedrea.']}
  (out/f'contraste_navidad_{year}_104.json').write_text(json.dumps(reports[str(year)],ensure_ascii=False,indent=2),encoding='utf-8')
  (out/f'ambiguedades_navidad_{year}_104.json').write_text(json.dumps(ambiguous[:200],ensure_ascii=False,indent=2),encoding='utf-8')
  failures.extend((year,d) for d in discrepancies)
 summary={'version':'1.04','fecha_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'publicable':False,'motor_validado':False,'historico_modificado':False,'anios':reports,'discrepancias_premios_mayores':len(failures)}
 (out/'informe_navidad_104.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
 print('LotoScan 1.04: informe generado. Discrepancias:',len(failures),'Publicable: NO')
if __name__=='__main__':main()
