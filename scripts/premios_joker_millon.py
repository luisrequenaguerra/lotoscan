#!/usr/bin/env python3
"""Categorías candidatas Joker y El Millón, con trazabilidad de escrutinio SELAE."""
import re

def _row(draw,product,category):
    rows=[r for r in draw.get("prizes",[]) if r.get("product")==product]
    for idx,row in enumerate(rows,1):
        try: ordinal=int(row["category_code"] if row.get("category_code") is not None else idx)
        except (ValueError,TypeError):continue
        if ordinal==category:
            return {"product":product,"category":category,"label":row["category_label"],
                    "amount_eur":row["amount_eur"],"raw_amount":row["raw_amount"],
                    "winners":row["winners"]}
    return None

# Anexo II, Normas de Joker (SELAE): premios acumulados por máximos
# aciertos consecutivos de primeras y últimas cifras, SIN solapamiento.
# https://www.loteriasyapuestas.es/f/loterias/documentos/normativa/Normativa%20de%20los%20juegos/Normas_de_Joker_Octubre_2018.pdf
JOKER_TABLE={
 (7,0):(1,1000000),
 (6,0):(2,10000),(0,6):(2,10000),
 (5,1):(3,1001),(5,0):(3,1000),(1,5):(3,1001),(0,5):(3,1000),
 (4,2):(4,305),(4,1):(4,301),(4,0):(4,300),
 (2,4):(4,305),(1,4):(4,301),(0,4):(4,300),
 (3,3):(5,100),(3,2):(5,55),(3,1):(5,51),(3,0):(5,50),
 (2,3):(5,55),(1,3):(5,51),(0,3):(5,50),
 (2,2):(6,10),(2,1):(6,6),(2,0):(6,5),(1,2):(6,6),(0,2):(6,5),
 (1,1):(7,2),(1,0):(7,1),(0,1):(7,1)
}
def joker(draw,code):
    if draw["draw"]["game_id"]!="LAPR":raise ValueError("Joker requires LAPR")
    if not isinstance(code,str) or not re.fullmatch(r"[0-9]{7}",code):
        raise ValueError("Joker must have exactly seven digits")
    official=draw["result"].get("joker")
    winning=official.get("combinacion") if isinstance(official,dict) else None
    if winning is None:return {"status":"pending_result","awards":[],"total_eur":None}
    winning=str(winning).zfill(7)
    if not re.fullmatch(r"[0-9]{7}",winning):
        return {"status":"invalid_result","awards":[],"total_eur":None}
    if code==winning:
        first,last=7,0
    else:
        first=next((i for i in range(7) if code[i]!=winning[i]),7)
        last=next((i for i in range(7) if code[6-i]!=winning[6-i]),7)
    pair=(first,last)
    matched=JOKER_TABLE.get(pair)
    if matched is None:
        if first==0 and last==0:
            return {"status":"candidate_not_certified","awards":[],
                    "matched_categories":[],"total_eur":None,"prize_certified":False}
        raise ValueError("unlisted Joker prefix/suffix pattern "+str(pair))
    cat,amount=matched
    row=_row(draw,"JOKER",cat)
    if row is None:return {"status":"pending_scrutiny","awards":[],"total_eur":None}
    # Anexo II defines the cumulative prize, not a sum of every matching
    # prefix/suffix and not repeated lower-category awards.
    from decimal import Decimal
    if row["amount_eur"] is None or Decimal(str(row["amount_eur"]))<=0:
        return {"status":"invalid_scrutiny","awards":[],"total_eur":None}
    return {"status":"calculated_gross_not_certified","awards":[{**row,
              "prefix_hits":first,"suffix_hits":last,
              "cumulative_amount_eur":str(amount)}],
            "matched_categories":[cat],"joker_gross_eur":str(amount),
            "total_eur":None,"prize_certified":False}

def millon(draw,code,receipt_verified=False):
    if draw["draw"]["game_id"]!="EMIL":raise ValueError("El Millón requires EMIL")
    if not isinstance(code,str) or not re.fullmatch(r"[A-Za-z]{3}[0-9]{5}",code):
        raise ValueError("El Millón code must have three letters and five digits")
    official=draw["result"].get("millon")
    winning=official.get("combinacion") if isinstance(official,dict) else None
    if winning is None:return {"status":"pending_result","matches":None,"award":None,"total_eur":None}
    if not re.fullmatch(r"[A-Za-z]{3}[0-9]{5}",str(winning)):
        return {"status":"invalid_result","matches":None,"award":None,"total_eur":None}
    matches=code.upper()==str(winning).upper()
    award=_row(draw,"EL_MILLON",1) if matches else None
    return {"status":"candidate_not_certified","matches":matches,"award":award,
            "receipt_verified":receipt_verified,"total_eur":None,"prize_certified":False,
            "issue":None if not matches else ("receipt_ownership_unverified" if not receipt_verified else "receipt_level_accumulation_pending")}
