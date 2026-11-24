#!/usr/bin/env python3
"""LotoScan 1.45: importes por décimo de sorteos ordinarios LNAC.
Entrada: JSON SELAE persistido por 1.37. PDF solo usado fuera de producción
para construir controles independientes incluidos en este archivo.
"""
import argparse, json, pathlib, re, sys
from decimal import Decimal

# Oráculo independiente: valores TRANSCRITOS de las listas oficiales SELAE
# S092, S093 y S094, página 1, euros/billete dividido entre 10.
ORACULOS = {
 '1328609092': {'75409':60000,'75408':1030,'75410':1036,'75400':36,'75414':48,'75491':60,'38422':12000,'38421':596,'38423':584,'38409':78,'75450':48,'75407':42},
 '1329109093': {'51664':30000,'51663':1230,'51665':1230,'51600':33,'51684':48,'68523':6000,'68522':762,'68524':765,'68580':93,'51670':39,'68500':18,'51625':36},
 '1329309094': {'23641':60000,'23640':1036,'23642':1030,'23600':36,'23607':48,'23673':60,'26323':12000,'26322':584,'26324':584,'26346':60,'23688':42,'26300':36},
}
FIELDS={'extraccionesDeCuatroCifras':4,'extraccionesDeTresCifras':3,'extraccionesDeDosCifras':2,'reintegros':1}

def cents(v):
 if isinstance(v,bool): raise ValueError('importe booleano')
 n=Decimal(str(v))
 if not n.is_finite() or n<0 or n!=n.to_integral_value():raise ValueError('importe no entero en céntimos')
 return int(n)

def validate(d):
 kind=d.get('tipoSorteoGeneral');price={'J':3,'S':6}.get(kind)
 if price is None or Decimal(str(d.get('precioDecimo'))) != price:raise ValueError('no es sorteo ordinario J/S compatible')
 if d.get('premioEspecial') is not None:raise ValueError('premio especial no implementado')
 for name in ('primerPremio','segundoPremio'):
  r=d[name]
  if not re.fullmatch(r'\d{5}',str(r.get('decimo',''))):raise ValueError(name+' inválido')
  cents(r['prize'])
 for name,width in FIELDS.items():
  rs=d.get(name)
  if not isinstance(rs,list) or not rs:raise ValueError(name+' ausente')
  expected={'extraccionesDeCuatroCifras':4,'extraccionesDeTresCifras':7 if kind=='J' else 10,'extraccionesDeDosCifras':9,'reintegros':3}[name]
  if len(rs)!=expected:raise ValueError(name+' cantidad incompatible con modalidad ordinaria')
  # Las extracciones pueden repetirse legítimamente; conservar multiplicidad.
  if name=='reintegros' and len({str(r.get('decimo','')) for r in rs})!=expected:raise ValueError('reintegros duplicados')
  for r in rs:
   if not re.fullmatch(r'\d{%d}'%width,str(r.get('decimo',''))):raise ValueError(name+' número inválido')
   cents(r['prize'])
 for r in d['reintegros']:
  if cents(r['prize'])!=price*100:raise ValueError('importe reintegro incompatible')
 return price

def calc(d,number):
 if not isinstance(number,str) or not re.fullmatch(r'\d{5}',number):raise ValueError('número de décimo inválido')
 price=validate(d);first=d['primerPremio'];second=d['segundoPremio']
 # La lista oficial refleja el premio principal sin acumulación de terminaciones
 # ni reintegros sobre el mismo número.
 for name,r in (('primer_premio',first),('segundo_premio',second)):
  if number==r['decimo']:
   total=cents(r['prize']);return {'numero':number,'importe_total_eur':total/100,'importe_centimos':total,'desglose':[{'concepto':name,'centimos':total}],'premios_verificados':False,'publicable':False}
 hits=[]
 def add(name,amount,ref):
  if amount: hits.append({'concepto':name,'referencia':ref,'centimos':amount})
 a=int(number)
 for name,r in (('primero',first),('segundo',second)):
  b=int(r['decimo'])
  if a in ((b-1)%100000,(b+1)%100000):
   # Importe por décimo de aproximación: sábado 1000/554; jueves 1200/747.
   amt= (100000 if name=='primero' else 55400) if price==6 else (120000 if name=='primero' else 74700)
   add('aproximacion_'+name,amt,r['decimo'])
  if a//100==b//100:
   add('centena_'+name,(3000 if (name=='primero' or price==6) else 1500),r['decimo'])
 # Terminaciones del primero; se excluye el primer premio, ya tratado arriba.
 if number[-4:]==first['decimo'][-4:] and price==3:add('terminacion_4_primer',7500,first['decimo'])
 if number[-3:]==first['decimo'][-3:]:add('terminacion_3_primer',3000 if price==6 else 1500,first['decimo'])
 if number[-2:]==first['decimo'][-2:]:add('terminacion_2_primer',1200 if price==6 else 600,first['decimo'])
 # Los tres reintegros ya vienen en el JSON; no duplicar el del primer premio.
 for name,width in FIELDS.items():
  for r in d[name]:
   if number[-width:]==r['decimo']:add(name,cents(r['prize']),r['decimo'])
 total=sum(x['centimos'] for x in hits)
 return {'numero':number,'importe_total_eur':total/100,'importe_centimos':total,'desglose':hits,'premios_verificados':False,'publicable':False}

def main():
 p=argparse.ArgumentParser();p.add_argument('--raiz',default='datos/lotoscan/loteria_nacional/historico_completo');p.add_argument('--informe',default='salida_145');p.add_argument('--numero');args=p.parse_args()
 out=pathlib.Path(args.informe);out.mkdir(parents=True,exist_ok=True)
 report={'version':'1.45','origen_produccion':'JSON SELAE','referencia_validacion':'Listas oficiales S092/S093/S094, usadas solo para pruebas','sorteos':0,'controles':0,'correctos':0,'fallidos':[],'sin_oraculo':[],'consultas':[],'premios_verificados':False,'publicable':False}
 paths=sorted(pathlib.Path(args.raiz).glob('*/original_resultados.json'))
 if not paths:report['fallidos'].append({'error':'No hay JSON en el histórico'})
 for path in paths:
  try:
   d=json.loads(path.read_text(encoding='utf-8'));validate(d);sid=str(d['drawIdSorteo']);report['sorteos']+=1
   oracle=ORACULOS.get(sid)
   if oracle:
    for number,expected in oracle.items():
     got=calc(d,number)['importe_centimos'];report['controles']+=1
     if got==expected*100:report['correctos']+=1
     else:report['fallidos'].append({'sorteo':sid,'numero':number,'esperado_eur':expected,'calculado_eur':got/100})
   else:report['sin_oraculo'].append(sid)
   if args.numero:
    result=calc(d,args.numero)
    result['premios_verificados']=bool(oracle) and all(x['sorteo']!=sid for x in report['fallidos'] if 'sorteo' in x)
    result['publicable']=False
    report['consultas'].append({'sorteo':sid,**result})
  except Exception as exc:report['fallidos'].append({'archivo':str(path),'error':str(exc)})
 report['premios_verificados']=bool(report['controles']) and not report['fallidos']
 report['publicable']=False # No publicar hasta cobertura ampliada, extraordinarios y especial.
 (out/'informe_145.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 print(json.dumps({k:report[k] for k in ('sorteos','controles','correctos','fallidos','sin_oraculo')},ensure_ascii=False))
 return 1 if report['fallidos'] else 0
if __name__=='__main__':sys.exit(main())
