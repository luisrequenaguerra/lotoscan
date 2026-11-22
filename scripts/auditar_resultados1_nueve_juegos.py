#!/usr/bin/env python3
"""Auditoría NO destructiva de resultados1, fechav3 y fecha2 para nueve juegos SELAE."""
import datetime as dt
import hashlib
import json
import pathlib
import time
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

BASE = "https://www.loteriasyapuestas.es/servicios/"
GAMES = {"euromillones":"EMIL","primitiva":"LAPR","bonoloto":"BONO",
         "gordo-primitiva":"ELGR","eurodreams":"EDMS","quiniela":"LAQU",
         "quinigol":"QGOL","lototurf":"LOTU","quintuple-plus":"QUPL"}
OUT = pathlib.Path("auditoria_resultados1")
MAX_BYTES = 2_000_000

def inspect(game, code, endpoint, day=None):
    params={"game_id":code}
    if day is not None: params["fecha_sorteo"]=day.strftime("%Y%m%d")
    url = BASE + endpoint + "?" + urllib.parse.urlencode(params)
    row = {"juego":game,"game_id":code,"endpoint":endpoint,"fecha_consultada":day.isoformat() if day else None,
           "url":url,"campos":{},"muestras":[],"premios_validados":False}
    try:
        req = urllib.request.Request(url,headers={"User-Agent":"LotoScan/1.31 source-audit",
            "Accept":"application/json"})
        with urllib.request.urlopen(req,timeout=25) as resp:
            data=resp.read(MAX_BYTES+1)
            row["http"]=resp.status
            row["content_type"]=resp.headers.get("Content-Type","")
        row["bytes"]=len(data)
        if len(data)>MAX_BYTES: raise ValueError("respuesta_mayor_2mb")
        row["sha256"]=hashlib.sha256(data).hexdigest()
        payload=json.loads(data.decode("utf-8-sig"))
        row["json_tipo"]=type(payload).__name__
        items=payload if isinstance(payload,list) else [payload]
        row["elementos"]=len(items)
        matching=[x for x in items if isinstance(x,dict) and x.get("game_id")==code]
        row["coincidencias_game_id"]=len(matching)
        row["claves_raiz"]=sorted(payload.keys()) if isinstance(payload,dict) else []
        for item in matching[:3]:
            row["muestras"].append({"id_sorteo":item.get("id_sorteo"),
                "fecha_sorteo":item.get("fecha_sorteo"),"claves":sorted(item.keys())})
        for field in ("combinacion","reintegro","reintegros","complementario",
                      "escrutinio","premios","acertantes","categorias"):
            row["campos"][field]={"presente":any(field in x for x in matching),
                "no_vacio":any(bool(x.get(field)) for x in matching)}
        row["estado"]="json_con_juego" if matching else "json_sin_identidad_confirmada"
        # Conservar respuesta íntegra como artefacto de auditoría, nunca en histórico.
        (OUT/(code+"_"+endpoint+"_"+(day.strftime("%Y%m%d") if day else "latest")+".json")).write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    except Exception as exc:
        row["estado"]="error"
        row["error"]=type(exc).__name__+": "+str(exc)[:220]
        if isinstance(exc,urllib.error.HTTPError): row["http"]=exc.code
    return row

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    rows=[]
    for name,code in GAMES.items():
        for endpoint in ("resultados1","fechav3","fecha2"):
            days=[None] if endpoint=="resultados1" else [dt.datetime.now(ZoneInfo("Europe/Madrid")).date()-dt.timedelta(days=n) for n in range(8)]
            for day in days:
                row=inspect(name,code,endpoint,day)
                rows.append(row)
                print(name,endpoint,str(day),row["estado"],row.get("http"),row.get("coincidencias_game_id"),flush=True)
                time.sleep(.25)
    report={"fecha_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
      "fuentes":["SELAE resultados1","SELAE fechav3","SELAE fecha2"],"solo_lectura":True,"publicable":False,
      "nota":"La presencia de campos no certifica categorías, premios ni cobertura histórica.",
      "juegos":rows}
    (OUT/"informe.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    if not any(x["estado"]=="json_con_juego" for x in rows):
        raise SystemExit("Sin resultados1 identificables; revisar artefacto")

if __name__=="__main__": main()
