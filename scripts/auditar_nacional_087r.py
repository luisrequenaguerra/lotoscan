#!/usr/bin/env python3
"""LotoScan 0.87R: auditoría de suficiencia de fuentes LNAC, sin cálculo de premios."""
import argparse, datetime, json, pathlib, re, sys

HIST=pathlib.Path('datos/selae_provisional/historico_provisional.json')
OUT=pathlib.Path('informe_nacional_087r.json')
BASE=[
 {'fecha':'2026-11-12','primero':'39430','segundo':'52774','pdf_extracciones_completas':False,'entradas_pdf_detectadas':200},
 {'fecha':'2026-11-14','primero':'75409','segundo':'38422','pdf_extracciones_completas':False,'entradas_pdf_detectadas':200},
]

def records(obj):
 if isinstance(obj,list):
  for x in obj: yield from records(x)
 elif isinstance(obj,dict):
  if obj.get('game_id')=='LNAC' and 'combinacion' in obj: yield obj
  else:
   for v in obj.values():
    if isinstance(v,(list,dict)): yield from records(v)

def audit(rec):
 c=rec.get('combinacion') or {}; first=str(c.get('primer_premio','')); second=str(c.get('Segundo_premio',''))
 issues=[]
 if not re.fullmatch(r'\d{5}',first): issues.append('primer_premio_no_valido')
 if not re.fullmatch(r'\d{5}',second): issues.append('segundo_premio_no_valido')
 rein=rec.get('reintegros')
 if not isinstance(rein,list) or not rein or any(not re.fullmatch(r'\d',str(x)) for x in rein): issues.append('reintegros_no_validos')
 rows=rec.get('escrutinio') or []
 if not isinstance(rows,list): issues.append('escrutinio_no_es_lista'); rows=[]
 ext=[r for r in rows if isinstance(r,dict) and str(r.get('tipo','')).startswith('Extracción')]
 # Los tipos e importes NO incluyen las combinaciones concretas de cada extracción.
 if ext: issues.append('extracciones_solo_importes_sin_numeros_ganadores')
 if not any(isinstance(r,dict) and r.get('tipo')=='Primer Premio' for r in rows): issues.append('falta_fila_primer_premio')
 if not any(isinstance(r,dict) and r.get('tipo')=='Segundo Premio' for r in rows): issues.append('falta_fila_segundo_premio')
 issues.extend(['sin_lista_completa_validada','reglas_acumulacion_no_verificadas','sin_verificacion_serie_fraccion'])
 return {'fecha_sorteo':rec.get('fecha_sorteo'),'id_sorteo':rec.get('id_sorteo'),'primer_premio':first,'segundo_premio':second,'reintegros':rein,'filas_extracciones_sin_numeros':len(ext),'bloqueos':issues,'apto_para_comprobar_decimos':False,'publicable':False}

def main():
 p=argparse.ArgumentParser();p.add_argument('--historico',default=str(HIST));args=p.parse_args()
 tests=[]
 def test(name,condition): tests.append({'caso':name,'aprobada':bool(condition)})
 sample={'game_id':'LNAC','fecha_sorteo':'2026-11-14 13:00:00','id_sorteo':'1328609092','combinacion':{'primer_premio':'75409','Segundo_premio':'38422'},'reintegros':['9','0','4'],'escrutinio':[{'tipo':'Primer Premio','premio':'60000'},{'tipo':'Segundo Premio','premio':'12000'},{'tipo':'Extracción de 4 cifras','premio':'150'}]}
 a=audit(sample)
 test('detecta_primero_y_segundo',a['primer_premio']=='75409' and a['segundo_premio']=='38422')
 test('detecta_reintegros',a['reintegros']==['9','0','4'])
 test('extraccion_sin_combinacion_bloquea','extracciones_solo_importes_sin_numeros_ganadores' in a['bloqueos'])
 test('no_publica_sin_lista',not a['publicable'] and not a['apto_para_comprobar_decimos'])
 bad=json.loads(json.dumps(sample));bad['combinacion']['primer_premio']='abc'
 test('rechaza_numero_invalido','primer_premio_no_valido' in audit(bad)['bloqueos'])
 test('pdf_086g_no_certifica_exhaustividad',all(not x['pdf_extracciones_completas'] for x in BASE))
 test('no_suma_reintegros_automaticamente',not any(k in a for k in ('premio_total','premio_eur')))
 test('no_infiere_sin_premio',not any(k in a for k in ('sin_premio','importe_cero')))
 path=pathlib.Path(args.historico); entries=[]; error=None
 if path.exists():
  try:
   raw=json.loads(path.read_text(encoding='utf-8')); entries=[audit(r) for r in records(raw)]
  except Exception as e: error=str(e)
 report={'version':'0.87R','generado_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'objetivo':'Auditar datos necesarios para motor exhaustivo Lotería Nacional; no calcular premios','fuentes_revisadas':['SELAE JSON histórico 0.87E (muestra de 2026-11-14)','auditoría de PDF oficiales 0.86G (2026-11-12 y 2026-11-14)'],'hallazgos_pdf_086g':BASE,'pruebas':tests,'aprobadas':sum(t['aprobada'] for t in tests),'fallidas':sum(not t['aprobada'] for t in tests),'historico_existe':path.exists(),'historico_error':error,'registros_lnac_auditados':len(entries),'auditoria_historico':entries,'historico_modificado':False,'publicables':0,'pendiente':'Obtener lista íntegra verificable de extracciones, aproximaciones, centenas, terminaciones y reglas de acumulación; cotejar por sorteo y décimo'}
 OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(f"0.87R: {report['aprobadas']}/{len(tests)} pruebas, {len(entries)} sorteos LNAC auditados; publicables=0")
 return 1 if report['fallidas'] or error else 0
if __name__=='__main__':sys.exit(main())
