#!/usr/bin/env python3
"""LotoScan 1.39: auditoría de reglas candidatas LNAC, SIN certificar importes.
No modifica datos. No interpreta 'prize' como euros por décimo sin validación.
"""
import argparse, json, pathlib, re, sys

CAMPOS={'extraccionesDeCuatroCifras':4,'extraccionesDeTresCifras':3,'extraccionesDeDosCifras':2,'reintegros':1}

def numero_premio(d, campo):
    row=d.get(campo)
    if not isinstance(row,dict) or not re.fullmatch(r'\d{5}',str(row.get('decimo',''))):
        raise ValueError(f'{campo} ausente o inválido')
    return row['decimo']

def validar(d):
    if not re.fullmatch(r'\d{6,20}',str(d.get('drawIdSorteo',''))): raise ValueError('id inválido')
    if d.get('tipoSorteoGeneral') not in ('J','S'): raise ValueError('tipo de sorteo no ordinario')
    for k in ('primerPremio','segundoPremio'):numero_premio(d,k)
    for k,n in CAMPOS.items():
        if not isinstance(d.get(k),list) or not d[k]:raise ValueError(f'{k} ausente')
        for row in d[k]:
            if not isinstance(row,dict) or not re.fullmatch(r'\d{'+str(n)+r'}',str(row.get('decimo',''))):
                raise ValueError(f'{k} inválido')

def evaluar(d, numero):
    if not isinstance(numero,str) or not re.fullmatch(r'\d{5}',numero):raise ValueError('décimo inválido')
    validar(d)
    p1,p2=(numero_premio(d,k) for k in ('primerPremio','segundoPremio'))
    hallazgos=[]
    def add(tipo,referencia,**extra):hallazgos.append({'tipo':tipo,'referencia':referencia,**extra})
    for k,p in [('primerPremio',p1),('segundoPremio',p2)]:
        if numero==p:add(k,p)
        # Se marcan como candidatas: validar reglas por tipo de sorteo antes de abonar.
        if int(numero) in ((int(p)-1)%100000,(int(p)+1)%100000):add('aproximacion_candidata_'+k,p)
        if numero[:3]==p[:3] and numero!=p:add('centena_candidata_'+k,p)
        if numero[-2:]==p[-2:] and numero!=p:add('terminacion_2_candidata_'+k,p)
    for k,w in CAMPOS.items():
        for row in d[k]:
            if numero[-w:]==row['decimo']:
                add(k,row['decimo'],prize_original=row.get('prize'),prizeType=row.get('prizeType'))
    return {'numero':numero,'coincidencias_y_candidatos':hallazgos,'importe_total_eur':None,
            'premios_verificados':False,'publicable':False,
            'advertencia':'Reglas de aproximación, centenas, terminaciones y acumulación pendientes de contraste con plan oficial; prize no convertido a euros.'}

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--raiz',default='datos/lotoscan/loteria_nacional/historico_completo')
    p.add_argument('--informe',default='salida_139')
    p.add_argument('--numero',help='Décimo de 5 cifras; opcional')
    args=p.parse_args();out=pathlib.Path(args.informe);out.mkdir(parents=True,exist_ok=True)
    report={'version':'1.39','sorteos':0,'pruebas':0,'superadas':0,'errores':[],
            'resultados':[],'premios_verificados':False,'publicable':False,
            'alcance':'auditoría de coincidencias y reglas candidatas; NO cálculo económico certificado'}
    files=sorted(pathlib.Path(args.raiz).glob('*/original_resultados.json'))
    if not files:report['errores'].append('Histórico LNAC 1.37 vacío')
    for path in files:
        try:
            d=json.loads(path.read_text(encoding='utf-8'));validar(d)
            p1=numero_premio(d,'primerPremio');p2=numero_premio(d,'segundoPremio')
            cases=[('primerPremio',p1,'primerPremio'),('segundoPremio',p2,'segundoPremio'),
                   ('aproximacion',f'{(int(p1)+1)%100000:05d}','aproximacion_candidata_primerPremio'),
                   ('centena',p1[:3]+'00','centena_candidata_primerPremio'),
                   ('terminacion', '000'+p1[-2:],'terminacion_2_candidata_primerPremio')]
            # Casos de centena/terminación pueden coincidir exactamente con el premio; evitar falso fallo.
            for name,num,tipo in cases:
                if num==p1 and name in ('centena','terminacion'):continue
                report['pruebas']+=1
                got=evaluar(d,num)
                if any(x['tipo']==tipo for x in got['coincidencias_y_candidatos']):report['superadas']+=1
                else:report['errores'].append({'archivo':str(path),'prueba':name,'numero':num})
            for campo,w in CAMPOS.items():
                num='0'*(5-w)+d[campo][0]['decimo']
                report['pruebas']+=1
                if any(x['tipo']==campo for x in evaluar(d,num)['coincidencias_y_candidatos']):report['superadas']+=1
                else:report['errores'].append({'archivo':str(path),'prueba':campo})
            report['pruebas']+=1
            try:evaluar(d,'1234')
            except ValueError:report['superadas']+=1
            else:report['errores'].append({'archivo':str(path),'prueba':'rechazo de número inválido'})
            entry={'id_sorteo':d['drawIdSorteo'],'tipo':d['tipoSorteoGeneral'],
                   'extracciones':{k:len(d[k]) for k in CAMPOS},
                   'prizeType_observados':sorted({str(row.get('prizeType')) for k in CAMPOS for row in d[k]})}
            if args.numero:entry['consulta']=evaluar(d,args.numero)
            report['resultados'].append(entry);report['sorteos']+=1
        except (ValueError,KeyError,TypeError,UnicodeError) as e:report['errores'].append({'archivo':str(path),'error':str(e)})
    report['fallidas']=len(report['errores'])
    (out/'informe_139.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('sorteos','pruebas','superadas','fallidas','premios_verificados')},ensure_ascii=False))
    return 1 if report['errores'] else 0
if __name__=='__main__':sys.exit(main())
