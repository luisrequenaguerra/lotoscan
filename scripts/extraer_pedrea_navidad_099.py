#!/usr/bin/env python3
"""LotoScan 0.99: auditoría conservadora de pedrea; nunca publicable."""
import collections, json, pathlib, re, subprocess, zipfile
from datetime import datetime, timezone

OUT=pathlib.Path('salida_099'); OUT.mkdir(exist_ok=True)
SOURCE=pathlib.Path('fuente_098.zip')
EXPECTED=1794  # programa habitual Navidad; no se presume igual a entradas PDF
# Un registro de lista tiene cinco cifras, hasta cinco puntos de separación,
# una marca opcional y el importe por billete. La extracción NO prueba pedrea.
PAT=re.compile(r'(?<!\d)(\d{5})\s*(?:\.\s*){0,2}(?:([a-z])\s*)?(?:\.\s*){0,5}(1[.,]?000|1000|12[.,]?500|12500|1[.,]?250[.,]?000|1250000)(?!\d)', re.I)

def extract(y, raw):
    rows=[]
    for line_no,line in enumerate(raw.splitlines(),1):
        for m in PAT.finditer(line):
            num,mark,amount=m.groups()
            rows.append({'numero':num,'marca':mark.lower() if mark else None,'euros_billete_texto':amount,'linea':line_no,'fragmento':line[max(0,m.start()-12):min(len(line),m.end()+12)].strip()})
    unmarked=[r for r in rows if not r['marca'] and r['euros_billete_texto'].replace('.','').replace(',','')=='1000']
    counts=collections.Counter((r['marca'] or 'sin_marca') for r in rows)
    nums=collections.Counter(r['numero'] for r in unmarked)
    duplicates={k:v for k,v in nums.items() if v>1}
    summary={'anio':y,'origen':'PDF oficial descargado en ejecución 0.98','registros_reconocidos':len(rows),'marcas':dict(counts),'candidatos_sin_marca_1000':len(unmarked),'candidatos_unicos':len(nums),'duplicados_candidatos':duplicates,'referencia_pedrea_habitual':EXPECTED,'diferencia_con_referencia':EXPECTED-len(nums),'pedrea_completa_validada':False,'publicable':False,'advertencia':'Sin marca no equivale necesariamente a pedrea. Las columnas, superposiciones y premios derivados pueden generar omisiones o falsos positivos.'}
    (OUT/f'candidatos_navidad_{y}.json').write_text(json.dumps({'resumen':summary,'candidatos':unmarked},ensure_ascii=False,indent=2))
    (OUT/f'registros_navidad_{y}.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
    return summary

def main():
    if not SOURCE.exists():
        raise SystemExit('Falta fuente_098.zip. Sube el artefacto de la 0.98 como fuente_098.zip o deja los TXT de referencia en la raíz.')
    report={'version':'0.99','generado_utc':datetime.now(timezone.utc).isoformat(),'fuente':str(SOURCE),'anios':[],'publicable':False,'historico_modificado':False}
    with zipfile.ZipFile(SOURCE) as z:
        for y in (2024,2025):
            name=f'lista_oficial_navidad_{y}.txt'
            if name not in z.namelist(): raise SystemExit(f'Falta {name} en el ZIP')
            raw=z.read(name).decode('utf-8',errors='replace')
            report['anios'].append(extract(y,raw))
    (OUT/'informe_navidad_099.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
