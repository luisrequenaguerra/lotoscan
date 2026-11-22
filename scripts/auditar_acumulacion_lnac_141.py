#!/usr/bin/env python3
"""LotoScan 1.41: auditoría conservadora de coincidencias económicas LNAC.
No presupone acumulación legal de premios ni cuantías derivadas.
"""
import argparse, json, pathlib, re, sys
from collections import Counter
from decimal import Decimal

DIRECTOS={'primerPremio':5,'segundoPremio':5,'extraccionesDeCuatroCifras':4,'extraccionesDeTresCifras':3,'extraccionesDeDosCifras':2,'reintegros':1}

def rows(d,campo):
    return [d[campo]] if campo in ('primerPremio','segundoPremio') else d[campo]

def validar(d):
    if d.get('tipoSorteoGeneral') not in ('J','S'):raise ValueError('tipo no ordinario')
    precio=Decimal(str(d.get('precioDecimo')))
    if precio<=0:raise ValueError('precio inválido')
    for campo,n in DIRECTOS.items():
        r=rows(d,campo)
        if not isinstance(r,list) or not r:raise ValueError(f'{campo} ausente')
        for item in r:
            if not isinstance(item,dict) or not re.fullmatch(r'\d{%s}'%n,str(item.get('decimo',''))):raise ValueError(f'{campo} inválido')
            p=item.get('prize')
            if isinstance(p,bool) or not isinstance(p,(int,float)) or p<0:raise ValueError(f'{campo} importe inválido')
    if any(Decimal(str(x['prize']))/100!=precio for x in d['reintegros']):raise ValueError('escala monetaria sin corroborar')
    return precio

def evaluar(d,numero):
    if not isinstance(numero,str) or not re.fullmatch(r'\d{5}',numero):raise ValueError('décimo inválido')
    validar(d)
    coincidencias=[]
    for campo,n in DIRECTOS.items():
        for i,r in enumerate(rows(d,campo)):
            if numero[-n:]==r['decimo']:
                coincidencias.append({'campo':campo,'indice_extraccion':i,'referencia':r['decimo'],'prizeType':r.get('prizeType'),'importe_eur':str(Decimal(str(r['prize']))/100)})
    # No deduplicar por valor: extracciones distintas con el mismo número son hechos distintos.
    p1=d['primerPremio']['decimo'];p2=d['segundoPremio']['decimo']
    candidatos=[]
    for nombre,p in [('primerPremio',p1),('segundoPremio',p2)]:
        if numero!=p and int(numero) in ((int(p)-1)%100000,(int(p)+1)%100000):candidatos.append({'concepto':'aproximacion','premio_referencia':nombre})
        if numero!=p and numero[:3]==p[:3]:candidatos.append({'concepto':'centena','premio_referencia':nombre})
        if numero!=p and numero[-2:]==p[-2:]:candidatos.append({'concepto':'terminacion_2','premio_referencia':nombre})
    subtotal=sum((Decimal(x['importe_eur']) for x in coincidencias),Decimal(0))
    return {'numero':numero,'coincidencias_directas':coincidencias,'numero_coincidencias_directas':len(coincidencias),
      'suma_aritmetica_directa_eur':str(subtotal),'suma_directa_no_certificada':True,
      'candidatos_derivados_sin_importe':candidatos,'importe_total_eur':None,'premios_verificados':False,'publicable':False,
      'advertencia':'La suma aritmética NO acredita acumulabilidad ni premio pagadero. Pendientes plan oficial, premios derivados y especial de serie/fracción.'}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--raiz',default='datos/lotoscan/loteria_nacional/historico_completo');ap.add_argument('--informe',default='salida_141');ap.add_argument('--numero');a=ap.parse_args()
    out=pathlib.Path(a.informe);out.mkdir(parents=True,exist_ok=True)
    report={'version':'1.41','sorteos':0,'pruebas':0,'correctas':0,'errores':[],'registros':[],
      'premios_verificados':False,'publicable':False,'alcance':'Auditoría de suma aritmética de coincidencias directas y detección de conceptos derivados sin importes'}
    paths=sorted(pathlib.Path(a.raiz).glob('*/original_resultados.json'))
    if not paths:report['errores'].append('No se encontraron sorteos LNAC')
    def prueba(ok,desc,path):
        report['pruebas']+=1
        if ok:report['correctas']+=1
        else:report['errores'].append({'archivo':str(path),'prueba':desc})
    for path in paths:
        try:
            d=json.loads(path.read_text(encoding='utf-8'));validar(d)
            entry={'id_sorteo':d.get('drawIdSorteo'),'tipo':d['tipoSorteoGeneral'],'ejemplos':{}}
            for campo,n in DIRECTOS.items():
                r=rows(d,campo)[0];num=('0'*(5-n))+r['decimo'];res=evaluar(d,num)
                prueba(any(x['campo']==campo and x['importe_eur']==str(Decimal(str(r['prize']))/100) for x in res['coincidencias_directas']),campo,path)
                entry['ejemplos'][campo]={'numero':num,'coincidencias':res['numero_coincidencias_directas'],'suma_no_certificada_eur':res['suma_aritmetica_directa_eur']}
            # Prueba de suma exacta: cada fila detectada contribuye una vez (incluso coincidencias cruzadas)
            num=d['primerPremio']['decimo'];res=evaluar(d,num)
            prueba(Decimal(res['suma_aritmetica_directa_eur'])==sum((Decimal(x['importe_eur']) for x in res['coincidencias_directas']),Decimal(0)),'suma exacta',path)
            # Aproximación del primer premio, con vuelta 00000/99999
            p=int(num);num2=f'{(p+1)%100000:05d}';res2=evaluar(d,num2)
            prueba(any(x['concepto']=='aproximacion' and x['premio_referencia']=='primerPremio' for x in res2['candidatos_derivados_sin_importe']),'aproximación candidata',path)
            prueba(res2['importe_total_eur'] is None and not res2['publicable'],'bloqueo publicación',path)
            try:evaluar(d,'1234')
            except ValueError:prueba(True,'rechazo número inválido',path)
            else:prueba(False,'rechazo número inválido',path)
            if a.numero:entry['consulta']=evaluar(d,a.numero)
            report['registros'].append(entry);report['sorteos']+=1
        except (ValueError,TypeError,KeyError,UnicodeError,json.JSONDecodeError) as e:report['errores'].append({'archivo':str(path),'error':str(e)})
    report['fallidas']=len(report['errores'])
    (out/'informe_141.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('sorteos','pruebas','correctas','fallidas','premios_verificados')},ensure_ascii=False))
    return int(bool(report['fallidas']))
if __name__=='__main__':sys.exit(main())
