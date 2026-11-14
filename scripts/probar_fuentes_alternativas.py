
"""Diagnóstico de accesibilidad; no extrae ni publica resultados.
Respeta robots.txt cuando es accesible. Una petición por origen.
"""
import json
import urllib.request
import urllib.error
import urllib.robotparser
from datetime import datetime, timezone
from pathlib import Path

SOURCES = {
    'lawebdelaprimitiva_historico': 'https://lawebdelaprimitiva.com/Euromillones/Historico%20de%20sorteos.html',
    'comprobarloteria_euromillones': 'https://comprobarloteria.com/euromillones/2026-11-13/',
}
UA = 'LotoScan-availability-audit/0.45'

def probe(name, url):
    from urllib.parse import urlsplit
    parts = urlsplit(url)
    robots_url = f'{parts.scheme}://{parts.netloc}/robots.txt'
    result = {'fuente': name, 'url': url, 'robots_url': robots_url}
    rp = urllib.robotparser.RobotFileParser()
    try:
        req = urllib.request.Request(robots_url, headers={'User-Agent': UA})
        with urllib.request.urlopen(req, timeout=12) as resp:
            robots_text = resp.read(100_000).decode('utf-8', 'replace')
        rp.parse(robots_text.splitlines())
        allowed = rp.can_fetch(UA, url)
        result['robots_permite'] = allowed
        if not allowed:
            result['estado'] = 'no_consultado_por_robots'
            return result
    except Exception as exc:
        result['estado'] = 'no_consultado_sin_verificar_robots'
        result['detalle'] = str(exc)[:180]
        return result
    try:
        req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'text/html'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            chunk = resp.read(150_000)
            result.update({'http': resp.status, 'tipo': resp.headers.get('Content-Type', ''),
                           'url_final': resp.geturl(), 'bytes_muestra': len(chunk),
                           'estado': 'accesible_no_validado'})
    except Exception as exc:
        result.update({'estado': 'error', 'detalle': str(exc)[:180]})
    return result

report = {'fecha_utc': datetime.now(timezone.utc).isoformat(),
          'fuentes': [probe(name, url) for name, url in SOURCES.items()],
          'datos_publicados': False,
          'nota': 'Accesibilidad no implica permiso de extracción, precisión ni importes completos.'}
Path('diagnostico-alternativas.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report, ensure_ascii=False, indent=2))

