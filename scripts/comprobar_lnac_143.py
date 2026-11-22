#!/usr/bin/env python3
"""LotoScan 1.43: auditoría de candidatos derivados y coincidencias oficiales JSON.
No presupone cuantías ni compatibilidades ausentes del JSON SELAE.
"""
import argparse, json, pathlib, re, sys
from decimal import Decimal

FIELDS={'primerPremio':5,'segundoPremio':5,'extraccionesDeCuatroCifras':4,'extraccionesDeTresCifras':3,'extraccionesDeDosCifras':2,'reintegros':1}

def cents(v):
    if isinstance(v,bool):raise ValueError('prize booleano')
    x=Decimal(str(v))
    if not x.is_finite() or x<0 or x!=x.to_integral_value():raise ValueError('prize no es céntimos enteros')
    return int(x)

def entries(d,k):
    return [d[k]] if k in ('primerPremio','segundoPremio') else d[k]

def validate(d):
    if d.get('tipoSorteoGeneral') not in ('J','S'):raise ValueError('sorteo no ordinario')
    if not re.fullmatch(r'\d{6,20}',str(d.get('drawIdSorteo',''))):raise ValueError('ID inválido')
    price=Decimal(str(d.get('precioDecimo','0')))
    if not price.is_finite() or price<=0:raise ValueError('precio inválido')
    for k,w in FIELDS.items():
        rows=entries(d,k)
        if not isinstance(rows,list) or not rows:raise ValueError('falta '+k)
        for x in rows:
            if not isinstance(x,dict) or not re.fullmatch(r'\d{%d}'%w,str(x.get('decimo',''))):raise ValueError('número inválido en '+k)
            cents(x.get('prize'))
    if any(Decimal(cents(x['prize']))/100!=price for x in d['reintegros']):raise ValueError('escala de reintegro incompatible')
    return price

def analyze(d,number,serie=None,fraccion=None):
    if not isinstance(number,str) or not re.fullmatch(r'\d{5}',number):raise ValueError('décimo inválido')
    price=validate(d)
    hits=[]
    for k,w in FIELDS.items():
        for i,x in enumerate(entries(d,k)):
            if number[-w:]==x['decimo']:
                hits.append({'concepto':k,'indice_extraccion':i,'referencia':x['decimo'],'prizeType':x.get('prizeType'),'importe_centimos':cents(x['prize'])})
    candidates=[]
    for k in ('primerPremio','segundoPremio'):
        winning=d[k]['decimo']; a=int(number); b=int(winning)
        if number!=winning:
            # No envolvemos 00000 y 99999: límite de numeración sin circularidad.
            if abs(a-b)==1:candidates.append({'concepto':'aproximacion','premio_base':k,'referencia':winning,'importe_centimos':None})
            if number[:3]==winning[:3]:candidates.append({'concepto':'centena','premio_base':k,'referencia':winning,'importe_centimos':None})
            if number[-2:]==winning[-2:]:candidates.append({'concepto':'terminacion_dos_cifras','premio_base':k,'referencia':winning,'importe_centimos':None})
    subtotal=sum(x['importe_centimos'] for x in hits)
    return {'numero':number,'id_sorteo':str(d['drawIdSorteo']),'fecha_sorteo':d.get('fechaSorteo'),
            'tipo_sorteo':d['tipoSorteoGeneral'],'precio_decimo_eur':str(price),
            'coincidencias_explicitas':hits,'candidatos_derivados':candidates,
            'subtotal_explicito_centimos':subtotal,'subtotal_explicito_eur':str(Decimal(subtotal)/100),
            'premio_especial_presente':d.get('premioEspecial') is not None,
            'serie_fraccion_proporcionadas':serie is not None and fraccion is not None,
            'importe_total_eur':None,'premios_verificados':False,'publicable':False,
            'motivos_bloqueo':['El JSON no especifica importes de aproximaciones/centenas/terminaciones ni reglas de compatibilidad',
                               'Premio especial exige validación independiente de número, serie y fracción']}

def controls(d):
    p=d['primerPremio']['decimo']; q=d['segundoPremio']['decimo']
    checks=[]
    def check(name,n,predicate):
        r=analyze(d,n);ok=bool(predicate(r));checks.append({'caso':name,'numero':n,'correcto':ok,'coincidencias':len(r['coincidencias_explicitas']),'derivados':[x['concepto'] for x in r['candidatos_derivados']]})
    check('primer_premio',p,lambda r:any(x['concepto']=='primerPremio' for x in r['coincidencias_explicitas']))
    check('segundo_premio',q,lambda r:any(x['concepto']=='segundoPremio' for x in r['coincidencias_explicitas']))
    for label,delta in [('aproximacion_anterior',-1),('aproximacion_posterior',1)]:
        n=int(p)+delta
        if 0<=n<=99999:
            check(label,f'{n:05d}',lambda r:any(x['concepto']=='aproximacion' and x['premio_base']=='primerPremio' for x in r['candidatos_derivados']))
    # Busca un número de la centena que no sea el principal y no sea aproximación.
    base=(int(p)//100)*100
    for n in range(base,base+100):
        if n!=int(p) and abs(n-int(p))>1:
            check('centena',f'{n:05d}',lambda r:any(x['concepto']=='centena' and x['premio_base']=='primerPremio' for x in r['candidatos_derivados']));break
    check('terminacion_2',f'{(int(p)+100)%100000:05d}',lambda r:any(x['concepto']=='terminacion_dos_cifras' and x['premio_base']=='primerPremio' for x in r['candidatos_derivados']))
    for field,w in [('extraccionesDeCuatroCifras',4),('extraccionesDeTresCifras',3),('extraccionesDeDosCifras',2),('reintegros',1)]:
        n='0'*(5-w)+d[field][0]['decimo']
        check(field,n,lambda r,field=field:any(x['concepto']==field for x in r['coincidencias_explicitas']))
    for n in ['00000','99999']:
        check('limite_'+n,n,lambda r:all(x['referencia']!=('99999' if n=='00000' else '00000') for x in r['candidatos_derivados'] if x['concepto']=='aproximacion'))
    try:analyze(d,'1234');checks.append({'caso':'rechazo_numero_corto','correcto':False})
    except ValueError:checks.append({'caso':'rechazo_numero_corto','correcto':True})
    return checks

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--raiz',default='datos/lotoscan/loteria_nacional/historico_completo');ap.add_argument('--informe',default='salida_143');ap.add_argument('--numero');ap.add_argument('--serie');ap.add_argument('--fraccion');args=ap.parse_args()
    out=pathlib.Path(args.informe);out.mkdir(parents=True,exist_ok=True)
    report={'version':'1.43','fuentes':'JSON SELAE resultados1/resultados2 archivados, sin PDF',
            'sorteos':0,'pruebas':0,'correctas':0,'errores':[],'controles':[],'registros':[],
            'premios_verificados':False,'publicable':False}
    paths=sorted(pathlib.Path(args.raiz).glob('*/original_resultados.json'))
    if not paths:report['errores'].append('No hay histórico completo de LNAC')
    for path in paths:
        try:
            d=json.loads(path.read_text(encoding='utf-8'));validate(d)
            cases=controls(d);report['pruebas']+=len(cases);report['correctas']+=sum(c['correcto'] for c in cases)
            report['controles'].append({'id_sorteo':d['drawIdSorteo'],'casos':cases})
            report['registros'].append(analyze(d,args.numero or d['primerPremio']['decimo'],args.serie,args.fraccion))
            report['sorteos']+=1
            for c in cases:
                if not c['correcto']:report['errores'].append({'id_sorteo':d['drawIdSorteo'],'caso':c['caso']})
        except Exception as exc:report['errores'].append({'archivo':str(path),'error':str(exc)})
    (out/'informe_143.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('sorteos','pruebas','correctas','errores')},ensure_ascii=False))
    return 1 if report['errores'] else 0
if __name__=='__main__':sys.exit(main())
