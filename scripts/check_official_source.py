
"""Conservative connectivity/structure audit; NEVER publishes lottery results.
Run with GitHub Actions or locally. The provider HTML has not yet been verified
as a machine-readable source of complete prizes and El Millón.
"""
import datetime as dt
import sys
import urllib.request
from html.parser import HTMLParser

class Text(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts=[]
    def handle_data(self, data):
        if data.strip(): self.parts.append(data.strip())

url='https://www.loteriasyapuestas.es/f/loterias/resultados/euromillones.html?game_id=EMIL&fecha_sorteo=20261113'
print('Auditoría de disponibilidad de fuente SELAE:', url)
try:
    req=urllib.request.Request(url,headers={'User-Agent':'LotoScan-source-audit/0.42 (non-commercial research)'})
    with urllib.request.urlopen(req,timeout=20) as response:
        html=response.read(2_000_000).decode('utf-8','replace')
        print('HTTP:',response.status,'bytes:',len(html))
    p=Text();p.feed(html)
    text=' '.join(p.parts)
    markers=['EUROMILLONES','13/11/2026','EL MILLÓN','5 + 2','5+2']
    for marker in markers: print('Marcador',repr(marker),':',marker.casefold() in text.casefold())
    print('Auditoría completada. Sin cambios en resultados: no existe extractor validado.')
except Exception as exc:
    print('No se pudo verificar la fuente:',str(exc))
    print('El histórico permanece sin cambios. Ningún boleto se marca como no premiado.')
    sys.exit(1)

