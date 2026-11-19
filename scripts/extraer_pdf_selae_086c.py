
#!/usr/bin/env python3
"""LotoScan 0.86C: diagnóstico de extracción de PDF oficiales SELAE.
Solo lectura. No modifica historico.json ni publica resultados.
Las 12 URL son muestras históricas de 0.85M, NO enlaces diarios dinámicos.
"""
import datetime as dt
import importlib.util
import json
import re
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "probar_notas_selae_085m.py"
if not SOURCE.is_file():
    raise SystemExit("Falta scripts/probar_notas_selae_085m.py")
spec = importlib.util.spec_from_file_location("selae085m", SOURCE)
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)

GAMES = [
    "euromillones", "primitiva", "bonoloto", "gordo-primitiva",
    "eurodreams", "loteria-nacional-lista", "loteria-nacional-mayores",
    "loteria-nacional-lista", "loteria-nacional-mayores",
    "quinigol", "lototurf", "quintuple-plus",
]
MONTHS = dict(zip(
    "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split(),
    range(1, 13)
))
MONTHS["setiembre"] = 9
MONTH_EXPR = "|".join(MONTHS)
DATE_WORD = re.compile(
    rf"\b(\d{{1,2}})\s+de\s+({MONTH_EXPR})\s+de\s+(20\d{{2}})\b", re.I
)
DATE_DIGIT = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b")
PRIZE_HEADING = re.compile(r"REPARTO DE PREMIOS|CATEGOR[IÍ]AS", re.I)


def date_from(text):
    match = DATE_WORD.search(text)
    if match:
        try:
            return dt.date(int(match[3]), MONTHS[match[2].lower()], int(match[1])).isoformat()
        except ValueError:
            pass
    match = DATE_DIGIT.search(text)
    if match:
        year = int(match[3])
        if year < 100:
            year += 2000
        try:
            return dt.date(year, int(match[2]), int(match[1])).isoformat()
        except ValueError:
            pass
    return None


def result_zone(text):
    """Zona entre la frase de combinación y la recaudación; no cruza tablas."""
    start = re.search(r"combinaci[oó]n ganadora.*?siguientes n[uú]meros\s*:", text, re.I | re.S)
    if not start:
        return ""
    tail = text[start.end():]
    stop = re.search(r"recaudaci[oó]n|REPARTO DE PREMIOS", tail, re.I)
    return tail[:stop.start() if stop else 700][:700]


def prefix_numbers(line):
    """Lee tokens numéricos iniciales, evitando cifras de etiquetas posteriores."""
    result = []
    for match in re.finditer(r"\d{1,2}", line):
        before = line[:match.start()]
        if re.search(r"[A-Za-zÁÉÍÓÚáéíóúñÑ]", before):
            break
        if match.start() and line[match.start()-1].isdigit():
            continue
        result.append(int(match.group()))
    return result


def extract_combination(text, game):
    zone = result_zone(text)
    warnings = []
    expected = 5 if game in ("euromillones", "gordo-primitiva") else 6
    lines = [line for line in zone.splitlines() if line.strip()]
    first = ""
    for line in lines:
        if "Números:" in line or "Numeros:" in line:
            first = re.split(r"N[uú]meros\s*:", line, flags=re.I)[-1]
            break
    if not first:
        first = lines[0] if lines else ""
    numbers = prefix_numbers(first)
    if len(numbers) < expected:
        warnings.append("No se reconocen todos los números principales")
    main = numbers[:expected] if len(numbers) >= expected else None
    extras = {}

    if game == "euromillones":
        m = re.search(r"(\d{1,2})\s*-\s*-\s*-\s*-\s*Estrellas\s*:\s*-\s*(\d{1,2})", zone, re.I)
        extras["estrellas"] = [int(m[1]), int(m[2])] if m else None
        if extras["estrellas"] is None:
            warnings.append("Estrellas no interpretadas")
        code = re.search(r"El Mill[oó]n[\s\S]{0,100}?\b([A-Z]{3}\d{5})\b", text, re.I)
        extras["el_millon"] = code[1] if code else None

    elif game in ("primitiva", "bonoloto"):
        extras["complementario"] = numbers[6] if len(numbers) > 6 else None
        extras["reintegro"] = numbers[7] if len(numbers) > 7 else None
        if extras["complementario"] is None or extras["reintegro"] is None:
            warnings.append("Complementario o reintegro ausente")
        if game == "primitiva":
            joker = re.search(r"JOKER\s*:\s*(\d{7})", zone, re.I)
            extras["joker"] = joker[1] if joker else None

    elif game == "gordo-primitiva":
        extras["clave"] = numbers[5] if len(numbers) > 5 else None

    elif game == "eurodreams":
        m = re.search(r"Sue[ñn]o\s*:\s*(\d)", zone, re.I)
        extras["sueno"] = int(m[1]) if m else None

    elif game == "lototurf":
        extras["caballo_cuarta"] = numbers[6] if len(numbers) > 6 else None
        m = re.search(r"Reintegro\s*:\s*(\d)", zone, re.I)
        extras["reintegro"] = int(m[1]) if m else None

    return main, extras, warnings, zone


def quintuple(text):
    match = re.search(r"1[ªa]\s*Carrera\s*:\s*(.*?)5[ªa]\s*Carrera", text, re.I | re.S)
    if not match:
        return None, ["No se encuentra bloque de las cuatro carreras"]
    block = match[1]
    vals = []

    for i in range(1, 5):
        if i == 1:
            segment = block.split("2ª Carrera")[0]
        else:
            segment_match = re.search(
                rf"{i}[ªa]\s*Carrera\s*:\s*(\d{{1,2}})", block, re.I
            )
            segment = segment_match[1] if segment_match else ""
        found = re.search(r"^\s*(\d{1,2})", segment)
        vals.append(int(found[1]) if found else None)

    if any(v is None for v in vals):
        cleaned = re.sub(r"(\d)([2-4][ªa]\s*Carrera)", r"\1 \2", block)
        head = re.split(r"2[ªa]\s*Carrera", cleaned, maxsplit=1)[0]
        first_four = re.findall(r"\b\d{1,2}\b", head)
        if len(first_four) == 4:
            vals = [int(x) for x in first_four]

    fifth = re.search(
        r"5[ªa]\s*Carrera\s*:\s*Primero\s*:\s*(\d{1,2})\s*Segundo\s*:\s*(\d{1,2})",
        text, re.I | re.S
    )
    result = vals + ([int(fifth[1]), int(fifth[2])] if fifth else [None, None])
    warnings = [] if all(v is not None for v in result) else ["Carreras incompletas"]
    return result, warnings


def quinigol(text):
    rows = []
    for line in text.splitlines():
        m = re.match(
            r"^\s*([1-6])\s+(.+?)\s{2,}(\d+)\s+(\d+)\s+(.+?)\s{2,}([012M]{2})\s*$",
            line
        )
        if m:
            rows.append({
                "partido": int(m[1]),
                "local": m[2].strip(),
                "goles_local": int(m[3]),
                "goles_visitante": int(m[4]),
                "visitante": m[5].strip(),
                "pronostico": m[6],
            })
    return rows


def parse(text, game):
    data = {"fecha": date_from(text), "advertencias": [], "validado": False}

    if game.startswith("loteria-nacional"):
        data["tipo_documento"] = game.rsplit("-", 1)[-1]
        data["advertencias"].append(
            "Pendiente: reconstruir lista completa y reglas de premios por sorteo"
        )
        data["fragmento_inicial"] = text[:2000]

    elif game == "quinigol":
        data["partidos"] = quinigol(text)
        if len(data["partidos"]) != 6:
            data["advertencias"].append("No se extrajeron los seis partidos")

    elif game == "quintuple-plus":
        data["caballos"], warnings = quintuple(text)
        data["advertencias"].extend(warnings)

    else:
        main, extras, warnings, zone = extract_combination(text, game)
        data["combinacion"] = main
        data["adicionales"] = extras
        data["advertencias"].extend(warnings)
        data["zona_resultado"] = zone

        ranges = {
            "euromillones": (1, 50, 5),
            "primitiva": (1, 49, 6),
            "bonoloto": (1, 49, 6),
            "gordo-primitiva": (1, 54, 5),
            "eurodreams": (1, 40, 6),
            "lototurf": (1, 31, 6),
        }

        low, high, count = ranges[game]

        if main is not None and (
            len(main) != count
            or len(set(main)) != count
            or any(n < low or n > high for n in main)
        ):
            data["advertencias"].append(
                "Combinación fuera de rango o repetida"
            )

    if data["fecha"] is None:
        data["advertencias"].append("Fecha no reconocida")

    return data


def main():
    output = Path("diagnostico_pdf_086c")
    output.mkdir(exist_ok=True)

    report = {
        "version": "0.86C",
        "generado_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "solo_lectura": True,
        "publicable": False,
        "urls": "12 PDF históricos de 0.85M",
        "documentos": [],
    }

    for i, (url, game) in enumerate(zip(old.SEED_PDFS, GAMES), 1):
        item = {
            "indice": i,
            "juego": game,
            "url": url,
            "error": None
        }

        try:
            meta, raw = old.fetch(url)
            item["http"] = meta.get("http")

            if item["http"] != 200 or not raw.startswith(b"%PDF-"):
                raise ValueError(f"Respuesta no válida: {meta}")

            reader = PdfReader(BytesIO(raw))

            if reader.is_encrypted or not reader.pages:
                raise ValueError("PDF cifrado o sin páginas")

            texts = [
                p.extract_text(extraction_mode="layout") or ""
                for p in reader.pages
            ]
            full = "\n".join(texts)

            if len(full.strip()) < 100:
                raise ValueError("Texto insuficiente")

            item["paginas"] = len(texts)
            item["datos"] = parse(full, game)

            (output / f"{i:02d}_{game}.txt").write_text(
                full,
                encoding="utf-8"
            )

        except Exception as exc:
            item["error"] = f"{type(exc).__name__}: {exc}"

        report["documentos"].append(item)

        print(
            f"{i:02d} {game}: "
            f"{item['error'] or 'extraído, pendiente de validación'}",
            flush=True
        )

    Path("informe_pdf_086c.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    summary = [
        "LotoScan 0.86C | SOLO LECTURA | NO PUBLICABLE",
        ""
    ]

    for item in report["documentos"]:
        data = item.get("datos", {})
        summary.append(
            f"{item['indice']:02d} {item['juego']} "
            f"| fecha={data.get('fecha')} "
            f"| combinación={data.get('combinacion')} "
            f"| advertencias={data.get('advertencias')} "
            f"| error={item['error']}"
        )

    summary.append("historico.json no se ha modificado.")

    Path("informe_pdf_086c.txt").write_text(
        "\n".join(summary) + "\n",
        encoding="utf-8"
    )

    if any(item["error"] for item in report["documentos"]):
        raise SystemExit(
            "Hay descargas fallidas: revisar informe_pdf_086c.json"
        )


if __name__ == "__main__":
    main()
