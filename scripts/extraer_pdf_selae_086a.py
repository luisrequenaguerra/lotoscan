
#!/usr/bin/env python3
"""LotoScan 0.86A - Extraccion de PDF oficiales SELAE.

Reutiliza las direcciones oficiales de la version 0.85M.
Extrae texto, fechas y candidatos a resultados.

SOLO LECTURA.
No modifica historico.json.
No publica ni verifica premios.
"""

import datetime as dt
import importlib.util
import json
import re
from pathlib import Path
from io import BytesIO

from pypdf import PdfReader

BASE = Path(__file__).resolve().parent
OLD = BASE / "probar_notas_selae_085m.py"

if not OLD.is_file():
    raise SystemExit(
        "ERROR: Falta probar_notas_selae_085m.py"
    )

spec = importlib.util.spec_from_file_location(
    "selae085m", OLD
)
previous = importlib.util.module_from_spec(spec)
spec.loader.exec_module(previous)

VERSION = "0.86A"

GAME_NAMES = [
    "euromillones",
    "primitiva",
    "bonoloto",
    "gordo-primitiva",
    "eurodreams",
    "loteria-nacional",
    "loteria-nacional",
    "loteria-nacional",
    "loteria-nacional",
    "quinigol",
    "lototurf",
    "quintuple-plus",
]

DATE_PATTERN = re.compile(
    r"(?<!\d)(?:"
    r"\d{1,2}[/-]\d{1,2}[/-]20\d{2}"
    r"|20\d{2}[/-]\d{1,2}[/-]\d{1,2}"
    r")(?!\d)"
)

MONEY_PATTERN = re.compile(
    r"\b\d{1,3}(?:\.\d{3})*,\d{2}\s*€"
    r"|\b\d+(?:,\d{2})?\s*€"
)

KEYWORDS = [
    "combinacion",
    "combinación",
    "resultado",
    "reintegro",
    "complementario",
    "estrellas",
    "sueño",
    "clave",
    "joker",
    "premios",
    "categoria",
    "categoría",
    "acertantes",
    "escrutinio",
    "primer premio",
    "segundo premio",
    "terminaciones",
    "aproximaciones",
    "caballo",
    "millon",
    "millón",
]


def normalize(value):
    return (
        value.lower()
        .replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
        .replace("ñ", "n")
    )


def relevant_lines(text):
    """Extrae lineas relevantes con su contexto."""
    lines = text.splitlines()
    results = []
    seen = set()

    for index, line in enumerate(lines):
        normalized = normalize(line)

        if not any(
            normalize(word) in normalized
            for word in KEYWORDS
        ):
            continue

        start = max(0, index - 1)
        end = min(len(lines), index + 4)

        block = "\n".join(lines[start:end]).strip()

        if block and block not in seen:
            seen.add(block)
            results.append({
                "linea": index + 1,
                "contenido": block[:1200],
            })

    return results[:120]


def extract_pdf(url, game, index):
    """Descarga y analiza un PDF oficial."""
    item = {
        "documento": index,
        "juego": game,
        "url": url,
        "fuente": "SELAE_PDF",
        "publicable": False,
        "validado": False,
        "error": None,
        "paginas": [],
        "fechas_candidatas": [],
        "importes_candidatos": [],
        "bloques_relevantes": [],
    }

    try:
        meta, data = previous.fetch(url)
        item["respuesta"] = meta

        if meta.get("http") != 200:
            raise RuntimeError(
                "No se pudo descargar el PDF"
            )

        if not data.startswith(b"%PDF-"):
            raise ValueError(
                "La respuesta no es un PDF"
            )

        reader = PdfReader(BytesIO(data))

        if reader.is_encrypted:
            raise ValueError(
                "PDF cifrado o protegido"
            )

        if len(reader.pages) == 0:
            raise ValueError(
                "PDF sin paginas"
            )

        full_text = []

        for page_number, page in enumerate(
            reader.pages, 1
        ):
            text = page.extract_text(
                extraction_mode="layout"
            ) or ""

            full_text.append(text)

            item["paginas"].append({
                "numero": page_number,
                "caracteres": len(text),
                "texto": text,
            })

        combined = "\n".join(full_text)

        if not combined.strip():
            raise ValueError(
                "PDF sin texto extraible"
            )

        item["total_paginas"] = len(reader.pages)
        item["total_caracteres"] = len(combined)

        item["fechas_candidatas"] = sorted(
            set(DATE_PATTERN.findall(combined))
        )

        item["importes_candidatos"] = (
            MONEY_PATTERN.findall(combined)[:100]
        )

        item["bloques_relevantes"] = (
            relevant_lines(combined)
        )

        item["texto_extraido"] = True
        item["requiere_parser_especifico"] = True

    except Exception as exc:
        item["error"] = (
            f"{type(exc).__name__}: {exc}"
        )

    return item


def main():
    report = {
        "version": VERSION,
        "generado_utc": dt.datetime.now(
            dt.timezone.utc
        ).isoformat(),
        "fuente": "PDF oficiales SELAE",
        "solo_lectura": True,
        "publicable": False,
        "quiniela": "fase_posterior",
        "documentos": [],
        "resumen": {},
    }

    output = Path("diagnostico_pdf_086a")
    output.mkdir(exist_ok=True)

    successful = 0

    for index, url in enumerate(
        previous.SEED_PDFS, 1
    ):
        game = GAME_NAMES[index - 1]

        print(
            f"Analizando {index}/12: {game}",
            flush=True
        )

        item = extract_pdf(url, game, index)

        report["documentos"].append({
            key: value
            for key, value in item.items()
            if key != "paginas"
        })

        filename = (
            f"{index:02d}_{game}.json"
        )

        (output / filename).write_text(
            json.dumps(
                item,
                ensure_ascii=False,
                indent=2
            ),
            encoding="utf-8"
        )

        if item["error"] is None:
            successful += 1

        print(
            "Resultado:",
            "OK" if item["error"] is None
            else item["error"],
            flush=True
        )

    report["resumen"] = {
        "documentos_previstos": len(
            previous.SEED_PDFS
        ),
        "documentos_descargados_y_leidos": successful,
        "documentos_con_error": (
            len(previous.SEED_PDFS) - successful
        ),
        "resultados_estructurados_validados": 0,
    }

    Path("informe_pdf_086a.json").write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    lines = [
        "LOTOSCAN 0.86A",
        "EXTRACCION PDF OFICIALES SELAE",
        "",
        f"Documentos: {len(previous.SEED_PDFS)}",
        f"Leidos: {successful}",
        "",
    ]

    for item in report["documentos"]:
        lines.extend([
            "------------------------------",
            f"Juego: {item['juego']}",
            f"Documento: {item['documento']}",
            f"Paginas: {item.get('total_paginas', 0)}",
            f"Caracteres: {item.get('total_caracteres', 0)}",
            f"Fechas: {item['fechas_candidatas']}",
            f"Importes: {len(item['importes_candidatos'])}",
            f"Bloques: {len(item['bloques_relevantes'])}",
            f"Error: {item['error']}",
            "",
        ])

    lines.extend([
        "Los datos requieren interpretacion.",
        "No se han publicado premios.",
        "historico.json no ha sido modificado.",
    ])

    Path("informe_pdf_086a.txt").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8"
    )

    print("\n".join(lines))

    if successful != len(previous.SEED_PDFS):
        raise SystemExit(
            "Diagnostico incompleto: revisar informes"
        )


if __name__ == "__main__":
    main()
