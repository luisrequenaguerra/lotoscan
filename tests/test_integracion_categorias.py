#!/usr/bin/env python3
"""Contraste de todas las categorías ordinarias con sorteos oficiales archivados."""
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from normalizar_resultados_selae import parse
from categorizar_premios import award,category

ROOT=Path(__file__).resolve().parents[1]/"datos/lotoscan/historico_oficial"
# Cada par (aciertos, estrellas) que tiene categoría en el escrutinio.
EURO={(5,2):1,(5,1):2,(5,0):3,(4,2):4,(4,1):5,(3,2):6,
      (4,0):7,(2,2):8,(3,1):9,(3,0):10,(1,2):11,(2,1):12,(2,0):13}

def choose(winning,hits,universe,count,excluded=()):
    winning=list(winning)
    others=[x for x in range(1,universe+1) if x not in winning and x not in excluded]
    assert len(others)>=count-hits
    return winning[:hits]+others[:count-hits]

class HistoricalCategoryTests(unittest.TestCase):
    def test_all_published_primary_categories(self):
        counters={"BONO":0,"LAPR":0,"EMIL":0}
        for game in counters:
            files=sorted((ROOT/game).glob("*/actual.json"))
            self.assertTrue(files,f"missing archive {game}")
            for path in files:
                draw=parse(json.loads(path.read_text(encoding="utf-8")))
                result=draw["result"]
                if not result["numbers"] or not draw["prizes"]:continue
                n=6 if game!="EMIL" else 5
                scenarios=[]
                if game=="BONO":
                    scenarios=[(6,False,False,1),(5,True,False,2),(5,False,False,3),
                               (4,False,False,4),(3,False,False,5),
                               (2,False,False,None),(0,False,False,None)]
                elif game=="LAPR":
                    scenarios=[(6,False,True,1),(6,False,False,2),
                               (5,True,False,3),(5,False,False,4),
                               (4,False,False,5),(3,False,False,6),
                               (2,False,False,None),(0,False,False,None)]
                else:
                    scenarios=[(hits,stars,False,cat) for (hits,stars),cat in EURO.items()]
                    scenarios += [(0,0,False,None),(1,0,False,None)]
                for hits,flag,rein,expected in scenarios:
                    with self.subTest(game=game,path=path.name,hits=hits,flag=flag,rein=rein):
                        if game=="EMIL":
                            nums=choose(result["numbers"],hits,50,5)
                            stars=choose(result["stars"],flag,12,2)
                            ticket={"game_id":game,"id_sorteo":draw["draw"]["id_sorteo"],
                                    "numbers":nums,"stars":stars}
                        else:
                            comp=result["complementary"]
                            nums=choose(result["numbers"],hits,49,6,
                                        excluded=([comp] if comp is not None else []))
                            if flag:
                                self.assertIsNotNone(comp)
                                nums[-1]=comp
                            ticket={"game_id":game,"id_sorteo":draw["draw"]["id_sorteo"],
                                    "numbers":nums}
                            if game=="LAPR":
                                r=result["reintegro"]
                                self.assertIsNotNone(r)
                                ticket["reintegro"]=r if rein else (r+1)%10
                        actual=award(draw,ticket)
                        self.assertEqual(actual["number_hits"],hits)
                        self.assertEqual(actual["category"],expected)
                        if expected is not None:
                            self.assertIsNotNone(actual["primary_award"],
                                f"category {expected} absent: {path}")
                            self.assertEqual(str(actual["primary_award"]["category"]),str(expected))
                            self.assertEqual(actual["primary_award"]["raw_amount"],
                                next(row["raw_amount"] for idx,row in enumerate(
                                    [r for r in draw["prizes"] if r["product"]==game],1)
                                    if int(row["category_code"] if row["category_code"] is not None else idx)==expected))
                        else:
                            self.assertIsNone(actual["primary_award"])
                        self.assertIsNone(actual["total_eur"])
                        self.assertFalse(actual["prize_certified"])
                        counters[game]+=1
        print("CATEGORY_CASES",json.dumps(counters,sort_keys=True))
        for count in counters.values():self.assertGreater(count,0)
if __name__=="__main__":unittest.main()
