import json,os,tempfile
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from actualizar_lnac_navidad import poll,assess
def write(path,data):
    with tempfile.NamedTemporaryFile(mode="w",dir=path.parent,delete=False,encoding="utf-8") as f:
        json.dump(data,f,ensure_ascii=False,indent=2);f.write("\n")
    os.replace(f.name,path)
def update(root,year,query=poll):
    date=f"{year}-12-22"
    folder=root/"resultados/lnac"; manifest=folder/"manifest.json"
    m=json.loads(manifest.read_text())
    target=folder/f"extra108_{date}.json"
    entry={"date":date,"file":f"./resultados/lnac/{target.name}"}
    existing=[x for x in m["draws"] if x["date"]==date]
    if existing:
        if existing!=[entry] or not target.exists():raise ValueError("Conflicto en histórico")
        data=json.loads(target.read_text())
        if data.get("modelDraw")==108 and data.get("lotoscan",{}).get("complete") is True:return "already_complete"
        raise ValueError("Registro existente no certificado")
    result=query(year)
    if result["status"]!="complete":return "pending"
    data=result["data"]
    if year<2026:raise ValueError("Año fuera del histórico público")
    if target.exists() and json.loads(target.read_text())!=data:raise ValueError("Archivo existente discordante")
    write(target,data)
    m["draws"].append(entry);m["draws"].sort(key=lambda x:x["date"],reverse=True)
    write(manifest,m)
    return "published"
if __name__=="__main__":
    now=datetime.now(ZoneInfo("Europe/Madrid"))
    if (now.month,now.day)!=(12,22) or not (8*60+30<=now.hour*60+now.minute<=23*60):print("outside_window")
    else:print(update(Path("."),now.year))
