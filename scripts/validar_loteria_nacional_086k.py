#!/usr/bin/env python3
"""LotoScan 0.86K: interpreta reglas desde la segunda página de listas SELAE.
Diagnóstico estricto para los dos PDF de muestra; nunca publica premios.
"""
import datetime as dt
import importlib.util
import json
import re
from io import BytesIO
from pathlib import Path
from pypdf import PdfReader

BASE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('source085m', BASE / 'probar_notas_selae_085m.py')
source = importlib.util.module_from_spec(spec)
spec.loader.exec_module(source)

SAMPLES = ((5, 6), (7, 8))


def integer(value):
    return int(value.replace('.', ''))


def download(index):
    url = source.SEED_PDFS[index]
    meta, raw = source.fetch(url)
    if meta.get('http') != 200 or not raw.startswith(b'%PDF-'):
        raise ValueError(f'PDF no disponible: {url} {meta}')
    pdf = PdfReader(BytesIO(raw))
    pages = [page.extract_text(extraction_mode='layout') or '' for page in pdf.pages]
    if not pages or any(len(p.strip()) < 100 for p in pages):
        raise ValueError('PDF sin texto legible')
    return url, pages


def capture(pattern, text, label, flags=re.I | re.S):
    m = re.search(pattern, text, flags)
    if not m:
        raise ValueError(f'No se reconoce {label}')
    return m


def read_rules(pages):
    if len(pages) < 2:
        raise ValueError('La lista oficial no tiene segunda página')
    page = pages[-1]
    # Layout de la página de reglas: sección izquierda y sección derecha.
    # Si SELAE cambia el diseño, los controles posteriores deben rechazarlo.
    lines = page.splitlines()
    left = '\n'.join(line[:155] for line in lines)
    right = '\n'.join(line[155:] for line in lines)
    d = capture(r'(\d{1,2}) DE (\w+) DE (20\d{2})', page, 'fecha')
    months = {'NOVIEMBRE': 11, 'ENERO': 1, 'FEBRERO': 2, 'MARZO': 3,
              'ABRIL': 4, 'MAYO': 5, 'JUNIO': 6, 'JULIO': 7,
              'AGOSTO': 8, 'SEPTIEMBRE': 9, 'OCTUBRE': 10, 'DICIEMBRE': 12}
    date = dt.date(int(d[3]), months[d[2].upper()], int(d[1])).isoformat()
    major = re.findall(r'\b1\s+Premio de\s+([\d.]+) euros para el billete n[uú]mero\.{3,}\s*(\d{5})', left, re.I)
    if len(major) != 2:
        raise ValueError(f'Premios mayores encontrados: {len(major)}')
    first_amt, first = integer(major[0][0]), int(major[0][1])
    second_amt, second = integer(major[1][0]), int(major[1][1])
    approx = [integer(v) for v in re.findall(r'2\s+Aproximaciones de\s+([\d.]+) euros', left, re.I)]
    hundreds = [integer(v) for v in re.findall(r'99\s+Centenas de\s+([\d.]+) euros', left, re.I)]
    if len(approx) != 2 or len(hundreds) != 2:
        raise ValueError('Aproximaciones o centenas incompletas')
    # Premios ligados al primer premio (4, 3, 2, 1 cifras).
    # Leemos el número tras los puntos de la frase "primer premio en".
    linked = re.findall(r'(?:Premios\s+de|Reintegros\s+de)\s+([\d.]+) euros.{0,230}?primer premio en\.{3,}\s*(\d{1,4})', left, re.I | re.S)
    linked_map = {len(s): (s, integer(v)) for v, s in linked}
    if set(linked_map) != {1, 2, 3} and set(linked_map) != {1, 2, 3, 4}:
        raise ValueError(f'Terminaciones del primer premio incompletas: {linked_map}')
    # En la columna derecha, cada bloque empieza con el número de premios
    # seguido del importe y del encabezado. Los sufijos están debajo.
    header = re.compile(r'\b([\d.]+)\s+Premios de\s+([\d.]+) euros cada uno, para todos los billetes terminados en\s*:', re.I)
    hits = list(header.finditer(right))
    if len(hits) != 3:
        raise ValueError(f'Bloques de terminaciones extraídas: {len(hits)}')
    ending = {4: {}, 3: {}, 2: {}, 1: {}}
    for length, (suffix, euros) in linked_map.items():
        ending[length][suffix] = euros
    for i, hit in enumerate(hits):
        stop = hits[i+1].start() if i+1 < len(hits) else len(right)
        block = right[hit.end():stop]
        # No incorporar la sección de reintegros al último bloque.
        block = re.split(r'\b10\.000\s+Reintegros', block, maxsplit=1, flags=re.I)[0]
        count = integer(hit[1]); prize = integer(hit[2])
        length = {40:4, 700:3, 1000:3, 9000:2}.get(count)
        if length is None:
            raise ValueError(f'Categoría no reconocida: {count}')
        # Los sufijos aparecen en líneas sin texto. Ignoramos palabras y cifras
        # fuera del ancho esperado; los guiones son relleno visual.
        suffixes = []
        for line in block.splitlines():
            if re.search(r'[A-Za-zÁÉÍÓÚáéíóú]', line):
                continue
            suffixes.extend(re.findall(rf'(?<!\d)\d{{{length}}}(?!\d)', line))
        suffixes = list(dict.fromkeys(suffixes))
        expected = count // (10 ** (5-length))
        if len(suffixes) != expected:
            raise ValueError(f'Terminaciones de {length} cifras: {len(suffixes)} encontradas; esperadas {expected}: {suffixes}')
        for suffix in suffixes:
            if suffix in ending[length]:
                raise ValueError(f'Terminación duplicada: {suffix}')
            ending[length][suffix] = prize
    special = re.findall(r'primera extracci[oó]n especial sea\.{3,}\s*(\d)|segunda extracci[oó]n especial sea\.{3,}\s*(\d)', right, re.I)
    special_digits = [a or b for a, b in special]
    if len(special_digits) != 2:
        raise ValueError(f'Reintegros especiales incompletos: {special_digits}')
    for digit in special_digits:
        if digit in ending[1]:
            raise ValueError('Reintegro especial duplicado')
        # El importe se obtiene del encabezado del reintegro especial.
        ending[1][digit] = integer(capture(r'10\.000\s+Reintegros de\s+([\d.]+) euros', right, 'importe reintegro')[1])
    totals = capture(r'Esta lista comprende los\s+([\d.]+) premios adjudicados para cada serie.*?En el conjunto de las\s+(\d+) series.*?por un importe de\s+([\d.]+)\s+(?:de\s+)?euros', page, 'totales oficiales')
    count, series, total_all = integer(totals[1]), int(totals[2]), integer(totals[3])
    if total_all % series:
        raise ValueError('Importe no divisible entre series')
    # Recuentos oficiales por categoría; para evitar contar dos veces números
    # premiados, las coincidencias se suman como adjudicaciones independientes.
    return dict(fecha=date, first=first, second=second, firstamt=first_amt,
                secondamt=second_amt, approx1=approx[0], approx2=approx[1],
                hundred1=hundreds[0], hundred2=hundreds[1], ending=ending,
                count=count, series=series, per_series=total_all//series)


def amount(n, case):
    if n == case['first']:
        return case['firstamt']
    if n == case['second']:
        return case['secondamt']
    code = f'{n:05d}'
    total = sum(v for length, prizes in case['ending'].items()
                for suffix, v in prizes.items() if code.endswith(suffix))
    for rank in ('first', 'second'):
        winner = case[rank]
        if n in ((winner-1) % 100000, (winner+1) % 100000):
            total += case['approx1' if rank == 'first' else 'approx2']
        if n//100 == winner//100:
            total += case['hundred1' if rank == 'first' else 'hundred2']
    return total


def audit(pair):
    url_list, pages = download(pair[0])
    url_major, major_pages = download(pair[1])
    rules = read_rules(pages)
    listing = '\n'.join(pages)
    major = '\n'.join(major_pages)
    issues = []
    for rank, title in [('first', 'PRIMER'), ('second', 'SEGUNDO')]:
        match = re.search(title + r' PREMIO\s+PREMIO DE\s+([\d.]+)\s+EUROS AL N[ÚU]MERO\s+([\d.]+)', major, re.I)
        if not match or integer(match[1]) != rules[rank+'amt'] or integer(match[2]) != rules[rank]:
            issues.append(f'Premio mayor {rank} distinto entre documentos')
    pairs = re.findall(r'(?<!\d)(\d{5})\.{3,}\s*([\d.]+)', listing)
    refs = {int(n): integer(value) for n, value in pairs}
    if len(pairs) != 200 or len(refs) != 200:
        issues.append(f'Filas de referencia incompletas: {len(pairs)}')
    values = [amount(n, rules) for n in range(100000)]
    discrepancies = [{'numero':f'{n:05d}', 'pdf':v, 'calculado':values[n]}
                     for n,v in sorted(refs.items()) if values[n] != v]
    if discrepancies:
        issues.append(f'{len(discrepancies)} discrepancias en importes completos')
    if sum(values) != rules['per_series']:
        issues.append(f'Importe por serie calculado {sum(values)} distinto de {rules["per_series"]}')
    # Cada premio adjudicado se cuenta por categoría, no por número único.
    # Las categorías asociadas al primer premio excluyen el billete ganador.
    # Las extracciones adicionales se cuentan por separado, incluso si se
    # solapan con otra terminación. Esto reproduce el recuento del PDF.
    ending = rules['ending']
    first_code = f"{rules['first']:05d}"
    linked4 = first_code[-4:] in ending[4]
    linked3 = first_code[-3:] in ending[3]
    linked2 = first_code[-2:] in ending[2]
    linked1 = first_code[-1:] in ending[1]
    issues_count = []
    if len(ending[1]) != 3:
        issues_count.append(f'Se esperaban 3 terminaciones de reintegro, hay {len(ending[1])}')
    if not (linked3 and linked2 and linked1):
        issues_count.append('Faltan terminaciones vinculadas al primer premio')
    counts_detail = {
        'primer_premio': 1,
        'aproximaciones_primero': 2,
        'centenas_primero': 99,
        'terminacion_4_primero': 9 if linked4 else 0,
        'terminacion_3_primero': 99 if linked3 else 0,
        'terminacion_2_primero': 999 if linked2 else 0,
        'reintegro_primero': 9999 if linked1 else 0,
        'segundo_premio': 1,
        'aproximaciones_segundo': 2,
        'centenas_segundo': 99,
        'terminaciones_4_adicionales': (len(ending[4]) - int(linked4)) * 10,
        'terminaciones_3_adicionales': (len(ending[3]) - int(linked3)) * 100,
        'terminaciones_2_adicionales': (len(ending[2]) - int(linked2)) * 1000,
        'reintegros_especiales': (len(ending[1]) - int(linked1)) * 10000,
    }
    computed_awards = sum(counts_detail.values())
    issues.extend(issues_count)
    if computed_awards != rules['count']:
        issues.append(f'Recuento por categorías {computed_awards} distinto del oficial {rules["count"]}')
    return {'fecha':rules['fecha'], 'pdf_lista':url_list, 'pdf_mayores':url_major,
            'reglas_extraidas':rules, 'referencias':len(refs),
            'discrepancias_referencias':discrepancies[:30],
            'importe_calculado_por_serie':sum(values),
            'importe_oficial_por_serie':rules['per_series'],
            'recuento_categorias_calculado':computed_awards, 'desglose_recuento':counts_detail,
            'recuento_oficial':rules['count'], 'incidencias':issues,
            'validado':not issues}


def main():
    report = {'version':'0.86K', 'origen':'PDF SELAE', 'publicable':False,
              'historico_modificado':False, 'sorteos':[]}
    for pair in SAMPLES:
        try:
            item = audit(pair)
        except Exception as exc:
            item = {'documentos':list(pair), 'validado':False,
                    'incidencias':[f'{type(exc).__name__}: {exc}']}
        report['sorteos'].append(item)
        print(item.get('fecha', pair), 'VALIDADO' if item['validado'] else 'PENDIENTE', item['incidencias'], flush=True)
    Path('informe_nacional_086k.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    Path('informe_nacional_086k.txt').write_text('\n'.join(f"{s.get('fecha',s.get('documentos'))}: {'VALIDADO' if s['validado'] else 'PENDIENTE'}: {s['incidencias']}" for s in report['sorteos'])+'\n',encoding='utf-8')
    if any(not s['validado'] for s in report['sorteos']):
        raise SystemExit('Validación incompleta; revisar informe_nacional_086k.json')


if __name__ == '__main__':
    main()
