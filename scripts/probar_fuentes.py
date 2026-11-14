
"""Diagnóstico sin publicar resultados ni eludir restricciones del proveedor."""
import datetime as dt
import json
import urllib.error
import urllib.request
from pathlib import Path

HOY = dt.datetime.now(dt.timezone.utc).date()
URLS = {
    'selae_pagina_rss': 'https://www.loteriasyapuestas.es/es/canales-rss',
    'selae_resultados_web': 'https://www.loteriasyapuestas.es/es/resultados-ultimos-sorteos',
    'selae_nota_euromillones_conocida': 'https://www.loteriasyapuestas.es/f/loterias/documentos/Euromillones/Notas%20de%20prensa/NOTA_DE_PRENSA_EUROMILLONES_13_11_26.pdf',
}

def check(name, url):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'LotoScan/0.44 source availability audit'})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = r.read(250000)
            ct = r.headers.get('Content-Type', '')
            final = r.geturl()
            return {'fuente': name, 'estado': r.status, 'tipo': ct, 'url_final': final,
                    'pdf_valido': data.startswith(b'%PDF') if name.endswith('conocida') else None,
                    'observacion': 'Accesibilidad no demuestra disponibilidad de premios completos ni permiso de reutilizacion'}
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return {'fuente': name, 'error': str(e), 'apta': False}

result = {'fecha_utc': HOY.isoformat(), 'diagnosticos': [check(k,v) for k,v in URLS.items()],
          'publicacion_resultados': False, 'motivo': 'No hay extractor validado ni fuente autorizada confirmada'}
Path('diagnostico-fuentes.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps(result, ensure_ascii=False, indent=2))

