#!/usr/bin/env python3
"""LotoScan 0.87S: revalidación independiente de 2 listas oficiales históricas.
No es extractor genérico, no acredita billetes ni publica resultados.
"""
import ast, datetime, hashlib, io, json, re, sys, urllib.request, zipfile
from pathlib import Path
from pypdf import PdfReader

BASE=Path(__file__).resolve().parent
OUT=Path('informe_nacional_087s.json')
URL='https://www.loteriasyapuestas.es/f/loterias/documentos/Lotería Nacional/listas de premios/SM_LISTAOFICIAL.A2026.S{:03d}.pdf'

def source_cases():
    p=BASE/'validar_loteria_nacional_086i.py'
    if not p.exists(): raise RuntimeError('Falta scripts/validar_loteria_nacional_086i.py (versión anterior)')
    tree=ast.parse(p.read_text(encoding='utf-8'))
    for node in tree.body:
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='CASES' for t in node.targets):
            return ast.literal_eval(node.value)
    raise RuntimeError('No se encontraron las configuraciones históricas CASES')

def amount(number,case):
    if number==case['first']:return case['firstamt']
    if number==case['second']:return case['secondamt']
    code=f'{number:05d}'
    total=sum(vals.get(code[-length:],0) for length,vals in case['ending'].items())
    for rank in ('first','second'):
        winner=case[rank]
        if number in ((winner-1)%100000,(winner+1)%100000):total+=case['approx1' if rank=='first' else 'approx2']
        if number//100==winner//100:total+=case['hundred1' if rank=='first' else 'hundred2']
    return total

def fetch_pdf(url):
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 LotoScanResearch/0.87S'})
    with urllib.request.urlopen(req,timeout=35) as response: data=response.read(5000000)
    if not data.startswith(b'%PDF-'):raise ValueError('Respuesta no es PDF')
    reader=PdfReader(io.BytesIO(data))
    content='\n'.join(page.extract_text(extraction_mode='layout') or '' for page in reader.pages)
    if len(content)<1000:raise ValueError('Extracción de texto insuficiente')
    return content,hashlib.sha256(data).hexdigest()

def audit(case,number):
    url=URL.format(number)
    txt,sha=fetch_pdf(url)
    pairs=re.findall(r'(?<!\d)(\d{5})\.{3,}\s*([\d.]+)',txt)
    reference={int(n):int(value.replace('.','')) for n,value in pairs}
    computed=[amount(i,case) for i in range(100000)]
    mismatches=[{'numero':f'{n:05d}','pdf':v,'calculado':computed[n]} for n,v in sorted(reference.items()) if computed[n]!=v]
    total=sum(computed)
    issues=[]
    if len(pairs)!=200 or len(reference)!=200:issues.append('No se han recuperado 200 filas únicas de importes acumulados')
    if mismatches:issues.append('Diferencias en importes acumulados del PDF')
    if total!=case['per_series']:issues.append('Total por serie distinto del declarado')
    if sum(case['awards'])!=case['count']:issues.append('Recuento de categorías no coincide')
    if reference.get(case['first'])!=case['firstamt'] or reference.get(case['second'])!=case['secondamt']:
        issues.append('Premios principales no coinciden con tabla oficial')
    # Esta verificación es histórica: reglas pretranscritas, NO extracción autónoma de reglas.
    return {'fecha':case['date'],'url_pdf':url,'sha256_pdf':sha,
      'filas_pdf':len(pairs),'filas_unicas':len(reference),'numeros_calculados':len(computed),
      'discrepancias':len(mismatches),'ejemplos_discrepancias':mismatches[:12],
      'importe_por_serie_calculado':total,'importe_por_serie_esperado':case['per_series'],
      'numeros_con_premio':sum(x>0 for x in computed),'ejemplos':{
        f'{i:05d}':{'euros_billete':computed[i],'euros_decimo':computed[i]/10}
        for i in [0,case['first'],case['second'],99999]},
      'incidencias':issues,'validado_historico':not issues,'publicable':False}

def main():
    report={'version':'0.87S','objetivo':'Revalidar listas oficiales acumuladas de dos sorteos históricos (no extracción general)',
      'metodologia':'100000 números calculados por reglas históricas pretranscritas y contrastados con 200 filas acumuladas PDF y total por serie',
      'fuente_reglas':'scripts/validar_loteria_nacional_086i.py','resultados':[],
      'historico_modificado':False,'publicables':0,'limitaciones':[
       'Las reglas históricas fueron transcritas; no se extraen automáticamente todas las categorías de PDF',
       'Solo se comprueban sorteos de 12 y 14 de noviembre de 2026',
       'No verifica serie/fracción ni autentica décimos; no sirve aún para sorteos nuevos',
       'El PDF contiene lista acumulada, no una lista exhaustiva de extracciones individuales']}
    try:
        cases=source_cases()
        for case,n in zip(cases,[91,92]):
            try: result=audit(case,n)
            except Exception as exc:result={'fecha':case['date'],'validado_historico':False,'incidencias':[str(exc)],'publicable':False}
            report['resultados'].append(result)
        report['aprobados']=sum(x['validado_historico'] for x in report['resultados'])
        report['fallidos']=len(report['resultados'])-report['aprobados']
    except Exception as exc:
        report['error_preparacion']=str(exc);report['aprobados']=0;report['fallidos']=1
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'version':'0.87S','aprobados':report['aprobados'],'fallidos':report['fallidos']},ensure_ascii=False))
    return 0 if report['fallidos']==0 else 1
if __name__=='__main__':sys.exit(main())
