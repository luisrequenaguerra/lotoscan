#!/usr/bin/env python3
"""Inventario reproducible de campos del JSON oficial archivado. No calcula premios."""
import argparse
import collections
import datetime as dt
import json
from pathlib import Path

GAMES=("EMIL","LAPR","BONO","ELGR","EDMS","LAQU","QGOL","LOTU","QUPL")

def kind(value):
    if value is None: return "null"
    if isinstance(value,bool): return "boolean"
    if isinstance(value,list): return "array"
    if isinstance(value,dict): return "object"
    if isinstance(value,str): return "string"
    return "number"

def scan(root):
    report={"generated_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
            "source":"archived SELAE JSON","games":{},"certifies_prizes":False}
    for game in GAMES:
        files=sorted((root/game).glob("*/actual.json"))
        fields=collections.defaultdict(lambda:{"present":0,"types":collections.Counter(),
                                                "nonempty":0,"sample":None})
        categories=collections.defaultdict(lambda:{"count":0,"types":set(),"sample":None})
        issues=[]
        for path in files:
            try:
                obj=json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(obj,dict): raise ValueError("not an object")
                for key,val in obj.items():
                    f=fields[key];f["present"]+=1;f["types"][kind(val)]+=1
                    if val not in (None,"",[],{}):
                        f["nonempty"]+=1
                        if f["sample"] is None: f["sample"]=str(val)[:160]
                for field in ("escrutinio","escrutinio_joker","escrutinio_millon",
                              "escrutinio_lluvia","escrutinioElige8"):
                    for row in obj.get(field,[]) if isinstance(obj.get(field),list) else []:
                        if not isinstance(row,dict): continue
                        cat=categories[field];cat["count"]+=1
                        for k,v in row.items(): cat["types"].add(k)
                        if cat["sample"] is None: cat["sample"]=row
            except (OSError,ValueError,TypeError) as exc:
                issues.append(str(path)+": "+str(exc))
        report["games"][game]={"draws":len(files),"fields":{
            k:{"present":v["present"],"nonempty":v["nonempty"],"types":dict(v["types"]),
               "sample":v["sample"]} for k,v in sorted(fields.items())},
            "scrutiny_tables":{k:{"rows":v["count"],"columns":sorted(v["types"]),
                "sample":v["sample"]} for k,v in sorted(categories.items())},"issues":issues}
    return report

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--historico",default="datos/lotoscan/historico_oficial")
    p.add_argument("--salida",default="salida_catalogo_selae/catalogo_campos.json")
    a=p.parse_args()
    out=Path(a.salida);out.parent.mkdir(parents=True,exist_ok=True)
    report=scan(Path(a.historico))
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({g:{"sorteos":d["draws"],"campos":len(d["fields"]),
      "tablas":list(d["scrutiny_tables"])} for g,d in report["games"].items()},ensure_ascii=False))
    if any(d["issues"] for d in report["games"].values()): raise SystemExit(1)

if __name__=="__main__": main()
