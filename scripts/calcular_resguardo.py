#!/usr/bin/env python3
"""Total bruto estimado de resguardos simples; sin autenticación SELAE ni fiscalidad."""
from decimal import Decimal, InvalidOperation
from categorizar_premios import award
from premios_joker_millon import joker, millon

def _euros(value):
    if value is None:return None
    try:
        n=Decimal(str(value))
        if not n.is_finite() or n<0:return None
        return n
    except (ValueError,InvalidOperation,TypeError):return None

def calculate_receipt(draw,receipt):
    if not isinstance(receipt,dict):raise ValueError("receipt object required")
    game=draw["draw"]["game_id"]
    if game not in ("BONO","LAPR","EMIL"):raise ValueError("unsupported game")
    if receipt.get("game_id")!=game or str(receipt.get("id_sorteo"))!=str(draw["draw"]["id_sorteo"]):
        raise ValueError("receipt game/draw mismatch")
    entries=receipt.get("entries")
    if not isinstance(entries,list) or not entries:raise ValueError("nonempty entries required")
    if receipt.get("voided") is True:
        return {"status":"voided","gross_eur":None,"prize_certified":False}
    issues=[]
    if receipt.get("validated") is not True or receipt.get("voided") is not False:
        issues.append("receipt_validity_not_confirmed")
    if receipt.get("multiple_draws") is not False:
        issues.append("multi_draw_receipt_not_supported")
    if game=="EMIL" and draw["result"].get("lluvia"):
        issues.append("lluvia_de_millones_requires_separate_validation")
    parts=[]
    for idx,entry in enumerate(entries):
        if not isinstance(entry,dict):raise ValueError("entry object required")
        if any(k in entry for k in ("joker_code","millon_code")):
            raise ValueError("linked codes must appear once at receipt level")
        ticket={**entry,"game_id":game,"id_sorteo":draw["draw"]["id_sorteo"]}
        if game=="LAPR":
            if "reintegro" not in receipt:
                issues.append("missing_receipt_reintegro")
            else:ticket["reintegro"]=receipt["reintegro"]
        elif game=="BONO" and "reintegro" in receipt:
            ticket["reintegro"]=receipt["reintegro"]
        result=award(draw,ticket)
        if result.get("award_status")!="candidate_not_certified":
            issues.append("pending_primary_result_"+str(idx));continue
        if result.get("issues"):
            issues.extend(result["issues"])
        if result.get("category") is not None:
            primary=result.get("primary_award")
            amount=_euros(primary.get("amount_eur")) if primary else None
            if amount is None:issues.append("missing_primary_amount_"+str(idx))
            elif primary.get("winners") is not None and str(primary["winners"]).strip()=="0" and amount>0:
                issues.append("positive_award_without_winners_"+str(idx))
            else:parts.append({"product":game,"entry":idx,"amount_eur":str(amount)})
    # Reintegro: official scrutiny provides the amount per simple wager.
    # Only a single simple bet with an explicit unit stake is supported.
    if game in ("BONO","LAPR"):
        if "reintegro" not in receipt:
            issues.append("missing_receipt_reintegro")
        else:
            rein=receipt["reintegro"]
            if type(rein)!=int or not 0<=rein<=9:raise ValueError("invalid receipt reintegro")
            official=draw["result"].get("reintegro")
            if official is None:issues.append("pending_reintegro_result")
            elif rein==official:
                rows=[r for r in draw["prizes"] if r["product"]==game
                      and "reintegro" in (r.get("category_label") or "").lower()]
                if len(entries)!=1 or receipt.get("simple_unit_stake") is not True:
                    issues.append("reintegro_multiple_bets_or_stake_unverified")
                elif game=="LAPR" and award(draw,{**entries[0],"game_id":game,
                         "id_sorteo":draw["draw"]["id_sorteo"],"reintegro":rein}).get("category")==1:
                    issues.append("primitiva_special_reintegro_overlap_unverified")
                elif len(rows)!=1 or _euros(rows[0].get("amount_eur")) is None:
                    issues.append("reintegro_scrutiny_missing")
                else:
                    parts.append({"product":"REINTEGRO","entry":None,
                                  "amount_eur":str(_euros(rows[0]["amount_eur"]))})
    if game=="LAPR":
        if receipt.get("joker_selected") is True:
            result=joker(draw,receipt.get("joker_code"))
            amount=_euros(result.get("joker_gross_eur"))
            if amount is None:
                if result.get("status")=="candidate_not_certified" and not result.get("awards"):
                    amount=Decimal("0")
                else:issues.append("joker_result_or_scrutiny_pending")
            if amount is not None:parts.append({"product":"JOKER","entry":None,"amount_eur":str(amount)})
        elif receipt.get("joker_selected") is not False:
            issues.append("joker_participation_unknown")
    if game=="EMIL":
        if "millon_code" not in receipt:issues.append("missing_receipt_millon_code")
        else:
            result=millon(draw,receipt["millon_code"])
            if result.get("matches") is None:issues.append("millon_result_pending")
            elif result["matches"]:
                row=result.get("award")
                amount=_euros(row.get("amount_eur")) if row else None
                if amount is None:issues.append("millon_scrutiny_pending")
                else:parts.append({"product":"EL_MILLON","entry":None,"amount_eur":str(amount)})
    # Never return a partial total if any applicable prize is unresolved.
    total=sum((Decimal(p["amount_eur"]) for p in parts),Decimal("0")) if not issues else None
    return {"status":"gross_estimate" if total is not None else "blocked_incomplete_receipt",
            "gross_eur":str(total) if total is not None else None,
            "components":parts,"issues":sorted(set(issues)),
            "prize_certified":False,"receipt_authentic":False,"net_eur":None,
            "warning":"Importe bruto orientativo; no acredita resguardo, titularidad, retenciones ni derecho de cobro"}
