#!/usr/bin/env python3
"""Validación lógica del resguardo: no autentica tickets ni acredita titularidad."""
import re
from premios_joker_millon import joker,millon

def verify_linked_receipt(draw,receipt):
    if not isinstance(receipt,dict):raise ValueError("receipt object required")
    game=draw["draw"]["game_id"]
    if game not in ("LAPR","EMIL"):raise ValueError("unsupported linked game")
    if str(receipt.get("id_sorteo"))!=str(draw["draw"]["id_sorteo"]):
        raise ValueError("receipt draw mismatch")
    if receipt.get("game_id")!=game:raise ValueError("receipt game mismatch")
    if receipt.get("voided") is True:
        return {"status":"voided","gross_eur":None,"receipt_authentic":False,"prize_certified":False}
    if receipt.get("voided") is not False or receipt.get("validated") is not True:
        return {"status":"receipt_validation_pending","gross_eur":None,"receipt_authentic":False,"prize_certified":False}
    if game=="LAPR":
        if receipt.get("joker_selected") is not True:raise ValueError("Joker participation not documented")
        candidate=joker(draw,receipt.get("joker_code"))
        gross=candidate.get("joker_gross_eur")
    else:
        code=receipt.get("millon_code")
        if not isinstance(code,str) or not re.fullmatch(r"[A-Za-z]{3}[0-9]{5}",code):
            raise ValueError("missing or invalid printed El Millon code")
        candidate=millon(draw,code)
        gross=candidate["award"]["amount_eur"] if candidate.get("award") else ("0" if candidate.get("matches") is False else None)
    return {"status":"gross_candidate_from_supplied_receipt",
            "gross_eur":gross,"receipt_authentic":False,"prize_certified":False,
            "total_eur":None,
            "warning":"Declaraciones del resguardo sin autenticación SELAE; no acredita validez, titularidad ni derecho de cobro"}
