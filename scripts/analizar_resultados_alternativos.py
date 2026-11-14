
"""LotoScan 0.46: inspeccion prudente de dos fuentes; NO publica premios.
Una solicitud de robots.txt y una de contenido por dominio, sin reintentos.
"""
import json
import re
import urllib.request
import urllib.robotparser
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

URLS = {
    "lawebdelaprimitiva": "https://lawebdelaprimitiva.com/Euromillones/Historico%20de%20sorteos.html",
    "comprobarloteria": "https://comprobarloteria.com/euromillones/2026-11-13/",
}
AGENTE = "LotoScan-diagnostic/0.46"
PALABRAS = ("13/11/2026", "13 de noviembre", "2026-11-13", "el mill", "estrella", "premio", "categor", "euromill")

class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip = 0
    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.skip += 1
    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self.skip:
            self.skip -= 1
    def handle_data(self, data):
        if not self.skip and data.strip():
            self.parts.append(data.strip())

def analizar(nombre, url):
    resultado = {"fuente": nombre, "url": url, "validado": False}
    p = urlsplit(url)
    robots = f"{p.scheme}://{p.netloc}/robots.txt"
    try:
        with urllib.request.urlopen(urllib.request.Request(robots, headers={"User-Agent": AGENTE}), timeout=12) as r:
            if r.status != 200:
                raise ValueError(f"robots HTTP {r.status}")
            reglas = r.read(100000).decode("utf-8", "replace")
        rp = urllib.robotparser.RobotFileParser()
        rp.parse(reglas.splitlines())
        if not rp.can_fetch(AGENTE, url):
            resultado["estado"] = "no_permitido_por_robots"
            return resultado
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": AGENTE, "Accept": "text/html"}), timeout=18) as r:
            resultado["http"] = r.status
            resultado["url_final"] = r.geturl()
            resultado["content_type"] = r.headers.get("Content-Type", "")
            contenido = r.read(400000).decode("utf-8", "replace")
        if "html" not in resultado["content_type"].lower():
            resultado["estado"] = "formato_no_html"
            return resultado
        lector = VisibleText()
        lector.feed(contenido)
        texto = " ".join(lector.parts)
        texto = re.sub(r"\s+", " ", texto)
        resultado["caracteres_texto"] = len(texto)
        # Fragmentos de inspeccion, NO campos estructurados ni resultados fiables.
        muestras = []
        for palabra in PALABRAS:
            encontrado = re.search(re.escape(palabra), texto, re.IGNORECASE)
            if encontrado:
                muestras.append({"termino": palabra, "fragmento": texto[max(0, encontrado.start()-100):encontrado.end()+180]})
        resultado["muestras"] = muestras
        resultado["estado"] = "html_recibido_pendiente_de_validacion"
    except Exception as exc:
        resultado["estado"] = "error_o_no_verificado"
        resultado["detalle"] = str(exc)[:220]
    return resultado

informe = {
    "fecha_utc": datetime.now(timezone.utc).isoformat(),
    "fuentes": [analizar(nombre, url) for nombre, url in URLS.items()],
    "publica_resultados": False,
    "advertencia": "El acceso y robots.txt no otorgan por si solos permiso de reutilizacion. Los fragmentos NO son premios verificados.",
}
Path("informe-lotoscan-046.json").write_text(json.dumps(informe, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
print(json.dumps(informe, ensure_ascii=False, indent=2))

