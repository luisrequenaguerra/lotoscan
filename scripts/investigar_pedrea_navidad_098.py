#!/usr/bin/env python3
"""LotoScan 0.98: auditoría de listas oficiales de Navidad; solo lectura."""
import datetime as dt
import json
import pathlib
import re
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request

BASE = 'https://www.loteriasyapuestas.es'
DRAWS = {'2024': '1259409102', '2025': '1295909102'}
OUT = pathlib.Path('salida_098')
HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; LotoScanAudit/0.98)', 'Accept': 'application/json,application/pdf,text/html,*/*'}

def get(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.status, r.read(), r.headers.get('Content-Type', '')

def pdf_analysis(txt):
    # Exploración, no interpretación definitiva de importes ni de categorías.
    lines = txt.splitlines()
    candidates = []
    for i, line in enumerate(lines):
        if re.search(r'(?<!\d)\d{5}(?!\d)', line):
            candidates.append({'linea': i + 1, 'texto': line.strip()[:220]})
    keywords = {}
    for word in ('pedrea', '1.000', '1000', 'reintegro', 'centenas', 'aproximaciones', 'LISTA OFICIAL', 'PREMIOS'):
        hits = [{'linea': i+1, 'texto': line.strip()[:220]} for i, line in enumerate(lines) if word.casefold() in line.casefold()]
        keywords[word] = {'total': len(hits), 'muestras': hits[:12]}
    return {'lineas': len(lines), 'lineas_con_numeros_5_cifras': len(candidates), 'muestras_numeros': candidates[:40], 'terminos': keywords,
            'advertencia': 'Las coincidencias de cinco cifras NO son una pedrea verificada. Requieren parsing y contraste con la lista oficial.'}

def main():
    OUT.mkdir(exist_ok=True)
    report = {'version': '0.98', 'fecha_utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'solo_lectura': True,
              'publicable': False, 'historico_modificado': False, 'sorteos': {}, 'conclusion': ''}
    for year, draw_id in DRAWS.items():
        entry = {'id': draw_id, 'json': {}, 'pdf': {}, 'pedrea_completa_validada': False}
        report['sorteos'][year] = entry
        url = BASE + '/servicios/resultados2?idsorteo=' + draw_id
        try:
            status, data, ct = get(url)
            detail = json.loads(data.decode('utf-8-sig'))
            if isinstance(detail, list):
                detail = next((x for x in detail if isinstance(x, dict) and str(x.get('drawIdSorteo')) == draw_id), {})
            if not isinstance(detail, dict) or str(detail.get('drawIdSorteo')) != draw_id:
                raise ValueError('ID de sorteo no coincide')
            (OUT / f'navidad_{year}_json.json').write_text(json.dumps(detail, indent=2, ensure_ascii=False), encoding='utf-8')
            entry['json'] = {'http': status, 'nombre': detail.get('nombreDelSorteo'), 'urlListadoOficial': detail.get('urlListadoOficial'),
                             'numero_quintos': len(detail.get('quintosPremios') or []), 'numero_reintegros': len(detail.get('reintegros') or [])}
            raw_path = detail.get('urlListadoOficial')
            if not raw_path or not raw_path.lower().endswith('.pdf'):
                raise ValueError('JSON sin enlace PDF oficial')
            pdf_url = urllib.parse.urljoin(BASE, urllib.parse.quote(raw_path, safe='/:'))
            entry['pdf']['url'] = pdf_url
            pdf_status, pdf_data, pdf_ct = get(pdf_url)
            if not pdf_data.startswith(b'%PDF'):
                raise ValueError('La respuesta no es un PDF válido')
            pdf_file = OUT / f'lista_oficial_navidad_{year}.pdf'
            pdf_file.write_bytes(pdf_data)
            entry['pdf'].update({'http': pdf_status, 'bytes': len(pdf_data), 'content_type': pdf_ct, 'cabecera_pdf': True})
            if shutil.which('pdftotext'):
                txt_file = OUT / f'lista_oficial_navidad_{year}.txt'
                subprocess.run(['pdftotext', '-layout', str(pdf_file), str(txt_file)], check=True, timeout=60)
                text = txt_file.read_text(encoding='utf-8', errors='replace')
                entry['pdf']['analisis_texto'] = pdf_analysis(text)
            else:
                entry['pdf']['error_extraccion'] = 'pdftotext no instalado; se conserva PDF para inspección'
        except Exception as exc:
            entry['error'] = type(exc).__name__ + ': ' + str(exc)
    report['conclusion'] = ('Auditoría documental de las listas oficiales. No se afirma haber recuperado la pedrea completa '
                           'hasta comprobar que se pueden extraer y verificar todos sus números y sus importes.')
    (OUT / 'informe_navidad_098.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps({'version': '0.98', 'resultados': {y: {'json': bool(x['json']), 'pdf': x['pdf'].get('http'), 'error': x.get('error')} for y, x in report['sorteos'].items()}}, ensure_ascii=False))

if __name__ == '__main__':
    main()
