#!/usr/bin/env python3
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from normalizar_resultados_selae import parse
from premios_joker_millon import joker,millon
from categorizar_premios import award

ROOT=Path(__file__).resolve().parents[1]/"datos/lotoscan/historico_oficial"

class LinkedGameTests(unittest.TestCase):
    def _draws(self,game):
        for p in sorted((ROOT/game).glob("*/actual.json")):
            d=parse(json.loads(p.read_text(encoding="utf-8")))
            if d["result"].get("joker" if game=="LAPR" else "millon") and d["prizes"]:
                yield d
    def test_joker_annex_ii_cumulative_awards(self):
        from premios_joker_millon import JOKER_TABLE
        checked=0
        self.assertEqual(len(JOKER_TABLE),28)
        for d in self._draws("LAPR"):
            code=str(d["result"]["joker"]["combinacion"]).zfill(7)
            self.assertEqual(joker(d,code)["joker_gross_eur"],"1000000")
            for (first,last),(cat,amount) in JOKER_TABLE.items():
                if first==7:continue
                chars=list(code)
                for i in range(first,7-last):
                    chars[i]=str((int(chars[i])+1)%10)
                candidate="".join(chars)
                result=joker(d,candidate)
                self.assertEqual(result["matched_categories"],[cat])
                self.assertEqual(result["joker_gross_eur"],str(amount))
                self.assertEqual(len(result["awards"]),1)
                self.assertIsNone(result["total_eur"])
            checked+=1
        self.assertGreater(checked,0)
        print("JOKER_DRAWS",checked)
    def test_millon_winner_nonwinner_and_format(self):
        checked=0
        for d in self._draws("EMIL"):
            code=str(d["result"]["millon"]["combinacion"])
            win=millon(d,code.lower())
            self.assertTrue(win["matches"])
            self.assertIsNotNone(win["award"])
            self.assertIsNone(win["total_eur"])
            chars=list(code)
            chars[-1]=str((int(chars[-1])+1)%10)
            lose=millon(d,"".join(chars))
            self.assertFalse(lose["matches"])
            self.assertIsNone(lose["award"])
            ticket={"game_id":"EMIL","id_sorteo":d["draw"]["id_sorteo"],
                    "numbers":d["result"]["numbers"],"stars":d["result"]["stars"],
                    "millon_code":code}
            self.assertTrue(any(r["product"]=="EL_MILLON" for r in award(d,ticket)["supplementary_awards"]))
            checked+=1
        self.assertGreater(checked,0)
        print("MILLON_DRAWS",checked)
    def test_reject_invalid_codes(self):
        d=next(self._draws("LAPR"))
        for code in ("123456","abcdefg","12345678"):
            with self.assertRaises(ValueError):joker(d,code)
        d=next(self._draws("EMIL"))
        for code in ("A1234567","AB123456","ABC1234"):
            with self.assertRaises(ValueError):millon(d,code)
if __name__=="__main__":unittest.main()
