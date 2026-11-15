
"""LotoScan 0.59: extracción conservadora, sin modificar histórico."""
import json
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

BASE = 'https://comprobarloteria.com'
PAGES = {'eurodreams': '/eurodreams/', 'gordo_primitiva': '/el-gordo/',
         'loteria_nacional': '/loteria-nacional/', 'quiniela': '/quiniela/'}
MONTHS = {name: i for i, name in enumerate(('enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre').split(), 1)}
OUTPUT = Path('informe-lotoscan-059.json')

class Node:
    def __init__(self, tag='', attrs=None, parent=None):
        self.tag, self.attrs, self.parent = tag, dict(attrs or []), parent
        self.children = []

    def text(self):
        return ' '.join(' '.join(c.split()) if isinstance(c, str) else c.text()
                        for c in self.children).strip()

    def has_class(self, name):
        return name in self.attrs.get('class', '').split()

    def find(self, tag=None, cls=None):
        found = []
        for child in self.children:
            if isinstance(child, Node):
                if (tag is None or child.tag == tag) and (cls is None or child.has_class(cls)):
                    found.append(child)
                found.extend(child.find(tag, cls))
        return found

class Tree(HTMLParser):
    VOID = {'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node('root')
        self.current = self.root

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs, self.current)
        self.current.children.append(node)
        if tag not in self.VOID:
            self.current = node

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        node = self.current
        while node is not self.root:
            if node.tag == tag:
                self.current = node.parent
                return
            node = node.parent

    def handle_data(self, data):
        if self.current.tag not in ('script','style','noscript'):
            self.current.children.append(data)

def fetch(path):
    req = urllib.request.Request(BASE + path, headers={
        'User-Agent': 'LotoScanDiagnostic/0.59', 'Accept': 'text/html'})
    with urllib.request.urlopen(req, timeout=25) as r:
        url = r.geturl()
        if urllib.parse.urlsplit(url).hostname not in ('comprobarloteria.com', 'www.comprobarloteria.com'):
            raise ValueError('Redirección externa')
        if 'html' not in r.headers.get('Content-Type', '').lower():
            raise ValueError('Respuesta no HTML')
        html = r.read(900_000).decode(r.headers.get_content_charset() or 'utf-8', errors='replace')
    tree = Tree()
    tree.feed(html)
    return url, tree.root

def draw_date(root):
    headings = root.find('h2', 'draw-date')
    if len(headings) != 1:
        raise ValueError('Fecha de sorteo ausente o ambigua')
    s = headings[0].text().lower()
    m = re.search(r'\b(\d{1,2}) de ([a-záéíóú]+) de (20\d{2})\b', s)
    if not m or m.group(2) not in MONTHS:
        raise ValueError('Fecha no interpretable')
    day, month, year = int(m.group(1)), MONTHS[m.group(2)], int(m.group(3))
    return datetime(year, month, day).date().isoformat()

def number(node, maximum, label):
    s = node.text().strip()
    if not re.fullmatch(r'\d{1,2}', s) or not 1 <= int(s) <= maximum:
        raise ValueError(f'{label}: número fuera de rango o ambiguo: {s[:40]}')
    return int(s)

def balls(root, count, max_number, extra_max):
    containers = root.find('div', 'draw-numbers')
    if len(containers) != 1:
        raise ValueError('Bloque draw-numbers ausente o duplicado')
    container = containers[0]
    all_balls = container.find('span', 'ball')
    main = [n for n in all_balls if not n.has_class('extra') and not n.has_class('refund')]
    extras = [n for n in all_balls if n.has_class('extra')]
    if len(main) != count or len(extras) != 1:
        raise ValueError(f'Cantidad de bolas inesperada: {len(main)} + {len(extras)}')
    nums = [number(n, max_number, 'principal') for n in main]
    if len(set(nums)) != count:
        raise ValueError('Números principales repetidos')
    return {'numeros': nums, 'extra': number(extras[0], extra_max, 'extra')}

def national(root):
    containers = root.find('div', 'draw-numbers')
    if len(containers) != 1:
        raise ValueError('Bloque draw-numbers ausente o duplicado')
    block = containers[0]
    prizes = block.find('span', 'decimo')
    refunds = block.find('span', 'refund')
    # Los reintegros pueden aparecer también dentro del número premiado:
    # solo se aceptan los span.ball.refund de una sola cifra.
    prizes = [n for n in prizes if n.has_class('ball')]
    refund_digits = [n.text().strip() for n in refunds if n.has_class('ball') and re.fullmatch(r'\d', n.text().strip())]
    if len(prizes) != 2 or any(not re.fullmatch(r'\d{5}', n.text().strip()) for n in prizes):
        raise ValueError('Premios principales no identificados inequívocamente')
    if len(refund_digits) != 3 or len(set(refund_digits)) != 3:
        raise ValueError('Reintegros incompletos o duplicados')
    return {'primer_premio': prizes[0].text().strip(), 'segundo_premio': prizes[1].text().strip(),
            'reintegros': [int(x) for x in refund_digits]}

def quiniela(root):
    matches = root.find('li', 'match-row')
    if len(matches) != 15:
        raise ValueError(f'Esperados 15 partidos, encontrados {len(matches)}')
    rows = []
    for i, match in enumerate(matches, 1):
        positions = match.find('span', 'match-pos')
        if len(positions) != 1 or positions[0].text() != str(i):
            raise ValueError(f'Posición incorrecta en partido {i}')
        scores = match.find('div', 'match-score')
        teams = match.find('div', 'match-teams')
        if len(scores) != 1 or len(teams) != 1:
            raise ValueError(f'Equipos o marcador ambiguos en partido {i}')
        score = scores[0].text()
        m = re.fullmatch(r'(\d+)\s*[-–]\s*(\d+)', score)
        if not m:
            raise ValueError(f'Marcador no interpretable en partido {i}: {score[:40]}')
        a, b = int(m.group(1)), int(m.group(2))
        rows.append({'posicion': i, 'equipos': teams[0].text()[:160], 'marcador': [a,b]})
    signs = [('1' if r['marcador'][0] > r['marcador'][1] else '2' if r['marcador'][0] < r['marcador'][1] else 'X') for r in rows[:14]]
    a, b = rows[14]['marcador']
    pleno = [str(min(a, 3)) if a <= 2 else 'M', str(min(b, 3)) if b <= 2 else 'M']
    # Se calcula a partir de marcadores; se conserva como derivado y NO verificado.
    return {'signos_14_derivados': signs, 'pleno_15_derivado': pleno,
            'partidos': rows, 'advertencia': 'Pronósticos derivados de marcadores; falta contraste con signos publicados.'}

def inspect(game, path):
    url, root = fetch(path)
    base = {'fuente': url, 'fecha': draw_date(root), 'validado_oficialmente': False,
            'publicable': False, 'incorporar_historico': False}
    if game == 'eurodreams':
        base['combinacion'] = balls(root, 6, 40, 5)
    elif game == 'gordo_primitiva':
        base['combinacion'] = balls(root, 5, 54, 9)
    elif game == 'loteria_nacional':
        base['combinacion'] = national(root)
    elif game == 'quiniela':
        base['combinacion'] = quiniela(root)
    base['estado'] = 'extraido_sin_verificacion_oficial'
    return base

def main():
    report = {'version': '0.59', 'generado_utc': datetime.now(timezone.utc).isoformat(),
              'fuente': BASE, 'publica_resultados': False, 'modifica_historico': False,
              'juegos': {}}
    for game, path in PAGES.items():
        try:
            report['juegos'][game] = inspect(game, path)
        except Exception as e:
            report['juegos'][game] = {'estado': 'pendiente', 'motivo': str(e)[:250],
                                     'validado_oficialmente': False, 'publicable': False}
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    for game, result in report['juegos'].items():
        print(game, result['estado'], result.get('motivo', ''))
    print('Informe:', OUTPUT)

if __name__ == '__main__':
    main()

