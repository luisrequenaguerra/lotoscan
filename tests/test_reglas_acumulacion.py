import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from normalizar_resultados_selae import parse
from reglas_acumulacion import assess,assess_receipt

class AccumulationTests(unittest.TestCase):
    def draw(self,game,comb,rows,**kwargs):
        return parse({"game_id":game,"id_sorteo":"123","combinacion":comb,"escrutinio":rows,**kwargs})
    def test_primitiva_special_is_exclusive(self):
        d=self.draw("LAPR","1 - 2 - 3 - 4 - 5 - 6 C(7) R(8)",[
            {"categoria":1,"tipo":"Especial","premio":"1000000"},
            {"categoria":2,"tipo":"Primera","premio":"200000"},
            {"categoria":7,"tipo":"Reintegro","premio":"1"}])
        r=assess(d,{"game_id":"LAPR","id_sorteo":"123","numbers":[1,2,3,4,5,6],"reintegro":8})
        self.assertEqual(r["category"],1)
        self.assertIn("primitiva_special_first_category_exclusive",r["accumulation_issues"])
        self.assertIsNone(r["total_eur"])
    def test_bonoloto_reintegro_requires_receipt(self):
        d=self.draw("BONO","1 - 2 - 3 - 4 - 5 - 6 C(7) R(8)",[
            {"categoria":5,"tipo":"3 aciertos","premio":"4"},
            {"categoria":6,"tipo":"Reintegro","premio":"0,5"}])
        t={"game_id":"BONO","id_sorteo":"123","numbers":[1,2,3,8,9,10],"reintegro":8}
        r=assess(d,t)
        self.assertIn("reintegro_receipt_stake_multiplicity_unverified",r["accumulation_issues"])
        self.assertIsNone(assess_receipt(d,[t,t])["total_eur"])
    def test_euromillones_millon_not_automatically_added(self):
        d=self.draw("EMIL","1 - 2 - 3 - 4 - 5 - 01 - 02",
            [{"tipo":"1ª 5 + 2","premio":"100000"}],
            millon={"combinacion":"ABC12345"},
            escrutinio_millon=[{"tipo":"El Millón","premio":"1000000"}])
        t={"game_id":"EMIL","id_sorteo":"123","numbers":[1,2,3,4,5],
            "stars":[1,2],"millon_code":"ABC12345"}
        r=assess(d,t)
        self.assertIn("millon_ticket_code_ownership_unverified",r["accumulation_issues"])
        self.assertIsNone(r["total_eur"])
    def test_empty_receipt_rejected(self):
        with self.assertRaises(ValueError):assess_receipt({},[])
if __name__=="__main__":unittest.main()
