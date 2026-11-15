
"""LotoScan 0.55: inspecciona estructura HTML, sin guardar ni publicar resultados."""
import json
import re
import urllib.error
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
MISSING = {
    'lototurf': ['lototurf'],
    'quinigol': ['quinigol'],
    'quintuple_plus': ['quintuple', 'quíntuple', 'quintuple-plus'],
}
OUT = Path('informe-lotoscan-055.json')

class InspectHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.headings = []
        self.tables = []
        self.links = []
        self.current_table = None
        self.current_link = None
        self.current_heading = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.stack.append(tag)
        if tag == 'table':
            self.current_table = {'filas': 0, 'cabeceras': []}
        if tag == 'tr' and self.current_table is not None:
            self.current_table['filas'] += 1
        if tag == 'a':
            self.current_link = {'href': attrs.get('href', ''), 'texto': ''}
        if tag in ('h1', 'h2', 'h3'):
            self.current_heading = {'nivel': tag, 'texto': ''}

    def handle_data(self, data):
        value = re.sub(r'\s+', ' ', data).strip()
        if not value:
            return
        if self.current_link is not None:
            self.current_link['texto'] += ' ' + value
        if self.current_heading is not None:
            self.current_heading['texto'] += ' ' + value
        if self.current_table is not None and self.stack and self.stack[-1] == 'th':
            if len(self.current_table['cabeceras']) < 30:
                self.current_table['cabeceras'].append(value[:80])

    def handle_endtag(self, tag):
        if tag == 'a' and self.current_link is not None:
            self.links.append(self.current_link)
            self.current_link = None
        if tag in ('h1', 'h2', 'h3') and self.current_heading is not None:
            self.headings.append(self.current_heading)
            self.current_heading = None
        if tag == 'table' and self.current_table is not None:
            self.tables.append(self.current_table)
            self.current_table = None
        if tag in self.stack:
            self.stack = self.stack[:len(self.stack)-1-self.stack[::-1].index(tag)]

def fetch(url):
    request = urllib.request.Request(url, headers={
        'User-Agent': 'LotoScanDiagnostic/0.55',
        'Accept': 'text/html',
    })
    with urllib.request.urlopen(request, timeout=20) as response:
        content_type = response.headers.get('Content-Type', '')
        if 'html' not in content_type.lower():
            raise ValueError('Respuesta no HTML: ' + content_type)
        data = response.read(750_000)
        encoding = response.headers.get_content_charset() or 'utf-8'
        return response.geturl(), data.decode(encoding, errors='replace')

def same_site(url):
    host = urllib.parse.urlsplit(url).hostname or ''
    return host in ('comprobarloteria.com', 'www.comprobarloteria.com')

def analyze(url):
    final, html = fetch(url)
    parser = InspectHTML()
    parser.feed(html)
    links = []
    for item in parser.links:
        target = urllib.parse.urljoin(final, item['href'])
        if same_site(target):
            links.append({'url': target, 'texto': item['texto'].strip()[:100]})
    result_links = [x for x in links if any(term in (x['url'] + x['texto']).lower()
                    for term in ('resultado', 'premio', 'escrutinio', 'sorteo', 'comprobar'))]
    return {
        'estado': 'html_accesible', 'url_final': final,
        'titulos': parser.headings[:20], 'tablas': parser.tables[:12],
        'enlaces_relacionados': result_links[:25],
        'indicios_json_ld': 'application/ld+json' in html.lower(),
        'indicios_tablas': len(parser.tables),
        'nota': 'Estructura detectada; ningún resultado extraído o validado.',
    }, links

def main():
    report = {
        'version': '0.55', 'generado_utc': datetime.now(timezone.utc).isoformat(),
        'publica_resultados': False, 'modifica_historico': False,
        'fuente': BASE, 'juegos': {}, 'busqueda_adicional': {},
    }
    for game, path in PAGES.items():
        try:
            report['juegos'][game], _ = analyze(BASE + path)
        except Exception as error:
            report['juegos'][game] = {'estado': 'fallo_acceso', 'error': str(error)[:250]}
    try:
        _, home_links = analyze(BASE + '/')
        for game, terms in MISSING.items():
            hits = [x for x in home_links if any(term in (x['url'] + x['texto']).lower()
                    for term in terms)]
            report['busqueda_adicional'][game] = {
                'estado': 'candidatos_en_portada' if hits else 'sin_candidatos_en_portada',
                'candidatos': hits[:10],
            }
    except Exception as error:
        report['busqueda_adicional'] = {'estado': 'fallo_portada', 'error': str(error)[:250]}
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2, ensure_ascii=False))

if __name__ == '__main__':
    main()

