#!/usr/bin/env python3
"""LotoScan 1.18: auditoría conservadora frente a JSON externo independiente.
No transforma filas PDF en premio definitivo. Nunca habilita publicación.
Requiere scripts/auditar_integracion_navidad_117.py (lector geométrico previo).
"""
import argparse, collections, datetime, hashlib, importlib.util, json, pathlib, sys, urllib.request

def guardar(path, obj):
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')

def oficial_desde(datos):
    """Solo esquemas explícitos: {premios_por_numero:{'00000':20,...}}
    o {premios:[{numero:'00000',euros_decimo:20},...]}. Nunca infiere ceros.
    """
    if not isinstance(datos,dict):raise ValueError('JSON oficial debe ser objeto')
    full='premios_por_numero' in datos
    if full:
        origen=datos['premios_por_numero']
        if not isinstance(origen,dict):raise ValueError('premios_por_numero debe ser objeto')
        registros=list(origen.items())
    else:
        if not isinstance(datos.get('premios'),list):raise ValueError('Esquema no reconocido: proporcionar premios_por_numero o premios')
        registros=[(x['numero'],x['euros_decimo']) for x in datos['premios']]
    tabla={}
    for n,valor in registros:
        n=str(n)
        if len(n)!=5 or not n.isdigit():raise ValueError('Número inválido: '+n)
        if n in tabla:raise ValueError('Número duplicado: '+n)
        if isinstance(valor,bool) or not isinstance(valor,(int,float)) or valor<0 or round(valor,2)!=valor:
            raise ValueError('Importe no válido: '+n)
        tabla[n]=round(float(valor),2)
    cobertura_completa=full and len(tabla)==100000
    if full and not cobertura_completa:raise ValueError('premios_por_numero requiere exactamente 100000 entradas, incluidos los no premiados con 0')
    return tabla,cobertura_completa

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--anio',type=int,required=True)
    p.add_argument('--pdf');p.add_argument('--pdf-url')
    p.add_argument('--json-oficial');p.add_argument('--json-url')
    p.add_argument('--salida',default='salida_118')
    a=p.parse_args();out=pathlib.Path(a.salida);out.mkdir(parents=True,exist_ok=True)
    incidencias=[]; auditoria=[]; comprobaciones=[]
    # Reutiliza lector probado 1.17, sin duplicar millones de caracteres embebidos.
    path=pathlib.Path(__file__).resolve().parent/'auditar_integracion_navidad_117.py'
    if not path.exists():raise SystemExit('Falta scripts/auditar_integracion_navidad_117.py: subir primero la versión 1.17')
    spec=importlib.util.spec_from_file_location('lotoscan_117',path);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    class Args:pass
    x=Args();x.historico=a.anio if a.anio in (2024,2025) and not (a.pdf or a.pdf_url) else None
    x.pdf=a.pdf;x.url=a.pdf_url
    if x.historico is None and not (a.pdf or a.pdf_url):raise SystemExit('Año nuevo: proporcionar PDF oficial por ruta o URL')
    pdf=mod.load(x);filas,paginas=mod.scan(pdf)
    geometria=collections.defaultdict(list);cats=collections.Counter()
    for f in filas:
        n=f['numero'];mark=f['marca'];importe=f['importe_euros_billete']
        if f['estado']!='asociacion_univoca' or importe is None or importe%10:
            incidencias.append({'tipo':'FILA_NO_CONCILIABLE','fila':f});continue
        categoria={'t':'terminacion','c':'centena','a':'aproximacion',None:'pedrea_candidata'}.get(mark)
        if categoria is None:incidencias.append({'tipo':'MARCA_DESCONOCIDA','fila':f});continue
        comp={'categoria':categoria,'euros_decimo_pdf':importe/10,'pagina':f['pagina'],'columna':f['columna'],'y':f['y']}
        geometria[n].append(comp);cats[categoria]+=1
    tabla={};cobertura=False;hash_json=None;estado_fuente='NO_APORTADA'
    if a.json_oficial or a.json_url:
        if a.json_oficial and a.json_url:raise SystemExit('Usar solo una fuente JSON')
        if a.json_oficial:raw=pathlib.Path(a.json_oficial).read_bytes();estado_fuente='ARCHIVO_EXTERNO'
        else:
            if not a.json_url.startswith('https://'):raise SystemExit('JSON URL debe ser HTTPS')
            with urllib.request.urlopen(urllib.request.Request(a.json_url,headers={'User-Agent':'LotoScan-auditoria/1.18'}),timeout=30) as r:raw=r.read(30_000_001)
            if len(raw)>30_000_000:raise SystemExit('JSON supera 30 MB')
            estado_fuente='URL_EXTERNA'
        hash_json=hashlib.sha256(raw).hexdigest()
        tabla,cobertura=oficial_desde(json.loads(raw))
    else:incidencias.append({'tipo':'SIN_JSON_OFICIAL','detalle':'No es posible contrastar importes independientes sin aportar JSON oficial normalizado.'})
    # Comparación por número, NO equivalencia: PDF ordinario excluye premios mayores y reglas derivadas.
    # Se compara una cota inferior solo cuando el origen externo representa un total por décimo.
    diferencias_cota=0
    for n in (f'{i:05d}' for i in range(100000)):
        comps=geometria.get(n,[]);base=round(sum(c['euros_decimo_pdf'] for c in comps),2)
        oficial=tabla.get(n)
        if oficial is not None and oficial+0.001<base:
            diferencias_cota+=1
            auditoria.append({'numero':n,'euros_decimo_oficial':oficial,'euros_decimo_filas_pdf':base,'componentes_pdf':comps,'estado':'INCOMPATIBLE_COTA_INFERIOR'})
        elif comps or oficial is not None:
            auditoria.append({'numero':n,'euros_decimo_oficial':oficial,'euros_decimo_filas_pdf':base,'componentes_pdf':comps,
              'estado':'PENDIENTE_REGLAS_Y_PREMIOS_MAYORES' if oficial is not None else 'SIN_REFERENCIA_OFICIAL'})
    # Invariantes y trazabilidad, no certificación económica.
    if len(filas)!=sum(cats.values())+sum(i['tipo']=='FILA_NO_CONCILIABLE' or i['tipo']=='MARCA_DESCONOCIDA' for i in incidencias):
        incidencias.append({'tipo':'RECUENTO_INCONSISTENTE'})
    comprobaciones=[{'control':'filas_pdf','valor':len(filas)}, {'control':'categorias','valor':dict(cats)},
      {'control':'numeros_oficiales','valor':len(tabla)}, {'control':'cobertura_completa_oficial','valor':cobertura},
      {'control':'incompatibilidades_cota_inferior','valor':diferencias_cota}]
    reporte={'version':'1.18','anio':a.anio,'fecha_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
      'sha256_pdf':hashlib.sha256(pdf).hexdigest(),'sha256_json_externo':hash_json,'fuente_json':estado_fuente,
      'esquema_esperado':'JSON normalizado independiente: premios_por_numero (100000 números) o premios (lista parcial)',
      'paginas':paginas,'comprobaciones':comprobaciones,'incidencias':len(incidencias),
      'advertencia':'El JSON externo NO se autentica como oficial por su contenido. Es imprescindible verificar su procedencia SELAE.',
      'limites':['PDF ordinario no incluye todos los premios mayores, reintegros y reglas derivadas',
                'Una cota inferior compatible no demuestra igualdad del premio final',
                'No se ha certificado acumulación ni completitud del motor de premios'],
      'motor_validado':False,'publicable':False}
    guardar(out/f'informe_{a.anio}_118.json',reporte)
    guardar(out/f'auditoria_{a.anio}_118.json',auditoria)
    guardar(out/f'incidencias_{a.anio}_118.json',incidencias)
    guardar(out/f'controles_{a.anio}_118.json',comprobaciones)
    print(json.dumps({'anio':a.anio,'filas':len(filas),'referencias_oficiales':len(tabla),'incompatibilidades_cota':diferencias_cota,'motor_validado':False,'publicable':False},ensure_ascii=False))

if __name__=='__main__':main()
