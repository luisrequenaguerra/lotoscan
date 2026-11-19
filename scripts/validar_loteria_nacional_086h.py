#!/usr/bin/env python3
"""LotoScan 0.86H: validación estricta de Lotería Nacional, solo lectura.
Usa los 4 PDF históricos oficiales de 0.85M. Nunca publica premios.
"""
import datetime as dt
import importlib.util
import json
import re
from io import BytesIO
from pathlib import Path
from pypdf import PdfReader

BASE=Path(__file__).resolve().parent
SPEC=importlib.util.spec_from_file_location('selae085m', BASE/'probar_notas_selae_085m.py')
if not SPEC.origin or not Path(SPEC.origin).exists():
    raise SystemExit('Falta scripts/probar_notas_selae_085m.py')
OLD=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(OLD)
PAIR=re.compile(r'(?<!\d)(\d{5})\.{3,}\s*(\d[\d.]*)')
TERM=re.compile(r'(?<!\d)(\d{1,4})\.{3,}\s*(\d[\d.]*)')
MONTHS=dict(zip('enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre'.split(),range(1,13)))

def fecha(text):
    m=re.search(r'(\d{1,2})\s+de\s+('+ '|'.join(MONTHS)+r')\s+de\s+(20\d{2})',text,re.I)
    if m:return dt.date(int(m[3]),MONTHS[m[2].lower()],int(m[1])).isoformat()
    m=re.search(r'FECHA\s*:\s*(\d{1,2})/(\d{1,2})/(\d{2,4})',text,re.I)
    if m:
        y=int(m[3]);return dt.date(y+2000 if y<100 else y,int(m[2]),int(m[1])).isoformat()
    return None

def read_pdf(url):
    meta,raw=OLD.fetch(url)
    if meta.get('http')!=200 or not raw.startswith(b'%PDF-'):raise ValueError('Descarga PDF inválida: '+str(meta))
    pdf=PdfReader(BytesIO(raw))
    if pdf.is_encrypted or not pdf.pages:raise ValueError('PDF ilegible')
    return '\n'.join(p.extract_text(extraction_mode='layout') or '' for p in pdf.pages)

def major(text):
    d={'fecha':fecha(text),'premios':{},'reintegros':None}
    for title,key in [('PRIMER PREMIO','primero'),('SEGUNDO PREMIO','segundo')]:
        m=re.search(title+r'\s+PREMIO DE\s+([\d.]+)\s+EUROS AL N[ÚU]MERO\s+([\d.]+)',text,re.I)
        if m:d['premios'][key]={'numero':m[2].replace('.','').zfill(5),'importe_billete':int(m[1].replace('.',''))}
    m=re.search(r'REINTEGROS\s+([0-9])\s+([0-9])\s+([0-9])',text,re.I)
    if m:d['reintegros']=[int(x) for x in m.groups()]
    return d

def list_data(text):
    # Solo la tabla acumulada inicial, no las instrucciones ni la segunda página.
    table=text.split('ESTE SORTEO PONE EN JUEGO',1)[0]
    numbers={};conflicts=[]
    for m in PAIR.finditer(table):
        n,amount=m[1],int(m[2].replace('.',''))
        if n in numbers and numbers[n]!=amount:conflicts.append(n)
        numbers[n]=amount
    # Las terminaciones son cantidades acumuladas, no componentes sumables.
    terms={};term_conflicts=[]
    for m in TERM.finditer(table):
        n=m[1]
        if len(n)==5:continue
        amount=int(m[2].replace('.',''))
        if n in terms and terms[n]!=amount:term_conflicts.append(n)
        terms[n]=amount
    m=re.search(r'Esta lista comprende los\s+([\d.]+)\s+premios adjudicados para cada serie',text,re.I)
    count=int(m[1].replace('.','')) if m else None
    m=re.search(r'En el conjunto de las\s+(\d+)\s+series.*?por un importe de\s+([\d.]+)\s+euros',text,re.I|re.S)
    series=int(m[1]) if m else None
    total=int(m[2].replace('.','')) if m else None
    return {'fecha':fecha(text),'numeros':numbers,'terminaciones':terms,'conflictos_numeros':conflicts,
            'conflictos_terminaciones':term_conflicts,'premios_declarados_por_serie':count,
            'series':series,'importe_total_declarado_eur':total}

def award(number,ld):
    """Consulta acumulados de lista oficial: primero número completo, luego sufijo más largo.
    No se suman sufijos porque el PDF ya da el total acumulado.
    """
    n=str(number).zfill(5)
    if not re.fullmatch(r'\d{5}',n):raise ValueError('Número debe tener cinco cifras')
    if n in ld['numeros']:return {'importe_billete':ld['numeros'][n],'criterio':'numero_completo','referencia':n}
    for size in (4,3,2,1):
        suffix=n[-size:]
        if suffix in ld['terminaciones']:
            return {'importe_billete':ld['terminaciones'][suffix],'criterio':f'terminacion_{size}','referencia':suffix}
    return {'importe_billete':None,'criterio':'no_determinado','referencia':None}

def main():
    if len(OLD.SEED_PDFS)<9:raise ValueError('Lista de PDF históricos incompleta')
    output=Path('diagnostico_pdf_086h');output.mkdir(exist_ok=True)
    report={'version':'0.86H','fuente':'PDF SELAE históricos','solo_lectura':True,'publicable':False,'sorteos':[]}
    for i,j in ((5,6),(7,8)):
        item={'documentos':[i+1,j+1],'errores':[],'validado_para_comprobar_decimos':False}
        try:
            list_text=read_pdf(OLD.SEED_PDFS[i]);major_text=read_pdf(OLD.SEED_PDFS[j])
            (output/f'{i+1:02d}_lista.txt').write_text(list_text,encoding='utf-8')
            (output/f'{j+1:02d}_mayores.txt').write_text(major_text,encoding='utf-8')
            ld=list_data(list_text);md=major(major_text)
            item['fecha']=ld['fecha'];item['numeros_completos']=len(ld['numeros'])
            item['terminaciones_recuperadas']=len(ld['terminaciones'])
            item['terminaciones_por_longitud']={str(k):sum(len(t)==k for t in ld['terminaciones']) for k in (4,3,2,1)}
            item['premios_declarados_por_serie']=ld['premios_declarados_por_serie']
            item['importe_total_declarado_eur']=ld['importe_total_declarado_eur']
            item['series']=ld['series'];item['premios_mayores']=md['premios'];item['reintegros']=md['reintegros']
            if ld['fecha']!=md['fecha'] or not ld['fecha']:item['errores'].append('Fechas no coinciden')
            if len(ld['numeros'])!=200:item['errores'].append('No hay exactamente 200 números completos')
            if ld['conflictos_numeros'] or ld['conflictos_terminaciones']:
                item['errores'].append('Valores contradictorios en el listado')
            for key in ('primero','segundo'):
                p=md['premios'].get(key)
                if not p:item['errores'].append(f'Falta premio {key}');continue
                if ld['numeros'].get(p['numero'])!=p['importe_billete']:
                    item['errores'].append(f'No coincide premio {key}')
            # Se exige que todos los reintegros estén entre las terminaciones.
            if not md['reintegros'] or any(str(x) not in ld['terminaciones'] for x in md['reintegros']):
                item['errores'].append('Reintegros incompletos en tabla de terminaciones')
            # La lista contiene acumulados; se prueba la consulta sobre las 200 filas impresas.
            mismatches=[]
            for n,amount in ld['numeros'].items():
                got=award(n,ld)['importe_billete']
                if got!=amount:mismatches.append(n)
            item['numeros_con_importe_contrastado']=len(ld['numeros'])-len(mismatches)
            if mismatches:item['errores'].append('Consulta inconsistente con tabla de números')
            # No basta contrastar 200 filas: se requiere validar el catálogo completo
            # de terminaciones y el total del sorteo antes de declarar "sin premio".
            item['validaciones_pendientes']=[
                'Verificar exhaustividad y alineación de todas las terminaciones multicolumna',
                'Reconciliar 100.000 números con el importe total oficial por serie',
                'Verificar el recuento oficial de premios y las excepciones de acumulación'
            ]
            # Muestras contrastables para la siguiente iteración.
            samples={p['numero'] for p in md['premios'].values()}
            samples.update(list(ld['numeros'])[:3])
            samples.update(['00000','00001','99999'])
            item['consultas_de_diagnostico']={n:award(n,ld) for n in sorted(samples)}
            item['tabla_terminaciones']=ld['terminaciones']
            item['validado_para_comprobar_decimos']=False
        except Exception as exc:
            item['errores'].append(f'{type(exc).__name__}: {exc}')
        report['sorteos'].append(item)
        print(f"Sorteo {item.get('fecha','desconocido')}: {item.get('numeros_completos',0)} números; {item.get('terminaciones_recuperadas',0)} terminaciones; errores={item['errores']}",flush=True)
    Path('informe_pdf_086h.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['LotoScan 0.86H — Lotería Nacional: auditoría de PDF oficiales','SOLO DIAGNÓSTICO: NO PUBLICAR NI COMPROBAR DÉCIMOS','']
    for s in report['sorteos']:
        lines.extend([f"Fecha: {s.get('fecha')}",f"Números completos: {s.get('numeros_completos')}",
            f"Terminaciones: {s.get('terminaciones_por_longitud')}",f"Errores: {s['errores']}",
            f"Validaciones pendientes: {s.get('validaciones_pendientes')}",''])
    Path('informe_pdf_086h.txt').write_text('\n'.join(lines),encoding='utf-8')
    if any(s['errores'] for s in report['sorteos']):raise SystemExit('Auditoría detectó problemas; descargar informe')

if __name__=='__main__':main()
