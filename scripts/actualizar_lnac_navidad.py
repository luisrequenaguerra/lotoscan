"""Consulta anual LNAC 108. Resultado completo o pendiente; sin publicación."""
import json,re,time
from actualizar_resultados_130 import BASE,fetch
from normalizar_lnac_108 import normalize
from motor_navidad_108 import calculate
from consultar_navidad_119 import premios_mayores
from collections import Counter
def discover(raw,year):
    rows=json.loads(raw)
    if not isinstance(rows,list):raise ValueError("Calendario inválido")
    matches=[r for r in rows if r.get("game_id")=="LNAC" and str(r.get("fecha_sorteo","")).startswith(f"{year}-12-22") and "NAVIDAD" in r.get("nombre","").upper()]
    if len(matches)!=1:raise ValueError("Sorteo no identificado unívocamente")
    draw=str(matches[0].get("id_sorteo",""))
    if not re.fullmatch(r"[0-9]+",draw):raise ValueError("Identificador inválido")
    return draw
def extract(html):
    a=html.find("startSimpleTablas");b=html.find("endSimpleTablas",a+1)
    if a<0 or b<=a:raise ValueError("Tablas no disponibles")
    entries=[(n.zfill(5),int(t),int(w)) for n,t,w in re.findall(r"\[(\d{1,5})\]\s*=\s*(\d+):(\d+)\s*;",html[a:b])]
    if Counter((t,w) for n,t,w in entries)!=Counter({(t,w):20 for t in range(1,10) for w in range(1,11)})+Counter({(10,1):7}):raise ValueError("Tablas incompletas o distribución inesperada")
    return entries
def assess(raw,entries,year,draw):
    try:
        data=normalize(raw,entries,year,draw)
        majors=premios_mayores(raw)
        result=calculate(majors,[e["decimo"] for e in data["extraccionesDeCincoCifras"]])
        for n,parts in majors.items():
            if sum(v for c,v in result[n])!=parts[0]["prize_raw"]:raise ValueError("Importe oficial discordante")
        return {"status":"complete","data":data}
    except (ValueError,TypeError,KeyError,AttributeError) as e:
        return {"status":"pending","reason":str(e)}
def poll(year):
    evidence=[]
    def get(url):
        raw,meta=fetch(url,retries=0)
        evidence.append({"url":url,"network":meta})
        if not raw:raise ValueError("Fuente no disponible")
        return raw
    try:
        draw=discover(get(BASE+f"fechav3?game_id=LNAC&fecha_sorteo={year}1222"),year)
        time.sleep(5)
        raw=json.loads(get(BASE+"resultados2?idsorteo="+draw))
        time.sleep(5)
        html=get("https://www.loteriasyapuestas.es/es/loteria-nacional/tablas-y-alambres?drawId="+draw).decode("utf-8")
        result=assess(raw,extract(html),year,draw)
    except (ValueError,TypeError,KeyError,AttributeError,OSError) as e:
        result={"status":"pending","reason":str(e)}
    return {**result,"evidence":evidence}
if __name__=="__main__":
    import argparse
    from datetime import datetime
    from zoneinfo import ZoneInfo
    p=argparse.ArgumentParser();p.add_argument("--year",type=int,default=datetime.now(ZoneInfo("Europe/Madrid")).year)
    args=p.parse_args()
    print(json.dumps(poll(args.year),ensure_ascii=False))
