
"""LotoScan 0.54 — diagnóstico de enlaces; no extrae ni publica premios."""
import json
import re
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

BASE = "https://www.comprobarloteria.com/"
GAMES = {
    "eurodreams": ("eurodreams",),
    "gordo_primitiva": ("gordo", "primitiva"),
    "loteria_nacional": ("loteria", "nacional"),
    "lototurf": ("lototurf",),
    "quiniela": ("quiniela",),
    "quinigol": ("quinigol",),
    "quintuple_plus": ("quintuple",),
}
OUT = Path("informe-lotoscan-054.json")

class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.items = []
        self.href = None
        self.text = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.href = dict(attrs).get("href")
            self.text = []

    def handle_data(self, data):
        if self.href is not None:
            self.text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.href is not None:
            self.items.append((self.href, " ".join(self.text)))
            self.href = None
            self.text = []

def fetch(url):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "LotoScanDiagnostic/0.54 (contact: repository maintainer)",
            "Accept": "text/html"
        }
    )
    with urllib.request.urlopen(req, timeout=18) as res:
        final = res.geturl()
        content_type = res.headers.get("Content-Type", "")
        if "html" not in content_type.lower():
            raise ValueError("La respuesta no es HTML: " + content_type)
        raw = res.read(600_000)
        charset = res.headers.get_content_charset() or "utf-8"
        return final, raw.decode(charset, errors="replace")

def main():
    report = {
        "version": "0.54",
        "generado_utc": datetime.now(timezone.utc).isoformat(),
        "publica_resultados": False,
        "modifica_historico": False,
        "objetivo": "Localizar posibles páginas de los siete juegos pendientes; NO valida resultados.",
        "fuente": BASE,
        "juegos": {}
    }

    try:
        final, html = fetch(BASE)
        parser = Links()
        parser.feed(html)

        links = []
        for href, label in parser.items:
            url = urllib.parse.urljoin(final, href)
            p = urllib.parse.urlparse(url)

            if (
                p.scheme not in ("http", "https")
                or p.netloc.lower() not in (
                    "comprobarloteria.com",
                    "www.comprobarloteria.com"
                )
            ):
                continue

            links.append({
                "url": url,
                "texto": re.sub(r"\s+", " ", label).strip()[:120]
            })

        report["acceso"] = "correcto"
        report["enlaces_internos_detectados"] = len(links)

        for game, terms in GAMES.items():
            hits = [
                link for link in links
                if all(
                    t in (link["url"] + " " + link["texto"]).lower()
                    for t in terms
                )
            ]

            # A matching URL is a candidate,
            # not evidence of an extractable result.
            report["juegos"][game] = {
                "estado": (
                    "enlaces_candidatos"
                    if hits else "sin_enlaces_en_portada"
                ),
                "candidatos": hits[:12]
            }

    except Exception as exc:
        report["acceso"] = "fallido"
        report["error"] = str(exc)

        for game in GAMES:
            report["juegos"][game] = {
                "estado": "sin_diagnosticar",
                "candidatos": []
            }

    OUT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )

    print(json.dumps(report, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()

