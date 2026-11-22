#!/usr/bin/env python3
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from normalizar_resultados_selae import parse
from verificar_resguardo_asociado import verify_linked_receipt
ROOT=Path(__file__).resolve().parents[1]/"datos/lotoscan/historico_oficial"
class ReceiptTests(unittest.TestCase):
    def test_linked_receipts_remain_uncertified(self):
        for game,key in (("LAPR","joker_code"),("EMIL","millon_code")):
            found=False
            for path in sorted((ROOT/game).glob("*/actual.json")):
                draw=parse(json.loads(path.read_text(encoding="utf-8")))
                linked=draw["result"].get("joker" if game=="LAPR" else "millon")
                if not isinstance(linked,dict) or not linked.get("combinacion"):continue
                receipt={"game_id":game,"id_sorteo":draw["draw"]["id_sorteo"],
                         "validated":True,"voided":False,key:str(linked["combinacion"])}
                if game=="LAPR":receipt["joker_selected"]=True
                outcome=verify_linked_receipt(draw,receipt)
                self.assertFalse(outcome["receipt_authentic"])
                self.assertFalse(outcome["prize_certified"])
                self.assertIsNone(outcome["total_eur"])
                self.assertIsNotNone(outcome["gross_eur"])
                with self.assertRaises(ValueError):
                    verify_linked_receipt(draw,{**receipt,"id_sorteo":"wrong"})
                pending=verify_linked_receipt(draw,{**receipt,"validated":False})
                self.assertIsNone(pending["gross_eur"])
                found=True
            self.assertTrue(found)
if __name__=="__main__":unittest.main()
