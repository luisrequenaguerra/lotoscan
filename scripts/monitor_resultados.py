
"""LotoScan 0.52: consulta multijuego; NO publica premios."""
import json
import time
import urllib.request
import urllib.robotparser
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from extraer_euromillones import Page as EMPage, extract as extract_em
from probar_bonoloto_primitiva import Page as OtherPage, extract as extract_other

TZ = ZoneInfo('Europe/Madrid')
BASE = 'https://comprobarloteria.com'
UA = 'LotoScan-diagnostic/0.52'
OUTPUT = Path('informe-lotoscan-048.json')  # conserva interfaz de 0.50
GAMES = {
    'euromillones': {'days': (1, 4), 'hour': 21},
    'bonoloto': {'days': tuple(range(7)), 'hour': 21},
    'primitiva': {'days': (0, 3, 5), 'hour': 21},
}
ALL_GAMES = ('euromillones', 'primitiva', 'bonoloto', 'loteria_nacional',
             'gordo_primitiva', 'eurodreams', 'quiniela', 'quinigol',
             'lototurf', 'quintuple_plus')


def get(url, limit=600000):
    request = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'text/html'})
    with urllib.request.urlopen(request, timeout=20) as response:
        if urlsplit(response.geturl()).netloc != urlsplit(BASE).netloc:
            raise ValueError('Redireccion externa')
        return response.status, response.headers.get('Content-Type', ''), response.read(limit).decode('utf-8', 'replace')


def pending_dates(now, config):
    result = []
    for delta in range(4):
        day = (now - timedelta(days=delta)).date()
        if day.weekday() in config['days'] and (delta or now.hour >= config['hour']):
            result.append(day.isoformat())
    return result


def run(now):
    report = {'version': '0.52', 'fecha_utc': datetime.now(timezone.utc).isoformat(),
              'fecha_espana': now.isoformat(), 'publica_resultados': False,
              'juegos': {}, 'nota': 'Datos no contrastados; no comprobar premios con este informe.'}
    for game in ALL_GAMES:
        report['juegos'][game] = {'estado': 'pendiente_de_adaptador_validado'} if game not in GAMES else {'estado': 'sin_sorteos_pendientes', 'sorteos': []}
    try:
        status, _, robots_text = get(BASE + '/robots.txt', 100000)
        if status != 200:
            raise ValueError('robots.txt no verificable')
        rp = urllib.robotparser.RobotFileParser()
        rp.parse(robots_text.splitlines())
    except Exception as exc:
        for game in GAMES:
            report['juegos'][game]['estado'] = 'sin_verificacion_robots'
            report['juegos'][game]['detalle'] = str(exc)[:180]
        return report
    requests_done = 0
    for game, config in GAMES.items():
        dates = pending_dates(now, config)
        entry = report['juegos'][game]
        if dates:
            entry['estado'] = 'comprobado'
        for day in dates:
            url = f'{BASE}/{game}/{day}/'
            item = {'fecha': day, 'datos_validos': False}
            entry['sorteos'].append(item)
            if not rp.can_fetch(UA, url):
                item['estado'] = 'no_permitido_por_robots'
                continue
            if requests_done:
                time.sleep(2)
            requests_done += 1
            try:
                status, ctype, html = get(url)
                item['http'] = status
                if status != 200 or 'html' not in ctype.lower():
                    item['estado'] = 'respuesta_no_valida'
                    continue
                if game == 'euromillones':
                    page = EMPage()
                    page.feed(html)
                    data = extract_em(day, page)
                    data.pop('filas_tabla', None)
                    for category in data.get('categorias', {}).values():
                        category.pop('fila', None)
                    item.update(data)
                else:
                    page = OtherPage()
                    page.feed(html)
                    data = extract_other(game, day, page)
                    item.update(data)
                    item['datos_validos'] = data.get('completo') is True
            except Exception as exc:
                item['estado'] = 'error_consulta'
                item['detalle'] = str(exc)[:180]
    return report


if __name__ == '__main__':
    result = run(datetime.now(TZ))
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    for game in GAMES:
        print(game, result['juegos'][game]['estado'], len(result['juegos'][game]['sorteos']))

