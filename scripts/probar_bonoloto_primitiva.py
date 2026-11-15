
"""LotoScan 0.51: diagnóstico de Bonoloto y La Primitiva.

No modifica el histórico ni publica resultados.
Utiliza únicamente la biblioteca estándar de Python.
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


UA = "LotoScan-diagnostic/0.51"
BASE = "https://comprobarloteria.com"

CASES = {
    "bonoloto": ["2026-11-13", "2026-11-12"],
    "primitiva": ["2026-11-12", "2026-11-09"],
}

EXPECTED = {
    "bonoloto": {"6", "5+C", "5", "4", "3", "R"},
    "primitiva": {"6+R", "6", "5+C", "5", "4", "3", "R"},
}


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.rows = []
        self.row = None
        self.cell = None
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.skip += 1

        if self.skip:
            return

        if tag == "tr":
            self.row = []

        elif tag in ("td", "th") and self.row is not None:
            self.cell = []

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"):
            self.skip = max(0, self.skip - 1)
            return

        if self.skip:
            return

        if tag in ("td", "th") and self.cell is not None and self.row is not None:
            self.row.append(" ".join(" ".join(self.cell).split()))
            self.cell = None

        if tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None

    def handle_data(self, data):
        if self.skip or not data.strip():
            return

        s = data.strip()
        self.parts.append(s)

        if self.cell is not None:
            self.cell.append(s)


def get(url):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "text/html",
        },
    )

    with urllib.request.urlopen(req, timeout=20) as response:
        return (
            response.status,
            response.headers.get("Content-Type", ""),
            response.read(600000).decode("utf-8", "replace"),
        )


def money(s):
    if "sin acertantes" in s.casefold():
        return None

    m = re.search(
        r"(\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2})\s*€",
        s,
    )

    if not m:
        return None

    return int(
        m.group(1).replace(".", "").replace(",", "")
    )


def category(s):
    t = s.casefold()

    if "reintegro" in t:
        return "R"

    if "especial" in t and "6" in t:
        return "6+R"

    if re.search(r"5\s*aciertos\s*\+\s*c", t):
        return "5+C"

    for n in (6, 5, 4, 3):
        if re.search(
            r"(?<!\d)" + str(n) + r"\s*aciertos",
            t,
        ):
            return str(n)

    return None


def extract(game, day, page):
    text = " ".join(" ".join(page.parts).split())

    result = {
        "fecha": day,
        "juego": game,
        "completo": False,
    }

    # Busca la sección del resultado del sorteo.
    pat = (
        r"Resultado de (?:Bonoloto|La Primitiva)"
        r"\s*[·\-]\s*Sorteo\s*\d+"
        r"(?P<section>.*?)Comprobar este sorteo"
    )

    m = re.search(pat, text, re.I | re.S)

    if not m:
        result["error"] = "No se identificó la sección del sorteo"
        return result

    section = m.group("section")

    numbers = re.search(
        r"(?<!\d)((?:\d{1,2}\s+){5}\d{1,2})"
        r"\s+Complementario\s+(\d{1,2})"
        r"\s+Reintegro\s+(\d)",
        section,
        re.I,
    )

    if not numbers:
        result["error"] = "No se identificó la combinación"
        return result

    nums = list(map(int, numbers.group(1).split()))
    comp = int(numbers.group(2))
    rein = int(numbers.group(3))

    if not (
        len(nums) == 6
        and len(set(nums)) == 6
        and all(1 <= x <= 49 for x in nums)
        and 1 <= comp <= 49
        and comp not in nums
        and 0 <= rein <= 9
    ):
        result["error"] = "Combinación fuera de rango"
        return result

    result.update(
        numeros=sorted(nums),
        complementario=comp,
        reintegro=rein,
    )

    if game == "primitiva":
        joker = re.search(
            r"\bJoker\s+(\d{7})\b",
            section,
            re.I,
        )

        if joker:
            result["joker"] = joker.group(1)
        else:
            result["advertencia_joker"] = (
                "No encontrado; requiere revisión"
            )

    prizes = {}

    for row in page.rows:
        if len(row) < 3:
            continue

        cat = category(row[0])

        if cat is None or cat not in EXPECTED[game]:
            continue

        if cat in prizes:
            result.setdefault("errores", []).append(
                "Categoría duplicada: " + cat
            )
            continue

        try:
            winners = int(re.sub(r"\D", "", row[1]))
        except ValueError:
            result.setdefault("errores", []).append(
                "Acertantes ilegibles: " + cat
            )
            continue

        amount = money(row[2])

        if amount is None and not (
            winners == 0
            and "sin acertantes" in row[2].casefold()
        ):
            result.setdefault("errores", []).append(
                "Importe ausente: " + cat
            )
            continue

        prizes[cat] = {
            "acertantes": winners,
            "importe_centimos": amount,
        }

    result["categorias"] = prizes
    result["categorias_encontradas"] = len(prizes)

    result["completo"] = (
        set(prizes) == EXPECTED[game]
        and not result.get("errores")
        and (
            game != "primitiva"
            or "joker" in result
        )
    )

    result["estado"] = (
        "estructura_completa_no_contrastada"
        if result["completo"]
        else "revision_necesaria"
    )

    return result


def main():
    report = {
        "version": "0.51",
        "fecha_utc": datetime.now(timezone.utc).isoformat(),
        "publica_resultados": False,
        "modifica_historico": False,
        "pruebas": [],
    }

    p = urlsplit(BASE)

    try:
        status, _, rules = get(
            f"{p.scheme}://{p.netloc}/robots.txt"
        )

        if status != 200:
            raise RuntimeError(
                "robots.txt no verificable"
            )

        rp = urllib.robotparser.RobotFileParser()
        rp.parse(rules.splitlines())

    except Exception as exc:
        report["error_general"] = (
            "No se pudo comprobar robots.txt: "
            + str(exc)[:180]
        )
        rp = None

    count = 0

    for game, dates in CASES.items():
        for day in dates:
            url = f"{BASE}/{game}/{day}/"

            item = {
                "juego": game,
                "fecha": day,
                "url": url,
                "completo": False,
            }

            if rp is None or not rp.can_fetch(UA, url):
                item["estado"] = (
                    "consulta_no_autorizada_o_no_verificada"
                )

            else:
                if count:
                    time.sleep(2)

                count += 1

                try:
                    status, content_type, html = get(url)
                    item["http"] = status

                    if (
                        status == 200
                        and "html" in content_type.lower()
                    ):
                        parser = Page()
                        parser.feed(html)

                        item.update(
                            extract(game, day, parser)
                        )

                    else:
                        item["estado"] = "respuesta_no_html"

                except Exception as exc:
                    item["estado"] = "error"
                    item["detalle"] = str(exc)[:180]

            report["pruebas"].append(item)

    Path("informe-lotoscan-051.json").write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    completas = sum(
        x["completo"] for x in report["pruebas"]
    )

    print(
        "LotoScan 0.51: completas",
        completas,
        "/",
        len(report["pruebas"]),
    )


if __name__ == "__main__":
    main()


