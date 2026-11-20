#!/usr/bin/env python3
"""LotoScan 0.88: auditoría del histórico LNAC; NO calcula ni publica premios."""
import argparse, datetime as dt, json, pathlib, re, sys

CAMPOS={'extraccionesDeCuatroCifras':4,'extraccionesDeTresCifras':3,'extraccionesDeDosCifras':2,'extraccionesDeCincoCifras':5,'reintegros':1}

def auditar(ruta):
    errores=[]; avisos=[]
    try: d=json.loads(ruta.read_text(encoding='utf-8'))
    except Exception as exc: return {'archivo':str(ruta),'valido':False,'errores':['JSON ilegible: '+str(exc)],'avisos':[]}
    if not isinstance(d,dict): return {'archivo':str(ruta),'valido':False,'errores':['Raíz no es objeto'],'avisos':[]}
    sid=str(d.get('id_sorteo','')); fecha=d.get('fecha_sorteo'); tipo=d.get('tipo_sorteo')
    if not re.fullmatch(r'\d{5,20}',sid): errores.append('Identificador inválido')
    if ruta.name != f'sorteo_{sid}.json': errores.append('Nombre de archivo e identificador no coinciden')
    try:
        fecha_dt=dt.date.fromisoformat(fecha)
        if fecha_dt>dt.datetime.now(dt.timezone.utc).date(): errores.append('Fecha futura')
        if tipo=='J' and fecha_dt.weekday()!=3: avisos.append('Jueves con día de semana distinto')
        if tipo=='S' and fecha_dt.weekday()!=5: avisos.append('Sábado con día de semana distinto')
    except (TypeError,ValueError): errores.append('Fecha inválida')
    if tipo not in ('J','S'): errores.append('Modalidad no ordinaria: revisión manual')
    principales=d.get('principales'); extracciones=d.get('extracciones')
    if not isinstance(principales,dict): errores.append('Premios principales ausentes'); principales={}
    if not isinstance(extracciones,dict): errores.append('Extracciones ausentes'); extracciones={}
    for k in ('primerPremio','segundoPremio'):
        item=principales.get(k)
        if not isinstance(item,dict): errores.append(k+' ausente'); continue
        if not re.fullmatch(r'\d{5}',str(item.get('numero',''))): errores.append(k+' número inválido')
        monto=item.get('premio_fuente')
        if not isinstance(monto,(int,float)) or isinstance(monto,bool) or monto<0: errores.append(k+' importe fuente inválido')
    cantidades={}
    for campo,ancho in CAMPOS.items():
        items=extracciones.get(campo)
        if not isinstance(items,list): errores.append(campo+' ausente'); continue
        cantidades[campo]=len(items); vistos=set()
        for n,item in enumerate(items):
            if not isinstance(item,dict): errores.append(f'{campo}[{n}] no es objeto'); continue
            numero=item.get('numero')
            if not isinstance(numero,str) or not re.fullmatch(r'\d{'+str(ancho)+r'}',numero): errores.append(f'{campo}[{n}] formato incorrecto')
            if numero in vistos: errores.append(f'{campo}[{n}] duplicado')
            vistos.add(numero)
            monto=item.get('premio_fuente')
            if not isinstance(monto,(int,float)) or isinstance(monto,bool) or monto<0: errores.append(f'{campo}[{n}] importe fuente inválido')
    if tipo=='J' and all(k in cantidades for k in CAMPOS):
        observado=[cantidades[k] for k in ('extraccionesDeCuatroCifras','extraccionesDeTresCifras','extraccionesDeDosCifras','reintegros')]
        if observado!=[4,7,9,3]: avisos.append('Cantidades distintas del jueves de referencia: requiere contraste oficial')
    if not cantidades.get('reintegros',0): errores.append('Sin reintegros')
    if d.get('publicable') is not False: errores.append('Marca publicable no bloqueada')
    validacion=d.get('validacion')
    if not isinstance(validacion,dict) or validacion.get('estructura_minima_completa') is not True: errores.append('Validación de captura ausente o incompleta')
    avisos.append('Importes fuente sin unidad monetaria verificada; motor de premios NO habilitado')
    avisos.append('Aproximaciones, centenas, terminaciones, acumulación y premios especiales NO validados')
    return {'archivo':str(ruta),'id_sorteo':sid,'fecha_sorteo':fecha,'tipo_sorteo':tipo,'cantidades':cantidades,'valido':not errores,'errores':errores,'avisos':avisos}

def main():
    p=argparse.ArgumentParser(); p.add_argument('--historico',default='datos/loteria_nacional/historico'); p.add_argument('--informe',default='informes/lnac_088/auditoria.json'); a=p.parse_args()
    archivos=sorted(pathlib.Path(a.historico).glob('sorteo_*.json'))
    registros=[auditar(x) for x in archivos]
    ids=[r.get('id_sorteo') for r in registros if r.get('id_sorteo')]
    if len(ids)!=len(set(ids)):
        for r in registros: r['errores'].append('Identificador repetido en histórico'); r['valido']=False
    informe={'version':'0.88','momento_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'total_archivos':len(archivos),'validos_estructuralmente':sum(r['valido'] for r in registros),'incidencias':sum(len(r['errores']) for r in registros),'publicacion_premios':False,'calculo_premios_habilitado':False,'estado':'sin_archivos' if not archivos else ('revision_necesaria' if any(not r['valido'] for r in registros) else 'auditoria_estructural_superada'),'sorteos':registros}
    salida=pathlib.Path(a.informe);salida.parent.mkdir(parents=True,exist_ok=True);salida.write_text(json.dumps(informe,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(informe,ensure_ascii=False,indent=2))
    return 1 if not archivos or any(not r['valido'] for r in registros) else 0
if __name__=='__main__':sys.exit(main())
