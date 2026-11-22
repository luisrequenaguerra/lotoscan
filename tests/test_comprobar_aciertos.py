#!/usr/bin/env python3
"""Unit tests for conservative ticket matching."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from normalizar_resultados_selae import parse
from comprobar_aciertos import compare

class TicketTests(unittest.TestCase):
    def draw(self,game,comb,**extras):
        return parse({"game_id":game,"id_sorteo":"123456","fecha_sorteo":"2026-11-20",
                      "combinacion":comb,"escrutinio":[{"tipo":"test","premio":"1,50","ganadores":"2"}],**extras})
    def test_bonoloto(self):
        d=self.draw("BONO","10 - 13 - 14 - 24 - 25 - 33 C(37) R(2)")
        x=compare(d,{"game_id":"BONO","id_sorteo":"123456","numbers":[10,13,14,24,25,37],"reintegro":2})
        self.assertEqual(x["number_hits"],5)
        self.assertTrue(x["complementary_hit"])
        self.assertTrue(x["reintegro_hit"])
        self.assertIsNone(x["prize_eur"])
    def test_primitiva_joker(self):
        d=self.draw("LAPR","01 - 06 - 14 - 23 - 30 - 39 C(36) R(2)",
                    joker={"combinacion":"2369520"})
        x=compare(d,{"game_id":"LAPR","id_sorteo":"123456",
            "numbers":[1,6,14,23,30,39],"joker_code":"2369520"})
        self.assertEqual(x["number_hits"],6)
        self.assertTrue(x["joker_full_match"])
        self.assertFalse(x["joker_partial_prizes_checked"])
    def test_euromillones(self):
        d=self.draw("EMIL","15 - 18 - 31 - 37 - 41 - 01 - 05",
                    millon={"combinacion":"HJL03816"})
        x=compare(d,{"game_id":"EMIL","id_sorteo":"123456",
            "numbers":[15,18,31,37,41],"stars":[1,5],"millon_code":"hjl03816"})
        self.assertEqual((x["number_hits"],x["star_hits"]),(5,2))
        self.assertTrue(x["millon_code_matches"])
    def test_pending(self):
        d=self.draw("BONO","")
        self.assertEqual(compare(d,{"game_id":"BONO","id_sorteo":"123456",
            "numbers":[1,2,3,4,5,6]})["status"],"pending_result")
    def test_wrong_draw_rejected(self):
        with self.assertRaises(ValueError):
            compare(self.draw("BONO","1 - 2 - 3 - 4 - 5 - 6 C(7) R(8)"),
                {"game_id":"BONO","id_sorteo":"999999","numbers":[1,2,3,4,5,6]})
    def test_duplicate_numbers_rejected(self):
        with self.assertRaises(ValueError):
            compare(self.draw("BONO","1 - 2 - 3 - 4 - 5 - 6 C(7) R(8)"),
                {"game_id":"BONO","id_sorteo":"123456","numbers":[1,1,2,3,4,5]})
if __name__=="__main__": unittest.main()
