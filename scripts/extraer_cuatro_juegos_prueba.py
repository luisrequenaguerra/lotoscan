
"""LotoScan 0.56: extracción exploratoria, sin modificar el histórico."""
import json
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

BASE = 'https://comprobarloteria.com'
PAGES = {
    'eurodreams': '/eurodreams/',
    'gordo_primitiva': '/el-gordo/',
    'loteria_nacional': '/loteria-nacional/',
    'quiniela': '/quiniela/',
}
OUT = Path('informe-lotoscan-056.json')


def clean(value):
    return re.sub(r'\s+', ' ', value).strip()


class ExtractHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.tables = []
        self.table = None
        self.row = None
        self.cell = None
        self.heading = None
        self.headings = []
        self.text_parts = []
        self.ignore = 0

    def handle_starttag(self, tag, attrs):
        self.stack.append(tag)
        if tag in ('script', 'style', 'noscript'):
            self.ignore += 1
        if tag == 'table':
            self.table = []
        elif tag == 'tr' and self.table is not None:
            self.row = []
        elif tag in ('td', 'th') and self.row is not None:
            self.cell = {'tipo': tag, 'texto': ''}
        elif tag in ('h1', 'h2', 'h3'):
            self.heading = {'nivel': tag, 'texto': ''}

    def handle_data(self, data):
        if self.ignore:
            return
        value = clean(data)
        if not value:
            return
        self.text_parts.append(value)
        if self.cell is not None:
            self.cell['texto'] += ' ' + value
        if self.heading is not None:
            self.heading['texto'] += ' ' + value

    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self.cell is not None:
            self.cell['texto'] = clean(self.cell['texto'])
            self.row.append(self.cell)
            self.cell = None
        elif tag == 'tr' and self.row is not None:
            if self.table is not None and self.row:
                self.table.append(self.row)
            self.row = None
        elif tag == 'table' and self.table is not None:
            self.tables.append(self.table)
            self.table = None
        elif tag in ('h1', 'h2', 'h3') and self.heading is not None:
            self.heading['texto'] = clean(self.heading['texto'])
            self.headings.append(self.heading)
            self.heading = None
        if tag in ('script', 'style', 'noscript') and self.ignore:
            self.ignore -= 1
        if tag in self.stack:
            idx = len(self.stack) - 1 - self.stack[::-1].index(tag)
            self.stack = self.stack[:idx]


def fetch(path):
    url = BASE + path
    req = urllib.request.Request(url, headers={
        'User-Agent': 'LotoScanDiagnostic/0.56', 'Accept': 'text/html',
    })
    with urllib.request.urlopen(req, timeout=25) as response:
        final = response.geturl()
        host = urllib.parse.urlsplit(final).hostname
        if host not in ('comprobarloteria.com', 'www.comprobarloteria.com'):
            raise ValueError('Redirección a dominio inesperado')
        if 'html' not in response.headers.get('Content-Type', '').lower():
            raise ValueError('Respuesta no HTML')
        html = response.read(900_000).decode(
            response.headers.get_content_charset() or 'utf-8', errors='replace'
        )
    return final, html


def inspect(game, path):
    final, html = fetch(path)
    parser = ExtractHTML()
    parser.feed(html)
    headings = parser.headings[:30]
    dates = [h['texto'] for h in headings if re.search(
        r'\b(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\b',
        h['texto'], re.I)]
    # Filas originales: no reinterpretar todavía importes ni categorías.
    tables = [
        [[{'tipo': c['tipo'], 'texto': c['texto']} for c in row[:8]]
         for row in table[:70]] for table in parser.tables[:8]
    ]
    # Fragmentos cercanos a pistas de combinaciones; son indicios, no números certificados.
    parts = parser.text_parts
    keywords = ('combinación', 'combinacion', 'números', 'numeros',
                'sueño', 'reintegro', 'clave', 'pleno al 15', 'primer premio',
                'segundo premio', 'resultado', 'premios')
    snippets = []
    for i, part in enumerate(parts):
        if any(k in part.lower() for k in keywords):
            snippets.append(clean(' '.join(parts[max(0, i-2):i+14]))[:450])
        if len(snippets) >= 24:
            break
    return {
        'estado': 'datos_brutos_obtenidos', 'url': final,
        'fechas_candidatas': dates[:5], 'titulos': headings,
        'tablas': tables, 'fragmentos_candidatos': snippets,
        'numero_tablas': len(parser.tables),
        'validado': False, 'publicable': False,
        'nota': 'Los datos son HTML bruto. No son combinaciones ni premios validados.'
    }


def main():
    report = {
        'version': '0.56',
        'generado_utc': datetime.now(timezone.utc).isoformat(),
        'fuente': BASE, 'modifica_historico': False,
        'publica_resultados': False, 'juegos': {},
    }
    for game, path in PAGES.items():
        try:
            report['juegos'][game] = inspect(game, path)
        except Exception as exc:
            report['juegos'][game] = {
                'estado': 'fallo', 'error': str(exc)[:300], 'validado': False
            }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Informe generado:', OUT)
    for game, result in report['juegos'].items():
        print(game, result['estado'], 'tablas:', result.get('numero_tablas', 0))


if __name__ == '__main__':
    main()

