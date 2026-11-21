#!/usr/bin/env python3
"""LotoScan 0.95: contraste documental del sábado, NO certifica automáticamente premios."""
import datetime as dt
import hashlib
import importlib.util
import json
import pathlib
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

DRAW_ID='1328609092'
URL_JSON=f'https://www.loteriasyapuestas.es/servicios/resultados2?idsorteo={DRAW_ID}'
PDF_PATH='/f/loterias/documentos/Lotería Nacional/listas de premios/SM_LISTAOFICIAL.A2026.S092.pdf'
URL_PDF='https://www.loteriasyapuestas.es'+urllib.parse.quote(PDF_PATH,safe='/')
NUMBERS=['75409','38422','75408','75410','38421','38423','02004','00249','00006','00000','11111']
OUT=pathlib.Path('informes/lnac_095')

def get(url,accept,max_bytes):
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; LotoScan-verificacion/0.95)','Accept':accept})
    with urllib.request.urlopen(req,timeout=35) as response:
        raw=response.read(max_bytes+1)
        if len(raw)>max_bytes:raise ValueError('Respuesta demasiado grande')
        return raw,dict(response.headers),response.status

def load_engine():
    path=pathlib.Path('scripts/calcular_sabado_nacional_094.py')
    if not path.exists():return None,'Falta '+str(path)
    spec=importlib.util.spec_from_file_location('motor_094',path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module,None

def extract_context(text,number):
    # Los listados pueden tener varias columnas; se conservan líneas completas y su contexto.
    lines=text.splitlines();matches=[]
    for i,line in enumerate(lines):
        if re.search(r'(?<!\d)'+re.escape(number)+r'(?!\d)',line):
            matches.append({'linea':i+1,'texto':line.strip()[:320],
                            'anterior':lines[i-1].strip()[:240] if i else '',
                            'siguiente':lines[i+1].strip()[:240] if i+1<len(lines) else ''})
        if len(matches)>=8:break
    return matches

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    report={'version':'0.95','fecha_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
      'objetivo':'Contrastar las cifras experimentales de 0.94 contra la lista oficial del sábado 14/11/2026',
      'draw_id':DRAW_ID,'fuentes':{},'muestras':[], 'incidencias':[],
      'validacion_normativa_completa':False,'publicable':False,'historico_modificado':False,
      'advertencia':'La coincidencia de autopruebas no es validación independiente; las líneas del PDF requieren interpretación y comprobación.'}
    engine,error=load_engine()
    if error:report['incidencias'].append(error)
    data=None
    try:
        raw,headers,status=get(URL_JSON,'application/json',1_000_000)
        data=json.loads(raw.decode('utf-8-sig'))
        report['fuentes']['json']={'url':URL_JSON,'http':status,'sha256':hashlib.sha256(raw).hexdigest(),
                                   'id_recibido':str(data.get('drawIdSorteo'))}
        if str(data.get('drawIdSorteo'))!=DRAW_ID:raise ValueError('ID JSON diferente')
        if engine:
            issues=engine.validate(data)
            if issues:raise ValueError('JSON no compatible con motor 094: '+str(issues))
    except Exception as exc:
        report['incidencias'].append('No se pudo obtener/verificar JSON: '+str(exc)[:250]);data=None
    pdf_text=None
    try:
        raw,headers,status=get(URL_PDF,'application/pdf,*/*',20_000_000)
        if not raw.startswith(b'%PDF-'):raise ValueError('La respuesta no es PDF')
        pdf_file=OUT/'lista_oficial_sabado_20261114.pdf';pdf_file.write_bytes(raw)
        proc=subprocess.run(['pdftotext','-layout',str(pdf_file),str(OUT/'lista_oficial_sabado_20261114.txt')],
                            capture_output=True,text=True,timeout=30)
        if proc.returncode:raise RuntimeError('pdftotext: '+proc.stderr[:180])
        pdf_text=(OUT/'lista_oficial_sabado_20261114.txt').read_text(encoding='utf-8',errors='replace')
        report['fuentes']['pdf']={'url':URL_PDF,'http':status,'sha256':hashlib.sha256(raw).hexdigest(),
                                 'bytes':len(raw),'caracteres_texto':len(pdf_text)}
    except Exception as exc:report['incidencias'].append('PDF oficial no disponible/extraíble: '+str(exc)[:250])
    for number in NUMBERS:
        item={'numero':number,'resultado_094':None,'apariciones_pdf':None,'validado_con_pdf':False}
        if engine and data:
            try:
                result=engine.calculate(data,number)
                item['resultado_094']={'total_euros_hipotetico':result['total_euros_hipotetico'],
                                       'componentes':result['componentes']}
            except Exception as exc:item['error_motor']=str(exc)[:250]
        if pdf_text is not None:item['apariciones_pdf']=extract_context(pdf_text,number)
        report['muestras'].append(item)
    report['estado']='evidencia_para_revision' if pdf_text and data and engine else 'evidencia_incompleta'
    (OUT/'contraste_095.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'estado':report['estado'],'incidencias':report['incidencias'],
                      'muestras':len(report['muestras'])},ensure_ascii=False))
    # No fallar por bloqueo HTTP de SELAE: se entrega informe y trazabilidad.
    return 0

if __name__=='__main__':sys.exit(main())
