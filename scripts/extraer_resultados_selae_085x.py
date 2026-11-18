
#!/usr/bin/env python3
"""LotoScan 0.85X - Diagnóstico ampliado de SELAE.

SOLO LECTURA.
No modifica historico.json.
No publica resultados ni verifica premios.
Requiere el extractor 0.85W en la misma carpeta.
"""

import datetime as dt
import importlib.util
import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent
OLD = BASE / "extraer_resultados_selae_085w.py"

if not OLD.exists():
    raise SystemExit(
        "ERROR: Falta extraer_resultados_selae_085w.py"
    )

spec = importlib.util.spec_from_file_location("selae085w", OLD)
previous = importlib.util.module_from_spec(spec)
spec.loader.exec_module(previous)

VERSION = "0.85X"

FIELDS = {
    "euromillones": [
        "millon", "millón", "codigo", "código"
    ],
    "primitiva": ["joker"],
    "eurodreams": ["sueno", "sueño", "dream"],
    "gordo-primitiva": ["clave"],
    "loteria-nacional": [
        "reintegro", "terminacion", "terminación",
        "aproximacion", "aproximación"
    ],
    "quinigol": [
        "signoganador", "resultado", "escrutinio"
    ],
    "lototurf": [
        "caballo", "complementario", "reintegro"
    ],
    "quintuple-plus": [
        "ganador", "resultado", "escrutinio"
    ],
}

def normalise(s):
    return (
        s.lower()
        .replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
        .replace("ñ", "n")
    )

def candidates(soup, words):
    """Identifica elementos candidatos sin asumir su significado."""
    found = []
    seen = set()

    for element in soup.find_all(True):
        identifier = element.get("id", "")
        classes = element.get("class", [])
        name = element.get("name", "")

        attrs = " ".join(
            [identifier, name] + list(classes)
        )

        normalized = normalise(attrs)

        if not any(
            normalise(word) in normalized
            for word in words
        ):
            continue

        if not attrs.strip():
            continue

        key = (identifier, name, tuple(classes))

        if key in seen:
            continue

        seen.add(key)

        value = previous.text(element)

        found.append({
            "tag": element.name,
            "id": identifier,
            "name": name,
            "class": classes,
            "texto": value[:250],
        })

        if len(found) >= 80:
            break

    return found

def validate_predictions(game, combination):
    errors = []

    if game == "quinigol":
        if len(combination) != 6:
            errors.append("Deben existir seis partidos")

        pattern = re.compile(r"^[012M]-[012M]$")

        for index, result in enumerate(combination, 1):
            if not pattern.fullmatch(result):
                errors.append(
                    f"Partido {index}: formato no reconocido"
                )

    if game == "quintuple-plus":
        if len(combination) != 6:
            errors.append(
                "Deben existir seis posiciones"
            )

        for index, result in enumerate(combination, 1):
            if not re.fullmatch(r"\d{1,2}", result):
                errors.append(
                    f"Posición {index}: valor no numérico"
                )

    return errors

def main():
    report = {
        "version": VERSION,
        "generado_utc": dt.datetime.now(
            dt.timezone.utc
        ).isoformat(),
        "fuente": previous.URL,
        "solo_lectura": True,
        "publicable": False,
        "resultados": [],
        "error": None,
        "aviso": (
            "Los candidatos DOM no son campos confirmados. "
            "La validación es experimental y no permite "
            "publicar resultados ni verificar premios."
        ),
    }

    try:
        import urllib.request
        import urllib.parse

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
                raise RuntimeError(
                    "HTML demasiado grande"
                )

            report["http"] = response.status

        soup = previous.BeautifulSoup(
            raw, "html.parser"
        )

        for game, code in previous.CODES.items():
            result = previous.parse(
                soup, game, code
            )

            result["candidatos_dom"] = candidates(
                soup, FIELDS.get(game, [])
            )

            result["validacion_pronosticos"] = (
                validate_predictions(
                    game, result["combinacion"]
                )
            )

            result["revision_manual_pendiente"] = True
            result["publicable"] = False

            report["resultados"].append(result)

    except Exception as exc:
        report["error"] = (
            f"{type(exc).__name__}: {exc}"
        )

    json_path = Path("informe_selae_085x.json")
    txt_path = Path("informe_selae_085x.txt")

    json_path.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    lines = [
        "LotoScan 0.85X - DIAGNÓSTICO SELAE",
        f"HTTP: {report.get('http', 'ERROR')}",
        "SOLO LECTURA - NO PUBLICABLE",
        ""
    ]

    for result in report["resultados"]:
        lines.append(
            f"JUEGO: {result['juego']}"
        )
        lines.append(
            f"Fecha: {result['fecha']}"
        )
        lines.append(
            f"Combinación: {result['combinacion']}"
        )
        lines.append(
            f"Premios: {len(result['premios'])}"
        )

        for error in result["errores"]:
            lines.append(f"PENDIENTE: {error}")

        for error in result[
            "validacion_pronosticos"
        ]:
            lines.append(
                f"PRONÓSTICO: {error}"
            )

        lines.append("Candidatos DOM:")

        for candidate in result[
            "candidatos_dom"
        ]:
            lines.append(
                json.dumps(
                    candidate,
                    ensure_ascii=False
                )
            )

        lines.append("")

    if report["error"]:
        lines.append(
            "ERROR: " + report["error"]
        )

    lines.append(
        "No se ha modificado historico.json."
    )

    txt_path.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8"
    )

    print("\n".join(lines))

    if report["error"]:
        raise SystemExit(1)

if __name__ == "__main__":
    main()
