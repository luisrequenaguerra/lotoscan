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

def joker(draw,code):
    if draw["draw"]["game_id"]!="LAPR":raise ValueError("Joker requires LAPR")
    if not isinstance(code,str) or not re.fullmatch(r"[0-9]{7}",code):
        raise ValueError("Joker must have exactly seven digits")
    official=draw["result"].get("joker")
    winning=official.get("combinacion") if isinstance(official,dict) else None
    if winning is None:return {"status":"pending_result","awards":[],"total_eur":None}
    winning=str(winning).zfill(7)
    if not re.fullmatch(r"[0-9]{7}",winning):return {"status":"invalid_result","awards":[],"total_eur":None}
    matched=[]
    if code==winning:
        row=_row(draw,"JOKER",1)
        if row:matched.append({**row,"direction":"full"})
    for digits in range(6,0,-1):
        cat=8-digits
        for direction in ("first","last"):
            equal=(code[:digits]==winning[:digits]) if direction=="first" else (code[-digits:]==winning[-digits:])
            if equal:
                row=_row(draw,"JOKER",cat)
                if row:matched.append({**row,"direction":direction})
    return {"status":"candidate_not_certified","awards":matched,
            "matched_categories":sorted(set(r["category"] for r in matched)),
            "total_eur":None,"prize_certified":False,
            "issue":"joker_accumulated_awards_table_requires_independent_validation"}

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
