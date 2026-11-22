#!/usr/bin/env python3
"""LotoScan 1.42 JSON: calcula importes explícitos SELAE y audita premios derivados.
No utiliza PDF ni presenta subtotales como premios definitivos.
"""
import argparse, json, pathlib, re, sys
from decimal import Decimal, InvalidOperation

FIELDS={'primerPremio':5,'segundoPremio':5,'extraccionesDeCuatroCifras':4,'extraccionesDeTresCifras':3,'extraccionesDeDosCifras':2,'reintegros':1}

def money(v):
    if isinstance(v,bool) or not isinstance(v,(int,float,str)): raise ValueError('importe inválido')
    try: d=Decimal(str(v))
    except InvalidOperation: raise ValueError('importe no numérico')
    if not d.is_finite() or d<0 or d!=d.to_integral_value():raise ValueError('prize debe ser céntimos enteros')
    return int(d)

def rows(d,k):return [d[k]] if k in ('primerPremio','segundoPremio') else d[k]

def validate(d):
    if d.get('tipoSorteoGeneral') not in ('J','S'):raise ValueError('tipo no ordinario J/S')
    if not re.fullmatch(r'\d{6,20}',str(d.get('drawIdSorteo',''))):raise ValueError('ID inválido')
    precio=Decimal(str(d.get('precioDecimo','0')))
    if not precio.is_finite() or precio<=0:raise ValueError('precioDecimo inválido')
    for k,w in FIELDS.items():
        r=rows(d,k)
        if not isinstance(r,list) or not r:raise ValueError(k+' ausente')
        for x in r:
            if not isinstance(x,dict) or not re.fullmatch(r'\d{%d}'%w,str(x.get('decimo',''))):raise ValueError(k+' número inválido')
            money(x.get('prize'))
    if any(Decimal(money(x['prize']))/100!=precio for x in d['reintegros']):raise ValueError('escala prize no corroborada con reintegro')
    return precio

def calc(d,num,serie=None,fraccion=None):
    if not isinstance(num,str) or not re.fullmatch(r'\d{5}',num):raise ValueError('número de décimo inválido')
    precio=validate(d); hits=[]
    for k,w in FIELDS.items():
        for i,x in enumerate(rows(d,k)):
            if num[-w:]==x['decimo']:
                hits.append({'concepto':k,'indice':i,'referencia':x['decimo'],'prizeType':x.get('prizeType'),'importe_centimos':money(x['prize'])})
    # No deduplicar extracciones distintas: pueden coincidir legítimamente.
    derived=[]
    for k in ('primerPremio','segundoPremio'):
        p=d[k]['decimo']; a=int(num); b=int(p)
        if num!=p and a in ((b-1)%100000,(b+1)%100000):derived.append({'tipo':'aproximacion','premio':k,'referencia':p,'importe_centimos':None})
        if num!=p and num[:3]==p[:3]:derived.append({'tipo':'centena','premio':k,'referencia':p,'importe_centimos':None})
        if num!=p and num[-2:]==p[-2:]:derived.append({'tipo':'terminacion_2','premio':k,'referencia':p,'importe_centimos':None})
    special=d.get('premioEspecial')
    pending=[]
    if derived:pending.append('Importes y acumulabilidad de aproximaciones/centenas/terminaciones no contenidos en los campos de extracciones')
    if special is not None:pending.append('Premio especial requiere validación de número, serie y fracción')
    if serie is not None or fraccion is not None:pending.append('Serie/fracción no certificadas por este motor')
    # Aunque no haya candidatos, no certificar total sin confirmar reglas de acumulación.
    pending.append('Acumulabilidad oficial de premios no validada para este sorteo')
    subtotal=sum(h['importe_centimos'] for h in hits)
    return {'numero':num,'id_sorteo':str(d['drawIdSorteo']),'precio_decimo_eur':str(precio),
            'coincidencias_explicitas':hits,'subtotal_explicito_centimos':subtotal,
            'subtotal_explicito_eur':str(Decimal(subtotal)/100),
            'candidatos_derivados':derived,'pendientes':pending,'importe_total_eur':None,
            'premios_verificados':False,'publicable':False}

def main():
    p=argparse.ArgumentParser();p.add_argument('--raiz',default='datos/lotoscan/loteria_nacional/historico_completo');p.add_argument('--informe',default='salida_142_json');p.add_argument('--numero');p.add_argument('--serie');p.add_argument('--fraccion');a=p.parse_args()
    out=pathlib.Path(a.informe);out.mkdir(parents=True,exist_ok=True)
    paths=sorted(pathlib.Path(a.raiz).glob('*/original_resultados.json'))
    report={'version':'1.42-json','fuentes':'JSON oficiales archivados de resultados1/resultados2; sin PDF',
            'sorteos':0,'pruebas':0,'correctas':0,'errores':[],'registros':[],
            'premios_verificados':False,'publicable':False}
    if not paths:report['errores'].append('Histórico completo vacío')
    for path in paths:
        try:
            d=json.loads(path.read_text(encoding='utf8'));validate(d)
            numbers=[d['primerPremio']['decimo'],d['segundoPremio']['decimo']]
            numbers += [('0'*(5-w)+d[k][0]['decimo']) for k,w in FIELDS.items() if w<5]
            numbers += [f'{(int(d["primerPremio"]["decimo"])+1)%100000:05d}',f'{(int(d["primerPremio"]["decimo"])-1)%100000:05d}']
            for n in numbers:
                result=calc(d,n)
                report['pruebas']+=1
                if result['numero']==n and result['importe_total_eur'] is None and not result['publicable']:report['correctas']+=1
                else:raise ValueError('control de seguridad fallido')
            report['sorteos']+=1
            chosen=a.numero or d['primerPremio']['decimo']
            report['registros'].append(calc(d,chosen,a.serie,a.fraccion))
        except Exception as e:report['errores'].append({'archivo':str(path),'error':str(e)})
    (out/'informe_142_json.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({k:report[k] for k in ('sorteos','pruebas','correctas','errores')},ensure_ascii=False))
    return 1 if report['errores'] else 0
if __name__=='__main__':sys.exit(main())
