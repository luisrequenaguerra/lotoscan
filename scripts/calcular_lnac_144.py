#!/usr/bin/env python3
"""LotoScan 1.44: cálculo económico trazable sobre JSON SELAE.
No declara premios definitivos hasta verificar exhaustivamente reglas y plan del sorteo.
"""
import argparse,json,pathlib,re,sys
from decimal import Decimal
FIELDS={'primerPremio':5,'segundoPremio':5,'extraccionesDeCuatroCifras':4,'extraccionesDeTresCifras':3,'extraccionesDeDosCifras':2,'reintegros':1}

def money(x):
    if isinstance(x,bool):raise ValueError('importe booleano')
    n=Decimal(str(x))
    if not n.is_finite() or n<0 or n!=n.to_integral_value():raise ValueError('importe inválido')
    return int(n)

def rows(d,k):return [d[k]] if k in ('primerPremio','segundoPremio') else d[k]

def validate(d):
    if d.get('tipoSorteoGeneral') not in ('J','S'):raise ValueError('tipo no ordinario')
    price=Decimal(str(d.get('precioDecimo',0)))
    if (d['tipoSorteoGeneral'],price) not in [('J',Decimal('3')),('S',Decimal('6'))]:raise ValueError('plan no admitido')
    if d.get('premioEspecial') is not None:raise ValueError('premio especial requiere comprobación independiente')
    for k,w in FIELDS.items():
        rr=rows(d,k)
        if not isinstance(rr,list) or not rr:raise ValueError('sin '+k)
        for r in rr:
            if not isinstance(r,dict) or not re.fullmatch(r'\d{%s}'%w,str(r.get('decimo',''))):raise ValueError('número inválido '+k)
            money(r.get('prize'))
    if any(money(r['prize'])!=int(price*100) for r in d['reintegros']):raise ValueError('reintegro incompatible')
    return price

def analyze(d,number):
    if not isinstance(number,str) or not re.fullmatch(r'\d{5}',number):raise ValueError('décimo inválido')
    price=validate(d)
    hits=[]; pending=[]
    def add(concept,ref,cents,origin):hits.append({'concepto':concept,'referencia':ref,'importe_centimos':cents,'origen':origin})
    for k,w in FIELDS.items():
        for r in rows(d,k):
            if number[-w:]==r['decimo']:
                add(k,r['decimo'],money(r['prize']),'SELAE JSON prize')
    # Premios derivados: los números base están excluidos de sus propios derivados.
    # No se infiere importe del JSON: estos candidatos no se suman sin un plan validado.
    for k in ('primerPremio','segundoPremio'):
        winner=d[k]['decimo']; a=int(number);b=int(winner)
        if number==winner:continue
        if a in ((b-1)%100000,(b+1)%100000):pending.append({'concepto':'aproximacion','base':k,'numero_base':winner})
        if a//100==b//100:pending.append({'concepto':'centena','base':k,'numero_base':winner})
        if k=='primerPremio':
            if number[-3:]==winner[-3:]:pending.append({'concepto':'terminacion_3','base':k,'numero_base':winner})
            if number[-2:]==winner[-2:]:pending.append({'concepto':'terminacion_2','base':k,'numero_base':winner})
    subtotal=sum(x['importe_centimos'] for x in hits)
    # La suma de coincidencias directas es verificable aritméticamente; no implica
    # que se hayan aplicado exclusiones/compatibilidades para premio pagadero.
    reasons=['Importes derivados y reglas de compatibilidad no acreditados para este sorteo mediante datos estructurados',
             'No se ha validado el cálculo frente a un oráculo independiente de pago SELAE']
    return {'id_sorteo':str(d['drawIdSorteo']),'numero':number,'precio_decimo_eur':str(price),
            'coincidencias_explicitas':hits,'premios_derivados_pendientes':pending,
            'subtotal_explicito_centimos':subtotal,'subtotal_explicito_eur':str(Decimal(subtotal)/100),
            'importe_total_eur':None,'premios_verificados':False,'publicable':False,'motivos_bloqueo':reasons}

def checks(d):
    p=d['primerPremio']['decimo']; b=int(p); tests=[]
    def t(label,n,pred):
        result=analyze(d,n);tests.append({'caso':label,'numero':n,'correcto':bool(pred(result))})
    t('primer_premio',p,lambda r:any(x['concepto']=='primerPremio' for x in r['coincidencias_explicitas']))
    t('aproximacion_anterior',f'{(b-1)%100000:05d}',lambda r:any(x['concepto']=='aproximacion' for x in r['premios_derivados_pendientes']))
    t('aproximacion_posterior',f'{(b+1)%100000:05d}',lambda r:any(x['concepto']=='aproximacion' for x in r['premios_derivados_pendientes']))
    t('no_autoderivado',p,lambda r:not any(x['base']=='primerPremio' for x in r['premios_derivados_pendientes']))
    t('centena',f'{b//100*100+(b+2)%100:05d}',lambda r:any(x['concepto']=='centena' and x['base']=='primerPremio' for x in r['premios_derivados_pendientes']) if (b+2)%100!=b%100 else True)
    for k,w in [('extraccionesDeCuatroCifras',4),('extraccionesDeTresCifras',3),('extraccionesDeDosCifras',2),('reintegros',1)]:
        t(k,'0'*(5-w)+d[k][0]['decimo'],lambda r,k=k:any(x['concepto']==k for x in r['coincidencias_explicitas']))
    try:analyze(d,'1234');tests.append({'caso':'numero_invalido','correcto':False})
    except ValueError:tests.append({'caso':'numero_invalido','correcto':True})
    return tests

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--raiz',default='datos/lotoscan/loteria_nacional/historico_completo');ap.add_argument('--informe',default='salida_144');ap.add_argument('--numero');args=ap.parse_args()
    out=pathlib.Path(args.informe);out.mkdir(parents=True,exist_ok=True)
    report={'version':'1.44','fuentes':'JSON SELAE, sin PDF','sorteos':0,'pruebas':0,'correctas':0,'errores':[],
            'registros':[],'controles':[],'premios_verificados':False,'publicable':False}
    paths=sorted(pathlib.Path(args.raiz).glob('*/original_resultados.json'))
    if not paths:report['errores'].append('Histórico LNAC vacío')
    for path in paths:
        try:
            d=json.loads(path.read_text(encoding='utf8'));validate(d)
            ts=checks(d);report['pruebas']+=len(ts);report['correctas']+=sum(x['correcto'] for x in ts)
            report['controles'].append({'id_sorteo':d['drawIdSorteo'],'casos':ts})
            report['registros'].append(analyze(d,args.numero or d['primerPremio']['decimo']))
            report['sorteos']+=1
            if not all(x['correcto'] for x in ts):report['errores'].append({'id':d['drawIdSorteo'],'fallos':[x for x in ts if not x['correcto']]})
        except Exception as exc:report['errores'].append({'archivo':str(path),'error':str(exc)})
    (out/'informe_144.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:report[k] for k in ('sorteos','pruebas','correctas','errores')},ensure_ascii=False))
    return bool(report['errores'])
if __name__=='__main__':sys.exit(main())
