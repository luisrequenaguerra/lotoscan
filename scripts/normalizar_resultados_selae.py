#!/usr/bin/env python3
"""Normalización conservadora de resultados SELAE: nueve juegos, sin cálculo de premios."""
import argparse
import datetime as dt
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re

GAMES={"EMIL","LAPR","BONO","ELGR","EDMS","LAQU","QGOL","LOTU","QUPL"}
def tokens(value):
    return [x.strip() for x in str(value).split("-")] if isinstance(value,str) else []
def decimal_text(value):
    if value is None or str(value).strip()=="": return None
    raw=str(value).strip().replace(".","").replace(",",".")
    try: return str(Decimal(raw))
    except InvalidOperation: return None
def tagged(raw,tag):
    match=re.search(r"\b"+re.escape(tag)+r"\s*\(\s*(\d+)\s*\)",raw)
    return int(match.group(1)) if match else None
def integers(raw):
    return [int(x) for x in re.findall(r"\d+",re.sub(r"\b[CR]\s*\(\s*\d+\s*\)","",raw))]
def table(item,name,product):
    out=[]
    for row in item.get(name,[]) if isinstance(item.get(name),list) else []:
        if not isinstance(row,dict): continue
        out.append({"product":product,"category_code":row.get("categoria",row.get("orden_escrutinio")),
            "category_label":row.get("tipo"),"winners":row.get("ganadores"),
            "winners_europe":row.get("ganadores_eu"),"amount_eur":decimal_text(row.get("premio")),
            "raw_amount":row.get("premio"),"raw":row})
    return out
def parse(item):
    game=item.get("game_id")
    if game not in GAMES: raise ValueError("unsupported game "+str(game))
    raw=item.get("combinacion") or ""
    result={"numbers":[],"stars":[],"complementary":None,"reintegro":None,
            "dream":None,"key_number":None,"joker":None,"millon":None,
            "quiniela_signs":[],"pleno_15":None,"elige8":None,
            "quinigol_scores":[],"races":[],"raw_combination":raw}
    issues=[]
    if raw:
        if game=="EMIL":
            nums=integers(raw)
            if len(nums)==7: result["numbers"],result["stars"]=nums[:5],nums[5:]
            else: issues.append("euromillones_expected_5_numbers_2_stars")
        elif game in ("LAPR","BONO","LOTU"):
            result["numbers"]=integers(raw)
            result["complementary"]=tagged(raw,"C")
            result["reintegro"]=tagged(raw,"R")
            if len(result["numbers"])!=6: issues.append("expected_6_numbers")
            if game=="LOTU": issues.append("lototurf_C_R_semantics_pending_validation")
        elif game=="ELGR":
            result["numbers"]=integers(raw)
            result["key_number"]=tagged(raw,"R")
            if len(result["numbers"])!=5: issues.append("expected_5_numbers")
        elif game=="EDMS":
            result["numbers"]=integers(raw)
            result["dream"]=tagged(raw,"C")
            if len(result["numbers"])!=6: issues.append("expected_6_numbers")
        elif game=="LAQU":
            signs=[x.strip() for x in raw.split("-")]
            if len(signs)==15:
                result["quiniela_signs"]=signs[:14]
                result["pleno_15"]=signs[14]
            else: issues.append("quiniela_expected_15_signs")
        elif game=="QGOL":
            scores=[x.strip() for x in raw.split("-")]
            if len(scores)==6: result["quinigol_scores"]=[x.replace(" ","").upper() for x in scores]
            else: issues.append("quinigol_expected_6_scores")
        elif game=="QUPL":
            result["races"]=integers(raw)
            result["second_fifth_race"]=tagged(raw,"C")
            if len(result["races"])!=5: issues.append("quintuple_expected_5_winners")
    else: issues.append("combination_pending")
    if game=="EMIL":
        result["millon"]=item.get("millon")
        result["lluvia"]=item.get("lluvia")
    if game=="LAPR": result["joker"]=item.get("joker")
    if game=="LAQU":
        result["elige8"]=item.get("elige8")
        result["matches"]=item.get("partidos",[])
    if game=="QGOL": result["matches"]=item.get("partidos",[])
    prizes=table(item,"escrutinio",game)
    for field,product in (("escrutinio_millon","EL_MILLON"),
                          ("escrutinio_joker","JOKER"),
                          ("escrutinio_lluvia","LLUVIA_MILLONES"),
                          ("escrutinioElige8","ELIGE8")):
        prizes+=table(item,field,product)
    if not prizes: issues.append("scrutiny_pending")
    return {"schema_version":"0.1","source":{"provider":"SELAE","endpoint":"fechav3"},
            "draw":{"game_id":game,"id_sorteo":str(item.get("id_sorteo")),
                    "date":str(item.get("fecha_sorteo",""))[:10],
                    "jornada":item.get("jornada"),"temporada":item.get("temporada")},
            "result":result,"prizes":prizes,
            "economics":{k:item.get(k) for k in ("apuestas","recaudacion","premios","fondo_bote","premio_bote")},
            "issues":issues,"prizes_certified":False,"raw":item}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--historico",default="datos/lotoscan/historico_oficial")
    p.add_argument("--salida",default="salida_normalizacion_selae")
    a=p.parse_args()
    root=Path(a.historico);out=Path(a.salida)
    summary={}
    for game in sorted(GAMES):
        files=sorted((root/game).glob("*/actual.json"))
        count=0;pending=0;issues={}
        for file in files:
            parsed=parse(json.loads(file.read_text(encoding="utf-8")))
            target=out/game/file.parent.name/"normalizado.json"
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_text(json.dumps(parsed,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
            count+=1
            if "combination_pending" in parsed["issues"]:pending+=1
            for issue in parsed["issues"]:issues[issue]=issues.get(issue,0)+1
        summary[game]={"draws":count,"combination_pending":pending,"issues":issues}
    out.mkdir(parents=True,exist_ok=True)
    (out/"resumen.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False))
    if not sum(x["draws"] for x in summary.values()): raise SystemExit("No archived draws")
if __name__=="__main__": main()
