#!/usr/bin/env python3
"""LotoScan 0.86G: auditoría conservadora de premios y listas SELAE.

Usa los 12 PDF históricos de prueba y el parser 0.86F. NO publica
resultados, NO calcula premios de boletos y NO modifica historico.json.
Opcional: --input-zip lotoscan-pdf-086f.zip para reproducir sin red.
"""
import argparse
import datetime as dt
from decimal import Decimal, InvalidOperation
import importlib.util
import json
from io import BytesIO
from pathlib import Path
import zipfile
from pypdf import PdfReader

BASE = Path(__file__).resolve().parent
GAMES = ['euromillones','primitiva','bonoloto','gordo-primitiva','eurodreams',
         'loteria-nacional-lista','loteria-nacional-mayores',
         'loteria-nacional-lista','loteria-nacional-mayores',
         'quinigol','lototurf','quintuple-plus']


def load(filename, alias):
    path = BASE / filename
    if not path.is_file():
        raise RuntimeError('Falta scripts/' + filename)
    spec = importlib.util.spec_from_file_location(alias, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def read_documents(parser, source_zip):
    docs = []
    if source_zip:
        with zipfile.ZipFile(source_zip) as z:
            for i, game in enumerate(GAMES, 1):
                name = f'diagnostico_pdf_086f/{i:02d}_{game}.txt'
                raw = z.read(name)
                docs.append({'indice':i, 'juego':game, 'error':None,
                             'datos':parser.parse_document(raw.decode('utf-8'),game)})
    else:
        old = load('probar_notas_selae_085m.py', 'source085m_g')
        if len(old.SEED_PDFS) != len(GAMES):
            raise RuntimeError('Cambió la cantidad de PDF: revisar asignación')
        for i, (url, game) in enumerate(zip(old.SEED_PDFS, GAMES), 1):
            item = {'indice':i, 'juego':game, 'url':url, 'error':None}
            try:
                meta, raw = old.fetch(url)
                if meta.get('http') != 200 or not raw.startswith(b'%PDF-'):
                    raise ValueError('PDF no descargado correctamente')
                reader = PdfReader(BytesIO(raw))
                if reader.is_encrypted or not reader.pages:
                    raise ValueError('PDF sin páginas accesibles')
                text = '\n'.join(p.extract_text(extraction_mode='layout') or '' for p in reader.pages)
                if len(text.strip()) < 100:
                    raise ValueError('Texto insuficiente')
                item['datos'] = parser.parse_document(text, game)
            except Exception as exc:
                item['error'] = f'{type(exc).__name__}: {exc}'
            docs.append(item)
    return docs


def check_categories(draw):
    rows = draw.get('categorias', [])
    errors, warnings = [], []
    seen = set()
    for row in rows:
        cat = row.get('categoria')
        if not cat:
            errors.append('Categoría sin nombre')
        if cat in seen:
            errors.append(f'Categoría repetida: {cat}')
        seen.add(cat)
        winners = row.get('acertantes')
        if not isinstance(winners, int) or winners < 0:
            errors.append(f'Acertantes inválidos: {cat}')
        amount = row.get('premio_unitario_eur')
        state = row.get('estado_premio')
        if amount is None:
            if not state:
                warnings.append(f'Sin importe ni estado: {cat}')
        else:
            try:
                value = Decimal(str(amount))
                if not value.is_finite() or value < 0 or value.as_tuple().exponent < -2:
                    errors.append(f'Importe inválido: {cat}')
            except (InvalidOperation, ValueError):
                errors.append(f'Importe no numérico: {cat}')
            if state:
                errors.append(f'Importe y estado simultáneos: {cat}')
    if not rows:
        errors.append('No hay categorías')
    # Sin el PDF original tabular y reglas específicas, estas comprobaciones
    # solo validan estructura, no exhaustividad ni adjudicación de premios.
    return {'filas':len(rows), 'errores':errors, 'advertencias':warnings,
            'estructura_correcta':not errors, 'premios_validados':False}


def check_national(draw, docs):
    issues = []
    indices = draw['documentos_origen']
    a, b = (docs[i-1] for i in indices)
    if a['error'] or b['error']:
        return {'documentos':indices, 'coincidencia_mayores':False,
                'errores':['Falta uno de los documentos'], 'lista_exhaustiva':False,
                'apto_para_comprobar_decimos':False}
    lista, mayores = a['datos'], b['datos']
    prices = lista.get('premios_acumulados_por_billete', {})
    checks = {}
    for name, key in [('primero','primer_premio'),('segundo','segundo_premio')]:
        major = mayores.get(key)
        actual = prices.get(major['numero']) if major else None
        expected = major.get('euros_por_billete') if major else None
        checks[name] = {'numero':major['numero'] if major else None,
                        'importe_lista':actual, 'importe_mayores':expected,
                        'coincide':actual is not None and actual == expected}
        if not checks[name]['coincide']:
            issues.append(f'{name}: discrepancia entre lista y premios mayores')
    dates_match = bool(lista.get('fecha')) and lista.get('fecha') == mayores.get('fecha')
    if not dates_match:
        issues.append('Fechas distintas o ausentes')
    reintegros = mayores.get('reintegros')
    if not isinstance(reintegros, list) or len(reintegros) != 3 or any(
        not isinstance(x, int) or x < 0 or x > 9 for x in reintegros
    ):
        issues.append('Reintegros incompletos')
    if not prices:
        issues.append('Lista de premios vacía')
    if any(len(str(n)) != 5 or not str(n).isdigit() or not isinstance(v,int) or v < 0
           for n,v in prices.items()):
        issues.append('Números o importes de lista inválidos')
    return {
        'documentos':indices, 'fecha':lista.get('fecha'),
        'fecha_coincide':dates_match, 'premios_mayores':checks,
        'coincidencia_mayores':all(x['coincide'] for x in checks.values()),
        'entradas_numeros_completos':len(prices),
        'terminaciones_candidatas':len(lista.get('terminaciones_informativas', {})),
        'reintegros':reintegros, 'errores':issues,
        'lista_exhaustiva':False, 'apto_para_comprobar_decimos':False,
        'limitaciones':[
            '200 entradas detectadas no demuestran que estén todos los premios',
            'El texto PDF multicolumna puede fusionar terminaciones e importes',
            'No se han verificado las reglas completas de aproximaciones, centenas y terminaciones',
            'No se puede declarar un décimo sin premio ni calcular su importe con este informe',
        ],
    }


def main():
    arg = argparse.ArgumentParser()
    arg.add_argument('--input-zip', help='ZIP de diagnóstico 0.86F; permite prueba sin red')
    args = arg.parse_args()
    parser = load('extraer_pdf_selae_086f.py','parser086f_g')
    docs = read_documents(parser, args.input_zip)
    draws, _ = parser.consolidate(docs)
    categories = {}
    national = []
    for draw in draws:
        if draw['juego'] == 'loteria-nacional':
            national.append(check_national(draw, docs))
        else:
            categories[draw['juego']] = check_categories(draw)
    report = {
        'version':'0.86G', 'generado_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
        'fuente':'PDF SELAE históricos de 0.85M; no hay descubrimiento diario',
        'solo_lectura':True, 'publicable':False,
        'documentos_procesados':len(docs),
        'errores_documentos':[{'indice':x['indice'],'error':x['error']}
                             for x in docs if x['error']],
        'auditoria_categorias':categories, 'auditoria_loteria_nacional':national,
        'validacion_premios_completa':False,
        'pendientes':[
            'Reconstruir y contrastar todas las reglas de Lotería Nacional',
            'Contrastar exhaustividad y semántica de las categorías por juego',
            'Descubrir dinámicamente PDF oficiales de sorteos nuevos',
            'Crear pruebas automatizadas antes de publicar resultados',
        ],
    }
    Path('informe_pdf_086g.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    lines = ['LotoScan 0.86G | AUDITORÍA HISTÓRICA | NO PUBLICABLE',
             f'Documentos: {len(docs)}; errores de descarga/parseo: {len(report["errores_documentos"])}', '']
    for name, value in categories.items():
        lines.append(f'{name}: {value["filas"]} categorías, estructura_correcta={value["estructura_correcta"]}, errores={value["errores"]}')
    for value in national:
        lines.append(f'Nacional {value.get("fecha")}: entradas={value.get("entradas_numeros_completos")}, mayores_coinciden={value["coincidencia_mayores"]}, errores={value["errores"]}, exhaustiva=NO')
    lines.append('No modificar historico.json ni comprobar décimos con esta auditoría.')
    Path('informe_pdf_086g.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('\n'.join(lines))
    if report['errores_documentos']:
        raise SystemExit('Hay documentos fallidos; consultar informe_pdf_086g.json')


if __name__ == '__main__':
    main()
