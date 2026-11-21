#!/usr/bin/env python3
"""LotoScan 1.24: inventario y verificación de fuentes oficiales para diez juegos.
No calcula premios, no altera históricos ni publica resultados.
"""
import argparse, datetime as dt, hashlib, json, os, pathlib, re, urllib.parse, urllib.request

GAMES = {
 'euromillones':['euromillones','euro_millones'],
 'la_primitiva':['la_primitiva','primitiva'],
 'bonoloto':['bonoloto'],
 'el_gordo_primitiva':['el_gordo','gordo_primitiva'],
 'eurodreams':['eurodreams','euro_dreams'],
 'loteria_nacional':['loteria_nacional','nacional'],
 'la_quiniela':['la_quiniela','quiniela'],
 'el_quinigol':['el_quinigol','quinigol'],
 'lototurf':['lototurf'],
 'quintuple_plus':['quintuple_plus','quintupleplus','quintuple-plus'],
}
VARIANTS = {'euromillones':['El Millón'], 'la_primitiva':['Joker'],
 'eurodreams':['Número Sueño'], 'loteria_nacional':['jueves','sábado','extraordinarios','Navidad'],
 'la_quiniela':['Pleno al 15','Elige8'], 'el_gordo_primitiva':['número clave'],
 'lototurf':['caballo'], 'quintuple_plus':['pronósticos'], 'el_quinigol':['pronósticos']}
ID_KEYS = {'idsorteo','id_sorteo','idSorteo','drawId','draw_id'}
HEADERS={'User-Agent':'LotoScan/1.24 (+diagnostico; SELAE)','Accept':'application/json,*/*'}

def guess_game(path):
 s=str(path).lower().replace(' ','_').replace('-','_')
 # Longest alias first, prevent primitiva matching gordo
 for key in ['el_gordo_primitiva','la_primitiva','loteria_nacional','quintuple_plus','el_quinigol','la_quiniela','euromillones','eurodreams','bonoloto','lototurf']:
  for alias in GAMES[key]:
   if alias in s: return key
 return None

def ids_from_obj(obj):
 found=set()
 def visit(x,depth=0):
  if depth>7:return
  if isinstance(x,dict):
   for k,v in x.items():
    if k in ID_KEYS and isinstance(v,(str,int)) and re.fullmatch(r'\d{5,20}',str(v)):
     found.add(str(v))
    elif isinstance(v,(dict,list)):visit(v,depth+1)
  elif isinstance(x,list):
   for v in x[:500]:visit(v,depth+1)
 visit(obj)
 return found

def fetch_id(draw_id):
 url='https://www.loteriasyapuestas.es/servicios/resultados2?'+urllib.parse.urlencode({'idsorteo':draw_id})
 req=urllib.request.Request(url,headers=HEADERS)
 result={'id_sorteo':draw_id,'url':url,'ok':False}
 try:
  with urllib.request.urlopen(req,timeout=25) as r:
   data=r.read(5_000_001)
   if len(data)>5_000_000:raise ValueError('Respuesta demasiado grande')
   if urllib.parse.urlsplit(r.url).hostname not in ('www.loteriasyapuestas.es','loteriasyapuestas.es'):
    raise ValueError('Redirección fuera de SELAE')
   obj=json.loads(data)
   result.update({'http':r.status,'sha256':hashlib.sha256(data).hexdigest(),
                  'bytes':len(data),'ok':True,'estructura':type(obj).__name__,
                  'claves_raiz':list(obj)[:45] if isinstance(obj,dict) else [],
                  'muestra_campos':inspect_fields(obj)})
 except Exception as e:result['error']=f'{type(e).__name__}: {e}'
 return result

def inspect_fields(obj):
 # Only keys, no assertion that their presence proves a complete variant
 keys=set()
 def walk(v,depth=0):
  if depth>5 or len(keys)>250:return
  if isinstance(v,dict):
   for k,x in v.items():
    keys.add(str(k));walk(x,depth+1)
  elif isinstance(v,list):
   for x in v[:3]:walk(x,depth+1)
 walk(obj)
 return sorted(keys)[:250]

def main():
 ap=argparse.ArgumentParser()
 ap.add_argument('--root',default='.')
 ap.add_argument('--out',default='salida_124')
 ap.add_argument('--quiniela-id',default='',help='ID SELAE conocido de La Quiniela; opcional')
 ap.add_argument('--max-por-juego',type=int,default=2)
 args=ap.parse_args()
 if args.quiniela_id and not re.fullmatch(r'\d{5,20}',args.quiniela_id):ap.error('ID de Quiniela inválido')
 root=pathlib.Path(args.root);out=pathlib.Path(args.out);out.mkdir(parents=True,exist_ok=True)
 inventory={g:[] for g in GAMES}
 # Search only JSON within known data directories; never process own reports.
 for directory in [root/'datos',root/'data']:
  if not directory.is_dir():continue
  for path in directory.rglob('*.json'):
   if path.stat().st_size>8_000_000:continue
   game=guess_game(path)
   if not game:continue
   try:
    obj=json.loads(path.read_text(encoding='utf-8-sig'))
    ids=ids_from_obj(obj)
    if ids:inventory[game].append({'archivo':str(path),'ids':sorted(ids)})
   except (OSError,UnicodeError,ValueError):continue
 if args.quiniela_id:inventory['la_quiniela'].append({'archivo':'entrada_manual_quiniela','ids':[args.quiniela_id]})
 report={'version':'1.24','fecha_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
         'fuente':'SELAE resultados2','solo_diagnostico':True,'publicable':False,
         'motor_validado':False,'juegos':{},'observaciones':[]}
 for game in GAMES:
  candidates=sorted({x for entry in inventory[game] for x in entry['ids']},reverse=True)
  selected=candidates[:max(0,args.max_por_juego)]
  results=[fetch_id(i) for i in selected]
  ok=sum(bool(r['ok']) for r in results)
  report['juegos'][game]={'variantes_previstas':VARIANTS.get(game,[]),
      'ids_localizados':len(candidates),'ids_probados':selected,'resultados':results,
      'descarga_oficial_verificada':ok>0,'variantes_verificadas':[],
      'integracion_completa':False,'estado':'FUENTE_VERIFICADA_PARCIAL' if ok else 'PENDIENTE_ID_O_DESCARGA'}
  print(game, 'ids',len(candidates),'descargas_ok',ok)
 report['observaciones']=[
  'La detección de campos no demuestra que todas las variantes estén presentes ni que los premios estén calculados.',
  'Si falta un ID, no se inventa: el informe señala el juego pendiente.',
  'No se modifican los históricos ni se publican premios.',
  'La Quiniela y Elige8 están incluidas en el alcance, pero su esquema requiere pruebas con resultados reales.']
 (out/'diagnostico_10_juegos_124.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 with (out/'resumen_124.txt').open('w',encoding='utf-8') as f:
  f.write('LotoScan 1.24 — Diagnóstico SELAE de 10 juegos\n\n')
  for game,v in report['juegos'].items():
   f.write(f"{game}: {v['estado']} | IDs encontrados {v['ids_localizados']} | descargas verificadas {sum(r['ok'] for r in v['resultados'])}\n")
  f.write('\nNo publicable. Ninguna variante se considera completa sin comprobación específica.\n')
if __name__=='__main__':main()
