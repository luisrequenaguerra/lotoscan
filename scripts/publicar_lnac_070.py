#!/usr/bin/env python3
"""Publica historico LNAC ordinario para LotoScan, sin premios especiales."""
import json
import pathlib
import re

ROOT = pathlib.Path("datos/lotoscan/loteria_nacional/historico_resultados1")
OUT = pathlib.Path("resultados/lnac")
WIDTHS = {"extraccionesDeCuatroCifras":4, "extraccionesDeTresCifras":3,
          "extraccionesDeDosCifras":2, "reintegros":1}

def valid(d):
    if not isinstance(d, dict) or d.get("tipoSorteoGeneral") not in ("J","S") or d.get("premioEspecial") is not None:
        return False
    if not re.fullmatch(r"\d{6,20}", str(d.get("drawIdSorteo",""))):
        return False
    if not re.match(r"^20\d\d-\d\d-\d\dT", str(d.get("fechaSorteo",""))):
        return False
    if d.get("precioDecimo") != (3 if d["tipoSorteoGeneral"]=="J" else 6):
        return False
    for key in ("primerPremio","segundoPremio"):
        x=d.get(key)
        if not isinstance(x,dict) or not re.fullmatch(r"\d{5}",str(x.get("decimo",""))) or not isinstance(x.get("prize"),int):
            return False
    for key,width in WIDTHS.items():
        rows=d.get(key)
        if not isinstance(rows,list) or not rows:
            return False
        for x in rows:
            if not isinstance(x,dict) or not re.fullmatch(r"\d{"+str(width)+r"}",str(x.get("decimo",""))) or not isinstance(x.get("prize"),int):
                return False
    return True

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    draws=[]
    for path in sorted(ROOT.glob("*/original_resultados.json")):
        try:
            d=json.loads(path.read_text(encoding="utf-8"))
        except (OSError,ValueError):
            continue
        if not valid(d):
            continue
        draw_id=str(d["drawIdSorteo"])
        name=draw_id+".json"
        (OUT/name).write_text(json.dumps(d,ensure_ascii=False,separators=(",",":"))+"\n",encoding="utf-8")
        draws.append({"date":d["fechaSorteo"][:10],"file":"./resultados/lnac/"+name,"id":draw_id})
    if not draws:
        raise RuntimeError("No hay sorteos ordinarios validos; no publicar manifest vacio")
    draws.sort(key=lambda x:(x["date"],x["id"]),reverse=True)
    manifest={"version":1,"draws":draws,"notice":"Sorteos ordinarios. No incluye premios especiales. Solo registros archivados por el flujo resultados1 de LotoScan 0.70."}
    (OUT/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("Publicados",len(draws),"sorteos")

if __name__=="__main__":
    main()
