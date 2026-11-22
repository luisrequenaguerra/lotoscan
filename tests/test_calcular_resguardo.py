#!/usr/bin/env python3
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from normalizar_resultados_selae import parse
from calcular_resguardo import calculate_receipt
ROOT=Path(__file__).resolve().parents[1]/"datos/lotoscan/historico_oficial"

def draws(game):
    for path in sorted((ROOT/game).glob("*/actual.json")):
        d=parse(json.loads(path.read_text(encoding="utf-8")))
        if d["result"]["numbers"] and d["prizes"]:yield d

class ReceiptGrossTests(unittest.TestCase):
    def test_euromillones_multiple_entries_and_millon_once(self):
        checked=0
        for d in draws("EMIL"):
            code=d["result"].get("millon")
            if not isinstance(code,dict) or not code.get("combinacion"):continue
            receipt={"game_id":"EMIL","id_sorteo":d["draw"]["id_sorteo"],
                     "validated":True,"voided":False,"multiple_draws":False,
                     "millon_code":code["combinacion"],
                     "entries":[{"numbers":d["result"]["numbers"],"stars":d["result"]["stars"]}]}
            result=calculate_receipt(d,receipt)
            self.assertFalse(result["prize_certified"])
            self.assertFalse(result["receipt_authentic"])
            self.assertEqual(sum(p["product"]=="EL_MILLON" for p in result["components"]),1)
            self.assertNotIn("missing_receipt_millon_code",result["issues"])
            invalid={**receipt,"entries":[{**receipt["entries"][0],"millon_code":code["combinacion"]}]}
            with self.assertRaises(ValueError):calculate_receipt(d,invalid)
            missing=calculate_receipt(d,{k:v for k,v in receipt.items() if k!="millon_code"})
            self.assertIsNone(missing["gross_eur"])
            checked+=1
        self.assertGreater(checked,0)
    def test_joker_only_once_and_unknown_receipt_blocked(self):
        checked=0
        for d in draws("LAPR"):
            code=d["result"].get("joker")
            if not isinstance(code,dict) or not code.get("combinacion"):continue
            entry={"numbers":d["result"]["numbers"]}
            receipt={"game_id":"LAPR","id_sorteo":d["draw"]["id_sorteo"],
                     "validated":True,"voided":False,"multiple_draws":False,
                     "joker_selected":True,"joker_code":str(code["combinacion"]).zfill(7),
                     "reintegro":(d["result"]["reintegro"]+1)%10,"entries":[entry,entry]}
            result=calculate_receipt(d,receipt)
            self.assertEqual(sum(p["product"]=="JOKER" for p in result["components"]),1)
            self.assertTrue(any(p["amount_eur"]=="1000000" for p in result["components"] if p["product"]=="JOKER"))
            self.assertFalse(result["prize_certified"])
            self.assertIsNone(calculate_receipt(d,{**receipt,"validated":False})["gross_eur"])
            checked+=1
        self.assertGreater(checked,0)
    def test_single_simple_bet_reintegro_from_scrutiny(self):
        for game in ("BONO","LAPR"):
            tested=0
            for d in draws(game):
                result=d["result"]
                nums=result["numbers"]
                # Three correct numbers: ordinary category plus reintegro.
                others=[n for n in range(1,50) if n not in nums and n!=result["complementary"]]
                entry={"numbers":nums[:3]+others[:3]}
                receipt={"game_id":game,"id_sorteo":d["draw"]["id_sorteo"],
                         "validated":True,"voided":False,"multiple_draws":False,
                         "simple_unit_stake":True,"reintegro":result["reintegro"],
                         "joker_selected":False,"entries":[entry]}
                outcome=calculate_receipt(d,receipt)
                rein=[p for p in outcome["components"] if p["product"]=="REINTEGRO"]
                self.assertEqual(len(rein),1)
                expected=next(r["amount_eur"] for r in d["prizes"]
                              if r["product"]==game and "reintegro" in (r["category_label"] or "").lower())
                self.assertEqual(float(rein[0]["amount_eur"]),float(expected))
                self.assertFalse(outcome["prize_certified"])
                tested+=1
            self.assertGreater(tested,0)
    def test_reintegro_blocks_ambiguous_stake(self):
        d=next(draws("LAPR"))
        receipt={"game_id":"LAPR","id_sorteo":d["draw"]["id_sorteo"],
                 "validated":True,"voided":False,"multiple_draws":False,
                 "joker_selected":False,"reintegro":d["result"]["reintegro"],
                 "entries":[{"numbers":d["result"]["numbers"]}]}
        result=calculate_receipt(d,receipt)
        self.assertIsNone(result["gross_eur"])
        self.assertIn("reintegro_multiple_bets_or_stake_unverified",result["issues"])
if __name__=="__main__":unittest.main()
