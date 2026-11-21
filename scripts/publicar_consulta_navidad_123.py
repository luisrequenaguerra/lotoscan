#!/usr/bin/env python3
"""LotoScan 1.23: índice de consulta manual, SIN certificar pagos.
Consume la tabla JSONL producida por 1.22; no modifica el cálculo histórico.
"""
import argparse,collections,json,pathlib,re

def ejecutar(anio,entrada,salida,numero=None):
    if numero and not re.fullmatch(r'\d{5}',numero): raise ValueError('El número debe tener cinco cifras')
    destino=pathlib.Path(salida);destino.mkdir(parents=True,exist_ok=True)
    origen=pathlib.Path(entrada)
    tabla=origen/f'tabla_{anio}_122.jsonl'
    informe=json.loads((origen/f'informe_{anio}_122.json').read_text(encoding='utf8'))
    incidencias=json.loads((origen/f'incidencias_{anio}_122.json').read_text(encoding='utf8'))
    anclas=json.loads((origen/f'anclas_{anio}_122.json').read_text(encoding='utf8'))
    if informe['numeros']!=100000:raise RuntimeError('Tabla de origen incompleta')
    clasificaciones=[]
    for a in anclas:
        if a['clasificacion']=='PREMIO_MAYOR_CONFIRMADO_JSON':
            tipo='PREMIO_MAYOR_RESPALDADO_POR_JSON'
        elif a['numero'] in ('12500','20000'):
            tipo='TOKEN_NUMERICO_AUXILIAR_CANDIDATO_A_IMPORTE_NO_USAR_COMO_PREMIO'
        else:
            tipo='TOKEN_AUXILIAR_SIN_CLASIFICACION'
        clasificaciones.append({'token':a['token_original'],'pagina':a['pagina'],'x':a['x'],'y':a['y'],'tipo':tipo})
    vistos=set();cont=collections.Counter();seleccion=None;premiados=0
    with tabla.open(encoding='utf8') as fin,(destino/f'consulta_{anio}_123.jsonl').open('w',encoding='utf8') as fout:
        for linea in fin:
            r=json.loads(linea);n=r['numero']
            if n in vistos:raise RuntimeError('Número duplicado '+n)
            vistos.add(n)
            mayor=bool(r['premios_mayores_json']);valor=r['euros_decimo_calculados']
            if not isinstance(valor,(int,float)) or valor<0:raise RuntimeError('Importe inválido '+n)
            if mayor:estado='PREMIO_MAYOR_PENDIENTE_ACUMULACIONES'
            elif valor>0:estado='PREMIO_ORDINARIO_EXPERIMENTAL'
            else:estado='SIN_PREMIO_CALCULADO_NO_CERTIFICADO'
            if valor:premiados+=1
            cont[estado]+=1
            registro={'numero':n,'euros_decimo_estimados':valor,'estado':estado,
                'componentes_pdf':r['componentes_pdf'],'premios_mayores_json':r['premios_mayores_json'],
                'reintegro_derivado_euros':r['reintegro_derivado_euros'],
                'importe_certificado':False,'publicable_como_premio_definitivo':False,
                'fuente':'PDF y JSON SELAE','anio':anio}
            fout.write(json.dumps(registro,ensure_ascii=False,separators=(',',':'))+'\n')
            if n==numero:seleccion=registro
    if len(vistos)!=100000 or '00000' not in vistos or '99999' not in vistos:raise RuntimeError('Cobertura de números incompleta')
    resumen={'version':'1.23','anio':anio,'numeros':len(vistos),'numeros_con_importe_positivo_experimental':premiados,
       'estados':dict(cont),'sha256_pdf':informe['sha256_pdf'],'anclas_clasificadas':len(clasificaciones),
       'incidencias_heredadas':incidencias,'motor_validado':False,'publicable':False,
       'nota':'Consulta manual funcional de importes estimados; no es un resultado cobrable certificado. No se añaden premios por tokens auxiliares.'}
    (destino/f'informe_{anio}_123.json').write_text(json.dumps(resumen,ensure_ascii=False,indent=2),encoding='utf8')
    (destino/f'anclas_{anio}_123.json').write_text(json.dumps(clasificaciones,ensure_ascii=False,indent=2),encoding='utf8')
    if numero:
        (destino/f'numero_{numero}_{anio}_123.json').write_text(json.dumps(seleccion,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(resumen,ensure_ascii=False,indent=2))
    return resumen

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--anio',type=int,required=True);p.add_argument('--entrada',required=True);p.add_argument('--salida',default='salida_123');p.add_argument('--numero');a=p.parse_args()
    ejecutar(a.anio,a.entrada,a.salida,a.numero)
