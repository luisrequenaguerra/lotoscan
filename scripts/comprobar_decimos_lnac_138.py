#!/usr/bin/env python3
"""LotoScan 1.38: coincidencias verificables LNAC, SIN atribuir premios económicos.
Lee los JSON originales archivados por 1.37. No modifica el histórico.
"""
import argparse, json, pathlib, re, sys

FIELDS={'extraccionesDeCuatroCifras':4,'extraccionesDeTresCifras':3,'extraccionesDeDosCifras':2,'reintegros':1}

def validar(d):
    if not isinstance(d,dict) or not re.fullmatch(r'\d{6,20}',str(d.get('drawIdSorteo',''))):
        raise ValueError('identificador de sorteo ausente')
    if d.get('tipoSorteoGeneral') not in ('J','S'):
        raise ValueError('solo sorteos ordinarios J/S')
    for k,w in [('primerPremio',5),('segundoPremio',5),*FIELDS.items()]:
        rows=[d.get(k)] if k in ('primerPremio','segundoPremio') else d.get(k)
        if not isinstance(rows,list) or not rows: raise ValueError(k+' ausente')
        for row in rows:
            if not isinstance(row,dict) or not re.fullmatch(r'\d{'+str(w)+r'}',str(row.get('decimo',''))):
                raise ValueError(k+' inválido')

def coincidencias(d,numero):
    if not re.fullmatch(r'\d{5}',numero): raise ValueError('décimo debe tener 5 cifras')
    validar(d)
    result=[]
    for k in ('primerPremio','segundoPremio'):
        row=d[k]
        if numero==row['decimo']:
            result.append({'tipo':k,'numero':row['decimo'],'prize_original':row.get('prize'),'prizeType':row.get('prizeType')})
    for k,w in FIELDS.items():
        for row in d[k]:
            if numero[-w:]==row['decimo']:
                result.append({'tipo':k,'numero':row['decimo'],'prize_original':row.get('prize'),'prizeType':row.get('prizeType')})
    return result

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--raiz',default='datos/lotoscan/loteria_nacional/historico_completo')
    ap.add_argument('--informe',default='salida_138')
    ap.add_argument('--numero',help='Décimo de 5 cifras para auditar en todos los sorteos')
    args=ap.parse_args()
    root=pathlib.Path(args.raiz); out=pathlib.Path(args.informe);out.mkdir(parents=True,exist_ok=True)
    report={'version':'1.38','alcance':'coincidencias directas; sin aproximaciones, centenas, terminaciones adicionales ni importes definitivos','sorteos':0,'pruebas':0,'superadas':0,'errores':[],'detalles':[],'premios_verificados':False,'publicable':False}
    paths=sorted(root.glob('*/original_resultados.json'))
    if not paths: report['errores'].append('No hay JSON originales del histórico 1.37')
    for path in paths:
        try:
            d=json.loads(path.read_text(encoding='utf-8'));validar(d)
            report['sorteos']+=1
            p1=d['primerPremio']['decimo'];p2=d['segundoPremio']['decimo']
            # Controles independientes de coincidencia, pérdida y formato.
            cases=[('primer premio',p1,'primerPremio'),('segundo premio',p2,'segundoPremio')]
            for k,w in FIELDS.items():
                cases.append((k,'00000'[:-w]+d[k][0]['decimo'],k))
            for name,num,expected in cases:
                hits=coincidencias(d,num);report['pruebas']+=1
                if any(x['tipo']==expected for x in hits):report['superadas']+=1
                else:report['errores'].append({'archivo':str(path),'prueba':name,'numero':num})
            report['pruebas']+=1
            try:coincidencias(d,'1234')
            except ValueError:report['superadas']+=1
            else:report['errores'].append({'archivo':str(path),'prueba':'rechazar número de 4 cifras'})
            detail={'id_sorteo':d['drawIdSorteo'],'pruebas':len(cases)+1,'extracciones':{k:len(d[k]) for k in FIELDS}}
            if args.numero:detail['consulta']={'numero':args.numero,'coincidencias':coincidencias(d,args.numero)}
            report['detalles'].append(detail)
        except (ValueError,KeyError,TypeError,UnicodeError) as e:report['errores'].append({'archivo':str(path),'error':str(e)})
    report['fallidas']=len(report['errores'])
    (out/'informe_138.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('sorteos','pruebas','superadas','fallidas','premios_verificados')},ensure_ascii=False))
    return 1 if report['errores'] else 0

if __name__=='__main__':sys.exit(main())
