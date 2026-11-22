#!/usr/bin/env python3
"""Histórico incremental SELAE: nueve juegos, fechav3 prioritario.
Solo archiva sorteos identificados; nunca calcula ni certifica premios.
"""
import argparse
import datetime as dt
import json
import time
import urllib.parse
from pathlib import Path
from zoneinfo import ZoneInfo

from actualizar_resultados_130 import BASE, GAMES, candidates, fetch, quality, update, write_json

CODES={k:v for k,v in GAMES.items() if v!="LNAC"}
TZ=ZoneInfo("Europe/Madrid")

def run(args):
    today=dt.datetime.now(TZ).date()
    end=dt.date.fromisoformat(args.fecha_fin) if args.fecha_fin else today
    if end>today: raise ValueError("No se admiten fechas futuras")
    history=Path(args.historico)
    output=Path(args.salida)
    report={"version":"historico-9-v1","fecha_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
            "fecha_fin":end.isoformat(),"fuente_prioritaria":"fechav3",
            "solo_lectura":args.solo_lectura,"premios_validados":False,
            "consultas":[],"sorteos":[]}
    seen=set()
    for offset in range(args.dias):
        day=end-dt.timedelta(days=offset)
        for name,code in CODES.items():
            # Consultar una sola vez por fecha/juego; 406 y 403 se registran, no se ocultan.
            endpoint="fechav3"
            url=BASE+endpoint+"?"+urllib.parse.urlencode({"game_id":code,"fecha_sorteo":day.strftime("%Y%m%d")})
            raw,network=fetch(url,retries=2)
            row={"juego":name,"game_id":code,"fecha":day.isoformat(),
                 "endpoint":endpoint,**network}
            if raw is None:
                row["estado"]="error_red"
            else:
                found,state=candidates(raw,code,day)
                row["estado"]=state
                row["encontrados"]=len(found)
                for item in found:
                    draw_id=str(item["id_sorteo"])
                    key=(code,draw_id)
                    if key in seen: continue
                    seen.add(key)
                    issues=quality(item,code)
                    if args.solo_lectura:
                        action="candidato"
                        write_json(output/"candidatos"/code/(draw_id+".json"),item)
                    else:
                        action,digest=update(history,code,item)
                    report["sorteos"].append({"juego":name,"game_id":code,
                        "id_sorteo":draw_id,"fecha":day.isoformat(),
                        "accion":action,"incidencias":issues,
                        "premios_validados":False})
            report["consultas"].append(row)
            print(day,code,row["estado"],row.get("http"),flush=True)
            time.sleep(args.espera)
    errors=[r for r in report["consultas"] if r["estado"] in ("error_red","no_json")]
    report["resumen"]={
        "consultas":len(report["consultas"]),
        "http_200":sum(r.get("http")==200 for r in report["consultas"]),
        "errores":len(errors),
        "errores_http":{str(code):sum(r.get("http")==code for r in errors)
                        for code in (403,406,429,500,502,503,504)},
        "sorteos_unicos":len(report["sorteos"]),
        "nuevos":sum(r["accion"]=="nuevo" for r in report["sorteos"]),
        "revisados":sum(r["accion"]=="revisado" for r in report["sorteos"]),
        "sin_cambios":sum(r["accion"]=="sin_cambios" for r in report["sorteos"]),
        "juegos_con_sorteo":sorted({r["game_id"] for r in report["sorteos"]})}
    write_json(output/"informe.json",report)
    # 403/406/503 no deben borrar histórico ni convertir un fallo en «sin sorteo».
    # El próximo ciclo vuelve a consultar toda la ventana y recupera pendientes.
    if not report["sorteos"]:
        raise SystemExit("ALERTA: ningún sorteo recuperado; consultar informe.json")
    print("RESUMEN",json.dumps(report["resumen"],ensure_ascii=False),flush=True)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--dias",type=int,default=15)
    p.add_argument("--fecha-fin",default="",help="AAAA-MM-DD")
    p.add_argument("--historico",default="datos/lotoscan/historico_oficial")
    p.add_argument("--salida",default="salida_historico_9")
    p.add_argument("--espera",type=float,default=0.8)
    p.add_argument("--solo-lectura",action="store_true")
    a=p.parse_args()
    if not 1<=a.dias<=90: p.error("--dias entre 1 y 90")
    if not 0<=a.espera<=10: p.error("--espera entre 0 y 10")
    run(a)

if __name__=="__main__": main()
