#!/usr/bin/env python3
"""Audita sin alterar el histórico SELAE almacenado por LotoScan."""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path

CODES={"EMIL","LAPR","BONO","ELGR","EDMS","LAQU","QGOL","LOTU","QUPL"}

def digest(obj):
    return hashlib.sha256(json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode("utf-8")).hexdigest()

def audit(root):
    report={"fecha_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
            "juegos":{},"errores":[],"avisos":[],"total_sorteos":0}
    for code in sorted(CODES):
        folder=root/code
        entries=[]
        if folder.exists():
            for file in sorted(folder.glob("*/actual.json")):
                draw_id=file.parent.name
                try:
                    item=json.loads(file.read_text(encoding="utf-8"))
                    if not isinstance(item,dict): raise ValueError("No es objeto JSON")
                    if str(item.get("id_sorteo"))!=draw_id: raise ValueError("Identificador no coincide")
                    if item.get("game_id")!=code: raise ValueError("Juego no coincide")
                    date=str(item.get("fecha_sorteo") or "")[:10]
                    dt.date.fromisoformat(date)
                    if not item.get("combinacion"): report["avisos"].append(f"{code}/{draw_id}: combinación vacía")
                    if not isinstance(item.get("escrutinio"),list) or not item["escrutinio"]:
                        report["avisos"].append(f"{code}/{draw_id}: escrutinio pendiente")
                    current_hash=digest(item)
                    revision=file.parent/"revisiones"/(current_hash+".json")
                    if not revision.exists():
                        report["avisos"].append(f"{code}/{draw_id}: falta revisión del estado actual")
                    else:
                        saved=json.loads(revision.read_text(encoding="utf-8"))
                        if digest(saved)!=current_hash:
                            report["errores"].append(f"{code}/{draw_id}: revisión actual corrupta")
                    entries.append({"id_sorteo":draw_id,"fecha":date,"sha256":current_hash,
                                    "revisiones":len(list((file.parent/"revisiones").glob("*.json")))})
                except (OSError,ValueError,TypeError) as exc:
                    report["errores"].append(f"{code}/{draw_id}: {exc}")
        report["juegos"][code]={"total":len(entries),"ultimo":max((x["fecha"] for x in entries),default=None)}
        report["total_sorteos"]+=len(entries)
    report["estado"]="error" if report["errores"] else ("advertencias" if report["avisos"] else "correcto")
    return report

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--historico",default="datos/lotoscan/historico_oficial")
    p.add_argument("--salida",default="salida_auditoria_historico")
    args=p.parse_args()
    report=audit(Path(args.historico))
    out=Path(args.salida)
    out.mkdir(parents=True,exist_ok=True)
    (out/"integridad.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"estado":report["estado"],"total_sorteos":report["total_sorteos"],
                      "juegos":report["juegos"],"errores":report["errores"][:20],
                      "avisos":report["avisos"][:20]},ensure_ascii=False))
    if report["total_sorteos"]==0 or report["errores"]: raise SystemExit(1)

if __name__=="__main__": main()
