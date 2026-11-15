
"""LotoScan 0.53: contraste independiente, sin publicar ni modificar histórico."""
import json
from datetime import date, datetime, timezone
from pathlib import Path

HIST = Path("datos_revision/historico.json")
REF = Path("datos_revision/referencias_independientes.json")
OUT = Path("informe-lotoscan-053.json")
GAMES = {"euromillones", "bonoloto", "primitiva"}

def combination(game, rec):
    keys = ("numeros", "estrellas", "el_millon") if game == "euromillones" else (
        ("numeros", "complementario", "reintegro", "joker") if game == "primitiva"
        else ("numeros", "complementario", "reintegro"))
    return {k: sorted(rec[k]) if k in ("numeros", "estrellas") else rec[k] for k in keys}

def check():
    history = json.loads(HIST.read_text(encoding="utf-8"))
    refs = json.loads(REF.read_text(encoding="utf-8"))
    if history.get("publicable") is not False or not isinstance(history.get("juegos"), dict):
        raise ValueError("Histórico no seguro")
    if refs.get("version") != "0.53" or not isinstance(refs.get("referencias"), list):
        raise ValueError("Formato de referencias incorrecto")
    results = []
    seen = set()
    for ref in refs["referencias"]:
        if not isinstance(ref, dict):
            raise ValueError("Referencia inválida")
        game, day = ref.get("juego"), ref.get("fecha")
        if game not in GAMES or not isinstance(day, str):
            raise ValueError("Juego o fecha inválidos")
        date.fromisoformat(day)
        key = (game, day)
        if key in seen:
            raise ValueError("Referencia duplicada: " + str(key))
        seen.add(key)
        source = ref.get("fuente")
        url = ref.get("url")
        if not isinstance(source, str) or not source.strip() or not isinstance(url, str) or not url.startswith("https://"):
            raise ValueError("Faltan identificación y enlace de fuente")
        if "combinacion" not in ref or not isinstance(ref["combinacion"], dict):
            raise ValueError("Falta combinación de referencia")
        original = history["juegos"].get(game, {}).get(day)
        if original is None:
            results.append({"juego": game, "fecha": day, "estado": "sin_historico"})
            continue
        expected = combination(game, original)
        observed = ref["combinacion"]
        if set(expected) != set(observed):
            status = "discrepancia_combinacion"
            fields = sorted(set(expected) ^ set(observed))
        else:
            fields = [k for k in expected if expected[k] != (
                sorted(observed[k]) if k in ("numeros", "estrellas") and isinstance(observed[k], list)
                else observed[k])]
            status = "discrepancia_combinacion" if fields else "combinacion_coincide"
        prize_status = "sin_contraste_de_importes"
        if "categorias" in ref:
            if not isinstance(ref["categorias"], dict):
                raise ValueError("Categorías de referencia inválidas")
            stored = original["categorias"]
            if set(ref["categorias"]) != set(stored):
                prize_status = "categorias_incompletas_o_diferentes"
            else:
                prize_status = "importes_coinciden" if all(
                    (stored[k] if game == "euromillones" else stored[k]["importe_centimos"])
                    == ref["categorias"][k] for k in stored
                ) else "discrepancia_importes"
        results.append({"juego": game, "fecha": day, "estado": status,
                        "campos_discrepantes": fields, "premios": prize_status,
                        "fuente": source, "url": url,
                        "nota": "Referencia aportada manualmente; su autenticidad no ha sido verificada por este script."})
    return {"version": "0.53", "generado_utc": datetime.now(timezone.utc).isoformat(),
            "publica_resultados": False, "modifica_historico": False,
            "referencias_comparadas": len(results), "resultados": results,
            "nota": "Coincidencia técnica no equivale a certificación oficial ni autoriza publicación."}

def main():
    result = check()
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if any(r["estado"] != "combinacion_coincide" or
           r["premios"] in ("discrepancia_importes", "categorias_incompletas_o_diferentes")
           for r in result["resultados"]):
        raise SystemExit("Hay discrepancias: revisar manualmente")

if __name__ == "__main__":
    main()

