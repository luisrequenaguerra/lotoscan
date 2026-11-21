#!/usr/bin/env python3
"""LotoScan 0.92: motor experimental parametrizado para jueves ordinarios.

No publica premios ni habilita liquidaciones. Las tarifas derivadas se basan
solo en el contraste del sorteo 93/26: NO se extrapolan sin validar el perfil.
"""
import argparse
import datetime as dt
import json
import pathlib
import re
import sys
from decimal import Decimal

RATES = {'aproximacion_primero':120000, 'aproximacion_segundo':74700,
         'centena_primero':3000, 'centena_segundo':1500,
         'terminacion_4_primero':7500, 'terminacion_3_primero':1500,
         'terminacion_2_primero':600}
FIELDS = {'extraccionesDeCuatroCifras':(4,4,7500),
          'extraccionesDeTresCifras':(3,7,1500),
          'extraccionesDeDosCifras':(2,9,600),
          'reintegros':(1,3,300)}
REFERENCE = {'51664':30000,'68523':6000,'51663':1230,'51665':1230,
             '68522':762,'68524':765,'51600':33,'68599':15,
             '51684':48,'68580':93,'02316':78,'00017':15,
             '00025':6,'00004':3,'11111':0,'99999':0,
             '01664':99,'00664':24,'00064':9,'00070':9}


def check(draw):
    """Bloqueo estricto ante perfiles desconocidos o datos incompletos."""
    errors=[]
    if draw.get('tipo_sorteo')!='J':errors.append('Solo se admite tipo J; sábado y extraordinarios bloqueados')
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',str(draw.get('fecha_sorteo',''))):errors.append('Fecha inválida')
    if not re.fullmatch(r'\d+',str(draw.get('id_sorteo',''))):errors.append('ID inválido')
    if draw.get('validacion',{}).get('estructura_minima_completa') is not True:errors.append('Estructura no validada')
    if draw.get('publicable') is not False:errors.append('Indicador publicable inesperado')
    p=draw.get('principales',{})
    for key,amount in [('primerPremio',3000000),('segundoPremio',600000)]:
        item=p.get(key,{})
        if not isinstance(item,dict) or not re.fullmatch(r'\d{5}',str(item.get('numero',''))):errors.append('Número principal inválido '+key)
        if item.get('premio_fuente')!=amount:errors.append('Importe principal fuera del perfil '+key)
    if p.get('primerPremio',{}).get('numero')==p.get('segundoPremio',{}).get('numero'):errors.append('Premios principales duplicados')
    ex=draw.get('extracciones',{})
    if not isinstance(ex,dict):ex={};errors.append('Extracciones no válidas')
    for field,(width,count,amount) in FIELDS.items():
        entries=ex.get(field)
        if not isinstance(entries,list) or len(entries)!=count:
            errors.append('Cantidad incompatible '+field);continue
        seen=set()
        for e in entries:
            if not isinstance(e,dict):errors.append('Entrada no válida '+field);continue
            n=e.get('numero')
            if not isinstance(n,str) or not re.fullmatch(r'\d{%d}'%width,n):errors.append('Formato incorrecto '+field)
            elif n in seen:errors.append('Duplicado '+field+':'+n)
            else:seen.add(n)
            if type(e.get('premio_fuente')) is not int or e['premio_fuente']!=amount:errors.append('Importe incompatible '+field)
    return errors


def evaluate(draw,number):
    if not isinstance(number,str) or not re.fullmatch(r'\d{5}',number):raise ValueError('Número debe contener exactamente cinco cifras')
    errors=check(draw)
    if errors:raise ValueError('; '.join(errors))
    p=draw['principales'];first=p['primerPremio']['numero'];second=p['segundoPremio']['numero']
    if number==first:parts=[{'categoria':'primer_premio','centimos':p['primerPremio']['premio_fuente']}]
    elif number==second:parts=[{'categoria':'segundo_premio','centimos':p['segundoPremio']['premio_fuente']}]
    else:
        parts=[]
        def add(name,amount):parts.append({'categoria':name,'centimos':amount})
        if abs(int(number)-int(first))==1:add('aproximacion_primero',RATES['aproximacion_primero'])
        if abs(int(number)-int(second))==1:add('aproximacion_segundo',RATES['aproximacion_segundo'])
        if number[:3]==first[:3]:add('centena_primero',RATES['centena_primero'])
        if number[:3]==second[:3]:add('centena_segundo',RATES['centena_segundo'])
        for width in (4,3,2):
            if number.endswith(first[-width:]):add('terminacion_%d_primero'%width,RATES['terminacion_%d_primero'%width])
        for field in FIELDS:
            for entry in draw['extracciones'][field]:
                if number.endswith(entry['numero']):add(field+':'+entry['numero'],entry['premio_fuente'])
    cents=sum(x['centimos'] for x in parts)
    return {'numero':number,'total_centimos_experimental':cents,
            'total_euros_experimental':str((Decimal(cents)/100).quantize(Decimal('0.01'))),
            'componentes':parts,'publicable':False}


def fixture():
    return {'id_sorteo':'1329109093','fecha_sorteo':'2026-11-19','tipo_sorteo':'J','publicable':False,
      'validacion':{'estructura_minima_completa':True},
      'principales':{'primerPremio':{'numero':'51664','premio_fuente':3000000},'segundoPremio':{'numero':'68523','premio_fuente':600000}},
      'extracciones':{'extraccionesDeCuatroCifras':[{'numero':n,'premio_fuente':7500} for n in ('2316','4388','7198','8580')],
      'extraccionesDeTresCifras':[{'numero':n,'premio_fuente':1500} for n in ('017','379','448','545','684','725','904')],
      'extraccionesDeDosCifras':[{'numero':n,'premio_fuente':600} for n in ('25','27','28','55','70','72','78','82','87')],
      'reintegros':[{'numero':n,'premio_fuente':300} for n in ('0','4','6')]}}


def tests():
    d=fixture();out=[]
    for number,expected in REFERENCE.items():
        result=evaluate(d,number)
        out.append({'caso':'referencia_'+number,'ok':Decimal(result['total_euros_experimental'])==Decimal(expected)})
    other=json.loads(json.dumps(d));other['id_sorteo']='999999999';other['fecha_sorteo']='2026-11-26'
    other['principales']['primerPremio']['numero']='12345';other['principales']['segundoPremio']['numero']='67890'
    out.append({'caso':'otro_jueves_numeros_dinamicos','ok':evaluate(other,'12345')['total_euros_experimental']=='30000.00'})
    out.append({'caso':'otro_jueves_aproximacion','ok':any(x['categoria']=='aproximacion_primero' for x in evaluate(other,'12344')['componentes'])})
    other['tipo_sorteo']='S'
    out.append({'caso':'sabado_bloqueado','ok':bool(check(other))})
    other['tipo_sorteo']='J';other['extracciones']['reintegros']=[]
    out.append({'caso':'reintegros_incompletos_bloqueados','ok':bool(check(other))})
    return out


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--historico',default='datos/loteria_nacional/historico');ap.add_argument('--informe',default='informes/lnac_092/analisis.json');ap.add_argument('--limite',type=int,default=20);args=ap.parse_args()
    report={'version':'0.92','fecha_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'publicacion_premios':False,
            'alcance':'jueves con perfil economico identico al 93/26; tarifas derivadas aun pendientes de validacion independiente para cada sorteo',
            'pruebas':tests(),'sorteos':[],'errores':[]}
    if args.limite<1 or args.limite>200:report['errores'].append('Límite fuera de rango')
    else:
        paths=sorted(pathlib.Path(args.historico).glob('sorteo_*.json'),reverse=True)[:args.limite]
        if not paths:report['errores'].append('No hay sorteos archivados')
        for path in paths:
            try:
                draw=json.loads(path.read_text(encoding='utf-8'));errors=check(draw)
                item={'archivo':str(path),'id_sorteo':draw.get('id_sorteo'),'fecha_sorteo':draw.get('fecha_sorteo'),
                      'estado':'bloqueado' if errors else 'perfil_experimental_admitido','motivos':errors,'publicable':False}
                if not errors:
                    sample=[draw['principales']['primerPremio']['numero'],draw['principales']['segundoPremio']['numero'],'00000','11111']
                    item['muestras']=[evaluate(draw,n) for n in sample]
                    if str(draw.get('id_sorteo'))=='1329109093':
                        results=[evaluate(draw,n)['total_euros_experimental']==str(Decimal(v).quantize(Decimal('0.01'))) for n,v in REFERENCE.items()]
                        item['contraste_93_26']={'casos':len(results),'correctos':sum(results)}
                        if not all(results):report['errores'].append('Fallo contraste 93/26 en histórico real')
                report['sorteos'].append(item)
            except Exception as exc:report['errores'].append(str(path)+': '+str(exc))
    if not all(x['ok'] for x in report['pruebas']):report['errores'].append('Fallan autopruebas')
    report['estado']='analisis_completado' if not report['errores'] else 'requiere_revision'
    dest=pathlib.Path(args.informe);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'estado':report['estado'],'autopruebas':sum(x['ok'] for x in report['pruebas']),
                      'sorteos':len(report['sorteos']),'errores':report['errores']},ensure_ascii=False))
    return 1 if report['errores'] else 0

if __name__=='__main__':sys.exit(main())
