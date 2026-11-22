#!/usr/bin/env python3
"""Motor conservador de compatibilidad: no suma premios sin reglas verificadas."""
from decimal import Decimal, InvalidOperation
from categorizar_premios import award

def _amount(entry):
    if not entry or entry.get("amount_eur") is None:return None
    try:
        value=Decimal(str(entry["amount_eur"]))
        if not value.is_finite() or value<0:return None
        return value
    except (InvalidOperation,ValueError,TypeError):return None

def assess(draw,ticket):
    a=award(draw,ticket)
    if a.get("award_status")!="candidate_not_certified":
        return {**a,"accumulation_status":"pending","total_eur":None}
    game=a["game_id"]
    issues=list(a["issues"])
    primary=a["primary_award"]
    supplements=a["supplementary_awards"]
    # Each basic combination has one exclusive primary category; the special
    # Primitiva category replaces first category, never stack both.
    if game=="LAPR" and a["category"]==1:
        issues.append("primitiva_special_first_category_exclusive")
    # Reintegro is a draw-ticket-level award. Without knowing stake, number of
    # combinations and receipt grouping, it cannot safely be multiplied.
    if game in ("BONO","LAPR") and a.get("reintegro_hit") is True:
        issues.append("reintegro_receipt_stake_multiplicity_unverified")
    # Joker is a separate optional product; partial matching and exclusivity
    # need the complete official rules, not just a full-code equality.
    if game=="LAPR" and "joker_code" in ticket:
        issues.append("joker_highest_matching_category_not_implemented")
    if game=="EMIL" and "millon_code" in ticket:
        issues.append("millon_ticket_code_ownership_unverified")
    if game=="EMIL" and draw["result"].get("lluvia"):
        issues.append("lluvia_de_millones_not_implemented")
    if primary is not None and _amount(primary) is None:
        issues.append("invalid_primary_amount")
    for s in supplements:
        if _amount(s) is None:issues.append("invalid_supplementary_amount_"+s["product"])
    # Zero winners with positive-looking category values, pending scrutiny, and
    # multiple lines all require further validation before payable amounts.
    return {**a,"accumulation_status":"blocked_pending_rule_validation",
            "accumulation_issues":sorted(set(issues)),
            "total_eur":None,"prize_certified":False}

def assess_receipt(draw,entries):
    if not isinstance(entries,list) or not entries:raise ValueError("nonempty entries required")
    results=[assess(draw,entry) for entry in entries]
    return {"entries":results,"total_eur":None,"prize_certified":False,
            "accumulation_status":"blocked_pending_receipt_validation",
            "reason":"Multiple bets, reintegro stake and linked games require receipt-level rules"}
