#!/usr/bin/env python3
"""Comparación de apuestas simples con resultados oficiales; sin certificación de premios."""
import argparse
import json
from pathlib import Path
from normalizar_resultados_selae import parse

LIMITS={"BONO":(6,1,49),"LAPR":(6,1,49),"EMIL":(5,1,50)}
def valid_numbers(values,count,low,high,label):
    if not isinstance(values,list) or len(values)!=count or any(type(x)!=int or not low<=x<=high for x in values) or len(set(values))!=count:
        raise ValueError("invalid "+label)
def compare(draw,ticket):
    game=draw.get("draw",{}).get("game_id")
    if game not in LIMITS: raise ValueError("game not yet supported")
    if ticket.get("game_id")!=game: raise ValueError("game mismatch")
    if str(ticket.get("id_sorteo"))!=str(draw["draw"]["id_sorteo"]):
        raise ValueError("draw mismatch")
    n,low,high=LIMITS[game]
    nums=ticket.get("numbers")
    valid_numbers(nums,n,low,high,"numbers")
    result=draw["result"]
    official=result.get("numbers",[])
    if len(official)!=n or len(set(official))!=n:
        return {"status":"pending_result","game_id":game,"id_sorteo":draw["draw"]["id_sorteo"],"prize_certified":False}
    valid_numbers(official,n,low,high,"official numbers")
    hits=len(set(nums)&set(official))
    output={"status":"matches_only","game_id":game,"id_sorteo":draw["draw"]["id_sorteo"],
            "number_hits":hits,"prize_certified":False,"prize_eur":None,
            "reason":"Category and award rules not yet validated"}
    if game=="EMIL":
        stars=ticket.get("stars")
        valid_numbers(stars,2,1,12,"stars")
        official_stars=result.get("stars",[])
        if len(official_stars)!=2: return {"status":"pending_result","prize_certified":False}
        valid_numbers(official_stars,2,1,12,"official stars")
        output["star_hits"]=len(set(stars)&set(official_stars))
        code=ticket.get("millon_code")
        official_millon=result.get("millon")
        if code is not None:
            if not isinstance(code,str) or not code.strip(): raise ValueError("invalid millon_code")
            if isinstance(official_millon,dict) and official_millon.get("combinacion"):
                output["millon_code_matches"]=code.strip().upper()==str(official_millon["combinacion"]).strip().upper()
            else: output["millon_code_matches"]=None
    else:
        comp=result.get("complementary")
        output["complementary_hit"]=comp in nums if comp is not None else None
        if "reintegro" in ticket:
            rein=ticket["reintegro"]
            if type(rein)!=int or not 0<=rein<=9: raise ValueError("invalid reintegro")
            output["reintegro_hit"]=rein==result.get("reintegro") if result.get("reintegro") is not None else None
        if game=="LAPR" and "joker_code" in ticket:
            code=ticket["joker_code"]
            if not isinstance(code,str) or not code.isdigit() or len(code)!=7: raise ValueError("invalid joker_code")
            joker=result.get("joker")
            output["joker_full_match"]=code==str(joker["combinacion"]).zfill(7) if isinstance(joker,dict) and joker.get("combinacion") is not None else None
            output["joker_partial_prizes_checked"]=False
    return output

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--sorteo",required=True,help="Archived official actual.json")
    p.add_argument("--boleto",required=True,help="JSON file containing one simple bet")
    a=p.parse_args()
    draw=parse(json.loads(Path(a.sorteo).read_text(encoding="utf-8")))
    ticket=json.loads(Path(a.boleto).read_text(encoding="utf-8"))
    print(json.dumps(compare(draw,ticket),ensure_ascii=False,indent=2))
if __name__=="__main__": main()
