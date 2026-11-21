#!/usr/bin/env python3
"""LotoScan 1.20: importes calculados por decimo, con bloqueo de publicacion.
Requiere scripts/consultar_navidad_119.py y scripts/auditar_integracion_navidad_117.py.
Los premios mayores JSON se tratan como importes autoritativos del numero, sin
sumar de nuevo componentes ordinarios o reintegros: posible solapamiento.
"""
import argparse,collections,hashlib,importlib.util,json,pathlib,re

def modulo(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod

def calcular(anio,pdf_path=None,json_path=None,numero=None,salida='salida_120'):
    root=pathlib.Path(__file__).resolve().parent
    prev=modulo(root/'consultar_navidad_119.py','consulta119')
    lector=modulo(root/'auditar_integracion_navidad_117.py','lector117')
    j=prev.leer_json(anio,json_path)
    if str(anio) not in str(j.get('fechaSorteo',''))[:4] or 'NAVIDAD' not in str(j.get('nombreDelSorteo','')).upper():
        raise ValueError('El JSON no corresponde a Navidad del año indicado')
    mayores=prev.premios_mayores(j)
    class A:pass
    a=A();a.historico=anio if not pdf_path else None;a.pdf=pdf_path;a.url=None
    pdf=lector.load(a);filas,paginas=lector.scan(pdf)
    componentes=collections.defaultdict(list); incidencias=[];categorias=collections.Counter()
    for r in filas:
        n=r['numero'];importe=r['importe_euros_billete'];marca=r['marca']
        if r['estado']!='asociacion_univoca' or importe is None or importe%10:
            incidencias.append({'tipo':'FILA_AMBIGUA','fila':r});continue
        cat={'t':'terminacion','c':'centena','a':'aproximacion',None:'pedrea_candidata'}.get(marca)
        if cat is None:
            incidencias.append({'tipo':'MARCA_DESCONOCIDA','fila':r});continue
        componentes[n].append({'categoria':cat,'euros_decimo':importe//10,'pagina':r['pagina'],'columna':r['columna'],'y':r['y']})
        categorias[cat]+=1
    if any(p.get('advertencias') for p in paginas):incidencias.append({'tipo':'ADVERTENCIAS_GEOMETRIA'})
    if anio in (2024,2025) and len(filas)!=5292:incidencias.append({'tipo':'RECUENTO_HISTORICO_INESPERADO','valor':len(filas)})
    primer=[n for n,items in mayores.items() if any(v['categoria']=='primer_premio' for v in items)]
    if len(primer)!=1:raise ValueError('Primer premio no unico')
    reintegro=primer[0][-1]
    out=pathlib.Path(salida);out.mkdir(parents=True,exist_ok=True)
    estados=collections.Counter();casos_solapados=[];tabla=[]
    for i in range(100000):
        n=f'{i:05d}';ord_=componentes.get(n,[]);maj=mayores.get(n,[])
        subtotal=sum(x['euros_decimo'] for x in ord_)
        r=20 if n[-1]==reintegro else 0
        if maj:
            # Premio JSON: importe oficial por numero, ya puede incluir acumulaciones.
            # No añadir automaticamente ordinarios ni reintegro.
            total=sum(x['euros_decimo_json'] for x in maj)
            estado='MAYOR_JSON_SIN_SUMAR_SOLAPAMIENTOS'
            if ord_ or r:
                casos_solapados.append({'numero':n,'importe_json':total,'subtotal_pdf_ordinario':subtotal,'reintegro_potencial':r})
        else:
            total=subtotal+r
            estado='CALCULO_ORDINARIO_MAS_REINTEGRO'
        estados[estado]+=1
        tabla.append({'numero':n,'euros_decimo_calculados':round(total,2),'estado':estado,
                      'componentes_pdf':ord_,'premios_mayores_json':maj,
                      'reintegro_derivado_euros':r,'subtotal_pdf_euros':subtotal,
                      'importe_certificado':False})
    # Un importe calculado no implica importe cobrable certificado.
    report={'version':'1.20','anio':anio,'sorteo':j.get('nombreDelSorteo'),
      'sha256_pdf':hashlib.sha256(pdf).hexdigest(),'numeros':len(tabla),
      'filas_pdf':len(filas),'categorias':dict(categorias),'premios_mayores':sum(map(len,mayores.values())),
      'digito_reintegro':reintegro,'estados':dict(estados),
      'casos_solapamiento_mayores':len(casos_solapados),'incidencias':len(incidencias),
      'numeros_con_importe_calculado':len(tabla),'motor_validado':False,'publicable':False,
      'advertencias':['Importes calculados experimentalmente; no publicar como premios definitivos.',
        'Para numeros con premio mayor se usa el importe del JSON sin añadir reintegros o PDF ordinario; revisar reglas de solapamiento.',
        'No se han conciliado de forma independiente las 17 anclas excluidas ni todas las reglas oficiales de acumulacion.',
        'No se garantiza que los importes de premios mayores del JSON sean totales finales para todos los supuestos.']}
    (out/f'informe_{anio}_120.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    (out/f'incidencias_{anio}_120.json').write_text(json.dumps(incidencias,ensure_ascii=False,indent=2),encoding='utf8')
    (out/f'solapamientos_{anio}_120.json').write_text(json.dumps(casos_solapados,ensure_ascii=False,indent=2),encoding='utf8')
    with (out/f'tabla_{anio}_120.jsonl').open('w',encoding='utf8') as f:
        for r in tabla:f.write(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n')
    if numero is not None:
        if not re.fullmatch(r'\d{5}',numero):raise ValueError('Numero debe tener cinco cifras')
        (out/f'consulta_{numero}_{anio}_120.json').write_text(json.dumps(tabla[int(numero)],ensure_ascii=False,indent=2),encoding='utf8')
        print(json.dumps(tabla[int(numero)],ensure_ascii=False,indent=2))
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--anio',type=int,required=True)
    p.add_argument('--pdf');p.add_argument('--json');p.add_argument('--numero');p.add_argument('--salida',default='salida_120')
    a=p.parse_args()
    if a.anio not in (2024,2025) and not (a.pdf and a.json):p.error('Años nuevos: --pdf y --json SELAE obligatorios')
    calcular(a.anio,a.pdf,a.json,a.numero,a.salida)
