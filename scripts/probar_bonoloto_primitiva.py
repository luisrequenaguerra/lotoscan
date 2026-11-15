
"""LotoScan 0.51.2: prueba aislada de extracción, sin publicar ni guardar premios."""
import json
import re
import time
import urllib.request
import urllib.robotparser
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

BASE = 'https://comprobarloteria.com'
UA = 'LotoScan-diagnostic/0.51.2'
CASES = {'bonoloto': ['2026-11-13', '2026-11-12'],
         'primitiva': ['2026-11-12', '2026-11-09']}
EXPECTED = {'bonoloto': {'6', '5+C', '5', '4', '3', 'R'},
            'primitiva': {'6+R', '6', '5+C', '5', '4', '3', 'R'}}

class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.rows = [], []
        self.row = self.cell = None
        self.skipped = []

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'noscript'):
            self.skipped.append(tag)
            return
        if self.skipped:
            return
        if tag == 'tr':
            self.row = []
        elif tag in ('td', 'th') and self.row is not None:
            self.cell = []

    def handle_endtag(self, tag):
        if self.skipped:
            if tag == self.skipped[-1]:
                self.skipped.pop()
            return
        if tag in ('td', 'th') and self.cell is not None and self.row is not None:
            self.row.append(' '.join(self.cell))
            self.cell = None
        elif tag == 'tr' and self.row is not None:
            if self.row:
                self.rows.append(self.row)
            self.row = None

    def handle_data(self, data):
        if self.skipped:
            return
        value = ' '.join(data.split())
        if value:
            self.parts.append(value)
            if self.cell is not None:
                self.cell.append(value)


def category(label):
    label = label.casefold()
    if 'reintegro' in label:
        return 'R'
    if re.search(r'especial\s*\(\s*6\s*aciertos\s*\+\s*r\s*\)', label):
        return '6+R'
    m = re.search(r'\(\s*([3456])\s*aciertos(?:\s*\+\s*c)?\s*\)', label)
    if not m:
        return None
    n = m.group(1)
    return '5+C' if n == '5' and re.search(r'\+\s*c\s*\)', label) else n


def amount(value, winners):
    if value.strip().casefold() == 'sin acertantes' and winners == 0:
        return None
    m = re.fullmatch(r'\s*(\d+(?:\.\d{3})*|\d+),([0-9]{2})\s*€\s*', value)
    if not m:
        raise ValueError('Importe no reconocido: ' + value[:80])
    return int(m.group(1).replace('.', '')) * 100 + int(m.group(2))


def extract(game, day, page):
    result = {'juego': game, 'fecha': day, 'completo': False}
    text = ' '.join(page.parts)
    # Delimitación por el bloque del sorteo, no por el encabezado principal.
    match = re.search(
        r'Resultado\s+de\s+(?:La\s+)?' + ('Bonoloto' if game == 'bonoloto' else 'Primitiva') +
        r'\s*[·\-]\s*Sorteo\s+(\d+)\b(.*?)Comprobar\s+este\s+sorteo',
        text, re.I | re.S)
    if not match:
        result['error'] = 'Bloque del sorteo no identificado'
        return result
    section = match.group(2)
    result['numero_sorteo'] = int(match.group(1))
    numbers = re.search(
        r'(?<!\d)((?:\d{1,2}\s+){5}\d{1,2})\s+Complementario\s+(\d{1,2})'
        r'\s+Reintegro\s+(\d)(?!\d)', section, re.I)
    if not numbers:
        result['error'] = 'Combinación no identificada'
        return result
    nums = list(map(int, numbers.group(1).split()))
    comp, rein = int(numbers.group(2)), int(numbers.group(3))
    if not (len(nums) == len(set(nums)) == 6 and all(1 <= n <= 49 for n in nums)
            and 1 <= comp <= 49 and comp not in nums and 0 <= rein <= 9):
        result['error'] = 'Combinación inválida'
        return result
    result.update(numeros=sorted(nums), complementario=comp, reintegro=rein)
    if game == 'primitiva':
        joker = re.search(r'\bJoker\s+(\d{7})(?!\d)', section, re.I)
        if not joker:
            result['error'] = 'Joker ausente'
            return result
        result['joker'] = joker.group(1)
    prizes = {}
    errors = []
    for row in page.rows:
        if len(row) != 3:
            continue
        cat = category(row[0])
        if cat not in EXPECTED[game]:
            continue
        if cat in prizes:
            errors.append('Categoría repetida: ' + cat)
            continue
        try:
            raw = row[1].strip()
            if not re.fullmatch(r'\d+(?:\.\d{3})*', raw):
                raise ValueError('Acertantes inválidos')
            winners = int(raw.replace('.', ''))
            prizes[cat] = {'acertantes': winners,
                           'importe_centimos': amount(row[2], winners)}
        except ValueError as exc:
            errors.append(cat + ': ' + str(exc))
    result['categorias'] = prizes
    result['categorias_encontradas'] = len(prizes)
    result['categorias_faltantes'] = sorted(EXPECTED[game] - set(prizes))
    if errors:
        result['errores'] = errors
    result['completo'] = not errors and set(prizes) == EXPECTED[game]
    result['estado'] = ('estructura_completa_no_contrastada' if result['completo']
                        else 'revision_necesaria')
    return result


def get(url):
    request = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'text/html'})
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.status, response.geturl(), response.headers.get('Content-Type', ''), response.read(600000).decode('utf-8', 'replace')


def main():
    report = {'version': '0.51.2', 'fecha_utc': datetime.now(timezone.utc).isoformat(),
              'publica_resultados': False, 'modifica_historico': False, 'pruebas': []}
    try:
        status, _, _, rules = get(BASE + '/robots.txt')
        if status != 200:
            raise ValueError('robots.txt no verificable')
        rp = urllib.robotparser.RobotFileParser()
        rp.parse(rules.splitlines())
    except Exception as exc:
        rp = None
        report['error_robots'] = str(exc)[:160]
    attempts = 0
    for game, days in CASES.items():
        for day in days:
            url = f'{BASE}/{game}/{day}/'
            item = {'juego': game, 'fecha': day, 'completo': False}
            if rp is None or not rp.can_fetch(UA, url):
                item['estado'] = 'consulta_no_autorizada_o_no_verificada'
            else:
                if attempts:
                    time.sleep(2)
                attempts += 1
                try:
                    status, final_url, content_type, html = get(url)
                    item['http'] = status
                    if (status != 200 or 'html' not in content_type.lower()
                            or urlsplit(final_url).netloc != urlsplit(BASE).netloc):
                        item['estado'] = 'respuesta_inesperada'
                    else:
                        page = Page()
                        page.feed(html)
                        item.update(extract(game, day, page))
                except Exception as exc:
                    item['estado'] = 'error_consulta'
                    item['detalle'] = str(exc)[:160]
            report['pruebas'].append(item)
    Path('informe-lotoscan-051.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('LotoScan 0.51.2:', sum(x['completo'] for x in report['pruebas']),
          '/', len(report['pruebas']), 'extracciones completas')
    for item in report['pruebas']:
        print(item['juego'], item['fecha'], item.get('estado', '-'), item['completo'])

if __name__ == '__main__':
    main()

