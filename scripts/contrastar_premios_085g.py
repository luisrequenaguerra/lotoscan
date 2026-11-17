
#!/usr/bin/env python3
"""LotoScan 0.85G: diagnostic only. Never writes the production history."""
import datetime as dt
import json
import re
import urllib.request
from pathlib import Path
from bs4 import BeautifulSoup

TARGETS = {
 'quinigol': [
  ('2026-10-28', 'eldecimo', 'https://eldecimo.com/quinigol/2026-10-28/'),
  ('2026-10-28', 'rtve', 'https://www.rtve.es/loterias/quinigol/'),
  ('2026-10-28', 'elpais', 'https://servicios.elpais.com/sorteos/quinigol/'),
  ('2026-09-16', 'rtve', 'https://www.rtve.es/loterias/quinigol/'),
  ('2026-09-16', 'elpais', 'https://servicios.elpais.com/sorteos/quinigol/'),
 ],
 'lototurf': [('2026-11-15', 'rtve', 'https://www.rtve.es/loterias/lototurf/')],
 'quintuple_plus': [('2026-11-15', 'rtve', 'https://www.rtve.es/loterias/quintuple-plus/')],
}

MONTHS = {'enero':1,'febrero':2,'marzo':3,'abril':4,'mayo':5,'junio':6,'julio':7,'agosto':8,'septiembre':9,'setiembre':9,'octubre':10,'noviembre':11,'diciembre':12,
          'ene':1,'feb':2,'mar':3,'abr':4,'may':5,'jun':6,'jul':7,'ago':8,'sep':9,'oct':10,'nov':11,'dic':12}

def tidy(s): return ' '.join(s.split())
def fetch(url):
 req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; LotoScanAudit/0.85G)','Accept':'text/html'})
 with urllib.request.urlopen(req,timeout=30) as r:
  raw=r.read(2500000)
  return r.status,r.url,BeautifulSoup(raw.decode(r.headers.get_content_charset() or 'utf-8','replace'),'html.parser')

def dates_in(text):
 found=set()
 for m in re.finditer(r'(?<!\d)(\d{1,2})[/.-](\d{1,2})[/.-](20\d{2})(?!\d)',text):
  d,mo,y=map(int,m.groups())
  if 1<=d<=31 and 1<=mo<=12:found.add(f'{y:04d}-{mo:02d}-{d:02d}')
 for m in re.finditer(r'(?<!\d)(20\d{2})-(\d{1,2})-(\d{1,2})(?!\d)',text):
  y,mo,d=map(int,m.groups())
  if 1<=d<=31 and 1<=mo<=12:found.add(f'{y:04d}-{mo:02d}-{d:02d}')
 for m in re.finditer(r'(?<!\d)(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(20\d{2})',text,re.I):
  d,mo,y=m.groups();mon=MONTHS.get(mo.lower())
  if mon:found.add(f'{int(y):04d}-{mon:02d}-{int(d):02d}')
 for m in re.finditer(r'(?<!\d)(\d{1,2})\s+(ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)\s+(20\d{2})',text,re.I):
  d,mo,y=m.groups();found.add(f'{int(y):04d}-{MONTHS[mo.lower()]:02d}-{int(d):02d}')
 return sorted(found)

def rows_of(table):
 return [[tidy(c.get_text(' ',strip=True)) for c in tr.find_all(['td','th'],recursive=False)] for tr in table.find_all('tr') if tr.find_all(['td','th'],recursive=False)]

def extract(game,date,source,url):
 item={'juego':game,'fecha_objetivo':date,'fuente':source,'url':url,'validado':False,'publicable':False}
 try:
  status,final,soup=fetch(url)
  item['http']=status;item['url_final']=final
  title=tidy(soup.title.get_text(' ',strip=True)) if soup.title else ''
  main=soup.find('main') or soup
  text=tidy(main.get_text(' ',strip=True))
  visible_dates=dates_in(text)
  url_date=date in final or date.replace('-','/') in final
  item['titulo']=title
  item['fechas_visibles']=visible_dates[:35]
  item['fecha_en_url']=url_date
  item['fecha_en_contenido']=date in visible_dates
  item['fecha_inequivoca']=url_date and (date in visible_dates or not visible_dates)
  item['tablas']=[]
  for table in main.find_all('table'):
   rows=rows_of(table)
   if rows and re.search(r'categor|acertant|ganador|premio|cuant', ' '.join(rows[0]),re.I):
    item['tablas'].append(rows[:20])
  item['total_tablas_candidatas']=len(item['tablas'])
  item['tablas']=item['tablas'][:12]
  item['marcadores_anulados']=len(re.findall(r'(?<!\w)A\s*-\s*A(?!\w)',text,re.I))
  item['fragmentos_fecha']=[]
  for pattern in (date,date[8:]+'/'+date[5:7]+'/'+date[:4],date[8:]+' de '+next((m for m,n in MONTHS.items() if n==int(date[5:7]) and len(m)>3),'')+' de '+date[:4]):
   for m in list(re.finditer(re.escape(pattern),text,re.I))[:2]:
    item['fragmentos_fecha'].append(text[max(0,m.start()-150):m.end()+500])
  item['advertencias']=[]
  if not item['fecha_inequivoca']:
   item['advertencias'].append('No existe asociación inequívoca fecha-tabla: prohibido comparar importes de esta página')
  if len(item['tablas'])!=1:
   item['advertencias'].append('Hay cero o varias tablas candidatas: requiere aislamiento por sorteo')
  if item['fecha_inequivoca'] and len(item['tablas'])==1:
   item['advertencias'].append('Tabla candidata aislada; faltan validar reglas de categoría, resultado y precisión monetaria')
  item['observacion']='Ningún importe se certifica automáticamente en esta prueba.'
 except Exception as e:item['error']=f'{type(e).__name__}: {e}'
 return item

def main():
 report={'version':'0.85G','utc':dt.datetime.now(dt.timezone.utc).isoformat(),'solo_lectura':True,'publicable':False,'criterio':'No comparar tablas de fechas diferentes; no certificar centimos ni categorías sin aislamiento y cotejo','consultas':[]}
 for game,entries in TARGETS.items():
  for date,source,url in entries:
   item=extract(game,date,source,url);report['consultas'].append(item)
   print(game,date,source,item.get('http','ERROR'),'tablas',item.get('total_tablas_candidatas',0),'fecha_inequivoca',item.get('fecha_inequivoca',False))
 Path('informe_fuentes_085g.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 lines=['LotoScan 0.85G - diagnostico de fuentes por fecha','NO PUBLICABLE: no se certifican importes','']
 for i in report['consultas']:
  lines.append(f"{i['juego']} {i['fecha_objetivo']} {i['fuente']}: HTTP={i.get('http','ERROR')} tablas={i.get('total_tablas_candidatas',0)} fecha_inequivoca={i.get('fecha_inequivoca',False)} error={i.get('error','ninguno')}")
  for warning in i.get('advertencias',[]):lines.append('  AVISO: '+warning)
 Path('informe_fuentes_085g.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
 print('\n'.join(lines))
if __name__=='__main__':main()
