#!/usr/bin/env python3
"""LotoScan 1.40: auditoría económica de premios explícitos SELAE, sin publicar total definitivo.
'prize' se interpreta como céntimos SOLO cuando reintegro/100 coincide con precioDecimo.
No inventa cuantías de aproximaciones, centenas, terminaciones ni premio especial.
"""
import argparse, json, pathlib, re, sys
from decimal import Decimal
CAMPOS={'primerPremio':5,'segundoPremio':5,'extraccionesDeCuatroCifras':4,'extraccionesDeTresCifras':3,'extraccionesDeDosCifras':2,'reintegros':1}

def decimal_eur(v):
    if isinstance(v,bool) or not isinstance(v,(int,float)) or v<0: raise ValueError('importe inválido')
    return Decimal(str(v))

def verificar(d):
    if d.get('tipoSorteoGeneral') not in ('J','S'): raise ValueError('tipo de sorteo no admitido')
    precio=decimal_eur(d.get('precioDecimo'))
    if precio<=0: raise ValueError('precioDecimo ausente')
    for campo,n in CAMPOS.items():
        rows=[d.get(campo)] if n==5 else d.get(campo)
        if not isinstance(rows,list) or not rows:raise ValueError(f'{campo} ausente')
        for row in rows:
            if not isinstance(row,dict) or not re.fullmatch(r'\d{'+str(n)+r'}',str(row.get('decimo',''))):raise ValueError(f'{campo}: número inválido')
            decimal_eur(row.get('prize'))
    for row in d['reintegros']:
        if decimal_eur(row['prize'])/100!=precio:
            raise ValueError('escala monetaria no corroborada: reintegro distinto de precioDecimo')
    return precio

def comprobar(d,numero):
    if not isinstance(numero,str) or not re.fullmatch(r'\d{5}',numero):raise ValueError('número de décimo inválido')
    verificar(d)
    coincidencias=[]
    for campo,n in CAMPOS.items():
        rows=[d[campo]] if n==5 else d[campo]
        for row in rows:
            if numero[-n:]==row['decimo']:
                coincidencias.append({'concepto':campo,'numero_premiado':row['decimo'],
                    'prizeType':row.get('prizeType'),'importe_eur':str(decimal_eur(row['prize'])/100)})
    subtotal=sum((Decimal(x['importe_eur']) for x in coincidencias),Decimal(0))
    return {'numero':numero,'premios_explicitos':coincidencias,'subtotal_explicito_eur':str(subtotal),
            'importe_total_eur':None,'premios_verificados':False,'publicable':False,
            'nota':'Subtotal de coincidencias explícitas, no premio total: faltan reglas oficiales de acumulación, aproximaciones, centenas, terminaciones y premio especial.'}

def main():
    p=argparse.ArgumentParser();p.add_argument('--raiz',default='datos/lotoscan/loteria_nacional/historico_completo');p.add_argument('--informe',default='salida_140');p.add_argument('--numero');a=p.parse_args()
    out=pathlib.Path(a.informe);out.mkdir(parents=True,exist_ok=True)
    paths=sorted(pathlib.Path(a.raiz).glob('*/original_resultados.json'))
    report={'version':'1.40','sorteos':0,'pruebas':0,'correctas':0,'errores':[],'registros':[],
            'premios_verificados':False,'publicable':False,'conversion':'prize / 100, validada contra reintegros y precioDecimo por sorteo',
            'alcance':'Importes de premios explícitos; no importe total definitivo'}
    if not paths:report['errores'].append('No hay sorteos en histórico completo')
    for path in paths:
        try:
            d=json.loads(path.read_text(encoding='utf8'));precio=verificar(d)
            registro={'id_sorteo':d.get('drawIdSorteo'),'tipo':d['tipoSorteoGeneral'],'precio_decimo_eur':str(precio),'ejemplos':{}}
            for campo,n in CAMPOS.items():
                row=d[campo] if n==5 else d[campo][0]
                numero=('0'*(5-n))+row['decimo']
                result=comprobar(d,numero)
                report['pruebas']+=1
                if any(x['concepto']==campo and Decimal(x['importe_eur'])==decimal_eur(row['prize'])/100 for x in result['premios_explicitos']):report['correctas']+=1
                else:report['errores'].append({'sorteo':str(path),'campo':campo,'error':'premio no detectado'})
                registro['ejemplos'][campo]={'premio_eur':str(decimal_eur(row['prize'])/100),'prize_original':row['prize']}
            report['pruebas']+=1
            try:comprobar(d,'1234')
            except ValueError:report['correctas']+=1
            else:report['errores'].append({'sorteo':str(path),'error':'acepta número inválido'})
            if a.numero:registro['consulta']=comprobar(d,a.numero)
            report['registros'].append(registro);report['sorteos']+=1
        except (ValueError,KeyError,TypeError,UnicodeError,json.JSONDecodeError) as e:
            report['errores'].append({'archivo':str(path),'error':str(e)})
    report['fallidas']=len(report['errores'])
    (out/'informe_140.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:report[k] for k in ('sorteos','pruebas','correctas','fallidas','premios_verificados')},ensure_ascii=False))
    return 1 if report['fallidas'] else 0
if __name__=='__main__':sys.exit(main())
