#!/usr/bin/env python3
"""LotoScan 1.46: consulta de décimo por fecha/ID, con control de alcance.
Usa exclusivamente el histórico JSON SELAE en producción; los 36 casos
oficiales transcritos en 1.45 se emplean solo como pruebas de regresión.
"""
import argparse
import datetime as dt
import json
import pathlib
import re
import sys
from collections import Counter
from comprobar_premios_lnac_145 import ORACULOS, calc, validate

ROOT='datos/lotoscan/loteria_nacional/historico_completo'

def read_draws(root):
    draws=[]; errors=[]
    for path in sorted(pathlib.Path(root).glob('*/original_resultados.json')):
        try:
            data=json.loads(path.read_text(encoding='utf-8'))
            validate(data)
            sid=str(data['drawIdSorteo'])
            # The parent directory is the historical draw ID in the 1.37 archive.
            if sid != path.parent.name:
                raise ValueError('drawIdSorteo no coincide con la carpeta')
            draws.append((sid,path,data))
        except Exception as exc:
            errors.append({'archivo':str(path),'error':str(exc)})
    return draws,errors

def date_of(d):
    # The archival format may carry one of several date field names.
    for key in ('fechaSorteo','fecha_sorteo','fecha'):
        value=d.get(key)
        if isinstance(value,str):
            match=re.search(r'(\d{4})-(\d{2})-(\d{2})',value)
            if match:return match.group(0)
            match=re.search(r'^(\d{2})/(\d{2})/(\d{4})',value)
            if match:return f'{match.group(3)}-{match.group(2)}-{match.group(1)}'
    return None

def audit(d,sid):
    oracle=ORACULOS.get(sid)
    if not oracle:return {'estado':'sin_referencia_independiente','controles':0,'correctos':0,'diferencias':[]}
    diffs=[]
    for number,expected in oracle.items():
        actual=calc(d,number)['importe_centimos']
        if actual!=expected*100:
            diffs.append({'numero':number,'esperado_centimos':expected*100,'calculado_centimos':actual})
    return {'estado':'controles_superados' if not diffs else 'discrepancias',
            'controles':len(oracle),'correctos':len(oracle)-len(diffs),'diferencias':diffs}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--raiz',default=ROOT)
    ap.add_argument('--informe',default='salida_146')
    ap.add_argument('--numero',help='cinco cifras')
    ap.add_argument('--sorteo',help='ID de sorteo (preferente para identificar un sorteo)')
    ap.add_argument('--fecha',help='AAAA-MM-DD')
    args=ap.parse_args()
    out=pathlib.Path(args.informe);out.mkdir(parents=True,exist_ok=True)
    errors=[]
    if args.numero is not None and not re.fullmatch(r'\d{5}',args.numero):errors.append('numero: deben ser cinco cifras')
    if args.fecha:
        try:dt.date.fromisoformat(args.fecha)
        except ValueError:errors.append('fecha: formato AAAA-MM-DD inválido')
    if (args.sorteo or args.fecha) and not args.numero:errors.append('Para consultar un sorteo debe indicar --numero')
    draws,read_errors=read_draws(args.raiz)
    audits={sid:audit(d,sid) for sid,_,d in draws}
    chosen=draws
    if args.sorteo:chosen=[x for x in chosen if x[0]==args.sorteo]
    if args.fecha:chosen=[x for x in chosen if date_of(x[2])==args.fecha]
    if args.numero and len(chosen)!=1:
        errors.append('La consulta requiere un único sorteo: indique --sorteo; --fecha solo si el JSON contiene fecha identificable')
    consultas=[]
    if args.numero and len(chosen)==1 and not errors:
        sid,path,d=chosen[0]
        a=audits[sid]
        result=calc(d,args.numero)
        # This only attests passing sampled tests, not exhaustive economic certification.
        result['premios_verificados']=False
        result['publicable']=False
        result['estado']='importe_calculado_no_certificado'
        result['aviso']='36 controles históricos no certifican todos los números ni todos los planes; premio especial no incluido'
        consultas.append({'sorteo':sid,'fecha':date_of(d),'fuente':str(path),
                          'auditoria_muestras':a,**result})
    report={'version':'1.46','fuente':'JSON SELAE archivado','pdf_en_produccion':False,
            'sorteos_validos':len(draws),'archivos_invalidos':read_errors,
            'auditorias':audits,'controles':sum(x['controles'] for x in audits.values()),
            'correctos':sum(x['correctos'] for x in audits.values()),
            'consultas':consultas,'errores':errors,
            'premios_verificados':False,'publicable':False}
    (out/'informe_146.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'sorteos':len(draws),'controles':report['controles'],
                      'correctos':report['correctos'],'consultas':len(consultas),
                      'errores':errors,'archivos_invalidos':read_errors},ensure_ascii=False))
    return 1 if errors or read_errors or not draws or any(x['diferencias'] for x in audits.values()) else 0
if __name__=='__main__':sys.exit(main())
