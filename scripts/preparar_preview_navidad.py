import json, shutil, sys
from pathlib import Path
src=Path(".")
out=Path(sys.argv[1])
out.mkdir(parents=True,exist_ok=True)
from actualizar_lnac_navidad import poll
html=(src/"index.html").read_text()
for old,new in [
 ("lotoscan_tickets_v010","lotoscan_preview_navidad_108"),
 ("const min=new Date(2026,0,1);","const min=new Date(game==='loteria_nacional'?2024:2026,0,1);"),
 ("if(date<'2026-01-01')","if(date<'2026-01-01' && !(game==='loteria_nacional' && ['2024-12-22','2025-12-22'].includes(date)))"),
 ("<body>","<body><div style='background:#fff3cd;color:#594500;text-align:center;padding:6px;font-size:12px'>PRUEBAS NAVIDAD · 2024 y 2025 · No es producción</div>")
]:
 assert html.count(old)==1,old
 html=html.replace(old,new)
(out/"index.html").write_text(html)
shutil.copytree(src/"resultados",out/"resultados",dirs_exist_ok=True)
for p in src.iterdir():
 if p.is_dir() and p.name in ("assets","icons","img","images","data"):
  shutil.copytree(p,out/p.name,dirs_exist_ok=True)
 elif p.is_file() and p.suffix in (".png",".svg",".ico",".css",".js",".webmanifest"):
  shutil.copy2(p,out/p.name)
folder=out/"resultados/lnac"
manifest=folder/"manifest.json"
m=json.loads(manifest.read_text())
for year in (2024,2025):
 r=poll(year)
 assert r["status"]=="complete",r
 name=f"extra108_{year}-12-22.json"
 (folder/name).write_text(json.dumps(r["data"],ensure_ascii=False))
 m["draws"].append({"date":f"{year}-12-22","file":f"./resultados/lnac/{name}"})
manifest.write_text(json.dumps(m,ensure_ascii=False))
print("PREVIEW_NAVIDAD OK")
