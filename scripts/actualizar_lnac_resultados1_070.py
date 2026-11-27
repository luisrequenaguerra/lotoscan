#!/usr/bin/env python3
"""Obtiene LNAC solo de resultados1; ante 406 no altera datos publicados."""
import json
import pathlib
import urllib.error
import urllib.parse
import urllib.request
from actualizar_lnac_137 import extract, save

BASE = "https://www.loteriasyapuestas.es/servicios/resultados1"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "es-ES,es;q=0.9",
    "Referer": "https://www.loteriasyapuestas.es/es/resultados",
    "Origin": "https://www.loteriasyapuestas.es",
}

def get_latest():
    # Solo variantes del mismo servicio resultados1; nunca resultados2.
    # Un 406 no se reintenta repetidamente contra la misma URL.
    errors = []
    for params in ({"game_id": "LNAC"}, {}):
        url = BASE + ("?" + urllib.parse.urlencode(params) if params else "")
        req = urllib.request.Request(url, headers=HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=20) as response:
                data = response.read(2_000_001)
                if len(data) > 2_000_000:
                    raise ValueError("Respuesta excesiva")
                payload = json.loads(data.decode("utf-8-sig"))
            candidates = payload if isinstance(payload, list) else [payload]
            valid = []
            for item in candidates:
                try:
                    summary = extract(item)
                    valid.append((summary, item))
                except (ValueError, TypeError, AttributeError):
                    continue
            if valid:
                return max(valid, key=lambda pair: pair[0]["fecha_sorteo"])
            errors.append("resultados1 sin sorteo LNAC ordinario válido")
        except urllib.error.HTTPError as exc:
            errors.append(f"HTTP {exc.code} ({'LNAC' if params else 'sin parámetros'})")
            if exc.code in (401, 403, 406, 429):
                continue
            raise
        except (urllib.error.URLError, TimeoutError, ValueError, UnicodeError) as exc:
            errors.append(f"{type(exc).__name__} ({'LNAC' if params else 'sin parámetros'})")
    raise RuntimeError("SELAE resultados1 inaccesible o inválido: " + "; ".join(errors) + ". No se publica ningún dato.")

def main():
    summary, item = get_latest()
    status = save(pathlib.Path("datos/lotoscan/loteria_nacional/historico_resultados1"), item, summary, False)
    print("LNAC", summary["id_sorteo"], status)

if __name__ == "__main__":
    main()
