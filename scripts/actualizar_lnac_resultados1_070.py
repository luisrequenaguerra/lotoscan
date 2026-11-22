#!/usr/bin/env python3
"""Archiva el ultimo sorteo ordinario LNAC desde resultados1 exclusivamente."""
import pathlib
from actualizar_lnac_137 import get_json, extract, save

def main():
    payload, _ = get_json("resultados1")
    candidates = payload if isinstance(payload, list) else [payload]
    valid = []
    for item in candidates:
        try:
            summary = extract(item)
            valid.append((summary, item))
        except (ValueError, AttributeError, TypeError):
            continue
    if not valid:
        raise RuntimeError("resultados1 no contiene LNAC ordinaria valida; no publicar")
    summary, item = max(valid, key=lambda pair: pair[0]["fecha_sorteo"])
    status = save(pathlib.Path("datos/lotoscan/loteria_nacional/historico_resultados1"), item, summary, False)
    print("LNAC", summary["id_sorteo"], status)

if __name__ == "__main__":
    main()
