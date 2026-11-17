
#!/usr/bin/env python3
"""LotoScan 0.85F: auditoría de fuentes alternativas, SOLO LECTURA.
No altera historico.json. No convierte importes redondeados en exactos.
"""
import datetime as dt
import json
import re
import urllib.request
from decimal import Decimal
from pathlib import Path
from bs4 import BeautifulSoup

TARGETS = {
 'quinigol_2026_10_28': {
  'rtve':'https://www.rtve.es/loterias/quinigol/',
  'eldecimo':'https://eldecimo.com/quinigol/2026-10-28/',
  'sorteosdehoy':'https://sorteosdehoy.com/quinigol/resultado-del-28-de-octubre-de-2026',
  'elpais':'https://servicios.elpais.com/sorteos/quinigol/'},
 'quinigol_2026_09_16': {
  'rtve':'https://www.rtve.es/loterias/quinigol/',
  'elpais':'https://servicios.elpais.com/sorteos/quinigol/'},
 'lototurf_2026_11_15': {
  'rtve':'https://www.rtve.es/loterias/lototurf/',
  'selae':'https://www.loteriasyapuestas.es/es/resultados?drawId=1321401246'},
 'quintuple_plus_2026_11_15': {
  'rtve':'https://www.rtve.es/loterias/quintuple-plus/',
  'selae':'https://www.loteriasyapuestas.es/es/resultados?drawId=1321401246'},
}

def fetch(url):
 req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; LotoScan/0.85F diagnostic)','Accept':'text/html'})
 with urllib.request.urlopen(req,timeout=25) as r:
  raw=r.read(2_000_000)
  encoding=r.headers.get_content_charset() or 'utf-8'
  status=r.status; final=r.url
 soup=BeautifulSoup(raw.decode(encoding,'replace'),'html.parser')
 for tag in soup(['script','style','noscript','nav','footer']): tag.decompose()
 return status,final,soup

def normalize(value): return ' '.join(value.split())

def table_rows(table):
 rows=[]
 for tr in table.find_all('tr'):
  cells=[normalize(c.get_text(' ',strip=True)) for c in tr.find_all(['td','th'],recursive=False)]
  if cells: rows.append(cells)
 return rows

def money_tokens(s):
 # preserve original monetary precision; never infer cents from rounded integer displays
 return re.findall(r'(?<!\d)(?:\d{1,3}(?:\.\d{3})+|\d+),\d{2}\s*€?',s)

def audit(url,game,date):
 item={'url':url,'fecha_objetivo':date,'juego':game,'verificado':False}
 try:
  status,final,soup=fetch(url)
  item.update({'http':status,'url_final':final,'titulo':normalize(soup.title.get_text(' ',strip=True)) if soup.title else ''})
  main=soup.find('main') or soup
  text=normalize(main.get_text(' ',strip=True))
  # Do not claim date-specific evidence just because date is present in unrelated navigation.
  item['fecha_mencionada']=date in text or date.split('-')[2]+'/'+date.split('-')[1]+'/'+date.split('-')[0] in text
  item['marcadores_A_A']=len(re.findall(r'\bA\s*-\s*A\b',text,re.I))
  item['tablas_candidatas']=[]
  for table in main.find_all('table'):
   rows=table_rows(table)
   if rows and re.search(r'categor|acertant|premio|importe|cuant',normalize(' '.join(' '.join(r) for r in rows[:2])),re.I):
    item['tablas_candidatas'].append(rows[:12])
  item['tablas_candidatas']=item['tablas_candidatas'][:8]
  item['importes_visibles_muestra']=money_tokens(text)[:35]
  item['fragmentos_fecha']=[]
  for match in list(re.finditer(re.escape(date),text,re.I))[:2]:
   item['fragmentos_fecha'].append(text[max(0,match.start()-150):match.end()+900])
  # Structured extraction and precise per-draw reconciliation require source-specific parsing.
  item['observacion']='DIAGNÓSTICO: tablas no asociadas automáticamente a una fecha; ninguna cuantía está certificada.'
 except Exception as exc: item['error']=f'{type(exc).__name__}: {exc}'
 return item

def main():
 report={'version':'0.85F','utc':dt.datetime.now(dt.timezone.utc).isoformat(),
  'solo_lectura':True,'publicable':False,
  'advertencias':[
   'Las páginas de portada pueden contener varias fechas: no emparejar tablas por índice sin validación.',
   'Quinigol A-A representa partidos anulados: no exigir seis marcadores ordinarios ni cinco categorías en esas jornadas.',
   'Los importes de RTVE pueden estar redondeados: no sustituir céntimos por ,00.',
   'Un HTTP 200 no garantiza que una fuente sea extraíble ni que tenga datos completos.'],
  'pruebas':{}}
 for key,sources in TARGETS.items():
  game,date=key.rsplit('_',3)[0],'-'.join(key.rsplit('_',3)[1:])
  report['pruebas'][key]={name:audit(url,game,date) for name,url in sources.items()}
  print(key,[(name,info.get('http'),info.get('error','')) for name,info in report['pruebas'][key].items()])
 Path('informe_fuentes_085f.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 lines=['LotoScan 0.85F - contraste de fuentes (NO PUBLICABLE)','']
 for key,items in report['pruebas'].items():
  lines.append(key)
  for name,info in items.items():
   lines.append(f"  {name}: HTTP={info.get('http','ERROR')} tablas={len(info.get('tablas_candidatas',[]))} fecha_mencionada={info.get('fecha_mencionada',False)} error={info.get('error','ninguno')}")
  lines.append('')
 lines.append('NO SE HAN CERTIFICADO IMPORTES: revisar JSON y desarrollar parsers específicos.')
 Path('informe_fuentes_085f.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
 print('\n'.join(lines))

if __name__=='__main__': main()
