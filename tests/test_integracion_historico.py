#!/usr/bin/env python3
"""Pruebas de integración sobre JSON oficiales archivados (sin apostar ni certificar)."""
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from normalizar_resultados_selae import parse
from categorizar_premios import award
from reglas_acumulacion import assess

ROOT=Path(__file__).resolve().parents[1]/"datos/lotoscan/historico_oficial"
GAMES=("BONO","LAPR","EMIL")

class HistoricalIntegrationTests(unittest.TestCase):
    def test_every_archived_complete_draw(self):
        seen={}
        for game in GAMES:
            files=sorted((ROOT/game).glob("*/actual.json"))
            self.assertTrue(files,f"no archived data for {game}")
            verified=0
            for path in files:
                with self.subTest(game=game,path=str(path)):
                    raw=json.loads(path.read_text(encoding="utf-8"))
                    draw=parse(raw)
                    if not draw["result"]["numbers"] or not draw["prizes"]:continue
                    numbers=draw["result"]["numbers"]
                    ticket={"game_id":game,"id_sorteo":draw["draw"]["id_sorteo"],
                            "numbers":numbers[:]}
                    if game=="EMIL":
                        ticket["stars"]=draw["result"]["stars"][:]
                    elif game=="LAPR":
                        ticket["reintegro"]=draw["result"]["reintegro"]
                    matched=award(draw,ticket)
                    self.assertEqual(matched["number_hits"],len(numbers))
                    self.assertEqual(matched["category"],1)
                    self.assertIsNotNone(matched["primary_award"],
                        f"missing first category in {path}")
                    self.assertEqual(matched["primary_award"]["raw_amount"],
                        next(r["raw_amount"] for r in draw["prizes"]
                             if r["product"]==game))
                    guarded=assess(draw,ticket)
                    self.assertIsNone(guarded["total_eur"])
                    self.assertFalse(guarded["prize_certified"])
                    verified+=1
            seen[game]=verified
            self.assertGreater(verified,0,f"no complete archived draws for {game}")
        print("INTEGRATION_VERIFIED",json.dumps(seen))
if __name__=="__main__":unittest.main()
