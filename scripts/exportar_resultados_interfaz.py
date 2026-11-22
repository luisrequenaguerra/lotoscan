#!/usr/bin/env python3
"""Publica resultados SELAE normalizados para consumo de la interfaz web."""
import json
from pathlib import Path
from normalizar_resultados_selae import parse

ROOT=Path(__file__).resolve().parents[1]
GAMES=("BONO","LAPR","EMIL")
def build(root=ROOT):
    output={"schema_version":"1","provider":"SELAE","games":{}}
    for game in GAMES:
        draws={}
        for path in sorted((root/"datos/lotoscan/historico_oficial"/game).glob("*/actual.json")):
            try:
                normalized=parse(json.loads(path.read_text(encoding="utf-8")))
            except (ValueError,TypeError,KeyError,json.JSONDecodeError):
                continue
            meta=normalized["draw"]
            date=meta["date"]
            if not date or not normalized["result"]["numbers"]:continue
            safe={k:normalized[k] for k in ("draw","result","prizes","issues")}
            safe["source"]={"provider":"SELAE","endpoint":"fechav3"}
            # Multiple official draws on one date must not be silently overwritten.
            if date in draws:
                draws[date]=None
            else:draws[date]=safe
        output["games"][game]={d:v for d,v in draws.items() if v is not None}
    return output

def main():
    output=build()
    target=ROOT/"resultados"/"selae-interfaz.json"
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(output,ensure_ascii=False,separators=(",",":"))+"\n",encoding="utf-8")
    print("OFFICIAL_INTERFACE_DRAWS", {g:len(v) for g,v in output["games"].items()})
if __name__=="__main__":main()
