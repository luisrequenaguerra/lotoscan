#!/usr/bin/env python3
"""Sondeo nocturno selectivo SELAE, 20:00-23:00 Europe/Madrid.
Juegos de calendario variable: sondeo ligero diario hasta disponer de calendario oficial.
"""
import argparse
import datetime as dt
import json
import time
import urllib.parse
from pathlib import Path
from zoneinfo import ZoneInfo
from actualizar_resultados_130 import BASE, fetch, candidates, quality, update, write_json

TZ=ZoneInfo("Europe/Madrid")
# weekday: Monday=0. Bonoloto todos los días.
FIXED={"EMIL":{1,4},"LAPR":{0,3,5},"BONO":set(range(7)),
       "ELGR":{6},"EDMS":{0,3}}
# Los juegos variables NO se restringen a domingos: hay jornadas extraordinarias.
VARIABLE={"LAQU","QGOL","LOTU","QUPL"}
GAMES=FIXED.keys() | VARIABLE

def complete(item,code):
    if not item.get("combinacion"): return False
    if not isinstance(item.get("escrutinio"),list) or not item["escrutinio"]: return False
    if code=="LAQU":
        # Elige8 puede publicarse posteriormente; no detener el sondeo antes.
        if not isinstance(item.get("escrutinioElige8"),list) or not item["escrutinioElige8"]:
            return False
    return True

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--forzar",action="store_true",help="Prueba manual fuera de la franja")
    p.add_argument("--solo-lectura",action="store_true")
    p.add_argument("--historico",default="datos/lotoscan/historico_oficial")
    p.add_argument("--salida",default="salida_sondeo_nocturno")
    args=p.parse_args()
    now=dt.datetime.now(TZ)
    report={"fecha_local":now.isoformat(),"consultas":[],"sorteos":[],
            "modo":"sondeo_selectivo","premios_validados":False}
    out=Path(args.salida)
    if not args.forzar and not (20<=now.hour<23 or (now.hour==23 and now.minute<=15)):
        report["estado"]="fuera_de_franja"
        write_json(out/"informe.json",report)
        print("Fuera de la franja 20:00-23:00 Europe/Madrid")
        return
    today=now.date()
    history=Path(args.historico)
    selected=sorted(code for code in GAMES if code in VARIABLE or today.weekday() in FIXED[code])
    report["juegos_seleccionados"]=selected
    for code in selected:
        url=BASE+"fechav3?"+urllib.parse.urlencode({"game_id":code,"fecha_sorteo":today.strftime("%Y%m%d")})
        current_files=list((history/code).glob("*/actual.json")) if (history/code).exists() else []
        # Si ya hay un resultado completo para hoy, omitirlo. La revisión diaria
        # seguirá comprobando correcciones posteriores.
        if any(_is_complete_for_day(f,code,today) for f in current_files):
            report["consultas"].append({"game_id":code,"estado":"ya_completo","fecha":str(today)})
            continue
        raw,net=fetch(url,retries=1)
        row={"game_id":code,"fecha":str(today),**net}
        if raw is None: row["estado"]="error_red"
        else:
            found,state=candidates(raw,code,today)
            row["estado"]=state
            row["encontrados"]=len(found)
            for item in found:
                if args.solo_lectura:
                    action="candidato"
                else:
                    action,_=update(history,code,item)
                report["sorteos"].append({"game_id":code,"id_sorteo":str(item["id_sorteo"]),
                    "accion":action,"completo":complete(item,code),"incidencias":quality(item,code)})
        report["consultas"].append(row)
        print(code,row["estado"],row.get("http"),flush=True)
        time.sleep(1.2)
    report["resumen"]={"consultas_http":sum("http" in r for r in report["consultas"]),
        "omitidos_completos":sum(r["estado"]=="ya_completo" for r in report["consultas"]),
        "errores":sum(r["estado"]=="error_red" for r in report["consultas"]),
        "sorteos":len(report["sorteos"])}
    write_json(out/"informe.json",report)
    print("RESUMEN",json.dumps(report["resumen"],ensure_ascii=False))

def _is_complete_for_day(path,code,day):
    try:
        item=json.loads(path.read_text(encoding="utf-8"))
        return str(item.get("fecha_sorteo",""))[:10]==day.isoformat() and complete(item,code)
    except (OSError,ValueError,TypeError):
        return False

if __name__=="__main__": main()
