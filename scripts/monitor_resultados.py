
"""LotoScan 0.48: monitor multijuego sin publicación ni modificación de resultados.
Solo Euromillones está habilitado como piloto. El resto requiere adaptadores validados.
"""
import json
import time
import urllib.request
import urllib.robotparser
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from urllib.parse import urlsplit

from extraer_euromillones import Page, extract

TZ = ZoneInfo('Europe/Madrid')
UA = 'LotoScan-diagnostic/0.48'
BASE = 'https://comprobarloteria.com/euromillones/{}/'
OUTPUT = Path('informe-lotoscan-048.json')
# weekday: lunes=0. No habilitar juegos sin extractor y reglas de premios probados.
GAMES = {
    'euromillones': {'enabled': True, 'days': [1, 4], 'earliest_hour': 21},
    'primitiva': {'enabled': False},
    'bonoloto': {'enabled': False},
    'loteria_nacional': {'enabled': False},
    'gordo_primitiva': {'enabled': False},
    'eurodreams': {'enabled': False},
    'quiniela': {'enabled': False},
    'quinigol': {'enabled': False},
    'lototurf': {'enabled': False},
    'quintuple_plus': {'enabled': False},
}

def get(url, limit=500_000):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'text/html'})
    with urllib.request.urlopen(req, timeout=15) as response:
        return response.status, response.headers.get('Content-Type', ''), response.read(limit).decode('utf-8', 'replace')

def pending_dates(now, config):
    """Revisa sorteos de los últimos 3 días; espera a hora orientativa del sorteo."""
    dates = []
    for days_ago in range(4):
        d = (now - timedelta(days=days_ago)).date()
        if d.weekday() not in config['days']:
            continue
        if days_ago == 0 and now.hour < config['earliest_hour']:
            continue
        dates.append(d.isoformat())
    return dates

def run(now):
    report = {
        'version': '0.48', 'fecha_utc': datetime.now(timezone.utc).isoformat(),
        'fecha_espana': now.isoformat(), 'publica_resultados': False,
        'juegos': {}, 'nota': 'Diagnostico; no certifica premios ni derechos de reutilizacion.'
    }
    for name, cfg in GAMES.items():
        if not cfg['enabled']:
            report['juegos'][name] = {'estado': 'pendiente_de_adaptador_validado'}
            continue
        dates = pending_dates(now, cfg)
        entry = {'estado': 'sin_sorteos_pendientes' if not dates else 'comprobado', 'sorteos': []}
        report['juegos'][name] = entry
        if not dates:
            continue
        origin = urlsplit(BASE).netloc
        try:
            status, _, robots = get(f'https://{origin}/robots.txt', 100_000)
            if status != 200:
                raise ValueError('robots.txt no verificado')
            rp = urllib.robotparser.RobotFileParser()
            rp.parse(robots.splitlines())
        except Exception as exc:
            entry['estado'] = 'sin_verificacion_robots'
            entry['detalle'] = str(exc)[:180]
            continue
        for i, date in enumerate(dates):
            url = BASE.format(date)
            item = {'fecha': date, 'datos_validos': False}
            entry['sorteos'].append(item)
            if not rp.can_fetch(UA, url):
                item['estado'] = 'no_permitido_por_robots'
                continue
            if i:
                time.sleep(2)
            try:
                status, content_type, html = get(url)
                item['http'] = status
                if status != 200 or 'html' not in content_type.lower():
                    item['estado'] = 'respuesta_no_valida'
                    continue
                parser = Page()
                parser.feed(html)
                data = extract(date, parser)
                # Evita guardar muestras HTML innecesarias en el informe.
                data.pop('filas_tabla', None)
                for cat in data.get('categorias', {}).values():
                    cat.pop('fila', None)
                item.update(data)
            except Exception as exc:
                item['estado'] = 'error_consulta'
                item['detalle'] = str(exc)[:180]
    return report

if __name__ == '__main__':
    report = run(datetime.now(TZ))
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Monitor ejecutado. Publicacion desactivada.')
    for name, game in report['juegos'].items():
        print(name, game['estado'], len(game.get('sorteos', [])))

