#!/usr/bin/env python3
"""LotoScan 1.28: inspeccion de las 10 fichas oficiales para terceros.
NO modifica historico, NO usa resultados2 ni PDF, NO publica premios.
Las fichas HTML son diagnostico, NO sustituyen la fuente JSON resultados1.
"""
import argparse, datetime as dt, hashlib, json, re, urllib.parse, urllib.request
from pathlib import Path
from html.parser import HTMLParser

BASE='https://www.loteriasyapuestas.es'
GAMES={
 'euromillones':('EMIL','euromillones.html'),
 'primitiva':('LAPR','primitiva.html'),
 'bonoloto':('BONO','bonoloto.html'),
 'gordo':('ELGR','gordo.html'),
 'eurodreams':('EDMS','eurodreams.html'),
 'loteria_nacional':('LNAC','lnac.html'),
 'quiniela':('LAQU','quiniela.html'),
 'quinigol':('QGOL','quinigol.html'),
 'lototurf':('LOTU','lototurf.html'),
 'quintuple_plus':('QUPL','quintuple.html'),
}
class Inspector(HTMLParser):
 def __init__(self):
  super().__init__();self.ids=[];self.scripts=[];self._script=False;self._buffer=[];self.text=[];self._skip=False
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if a.get('id'):self.ids.append(a['id'])
  if tag=='script':self._script=True;self._buffer=[];self.scripts.append({'src':a.get('src'),'type':a.get('type')})
 def handle_data(self,data):
  if self._script:self._buffer.append(data)
  elif data.strip():self.text.append(data.strip())
 def handle_endtag(self,tag):
  if tag=='script' and self._script:
   self.scripts[-1]['contenido']= ''.join(self._buffer)[:1000]
   self._script=False

def fetch(url):
 req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (LotoScan 1.28; fuentes SELAE)','Accept':'text/html,application/xhtml+xml','Cache-Control':'no-cache'})
 with urllib.request.urlopen(req,timeout=35) as r:
  if urllib.parse.urlsplit(r.url).hostname not in ('www.loteriasyapuestas.es','loteriasyapuestas.es'):raise ValueError('Redireccion fuera de SELAE')
  data=r.read(3_000_001)
  if len(data)>3_000_000:raise ValueError('Respuesta demasiado grande')
  return r.status,r.headers.get('Content-Type',''),data

def main():
 p=argparse.ArgumentParser();p.add_argument('--out',default='salida_128');args=p.parse_args()
 out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
 report={'version':'1.28','fecha_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'objetivo':'inspeccion fuentes oficiales HTML para terceros; no histórico','fuente_documentacion':BASE+'/es/resultados-medios/resultados-ultimos-sorteos','juegos':{}}
 for name,(code,file) in GAMES.items():
  url=BASE+'/f/loterias/resultados/'+file+'?'+urllib.parse.urlencode({'game_id':code})
  rec={'codigo':code,'url':url,'tipo':'HTML oficial para terceros, no JSON resultados1','publicable':False}
  try:
   status,ctype,data=fetch(url);rec.update(http=status,content_type=ctype,bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
   page=data.decode('utf-8','replace');parser=Inspector();parser.feed(page)
   rec['ids_resultados']=[i for i in parser.ids if any(x in i.lower() for x in ('result','quin','escrut','premio','elige'))][:100]
   rec['scripts_externos']=[s['src'] for s in parser.scripts if s.get('src')][:40]
   rec['json_embebido_detectado']=any(s.get('type') in ('application/json','application/ld+json') for s in parser.scripts)
   rec['texto_muestra']=' '.join(parser.text)[:1000]
   rec['menciones_elige8']=bool(re.search(r'elige\s*8|elige8',page,re.I))
   rec['menciones_pleno15']=bool(re.search(r'pleno\s+al\s+15|pleno\s+al\s+quince',page,re.I))
   # Muestra HTML original como evidencia de estructura, sin incluirlo en historico
   (out/(name+'.html')).write_bytes(data)
  except Exception as e:rec['error']=str(e)
  report['juegos'][name]=rec
 (out/'diagnostico_128.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 ok=sum(1 for x in report['juegos'].values() if x.get('http')==200)
 print(f'LotoScan 1.28: {ok}/10 fichas HTTP 200; SOLO diagnóstico, histórico intacto')
 for name,x in report['juegos'].items():print(name,x.get('http','ERROR'),x.get('error',''))
if __name__=='__main__':main()
