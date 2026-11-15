
"""LotoScan 0.51.1 - Diagnostico HTML de Bonoloto y Primitiva.

No publica resultados ni modifica el historico.
Genera informe-lotoscan-051.json para el workflow existente.
"""

import json
import re
import time
import urllib.request
import urllib.robotparser

from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit


VERSION = "0.51.1"
BASE = "https://comprobarloteria.com"
UA = "LotoScan-diagnostic/0.51.1"

CASES = {
    "bonoloto": [
        "2026-11-13",
        "2026-11-12",
    ],
    "primitiva": [
        "2026-11-12",
        "2026-11-09",
    ],
}

KEYWORDS = (
    "resultado",
    "sorteo",
    "combinacion",
    "combinación",
    "complementario",
    "reintegro",
    "joker",
    "acertantes",
    "premios",
    "categoria",
    "categoría",
    "bonoloto",
    "primitiva",
)


class Page(HTMLParser):

    def __init__(self):
        super().__init__(convert_charrefs=True)

        self.parts = []
        self.headings = []
        self.rows = []

        self.skip = []
        self.heading = None
        self.cell = None
        self.row = None

    def handle_starttag(self, tag, attrs):

        if tag in ("script", "style", "noscript"):
            self.skip.append(tag)
            return

        if self.skip:
            return

        if tag in ("h1", "h2", "h3", "h4"):
            self.heading = {
                "nivel": tag,
                "texto": [],
            }

        elif tag == "tr":
            self.row = []

        elif tag in ("td", "th") and self.row is not None:
            self.cell = []

    def handle_data(self, data):

        if self.skip:
            return

        value = " ".join(data.split())

        if not value:
            return

        self.parts.append(value)

        if self.heading is not None:
            self.heading["texto"].append(value)

        if self.cell is not None:
            self.cell.append(value)

    def handle_endtag(self, tag):

        if self.skip:
            if tag == self.skip[-1]:
                self.skip.pop()
            return

        if (
            tag in ("h1", "h2", "h3", "h4")
            and self.heading is not None
            and self.heading["nivel"] == tag
        ):
            self.headings.append({
                "nivel": tag,
                "texto": " ".join(
                    self.heading["texto"]
                )[:300],
            })
            self.heading = None

        if (
            tag in ("td", "th")
            and self.cell is not None
            and self.row is not None
        ):
            self.row.append(
                " ".join(self.cell)[:250]
            )
            self.cell = None

        if tag == "tr" and self.row is not None:
            if self.row:
                self.rows.append(self.row)
            self.row = None


def get(url, limit=600000):

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "text/html",
        },
    )

    with urllib.request.urlopen(
        request,
        timeout=20,
    ) as response:

        raw = response.read(limit)

        charset = (
            response.headers.get_content_charset()
            or "utf-8"
        )

        return {
            "http": response.status,
            "url_final": response.geturl(),
            "content_type": response.headers.get(
                "Content-Type", ""
            ),
            "html": raw.decode(
                charset, errors="replace"
            ),
        }


def fragments(text):

    output = []
    seen = set()

    for word in KEYWORDS:

        matches = list(
            re.finditer(
                re.escape(word),
                text,
                flags=re.IGNORECASE,
            )
        )

        for match in matches[:3]:

            start = max(0, match.start() - 130)
            end = min(
                len(text),
                match.end() + 230,
            )

            fragment = text[start:end]

            if fragment in seen:
                continue

            seen.add(fragment)

            output.append({
                "termino": word,
                "texto": fragment,
            })

            if len(output) >= 25:
                return output

    return output


def inspect_page(game, day, html):

    parser = Page()
    parser.feed(html)

    text = " ".join(parser.parts)
    text = re.sub(r"\s+", " ", text)

    relevant_rows = []

    for row in parser.rows:

        joined = " ".join(row).casefold()

        if any(
            word in joined
            for word in (
                "acierto",
                "premio",
                "categoria",
                "categoría",
                "reintegro",
                "especial",
                "complementario",
            )
        ):
            relevant_rows.append(row)

    return {
        "juego": game,
        "fecha": day,
        "caracteres_html": len(html),
        "caracteres_texto": len(text),
        "inicio_texto": text[:1800],
        "encabezados": parser.headings[:35],
        "total_filas_tabla": len(parser.rows),
        "primeras_filas": parser.rows[:15],
        "filas_relevantes": relevant_rows[:25],
        "fragmentos": fragments(text),
        "diagnostico_completo": True,
        "extraccion_validada": False,
    }


def main():

    report = {
        "version": VERSION,
        "fecha_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "publica_resultados": False,
        "modifica_historico": False,
        "tipo": "diagnostico_html",
        "pruebas": [],
    }

    parsed = urlsplit(BASE)

    robots_url = (
        f"{parsed.scheme}://"
        f"{parsed.netloc}/robots.txt"
    )

    try:
        response = get(
            robots_url,
            limit=100000,
        )

        if response["http"] != 200:
            raise ValueError(
                "robots.txt no disponible"
            )

        robots = urllib.robotparser.RobotFileParser()
        robots.parse(
            response["html"].splitlines()
        )

    except Exception as exc:

        robots = None
        report["error_robots"] = str(exc)[:200]

    requests_done = 0

    for game, dates in CASES.items():

        for day in dates:

            url = f"{BASE}/{game}/{day}/"

            item = {
                "juego": game,
                "fecha": day,
                "url": url,
                "diagnostico_completo": False,
                "extraccion_validada": False,
            }

            if (
                robots is None
                or not robots.can_fetch(UA, url)
            ):
                item["estado"] = (
                    "consulta_no_permitida_o_no_verificada"
                )

                report["pruebas"].append(item)
                continue

            if requests_done:
                time.sleep(2)

            requests_done += 1

            try:

                response = get(url)

                item["http"] = response["http"]
                item["url_final"] = response["url_final"]

                if (
                    response["http"] != 200
                    or "html" not in response[
                        "content_type"
                    ].lower()
                ):
                    item["estado"] = (
                        "respuesta_no_html"
                    )

                elif (
                    urlsplit(
                        response["url_final"]
                    ).netloc
                    != parsed.netloc
                ):
                    item["estado"] = (
                        "redireccion_externa_no_analizada"
                    )

                else:

                    result = inspect_page(
                        game,
                        day,
                        response["html"],
                    )

                    item.update(result)

                    item["estado"] = (
                        "diagnostico_generado"
                    )

            except Exception as exc:

                item["estado"] = "error"
                item["detalle"] = str(exc)[:200]

            report["pruebas"].append(item)

    output = Path(
        "informe-lotoscan-051.json"
    )

    output.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    completed = sum(
        item["diagnostico_completo"]
        for item in report["pruebas"]
    )

    print(
        "LotoScan",
        VERSION,
        "- diagnosticos:",
        completed,
        "/",
        len(report["pruebas"]),
    )

    for item in report["pruebas"]:
        print(
            item["juego"],
            item["fecha"],
            item.get("estado"),
            item.get("http", "-"),
        )


if __name__ == "__main__":
    main()

