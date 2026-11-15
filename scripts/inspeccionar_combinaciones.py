
"""LotoScan 0.58: diagnóstico de marcado de combinaciones, solo lectura."""
import json
import re
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

BASE = 'https://comprobarloteria.com'
PAGES = {'eurodreams':'/eurodreams/', 'gordo_primitiva':'/el-gordo/',
         'loteria_nacional':'/loteria-nacional/', 'quiniela':'/quiniela/'}
OUTPUT = Path('informe-lotoscan-058.json')

class Inspect(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.elements = []
        self.sections = []
        self.tokens = []
        self.capture = None
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self.stack.append((tag,a))
        if tag in ('script','style','noscript'):
            self.hidden += 1
        if tag in ('h1','h2','h3','section','article','li','span','div','strong','p'):
            classes = a.get('class','')
            ident = a.get('id','')
            if re.search(r'ball|bola|numero|number|sue.n|clave|quiniela|pleno|resultado|reintegro|premio|match|partido|signo|combinacion|draw|sorteo', classes+' '+ident, re.I):
                if len(self.elements) < 220:
                    self.elements.append({'tag':tag,'class':classes[:160],'id':ident[:100],
                                          'data':{k:v[:100] for k,v in a.items() if k.startswith('data-') and isinstance(v,str)}})

    def handle_data(self, data):
        if self.hidden:
            return
        s = re.sub(r'\s+',' ',data).strip()
        if s and len(self.tokens) < 2200:
            self.tokens.append(s[:160])

    def handle_endtag(self, tag):
        if tag in ('script','style','noscript') and self.hidden:
            self.hidden -= 1
        for i in range(len(self.stack)-1,-1,-1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break

def inspect(path):
    req = urllib.request.Request(BASE+path, headers={'User-Agent':'LotoScanDiagnostic/0.58','Accept':'text/html'})
    with urllib.request.urlopen(req,timeout=25) as r:
        url = r.geturl()
        if urllib.parse.urlsplit(url).hostname not in ('comprobarloteria.com','www.comprobarloteria.com'):
            raise ValueError('Redirección externa')
        if 'html' not in r.headers.get('Content-Type','').lower():
            raise ValueError('Contenido no HTML')
        html = r.read(900_000).decode(r.headers.get_content_charset() or 'utf-8',errors='replace')
    p = Inspect(); p.feed(html)
    # Fragmentos delimitados, para poder diseñar selectores sin deducir resultados.
    cues = ('último resultado','sorteo de lotería nacional','número clave','sueño','pleno al 15','jornada')
    snippets = []
    for i,t in enumerate(p.tokens):
        if any(c in t.lower() for c in cues):
            snippets.append({'indice':i,'tokens':p.tokens[max(0,i-3):i+38]})
        if len(snippets)>=12:
            break
    return {'estado':'html_accesible','url':url,'elementos_con_clases_relevantes':p.elements,
            'fragmentos':snippets,'total_tokens':len(p.tokens),'validado':False,
            'nota':'Solo diagnóstico: no infiere ni publica combinaciones.'}

def main():
    report={'version':'0.58','generado_utc':datetime.now(timezone.utc).isoformat(),
            'publica_resultados':False,'modifica_historico':False,'juegos':{}}
    for game,path in PAGES.items():
        try:
            report['juegos'][game]=inspect(path)
        except Exception as e:
            report['juegos'][game]={'estado':'fallo','error':str(e)[:250]}
    OUTPUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for game,result in report['juegos'].items():
        print(game,result['estado'])
    print('Informe:',OUTPUT)

if __name__=='__main__':
    main()

