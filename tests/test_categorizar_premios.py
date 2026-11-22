import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from normalizar_resultados_selae import parse
from categorizar_premios import award,category

class AwardTests(unittest.TestCase):
    def draw(self,game,comb,rows,**extras):
        return parse({"game_id":game,"id_sorteo":"123456","fecha_sorteo":"2026-11-20",
            "combinacion":comb,"escrutinio":rows,**extras})
    def test_bonoloto_second(self):
        d=self.draw("BONO","10 - 13 - 14 - 24 - 25 - 33 C(37) R(2)",
          [{"categoria":2,"tipo":"2ª (5 Aciertos + C)","premio":"1234,56","ganadores":"2"}])
        a=award(d,{"game_id":"BONO","id_sorteo":"123456",
            "numbers":[10,13,14,24,25,37]})
        self.assertEqual(a["category"],2)
        self.assertEqual(a["primary_award"]["amount_eur"],"1234.56")
        self.assertIsNone(a["total_eur"])
    def test_euromillones_first(self):
        d=self.draw("EMIL","15 - 18 - 31 - 37 - 41 - 01 - 05",
          [{"tipo":"1ª 5 + 2","premio":"141899445","ganadores":"1"}])
        a=award(d,{"game_id":"EMIL","id_sorteo":"123456",
            "numbers":[15,18,31,37,41],"stars":[1,5]})
        self.assertEqual(a["category"],1)
        self.assertEqual(a["primary_award"]["amount_eur"],"141899445")
    def test_primitiva_special(self):
        d=self.draw("LAPR","01 - 06 - 14 - 23 - 30 - 39 C(36) R(2)",
          [{"categoria":1,"tipo":"Especial (6 Aciertos + R)","premio":"1000000","ganadores":"1"},
           {"categoria":7,"tipo":"Reintegro","premio":"1","ganadores":"100"}])
        a=award(d,{"game_id":"LAPR","id_sorteo":"123456",
            "numbers":[1,6,14,23,30,39],"reintegro":2})
        self.assertEqual(a["category"],1)
        self.assertTrue(a["issues"])
        self.assertIsNone(a["total_eur"])
    def test_no_prize(self):
        self.assertIsNone(category("BONO",2))
        self.assertIsNone(category("EMIL",1,0))
    def test_missing_scrutiny(self):
        d=self.draw("BONO","10 - 13 - 14 - 24 - 25 - 33 C(37) R(2)",[])
        a=award(d,{"game_id":"BONO","id_sorteo":"123456",
            "numbers":[10,13,14,24,25,37]})
        self.assertIn("missing_primary_category",a["issues"])
if __name__=="__main__":unittest.main()
