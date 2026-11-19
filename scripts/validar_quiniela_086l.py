#!/usr/bin/env python3
"""LotoScan 0.86L: extracción y pruebas de notas oficiales de La Quiniela.
Solo diagnóstico; no publica ni modifica historico.json.
Uso: python scripts/validar_quiniela_086l.py --pdf-dir datos/quiniela
"""
import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from pypdf import PdfReader

MONTHS = {'enero':1,'febrero':2,'marzo':3,'abril':4,'mayo':5,'junio':6,'julio':7,'agosto':8,'septiembre':9,'octubre':10,'noviembre':11,'diciembre':12}
REFERENCE = {
 '2026-11-04': {'jornada':19,'signos':'1X122111222X22','pleno':'02','acertantes':[2,18,534,7285,45070,152115],'euros':[4225509,1001602,15826,1160,188,0],'elige8':[1272,2163]},
 '2026-11-08': {'jornada':20,'signos':'2X221X1222XX21','pleno':'12','acertantes':[1,6,185,2301,17496,89116],'euros':[164798655,9009900,136975,11013,1448,341],'elige8':[258,21466]},
 '2026-11-15': {'jornada':21,'signos':'2X1X211X11122X','pleno':'2M','acertantes':[0,4,40,459,3831,21762],'euros':[None,6344901,297417,25919,3105,656],'elige8':[49,66636]},
}
CATEGORIES = ['pleno_15','14','13','12','11','10']

def cents(s):
    if s.upper() == 'BOTE': return None
    return int(s.replace('.','').replace(',',''))

def parse(path):
    reader = PdfReader(str(path))
    if not reader.pages: raise ValueError('PDF sin páginas')
    raw = '\n'.join(p.extract_text(extraction_mode='layout') or '' for p in reader.pages)
    # Layout PDF extraction may differ by library. Normalize whitespace but preserve order.
    compact = re.sub(r'\s+', ' ', raw)
    dm = re.search(r'(\d{1,2})\s+de\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\s+de\s+(20\d{2})',compact,re.I)
    if not dm: raise ValueError('Fecha ausente')
    day = date(int(dm.group(3)), MONTHS[dm.group(2).lower()], int(dm.group(1))).isoformat()
    sm = re.search(r'(?<![A-Z0-9])([12X](?:\s*-\s*[12X]){13})(?![A-Z0-9])', compact, re.I)
    if not sm: raise ValueError('No se encuentran los 14 signos')
    signs = re.findall('[12X]',sm.group(1).upper())
    pm = re.search(r'Pleno\s+al\s+quince\s*-?\s*([012M])\s*([012M])\s*-?', compact, re.I)
    if not pm:
        # Some PDFs place the plenary header after the combination.
        vicinity = compact[sm.end():sm.end()+130]
        pm = re.search(r'-\s*([012M])\s*([012M])\s*-',vicinity,re.I)
    if not pm: raise ValueError('Pleno al 15 ausente')
    pleno = (pm.group(1)+pm.group(2)).upper()
    # Locate prize rows by label rather than relying on column order.
    rows=[]
    for label in ['Pleno al 15','14 Aciertos','13 Aciertos','12 Aciertos','11 Aciertos','10 Aciertos']:
        pat = re.compile(re.escape(label)+r'\s+([\d.]+)\s+(BOTE|[\d.]+,\d{2})',re.I)
        m = pat.search(compact)
        if not m: raise ValueError('Categoría no recuperada: '+label)
        rows.append({'categoria':label,'acertantes':int(m.group(1).replace('.','')),'premio_centimos':cents(m.group(2))})
    em = re.search(r'REPARTO DE PREMIOS Elige8.*?\b8\s+([\d.]+)\s+([\d.]+,\d{2})',compact,re.I)
    if not em: raise ValueError('Elige8 no recuperado')
    return {'fecha':day,'signos':signs,'pleno_15':pleno,'categorias':rows,'elige8':{'acertantes':int(em.group(1).replace('.','')),'premio_centimos':cents(em.group(2))},'fuente':path.name}

def audit(d):
    errors=[]; ref=REFERENCE.get(d['fecha'])
    if len(d['signos'])!=14 or any(s not in ('1','X','2') for s in d['signos']): errors.append('signos inválidos')
    if len(d['pleno_15'])!=2 or any(c not in '012M' for c in d['pleno_15']): errors.append('pleno inválido')
    for row in d['categorias']:
        if row['acertantes']<0 or (row['premio_centimos'] is None and row['acertantes']>0): errors.append('premio/categoría incoherente')
    if ref:
        d['jornada']=ref['jornada']
        checks={'signos': ''.join(d['signos'])==ref['signos'], 'pleno':d['pleno_15']==ref['pleno'],
          'acertantes':[r['acertantes'] for r in d['categorias']]==ref['acertantes'],
          'importes':[r['premio_centimos'] for r in d['categorias']]==ref['euros'],
          'elige8':[d['elige8']['acertantes'],d['elige8']['premio_centimos']]==ref['elige8']}
        d['contraste_referencia']=checks
        errors += [f'contraste {k} no coincide' for k,v in checks.items() if not v]
    else: d['contraste_referencia']={}; errors.append('jornada sin referencia independiente: requiere revisión')
    d['errores']=errors; d['validado_para_diagnostico']=not errors
    d['publicable']=False
    return d

def check_bet(result, signs, pleno=None, elige8_indices=None):
    """Una columna SIMPLE. No pretende interpretar un boleto múltiple ni combinaciones Elige8 sin selección."""
    if len(signs)!=14 or any(x not in ('1','X','2') for x in signs): raise ValueError('Se requieren 14 signos')
    hits=sum(a==b for a,b in zip(signs,result['signos']))
    category = ('14' if hits==14 else str(hits)) if hits>=10 else None
    amount = next((r['premio_centimos'] for r in result['categorias'] if r['categoria']==(category+' Aciertos')),0) if category else 0
    if hits==14 and pleno is not None and pleno.upper()==result['pleno_15']:
        extra=result['categorias'][0]['premio_centimos']
        if extra is not None: amount+=extra
        else: return {'aciertos':hits,'pleno':True,'importe_centimos':amount,'bote':True}
    return {'aciertos':hits,'pleno':hits==14 and pleno==result['pleno_15'],'importe_centimos':amount,'bote':False}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--pdf-dir',default='datos/quiniela');ap.add_argument('--out',default='informe_quiniela_086l.json'); args=ap.parse_args()
    files=sorted(Path(args.pdf_dir).glob('*.pdf'))
    report={'version':'0.86L','pdf_encontrados':len(files),'resultados':[],'errores_archivos':[],'publicable':False}
    for path in files:
        try:
            d=audit(parse(path))
            if d['validado_para_diagnostico']:
                d['pruebas_apuestas']={'14_y_pleno':check_bet(d,d['signos'],d['pleno_15']), '14_sin_pleno':check_bet(d,d['signos'],'MM' if d['pleno_15']!='MM' else '00')}
            report['resultados'].append(d)
            print(path.name, d['fecha'], 'OK' if not d['errores'] else 'ERROR: '+', '.join(d['errores']))
        except Exception as exc:
            report['errores_archivos'].append({'archivo':path.name,'error':str(exc)});print(path.name,'ERROR:',exc)
    expected=set(REFERENCE); found={d['fecha'] for d in report['resultados'] if d['validado_para_diagnostico']}
    report['referencias_cubiertas']=sorted(found & expected)
    report['diagnostico_completo']=expected<=found and not report['errores_archivos'] and len(files)==3
    Path(args.out).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if not report['diagnostico_completo']:
        print('Diagnóstico incompleto: faltan PDFs o hay errores. No se publica nada.');return 1
    print('Tres jornadas contrastadas. Diagnóstico correcto; NO publicable.');return 0
if __name__=='__main__':sys.exit(main())
