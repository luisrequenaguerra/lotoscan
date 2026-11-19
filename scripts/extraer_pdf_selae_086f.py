#!/usr/bin/env python3
"""LotoScan 0.86F: combina lectura 0.86C y premios 0.86E.
Diagnóstico histórico, SOLO LECTURA. No escribe historico.json.
Requiere scripts/probar_notas_selae_085m.py, extraer_pdf_selae_086c.py,
extraer_pdf_selae_086e.py. No descubre sorteos nuevos.
"""
import datetime as dt
import importlib.util
import json
from io import BytesIO
from pathlib import Path
from pypdf import PdfReader

BASE = Path(__file__).resolve().parent

def load(filename, name):
    path = BASE / filename
    if not path.is_file():
        raise SystemExit('Falta dependencia: scripts/' + filename)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

old = load('probar_notas_selae_085m.py', 'old085m_f')
c = load('extraer_pdf_selae_086c.py', 'parser086c_f')
e = load('extraer_pdf_selae_086e.py', 'parser086e_f')
GAMES = e.GAMES


def parse_document(text, game):
    cdata = c.parse(text, game)
    if game == 'loteria-nacional-lista':
        edata = e.national_list(text)
    elif game == 'loteria-nacional-mayores':
        edata = e.national_major(text)
    else:
        edata = e.generic(text, game)
    warnings = list(dict.fromkeys(cdata.get('advertencias', []) + edata.get('advertencias', [])))
    data = {
        'juego': game, 'fecha': cdata.get('fecha'), 'validado': False,
        'advertencias': warnings,
        'categorias': edata.get('categorias', []),
    }
    if cdata.get('fecha') != edata.get('fecha'):
        warnings.append('Fechas discrepantes entre lectores')
    if game.startswith('loteria-nacional'):
        data.update({k:v for k,v in edata.items() if k not in ('fecha', 'advertencias')})
    elif game == 'quinigol':
        data['partidos'] = cdata.get('partidos', [])
        if len(data['partidos']) != 6:
            warnings.append('Faltan partidos')
    elif game == 'quintuple-plus':
        data['caballos'] = cdata.get('caballos')
        if not data['caballos'] or len(data['caballos']) != 6 or any(x is None for x in data['caballos']):
            warnings.append('Resultados hípicos incompletos')
    else:
        data['combinacion'] = cdata.get('combinacion')
        data['adicionales'] = cdata.get('adicionales', {})
        if game == 'primitiva' and not data['adicionales'].get('joker'):
            data['adicionales']['joker'] = edata.get('joker')
        if not data['combinacion']:
            warnings.append('Combinación incompleta')
        required = {
            'euromillones':['estrellas', 'el_millon'],
            'primitiva':['complementario','reintegro','joker'],
            'bonoloto':['complementario','reintegro'],
            'gordo-primitiva':['clave'],
            'eurodreams':['sueno'],
            'lototurf':['caballo_cuarta','reintegro'],
        }[game]
        for key in required:
            if data['adicionales'].get(key) is None:
                warnings.append('Falta adicional: '+key)
    if not data['fecha']:
        warnings.append('Fecha no identificada')
    if not game.startswith('loteria-nacional') and not data['categorias']:
        warnings.append('No se extrajeron categorías de premios')
    data['integridad_basica'] = not warnings
    # Incluso con integridad básica, las reglas de comprobación de boletos
    # y la exhaustividad no se han validado. No habilitar publicación.
    data['validado'] = False
    return data


def consolidate(documents):
    draws = []
    for entry in documents:
        if entry['error'] or entry['juego'].startswith('loteria-nacional'):
            continue
        draw = dict(entry['datos'])
        draw['documentos_origen'] = [entry['indice']]
        draws.append(draw)
    checks = []
    for li, ma in ((5,6),(7,8)):
        a, b = documents[li], documents[ma]
        draw = {'juego':'loteria-nacional','fecha':None,'validado':False,
                'integridad_basica':False,'documentos_origen':[li+1,ma+1],
                'advertencias':['No está demostrada la exhaustividad de la lista oficial; prohibido inferir boletos sin premio']}
        check = {'documentos':[li+1,ma+1], 'fecha_coincide':False,
                 'premios_mayores_coinciden':False}
        if not a['error'] and not b['error']:
            lista, mayores = a['datos'], b['datos']
            draw['fecha'] = lista['fecha']
            draw['sorteo'] = mayores.get('sorteo')
            draw['premios_acumulados_por_billete'] = lista['premios_acumulados_por_billete']
            draw['terminaciones_informativas'] = lista['terminaciones_informativas']
            draw['premios_mayores'] = {
                'primero':mayores.get('primer_premio'),
                'segundo':mayores.get('segundo_premio')}
            draw['reintegros'] = mayores.get('reintegros')
            check['fecha_coincide'] = bool(lista['fecha']) and lista['fecha'] == mayores['fecha']
            checks_for_prizes = []
            for k in ('primer_premio','segundo_premio'):
                p = mayores.get(k)
                checks_for_prizes.append(bool(p) and lista['premios_acumulados_por_billete'].get(p['numero']) == p['euros_por_billete'])
            check['premios_mayores_coinciden'] = all(checks_for_prizes)
            if not check['fecha_coincide']:
                draw['advertencias'].append('Fechas de documentos no coinciden')
            if not check['premios_mayores_coinciden']:
                draw['advertencias'].append('Premios mayores no coinciden')
        else:
            draw['advertencias'].append('Falta documento de Lotería Nacional')
        draws.append(draw)
        checks.append(check)
    return draws, checks


def main():
    if len(old.SEED_PDFS) != len(GAMES):
        raise SystemExit('La lista de 12 URL ha cambiado; revisar mapeo')
    out = Path('diagnostico_pdf_086f'); out.mkdir(exist_ok=True)
    documents = []
    for i, (url, game) in enumerate(zip(old.SEED_PDFS, GAMES), 1):
        entry = {'indice':i,'juego':game,'url':url,'error':None}
        try:
            meta, raw = old.fetch(url)
            entry['http'] = meta.get('http')
            if entry['http'] != 200 or not raw.startswith(b'%PDF-'):
                raise ValueError('Descarga no válida')
            reader = PdfReader(BytesIO(raw))
            if reader.is_encrypted or not reader.pages:
                raise ValueError('PDF sin páginas legibles')
            full = '\n'.join(page.extract_text(extraction_mode='layout') or '' for page in reader.pages)
            if len(full.strip()) < 100:
                raise ValueError('PDF sin texto suficiente')
            (out / f'{i:02d}_{game}.txt').write_text(full, encoding='utf-8')
            entry['datos'] = parse_document(full, game)
        except Exception as ex:
            entry['error'] = f'{type(ex).__name__}: {ex}'
        documents.append(entry)
        print(f'{i:02d} {game}: {entry["error"] or "procesado, NO validado"}', flush=True)
    draws, checks = consolidate(documents)
    report = {'version':'0.86F','generado_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
              'fuente':'PDF SELAE: 12 URLs históricas 0.85M',
              'publicable':False,'solo_lectura':True,'documentos':documents,
              'sorteos_unificados':draws,'comprobaciones_loteria_nacional':checks,
              'nota':'No calcular premios de boletos ni actualizar historico.json'}
    Path('informe_pdf_086f.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    summary = ['LotoScan 0.86F | NO PUBLICABLE | SIN CAMBIOS EN historico.json',
               f'Documentos: {len(documents)}; sorteos unificados: {len(draws)}', '']
    for d in draws:
        summary.append(f'{d["juego"]} {d.get("fecha")} | integridad_basica={d["integridad_basica"]} | advertencias={d["advertencias"]}')
    for ck in checks:
        summary.append('Nacional: '+json.dumps(ck,ensure_ascii=False))
    Path('informe_pdf_086f.txt').write_text('\n'.join(summary)+'\n',encoding='utf-8')
    if any(d['error'] for d in documents):
        raise SystemExit('Error en algún documento; descargar informe para diagnosticar')

if __name__ == '__main__':
    main()
