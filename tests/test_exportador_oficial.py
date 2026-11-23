#!/usr/bin/env python3
"""Regresión de la exportación de los nueve juegos SELAE desde el histórico."""
import json
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from exportar_resultados_interfaz import build,GAMES

class OfficialExportAudit(unittest.TestCase):
    def test_all_nine_games_have_published_draws(self):
        exported=build(ROOT)
        self.assertEqual(set(exported["games"]),set(GAMES))
        for game in GAMES:
            with self.subTest(game=game):
                files=list((ROOT/"datos/lotoscan/historico_oficial"/game).glob("*/actual.json"))
                if files:
                    self.assertTrue(exported["games"][game],
                        f"{game}: hay {len(files)} sorteos archivados pero ninguno exportado")

    def test_exported_results_are_complete_and_scrutinized(self):
        exported=build(ROOT)
        for game,draws in exported["games"].items():
            for date,draw in draws.items():
                with self.subTest(game=game,date=date):
                    result=draw["result"]
                    self.assertTrue(draw["prizes"],"Escrutinio ausente")
                    if game=="LAQU":
                        self.assertEqual(len(result["quiniela_signs"]),14)
                        self.assertRegex(str(result["pleno_15"]),r"^[012M]{2}$")
                        self.assertTrue(any(p["product"]=="LAQU" for p in draw["prizes"]))
                    elif game=="QGOL":
                        self.assertEqual(len(result["quinigol_scores"]),6)
                        self.assertTrue(all(__import__("re").fullmatch(r"[012M]{2}",s) for s in result["quinigol_scores"]))
                    elif game=="QUPL":
                        self.assertEqual(len(result["races"]),5)
                        self.assertIsInstance(result["second_fifth_race"],int)
                    else:
                        self.assertTrue(result["numbers"])

    def test_checked_in_json_matches_exporter(self):
        generated=build(ROOT)
        published=json.loads((ROOT/"resultados/selae-interfaz.json").read_text(encoding="utf-8"))
        self.assertEqual(published,generated,
            "El JSON publicado no coincide con el histórico oficial normalizado")

if __name__=="__main__":
    unittest.main()
