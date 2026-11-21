#!/usr/bin/env python3
"""LotoScan 0.91: contraste experimental del sorteo LNAC 19-11-2026.

Referencia: lista oficial SELAE sorteo 93/26 (premios en euros por billete).
NO autoriza liquidación/publicación. Solo un sorteo y pruebas seleccionadas.
"""
import argparse
import datetime as dt
import json
import pathlib
import re
import sys
from decimal import Decimal

DRAW_ID = '1329109093'
OFFICIAL_URL = 'https://www.loteriasyapuestas.es/f/loterias/documentos/Loter%C3%ADa%20Nacional/listas%20de%20premios/SM_LISTAOFICIAL.A2026.S093.pdf'
# Importes por décimo en céntimos, contrastados con la lista oficial de este sorteo.
RATES = {'aprox1':120000,'aprox2':74700,'cent1':3000,'cent2':1500,
         't4_1':7500,'t3_1':1500,'t2_1':600,'reintegro':300}
# Cifras de contraste: importes oficiales por billete / 10.
REFERENCE = {'51664':30000,'68523':6000,'51663':1230,'51665':1230,
             '68522':762,'68524':765,'51600':33,'68599':15,
             '51684':48,'68580':93,'02316':78,'00017':15,
             '00025':6,'00004':3,'11111':0,'99999':0,
             '01664':99,'00664':24,'00064':9,'00070':9}


def get_entries(draw, field, width):
    entries = draw.get('extracciones',{}).get(field)
    if not isinstance(entries,list):
        raise ValueError('Falta lista '+field)
    result=[]
    for e in entries:
        if not isinstance(e,dict): raise ValueError('Entrada inválida '+field)
        num=e.get('numero')
        if not isinstance(num,str) or not re.fullmatch(r'\d{%d}'%width,num):
            raise ValueError('Formato inválido en '+field+': '+repr(num))
        amount=e.get('premio_fuente')
        if isinstance(amount,bool) or not isinstance(amount,int) or amount<0:
            raise ValueError('Importe inválido en '+field)
        result.append((num,amount))
    return result


def evaluate(draw, number):
    if not re.fullmatch(r'\d{5}',number): raise ValueError('Número inválido')
    p=draw['principales']
    a=p['primerPremio']; b=p['segundoPremio']
    first=a['numero']; second=b['numero']
    if not all(isinstance(n,str) and re.fullmatch(r'\d{5}',n) for n in (first,second)):
        raise ValueError('Premios principales inválidos')
    if first==second: raise ValueError('Premios principales duplicados')
    for entry, expected in ((a,3000000),(b,600000)):
        if entry.get('premio_fuente')!=expected: raise ValueError('Cuantía principal inesperada')
    # Las extracciones ya incluyen las terminaciones derivadas del primer premio.
    four=get_entries(draw,'extraccionesDeCuatroCifras',4)
    three=get_entries(draw,'extraccionesDeTresCifras',3)
    two=get_entries(draw,'extraccionesDeDosCifras',2)
    rein=get_entries(draw,'reintegros',1)
    if (len(four),len(three),len(two),len(rein))!=(4,7,9,3):
        raise ValueError('Conteo de extracciones no corresponde al sorteo 93/26')
    if any(x!=7500 for _,x in four) or any(x!=1500 for _,x in three) or any(x!=600 for _,x in two) or any(x!=300 for _,x in rein):
        raise ValueError('Importes de extracciones inesperados')
    if sorted(n for n,_ in rein)!=['0','4','6']:
        raise ValueError('Reintegros inesperados para sorteo de referencia')
    if number==first:
        return {'numero':number,'centimos':3000000,'euros':'30000.00','componentes':[{'tipo':'primer_premio','centimos':3000000}]}
    if number==second:
        return {'numero':number,'centimos':600000,'euros':'6000.00','componentes':[{'tipo':'segundo_premio','centimos':600000}]}
    parts=[]
    def add(category,cents):parts.append({'tipo':category,'centimos':cents})
    if abs(int(number)-int(first))==1:add('aproximacion_primero',RATES['aprox1'])
    if abs(int(number)-int(second))==1:add('aproximacion_segundo',RATES['aprox2'])
    if number[:3]==first[:3]:add('centena_primero',RATES['cent1'])
    if number[:3]==second[:3]:add('centena_segundo',RATES['cent2'])
    if number[-4:]==first[-4:]:add('terminacion_4_primero',RATES['t4_1'])
    if number[-3:]==first[-3:]:add('terminacion_3_primero',RATES['t3_1'])
    if number[-2:]==first[-2:]:add('terminacion_2_primero',RATES['t2_1'])
    for label, width, entries in [('extraccion_4',4,four),('extraccion_3',3,three),('extraccion_2',2,two),('reintegro',1,rein)]:
        for suffix,amount in entries:
            if number.endswith(suffix):add(label+':'+suffix,amount)
    # El reintegro del primer premio YA está incluido en 'reintegros' del JSON.
    # No añadirlo dos veces.
    total=sum(part['centimos'] for part in parts)
    return {'numero':number,'centimos':total,'euros':str((Decimal(total)/100).quantize(Decimal('0.01'))),'componentes':parts}


def verify_draw(draw):
    if str(draw.get('id_sorteo'))!=DRAW_ID or draw.get('fecha_sorteo')!='2026-11-19' or draw.get('tipo_sorteo')!='J':
        raise ValueError('Sorteo distinto del 93/26; motor no generalizado')
    if draw.get('validacion',{}).get('estructura_minima_completa') is not True:
        raise ValueError('Histórico sin validación estructural')
    if draw.get('publicable') is not False:
        raise ValueError('El histórico no debe estar marcado como publicable')


def selftest():
    # Prueba sintética autocontenida de reglas sin dependencia del repositorio.
    d={'id_sorteo':DRAW_ID,'fecha_sorteo':'2026-11-19','tipo_sorteo':'J','publicable':False,
       'validacion':{'estructura_minima_completa':True},
       'principales':{'primerPremio':{'numero':'51664','premio_fuente':3000000},'segundoPremio':{'numero':'68523','premio_fuente':600000}},
       'extracciones':{'extraccionesDeCuatroCifras':[{'numero':n,'premio_fuente':7500} for n in ('2316','4388','7198','8580')],
       'extraccionesDeTresCifras':[{'numero':n,'premio_fuente':1500} for n in ('017','379','448','545','684','725','904')],
       'extraccionesDeDosCifras':[{'numero':n,'premio_fuente':600} for n in ('25','27','28','55','70','72','78','82','87')],
       'reintegros':[{'numero':n,'premio_fuente':300} for n in ('0','4','6')]}}
    verify_draw(d)
    results=[]
    for n,euros in REFERENCE.items():
        result=evaluate(d,n)
        actual=Decimal(result['euros']); expected=Decimal(euros)
        results.append({'numero':n,'esperado_euros':str(expected),'calculado_euros':str(actual),'ok':actual==expected,'componentes':result['componentes']})
    return d,results


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--historico',default='datos/loteria_nacional/historico')
    ap.add_argument('--informe',default='informes/lnac_091/validacion.json')
    args=ap.parse_args()
    report={'version':'0.91','fecha_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
            'objetivo':'contraste limitado sorteo jueves 93/26','referencia_oficial':OFFICIAL_URL,
            'unidad_json':'centimos EUR por decimo (contrastada en sorteo 93/26)',
            'publicacion_premios':False,'liquidacion_habilitada':False,'errores':[]}
    try:
        _,tests=selftest()
        report['autopruebas']={'total':len(tests),'correctas':sum(t['ok'] for t in tests),'detalle':tests}
        if not all(t['ok'] for t in tests):raise ValueError('Autopruebas no coinciden con lista oficial')
        path=pathlib.Path(args.historico)/('sorteo_'+DRAW_ID+'.json')
        draw=json.loads(path.read_text(encoding='utf-8'))
        verify_draw(draw)
        live=[{'numero':n,'esperado_euros':str(Decimal(v)),'calculado_euros':evaluate(draw,n)['euros'],
               'ok':Decimal(evaluate(draw,n)['euros'])==Decimal(v)} for n,v in REFERENCE.items()]
        report['historico_real']={'archivo':str(path),'pruebas':len(live),'correctas':sum(x['ok'] for x in live),'detalle':live}
        if not all(x['ok'] for x in live):raise ValueError('Diferencias con lista oficial en histórico real')
    except Exception as exc:report['errores'].append(str(exc))
    report['estado']='contraste_limitado_superado' if not report['errores'] else 'requiere_revision'
    dest=pathlib.Path(args.informe);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'estado':report['estado'],'autopruebas':report.get('autopruebas',{}).get('correctas'),
                      'historico':report.get('historico_real',{}).get('correctas'),'errores':report['errores']},ensure_ascii=False))
    return 1 if report['errores'] else 0

if __name__=='__main__':sys.exit(main())
