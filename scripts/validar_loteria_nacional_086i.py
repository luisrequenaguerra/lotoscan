#!/usr/bin/env python3
"""LotoScan 0.86I: validación exhaustiva de DOS sorteos históricos de Nacional.

Reglas de estos sorteos transcritas de la LISTA OFICIAL de SELAE.
Se verifican contra 200 importes acumulados de cada PDF y el total de premios.
No es un extractor general para fechas futuras. No modifica historico.json.
"""
import datetime as dt
import importlib.util
import json
import re
from io import BytesIO
from pathlib import Path
from pypdf import PdfReader

BASE = Path(__file__).resolve().parent
SOURCE = BASE / 'probar_notas_selae_085m.py'
if not SOURCE.exists():
    raise SystemExit('Falta scripts/probar_notas_selae_085m.py')
spec = importlib.util.spec_from_file_location('selae085m', SOURCE)
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)

# Valores de la sección LISTA OFICIAL de los PDF del 12 y 14 de noviembre.
# No aplicar estas reglas a ningún otro sorteo.
CASES = [
    dict(date='2026-11-12', indexes=(5, 6), first=39430, second=52774,
         firstamt=300000, secondamt=60000, approx1=12000, approx2=7470,
         hundred1=300, hundred2=150, per_series=2100000, series=6,
         count=41050, ticket=30,
         awards=[1,2,99,9,99,999,9999,1,2,99,40,700,9000,10000,10000],
         ending={4:{s:750 for s in '9430 0639 0709 1372 8331'.split()},
                 3:{s:150 for s in '430 096 115 223 325 416 857 922'.split()},
                 2:{s:60 for s in '30 06 19 26 35 37 46 61 76 97'.split()},
                 1:{s:30 for s in '0 3 1'.split()}}),
    dict(date='2026-11-14', indexes=(7, 8), first=75409, second=38422,
         firstamt=600000, secondamt=120000, approx1=10000, approx2=5540,
         hundred1=300, hundred2=300, per_series=4200000, series=10,
         count=41341, ticket=60,
         awards=[1,2,99,99,999,9999,1,2,99,40,1000,9000,10000,10000],
         ending={4:{s:1500 for s in '2004 2888 4896 8274'.split()},
                 3:{s:300 for s in '409 249 491 594 624 640 655 781 824 863 924'.split()},
                 2:{s:120 for s in '09 06 07 14 21 38 48 50 76 98'.split()},
                 1:{s:60 for s in '9 4 0'.split()}}),
]


def amount(number, case):
    """Importe acumulado por billete; el premio mayor sustituye al acumulado."""
    if number == case['first']:
        return case['firstamt']
    if number == case['second']:
        return case['secondamt']
    code = f'{number:05d}'
    total = sum(prizes.get(code[-length:], 0)
                for length, prizes in case['ending'].items())
    for rank in ('first', 'second'):
        winner = case[rank]
        if number in ((winner - 1) % 100000, (winner + 1) % 100000):
            total += case['approx1' if rank == 'first' else 'approx2']
        if number // 100 == winner // 100:
            total += case['hundred1' if rank == 'first' else 'hundred2']
    return total


def download(index):
    url = old.SEED_PDFS[index]
    meta, data = old.fetch(url)
    if meta.get('http') != 200 or not data.startswith(b'%PDF-'):
        raise ValueError(f'Descarga incorrecta {url}: {meta}')
    pdf = PdfReader(BytesIO(data))
    text = '\n'.join(p.extract_text(extraction_mode='layout') or '' for p in pdf.pages)
    if len(text) < 100:
        raise ValueError('PDF sin texto suficiente')
    return url, text


def audit(case):
    list_url, listing = download(case['indexes'][0])
    major_url, majors = download(case['indexes'][1])
    issues = []
    date_words = dt.date.fromisoformat(case['date']).strftime('%d/%m/%y')
    if date_words not in majors:
        issues.append('Fecha del PDF de premios mayores distinta')
    for rank in ('first', 'second'):
        # En el documento de mayores el importe y número aparecen separados.
        header = 'PRIMER PREMIO' if rank == 'first' else 'SEGUNDO PREMIO'
        m = re.search(header + r'\s+PREMIO DE\s+([\d.]+)\s+EUROS AL N[ÚU]MERO\s+([\d.]+)', majors, re.I)
        if not m or int(m[1].replace('.', '')) != case[rank+'amt'] or int(m[2].replace('.', '')) != case[rank]:
            issues.append(f'No coincide el {rank} premio entre documentos')
    # El PDF de lista ofrece 200 importes completos y acumulados (2 centenas).
    pairs = re.findall(r'(?<!\d)(\d{5})\.{3,}\s*([\d.]+)', listing)
    full = {int(n):int(v.replace('.', '')) for n,v in pairs}
    if len(pairs) != 200 or len(full) != 200:
        issues.append(f'Se esperaban 200 números completos; hay {len(pairs)} filas')
    for rank in ('first', 'second'):
        if case[rank] not in full or full[case[rank]] != case[rank+'amt']:
            issues.append(f'El premio {rank} no coincide con la tabla acumulada')
    # Comprobar que cada terminación de la configuración está impresa en la
    # lista oficial. Esto no demuestra por sí solo que se hayan recuperado todas.
    for length, prizes in case['ending'].items():
        for suffix in prizes:
            if not re.search(r'(?<!\d)' + re.escape(suffix) + r'\.{2,}', listing):
                # En la segunda página pueden aparecer sin puntos separadores.
                if not re.search(r'(?<!\d)' + re.escape(suffix) + r'(?!\d)', listing):
                    issues.append(f'Terminación {suffix} ausente del PDF')
    computed = [amount(n,case) for n in range(100000)]
    mismatches = [{'numero':f'{n:05d}', 'pdf':v, 'calculado':computed[n]}
                  for n,v in sorted(full.items()) if computed[n] != v]
    if mismatches:
        issues.append(f'{len(mismatches)} discrepancias con los 200 importes acumulados')
    actual_total = sum(computed)
    if actual_total != case['per_series']:
        issues.append(f'Importe por serie no cuadra: {actual_total}')
    if sum(case['awards']) != case['count']:
        issues.append('El recuento de categorías no cuadra')
    if not re.search(r'\b' + re.escape(f'{case["count"]:,}'.replace(',', '.')) + r'\b', listing):
        issues.append('No aparece el recuento de premios en la lista')
    total_all = case['per_series'] * case['series']
    if not re.search(re.escape(f'{total_all:,}'.replace(',', '.')), listing):
        issues.append('No aparece el importe total oficial en la lista')
    # Una fila por cada número, incluido importe cero. Es un resultado de
    # prueba, nunca publicar automáticamente sin validación de reglas.
    out = Path('diagnostico_nacional_086i')
    out.mkdir(exist_ok=True)
    (out / f'{case["date"]}_100000.json').write_text(
        json.dumps({'fecha':case['date'], 'unidad':'euros por billete completo',
                    'premios':[{'numero':f'{n:05d}', 'euros_billete':v}
                               for n,v in enumerate(computed)]}, ensure_ascii=False),
        encoding='utf-8')
    return {'fecha':case['date'], 'urls':[list_url,major_url],
            'filas_acumuladas_pdf':len(full), 'discrepancias':len(mismatches),
            'ejemplos_discrepancias':mismatches[:20],
            'importe_calculado_por_serie':actual_total,
            'importe_oficial_por_serie':case['per_series'],
            'premios_por_serie_categorias':sum(case['awards']),
            'premios_por_serie_oficiales':case['count'],
            'numeros_evaluados':len(computed),
            'numeros_con_importe_positivo':sum(v>0 for v in computed),
            'ejemplos':{f'{n:05d}':{'billete':computed[n], 'decimo':computed[n]/10}
                        for n in (0,case['first'],case['second'],99999)},
            'incidencias':issues,
            'validacion_fixtures_historicas':not issues,
            'apto_para_publicacion_automatica':False}


def main():
    result = {'version':'0.86I', 'origen':'PDF oficiales SELAE',
              'solo_dos_sorteos_historicos':True, 'modifica_historico':False,
              'sorteos':[]}
    for case in CASES:
        try:
            item = audit(case)
        except Exception as exc:
            item = {'fecha':case['date'], 'incidencias':[f'{type(exc).__name__}: {exc}'],
                    'validacion_fixtures_historicas':False}
        result['sorteos'].append(item)
        print(case['date'], 'OK' if item['validacion_fixtures_historicas'] else 'REVISAR',
              item['incidencias'], flush=True)
    Path('informe_nacional_086i.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    lines = ['LotoScan 0.86I - VALIDACIÓN DE DOS SORTEOS HISTÓRICOS',
             'NO PUBLICAR NI MODIFICAR historico.json', '']
    for item in result['sorteos']:
        lines += [f"{item['fecha']}: validado={item['validacion_fixtures_historicas']}",
                  f"  discrepancias={item.get('discrepancias')} importe={item.get('importe_calculado_por_serie')}",
                  f"  incidencias={item['incidencias']}"]
    Path('informe_nacional_086i.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    if not all(i['validacion_fixtures_historicas'] for i in result['sorteos']):
        raise SystemExit('La validación ha encontrado incidencias: consultar informe')

if __name__ == '__main__':
    main()
