#!/usr/bin/env python3
"""Vincula aciertos con categorías SELAE sin certificar pagos ni sumas de boletos."""
import re
from decimal import Decimal, InvalidOperation
from comprobar_aciertos import compare

def money(value):
    if value is None or str(value).strip()=="": return None
    raw=str(value).strip().replace(".","").replace(",",".")
    try: return Decimal(raw)
    except InvalidOperation: return None

def category(game,hits,stars=0,complementary=False,reintegro=False):
    if game=="BONO":
        if hits==6:return 1
        if hits==5:return 2 if complementary else 3
        return {4:4,3:5}.get(hits)
    if game=="LAPR":
        if hits==6:return 1 if reintegro else 2
        if hits==5:return 3 if complementary else 4
        return {4:5,3:6}.get(hits)
    if game=="EMIL":
        return {(5,2):1,(5,1):2,(5,0):3,(4,2):4,(4,1):5,
                (3,2):6,(4,0):7,(2,2):8,(3,1):9,(3,0):10,
                (1,2):11,(2,1):12,(2,0):13}.get((hits,stars))
    raise ValueError("unsupported game")

def award(draw,ticket):
    match=compare(draw,ticket)
    if match["status"]!="matches_only":
        return {**match,"award_status":"pending"}
    game=match["game_id"]
    cat=category(game,match["number_hits"],match.get("star_hits",0),
                 match.get("complementary_hit") is True,match.get("reintegro_hit") is True)
    primary=None
    for idx,row in enumerate(draw["prizes"],1):
        if row["product"]!=game:continue
        # Ordinal is the official category position in each game's scrutiny.
        ordinal=row["category_code"] if row["category_code"] is not None else idx
        try: ordinal=int(ordinal)
        except (ValueError,TypeError): continue
        if ordinal==cat:
            primary={"category":cat,"label":row["category_label"],
                     "amount_eur":row["amount_eur"],"winners":row["winners"],
                     "raw_amount":row["raw_amount"]}
            break
    supplements=[]
    if game in ("BONO","LAPR") and match.get("reintegro_hit") is True:
        reinrow=next((r for r in draw["prizes"] if r["product"]==game
                     and re.search(r"\breintegro\b",r.get("category_label") or "",re.I)),None)
        if reinrow:
            supplements.append({"product":"REINTEGRO","amount_eur":reinrow["amount_eur"],
                                "label":reinrow["category_label"]})
    if game=="EMIL" and match.get("millon_code_matches") is True:
        for r in draw["prizes"]:
            if r["product"]=="EL_MILLON":
                supplements.append({"product":"EL_MILLON","amount_eur":r["amount_eur"],
                                    "label":r["category_label"]})
    if game=="LAPR" and match.get("joker_full_match") is True:
        for r in draw["prizes"]:
            if r["product"]=="JOKER" and re.search(r"todas las cifras",r.get("category_label") or "",re.I):
                supplements.append({"product":"JOKER","amount_eur":r["amount_eur"],
                                    "label":r["category_label"]})
    issues=[]
    if cat is not None and primary is None:issues.append("missing_primary_category")
    if cat is not None and primary and money(primary["amount_eur"]) is None:
        issues.append("invalid_primary_amount")
    if game=="LAPR" and "joker_code" in ticket:
        issues.append("joker_partial_categories_not_implemented")
    if game=="LAPR" and match.get("number_hits")==6 and match.get("reintegro_hit") is True:
        issues.append("special_prize_and_reintegro_overlap_requires_rules_validation")
    return {**match,"category":cat,"primary_award":primary,"supplementary_awards":supplements,
            "award_status":"candidate_not_certified","issues":issues,
            "total_eur":None,"prize_certified":False}
