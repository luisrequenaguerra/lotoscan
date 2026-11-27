#!/usr/bin/env python3
"""Regresión offline de publicación LNAC con históricos archivados."""
import json
import pathlib
import subprocess
import sys
import tempfile

ROOT=pathlib.Path("datos/lotoscan/loteria_nacional/historico_completo")
for ident in ("1328609092","1329109093","1329309094"):
    path=ROOT/ident/"original_resultados.json"
    assert path.is_file(),f"Falta fixture {ident}"
    d=json.loads(path.read_text(encoding="utf-8"))
    assert str(d["drawIdSorteo"])==ident
with tempfile.TemporaryDirectory() as tmp:
    # Publicador opera en el directorio de trabajo: usar fixtures aislados.
    base=pathlib.Path(tmp)
    for ident in ("1328609092","1329109093","1329309094"):
        src=ROOT/ident/"original_resultados.json"
        dst=base/"datos/lotoscan/loteria_nacional/historico_resultados1"/ident/"original_resultados.json"
        dst.parent.mkdir(parents=True,exist_ok=True)
        dst.write_bytes(src.read_bytes())
    subprocess.run([sys.executable,str(pathlib.Path.cwd()/"scripts/publicar_lnac_070.py")],cwd=base,check=True)
    manifest=json.loads((base/"resultados/lnac/manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"]==1
    assert len(manifest["draws"])==3,manifest
    for item in manifest["draws"]:
        path=base/item["file"].removeprefix("./")
        d=json.loads(path.read_text(encoding="utf-8"))
        assert d["fechaSorteo"][:10]==item["date"]
        assert str(d["drawIdSorteo"])==item["id"]
print("OK: 3 sorteos publicados con rutas compatibles con LotoScan")
