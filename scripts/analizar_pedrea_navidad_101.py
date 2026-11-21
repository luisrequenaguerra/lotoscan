#!/usr/bin/env python3
"""LotoScan 1.01: comprueba hipótesis 'sin letra = pedrea', sin publicar premios."""
import collections, json, pathlib, re
from datetime import datetime, timezone

IN=pathlib.Path('entrada_099'); OUT=pathlib.Path('salida_101'); OUT.mkdir(exist_ok=True)
EXPECTED=1794

def run(year):
    source=next(iter(IN.rglob(f'registros_navidad_{year}.json')),None)
    if source is None: raise FileNotFoundError(f'Falta registros_navidad_{year}.json del artefacto 0.99')
    records=json.loads(source.read_text(encoding='utf-8'))
    bynum=collections.defaultdict(list)
    for row in records:
        bynum[row['numero']].append(row)
    plain=[r for r in records if not r.get('marca') and re.sub(r'\D','',r['euros_billete_texto'])=='1000']
    unique_plain=set(r['numero'] for r in plain)
    marks=collections.Counter(r.get('marca') or 'sin_marca' for r in records)
    overlaps=[{'numero':n,'marcas':sorted(set(str(r.get('marca') or 'sin_marca') for r in rows)),
               'registros':len(rows)} for n,rows in bynum.items() if n in unique_plain and any(r.get('marca') for r in rows)]
    repeated_plain=[n for n,c in collections.Counter(r['numero'] for r in plain).items() if c>1]
    # La marca es un concepto de premio, no una prueba de ausencia de pedrea.
    # Un número puede acumular premios: NO restar los solapamientos.
    report={
        'anio':year,'registros':len(records),'marcas':dict(marks),
        'candidatos_sin_letra_1000':len(plain),'candidatos_sin_letra_unicos':len(unique_plain),
        'repetidos_sin_letra':len(repeated_plain),'solapamientos_sin_letra_y_con_letra':len(overlaps),
        'referencia_extracciones_pedrea':EXPECTED,
        'diferencia_extracciones_menos_candidatos':EXPECTED-len(unique_plain),
        'hipotesis_sin_letra_equivale_toda_pedrea':'NO DEMOSTRADA',
        'explicacion':'Las letras a/c/t indican premios derivados. La ausencia de letra es compatible con pedrea, pero la lista de registros 0.99 no permite acreditar exhaustividad ni excluir coincidencias.',
        'pedrea_completa_validada':False,'publicable':False
    }
    (OUT/f'diagnostico_navidad_{year}.json').write_text(json.dumps({'resumen':report,'solapamientos':overlaps,'repetidos_sin_letra':repeated_plain,'candidatos_sin_letra':sorted(unique_plain)},ensure_ascii=False,indent=2),encoding='utf-8')
    return report

def main():
    results=[run(y) for y in (2024,2025)]
    data={'version':'1.01','fecha_utc':datetime.now(timezone.utc).isoformat(),
          'fuente':'registros originales extraídos en 0.99, no nueva consulta a SELAE',
          'anios':results,'publicable':False,'historico_modificado':False,
          'siguiente_validacion':'Contrastar con 1794 extracciones individualizadas de pedrea en una fuente oficial completa; auditar pérdidas del parser 0.99 y números de premios principales.'}
    (OUT/'informe_navidad_101.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(data,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
