
#!/usr/bin/env python3
"""LotoScan 0.85Y - Diagnostico de resultados SELAE.

Solo lectura. No modifica historico.json.
No publica resultados ni comprueba premios.
Requiere extraer_resultados_selae_085w.py.
"""

import datetime as dt
import importlib.util
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
OLD = BASE / "extraer_resultados_selae_085w.py"

spec = importlib.util.spec_from_file_location("selae085w", OLD)
if spec is None or spec.loader is None:
    raise SystemExit("No se encuentra el extractor 0.85W")

previous = importlib.util.module_from_spec(spec)
spec.loader.exec_module(previous)

VERSION = "0.85Y"


def clean_number(value, digits=1):
    value = value.strip()
    if re.fullmatch(r"\d{" + str(digits) + r"}", value):
        return value
    return None


def game_section(soup, code):
    """Busca el contenedor especifico del juego."""
    return soup.find(id="qa_ultResult-" + code)


def extract_extras(soup, result, game, code):
    """Extrae adicionales con selectores conocidos."""
    extras = result["adicionales"]
    issues = []

    if game == "eurodreams":
        dream = previous.value(
            soup, "qa_ultResult-EDMS-reintegro"
        )
        extras["numero_sueno"] = clean_number(dream)
        if extras["numero_sueno"] is None:
            issues.append("Numero Sueno no confirmado")

    elif game == "gordo-primitiva":
        key = previous.value(
            soup, "qa_ultResult-ELGR-reintegro"
        )
        extras["numero_clave"] = clean_number(key)
        if extras["numero_clave"] is None:
            issues.append("Numero clave no confirmado")

    elif game == "primitiva":
        joker = previous.value(
            soup, "qa_ultResult-LAPR-JOKER"
        )
        joker_digits = re.sub(r"\s+", "", joker)

        extras["joker"] = (
            joker_digits
            if re.fullmatch(r"\d{7}", joker_digits)
            else None
        )

        joker_table = soup.find(
            id="qa_ultResult-JOKER-escrutinio"
        )

        extras["joker_premios"] = []

        if joker_table:
            for row in joker_table.find_all("tr"):
                cells = [
                    previous.text(c)
                    for c in row.find_all(
                        ["th", "td"], recursive=False
                    )
                ]
                if len(cells) >= 2 and "€" in " ".join(cells):
                    extras["joker_premios"].append(cells)

        if extras["joker"] is None:
            issues.append("Joker no confirmado")
        if len(extras["joker_premios"]) != 7:
            issues.append("Premios Joker incompletos")

    elif game == "loteria-nacional":
        raw = extras.get("reintegros", [])
        normalized = []

        for value in raw:
            match = re.fullmatch(
                r"\s*R\s*(\d)\s*", value
            )
            normalized.append(
                match.group(1) if match else None
            )

        extras["reintegros_originales"] = raw
        extras["reintegros"] = normalized

        if len(normalized) != 3 or None in normalized:
            issues.append("Reintegros incompletos")

        issues.append(
            "Faltan terminaciones, aproximaciones "
            "y otras reglas de premios"
        )

    elif game == "euromillones":
        issues.append(
            "El Millon: codigo ganador no confirmado"
        )

    elif game == "lototurf":
        issues.append(
            "Pendiente confirmar caballo ganador "
            "y significado de campos adicionales"
        )

    return issues


def validate_predictions(game, combination):
    issues = []

    if game == "quinigol":
        if len(combination) != 6:
            issues.append("Se esperan seis partidos")

        for index, value in enumerate(combination, 1):
            if not re.fullmatch(
                r"[012M]-[012M]", value
            ):
                issues.append(
                    f"Partido {index}: formato invalido"
                )

        issues.append(
            "Pendiente validar reglas y premios"
        )

    elif game == "quintuple-plus":
        if len(combination) != 6:
            issues.append("Se esperan seis posiciones")

        for index, value in enumerate(combination, 1):
            if not re.fullmatch(r"\d{1,2}", value):
                issues.append(
                    f"Posicion {index}: formato invalido"
                )

        issues.append(
            "Pendiente validar orden, rango "
            "y reglas de premios"
        )

    return issues


def parse_game(soup, game, code):
    result = previous.parse(soup, game, code)

    result["version_extractor"] = VERSION
    result["errores_originales_085w"] = list(
        result["errores"]
    )

    issues = extract_extras(
        soup, result, game, code
    )

    issues.extend(
        validate_predictions(
            game, result["combinacion"]
        )
    )

    result["pendientes_085y"] = issues

    result["revision_manual_pendiente"] = True
    result["validado_para_premios"] = False
    result["publicable"] = False

    return result


def main():
    report = {
        "version": VERSION,
        "fuente": previous.URL,
        "generado_utc": dt.datetime.now(
            dt.timezone.utc
        ).isoformat(),
        "solo_lectura": True,
        "publicable": False,
        "quiniela": "pendiente_fase_posterior",
        "resultados": [],
        "error": None,
        "aviso": (
            "Extraccion experimental. "
            "Los campos requieren verificacion "
            "contra resultados oficiales. "
            "No apto para comprobar premios."
        )
    }

    try:
        request = urllib.request.Request(
            previous.URL,
            headers=previous.HEADERS
        )

        with urllib.request.urlopen(
            request, timeout=40
        ) as response:
            destination = urllib.parse.urlsplit(
                response.url
            )

            if (
                response.status != 200
                or destination.scheme != "https"
                or destination.hostname not in (
                    "www.loteriasyapuestas.es",
                    "loteriasyapuestas.es"
                )
            ):
                raise RuntimeError(
                    "Respuesta o destino inesperado"
                )

            raw = response.read(5_000_001)
            if len(raw) > 5_000_000:
                raise RuntimeError("HTML demasiado grande")

            report["http"] = response.status

        soup = previous.BeautifulSoup(
            raw, "html.parser"
        )

        for game, code in previous.CODES.items():
            result = parse_game(soup, game, code)
            report["resultados"].append(result)

    except Exception as exc:
        report["error"] = (
            f"{type(exc).__name__}: {exc}"
        )

    Path("informe_selae_085y.json").write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    lines = [
        "LotoScan 0.85Y",
        f"HTTP: {report.get('http', 'ERROR')}",
        "SOLO LECTURA - NO PUBLICABLE",
        "La Quiniela: pendiente",
        ""
    ]

    for result in report["resultados"]:
        lines.extend([
            "--------------------------------",
            f"JUEGO: {result['juego']}",
            f"Fecha: {result['fecha']}",
            f"Combinacion: {result['combinacion']}",
            "Adicionales: " + json.dumps(
                result["adicionales"],
                ensure_ascii=False
            ),
            f"Categorias: {len(result['premios'])}",
            "Pendientes:"
        ])

        for issue in result["pendientes_085y"]:
            lines.append(" - " + issue)

        lines.append("Errores originales:")
        for issue in result["errores_originales_085w"]:
            lines.append(" - " + issue)

        lines.append("")

    if report["error"]:
        lines.append("ERROR: " + report["error"])

    lines.append(
        "No se ha modificado historico.json."
    )

    Path("informe_selae_085y.txt").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8"
    )

    print("\n".join(lines))

    if report["error"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
