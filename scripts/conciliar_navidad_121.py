#!/usr/bin/env python3
"""LotoScan 1.21: conciliación explícita de premios mayores y reintegros.
No certifica la tabla completa: conserva bloqueo hasta cerrar reglas y anclas.
Requiere scripts de las versiones 1.17, 1.19 y 1.20.
"""
import argparse,collections,hashlib,json,pathlib,re,sys,tempfile
from calcular_navidad_120 import calcular
from consultar_navidad_119 import leer_json,premios_mayores
BASE={'primer_premio':400000,'segundo_premio':125000,'tercer_premio':50000,'cuarto_premio':20000,'quinto_premio':6000}
CUOTAS={'primer_premio':1,'segundo_premio':1,'tercer_premio':1,'cuarto_premio':2,'quinto_premio':8}

def ejecutar(anio,pdf=None,json_path=None,numero=None,salida='salida_121'):
    out=pathlib.Path(salida);out.mkdir(parents=True,exist_ok=True)
    j=leer_json(anio,json_path);mayores=premios_mayores(j)
    primero=[n for n,v in mayores.items() for p in v if p['categoria']=='primer_premio']
    if len(primero)!=1:raise ValueError('No hay un primer premio único')
    digito=primero[0][-1]
    diagnosticos=[];errores=[];conteos=collections.Counter()
    for n,items in sorted(mayores.items()):
        for p in items:
            cat=p['categoria'];importe=p['euros_decimo_json'];base=BASE[cat]
            delta=round(importe-base,2);coincide=n.endswith(digito)
            # SELAE ha publicado históricamente tanto base como base+20.
            # Diferenciar el componente ya incluido sin duplicarlo.
            admisible=delta==0 or (delta==20 and coincide and cat!='primer_premio')
            if not admisible:errores.append({'tipo':'IMPORTE_MAYOR_INESPERADO','numero':n,'categoria':cat,'delta':delta})
            if delta==20 and coincide:estado='REINTEGRO_INCLUIDO_EN_JSON'
            elif coincide:estado='REINTEGRO_NO_DESGLOSADO_EN_JSON_NO_SUMAR'
            else:estado='PREMIO_BASE_JSON'
            conteos[cat]+=1
            diagnosticos.append({'numero':n,'categoria':cat,'euros_base_categoria':base,
              'euros_json':importe,'digito_reintegro':digito,'coincide_reintegro':coincide,
              'diferencia_json_menos_base':delta,'estado':estado,
              'euros_para_tabla':importe,'sumar_reintegro_adicional':False,
              'coherente_con_patron_historico':admisible})
    for cat,cantidad in CUOTAS.items():
        if conteos[cat]!=cantidad:errores.append({'tipo':'RECUENTO_MAYORES','categoria':cat,'obtenido':conteos[cat],'esperado':cantidad})
    with tempfile.TemporaryDirectory(prefix='lotoscan121_') as td:
        base_report=calcular(anio,pdf,json_path,numero,td)
        src=pathlib.Path(td)/f'tabla_{anio}_120.jsonl'
        tabla_path=out/f'tabla_{anio}_121.jsonl';conteo=0;pedreas=0;sin_premio=0
        with src.open(encoding='utf8') as fin,tabla_path.open('w',encoding='utf8') as fout:
            for linea in fin:
                r=json.loads(linea);n=r['numero'];conteo+=1
                comps=r['componentes_pdf'];pedreas+=sum(x['categoria']=='pedrea_candidata' for x in comps)
                if r['euros_decimo_calculados']==0:sin_premio+=1
                r['version']='1.21';r['importe_certificado']=False
                if n in mayores:
                    r['estado']='PREMIO_MAYOR_CONCILIADO_PATRON_JSON_PENDIENTE_REGLAS'
                    r['nota']='El importe mayor del JSON se conserva sin sumar reintegro otra vez.'
                else:
                    r['estado']='ORDINARIOS_Y_REINTEGRO_CALCULADOS_PENDIENTE_REGLAS'
                fout.write(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n')
        if conteo!=100000:errores.append({'tipo':'TABLA_INCOMPLETA','conteo':conteo})
        if pedreas!=1794 and anio in (2024,2025):errores.append({'tipo':'PEDREAS_INESPERADAS','conteo':pedreas})
        if base_report['incidencias']:errores.append({'tipo':'INCIDENCIAS_120','cantidad':base_report['incidencias']})
        if numero is not None:
            if not re.fullmatch(r'\d{5}',numero):raise ValueError('Número de cinco cifras obligatorio')
            with tabla_path.open(encoding='utf8') as f:
                for linea in f:
                    r=json.loads(linea)
                    if r['numero']==numero:
                        (out/f'consulta_{numero}_{anio}_121.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf8');break
    informe={'version':'1.21','anio':anio,'origen':'SELAE PDF y JSON','sha256_pdf':base_report['sha256_pdf'],
      'numeros':conteo,'pedreas_candidatas':pedreas,'numeros_sin_premio_calculado':sin_premio,
      'premios_mayores':len(diagnosticos),'premios_mayores_con_reintegro_incluido':sum(x['estado']=='REINTEGRO_INCLUIDO_EN_JSON' for x in diagnosticos),
      'premios_mayores_con_terminacion_del_gordo_sin_reintegro_adicional':sum(x['estado']=='REINTEGRO_NO_DESGLOSADO_EN_JSON_NO_SUMAR' for x in diagnosticos),
      'errores_control':len(errores),'incidencias_extraccion':base_report['incidencias'],
      'motor_validado':False,'publicable':False,
      'pendientes':['Confirmar compatibilidad y acumulación de categorías de premios en todos los supuestos.',
        'Resolver documentalmente las 17 anclas excluidas del lector ordinario.',
        'Comprobar integridad del documento del nuevo sorteo antes de habilitar publicación.',
        'El patrón de premios mayores histórico no certifica automáticamente sorteos futuros.']}
    for nombre,contenido in [(f'informe_{anio}_121.json',informe),(f'premios_mayores_{anio}_121.json',diagnosticos),(f'incidencias_{anio}_121.json',errores)]:
        (out/nombre).write_text(json.dumps(contenido,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(informe,ensure_ascii=False,indent=2));return informe

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--anio',type=int,required=True);p.add_argument('--pdf');p.add_argument('--json');p.add_argument('--numero');p.add_argument('--salida',default='salida_121');a=p.parse_args()
    if a.anio not in (2024,2025) and not(a.pdf and a.json):p.error('Sorteos nuevos requieren PDF y JSON oficiales')
    ejecutar(a.anio,a.pdf,a.json,a.numero,a.salida)
