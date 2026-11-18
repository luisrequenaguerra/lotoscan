
#!/usr/bin/env python3
"""LotoScan 0.85S: inspección de portada SELAE; nunca publica datos."""
import datetime as dt
import json
import re
import traceback
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

URL = 'https://www.loteriasyapuestas.es/es/resultados'
GAMES = ('bonoloto','euromillones','primitiva','eurodreams','gordo',
         'loteria nacional','quinigol','lototurf','quintuple plus')
OUT = Path('informe_selae_085s.json')

class Extract(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts=[]; self.links=[]; self.current=None; self.text=[]
    def handle_starttag(self, tag, attrs):
        d=dict(attrs)
        if tag=='a':
            self.current=d.get('href',''); self.text=[]
    def handle_data(self, data):
        self.parts.append(data)
        if self.current is not None: self.text.append(data)
    def handle_endtag(self, tag):
        if tag=='a' and self.current is not None:
            self.links.append({'href':self.current,'texto':' '.join(' '.join(self.text).split())[:160]})
            self.current=None; self.text=[]

def main():
    now=dt.datetime.now(dt.timezone.utc)
    report={'version':'0.85S','fecha_utc':now.isoformat(), 'fuente':URL,
            'solo_diagnostico':True,'publicado':False,'juegos_esperados':list(GAMES)}
    try:
        request=urllib.request.Request(URL,headers={
            'User-Agent':'Mozilla/5.0 (compatible; LotoScanDiagnostic/0.85S)',
            'Accept':'text/html,application/xhtml+xml',
            'Cache-Control':'no-cache','Pragma':'no-cache'})
        with urllib.request.urlopen(request,timeout=35) as response:
            raw=response.read(5_000_001)
            if len(raw)>5_000_000: raise ValueError('HTML superior a 5 MB')
            report.update({'http':response.status,'url_final':response.url,
                           'content_type':response.headers.get('Content-Type',''),
                           'last_modified':response.headers.get('Last-Modified',''),
                           'age':response.headers.get('Age',''),
                           'bytes':len(raw)})
        parser=Extract(); parser.feed(raw.decode('utf-8','replace'))
        text=' '.join(' '.join(parser.parts).split())
        report['juegos_mencionados']=[g for g in GAMES if g in text.lower()]
        report['fechas_en_texto']=list(dict.fromkeys(re.findall(
            r'(?<!\d)(?:[0-3]?\d[/.-][01]?\d[/.-]20\d{2})(?!\d)',text)))[:60]
        report['enlaces_notas']=[a for a in parser.links if re.search(
            r'nota\s+de\s+prensa|\.pdf(?:\?|$)',a['texto']+' '+a['href'],re.I)][:80]
        report['enlaces_resultados']=[a for a in parser.links if re.search(
            r'/resultados/|/servicios/',a['href'],re.I)][:50]
        report['fragmentos_resultados']=[]
        for match in list(re.finditer(r'premios|acertantes|nota de prensa|combinaci[oó]n ganadora',text,re.I))[:25]:
            report['fragmentos_resultados'].append(text[max(0,match.start()-90):match.end()+160])
        report['muestra_texto']=text[:1800]
        # No se acepta frescura por la fecha del propio informe: solo fechas observadas.
        report['frescura_confirmada']=False
        report['advertencia']='Las fechas y enlaces detectados son indicios, no sorteos validados. No publicar.'
    except Exception as exc:
        report['error']=f'{type(exc).__name__}: {exc}'
        report['detalle_error']=traceback.format_exc()[-1500:]
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=[f"LotoScan 0.85S | {report['fecha_utc']}",
           f"HTTP: {report.get('http','ERROR')} | bytes: {report.get('bytes',0)}",
           f"Error: {report.get('error','ninguno')}",
           f"Juegos mencionados: {', '.join(report.get('juegos_mencionados',[]))}",
           f"Fechas detectadas: {', '.join(report.get('fechas_en_texto',[]))}",
           f"Enlaces a notas: {len(report.get('enlaces_notas',[]))}",
           'NO SE MODIFICA EL HISTORICO NI LA APP.']
    Path('informe_selae_085s.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('\n'.join(lines),flush=True)

if __name__=='__main__': main()
