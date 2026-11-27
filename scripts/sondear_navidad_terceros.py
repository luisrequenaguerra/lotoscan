import json,time,hashlib
from pathlib import Path
from actualizar_resultados_130 import BASE,fetch
from consultar_navidad_119 import leer_json
out=Path("evidencias-terceros");out.mkdir(exist_ok=True)
def inspect(x,path="$"):
    if isinstance(x,dict):
        for k,v in x.items():
            p=path+"."+k
            if isinstance(v,(list,dict)): print(p,"count",len(v))
            elif any(t in k.lower() for t in ("model","fecha","sorteo","url","tipo")):print(p,str(v)[:500])
            if isinstance(v,dict):inspect(v,p)
            elif isinstance(v,list) and v and isinstance(v[0],dict):inspect(v[0],p+"[0]")
for year in (2024,2025):
    j=leer_json(year,None)
    raw=json.dumps(j,ensure_ascii=False,indent=2).encode()
    (out/f"historico_{year}.json").write_bytes(raw)
    print("HISTORICO RECONSTRUIDO",year,hashlib.sha256(raw).hexdigest());inspect(j)
queries=[("control_bono",BASE+"fechav3?game_id=BONO&fecha_sorteo=20261126")]
for year,id_ in [(2024,"1259409102"),(2025,"1295909102")]:
    for endpoint in ("fechav3","fecha2"):
        queries.append((f"{year}_{endpoint}",BASE+endpoint+f"?game_id=LNAC&fecha_sorteo={year}1222"))
    queries.append((f"{year}_resultados2",BASE+"resultados2?idsorteo="+id_))
for name in ("configuracionLNAC","estadoCelebracionLNAC","TempJSONResultadosLNAC_I","TempJSONRepartidoEnLNAC_I"):
    queries.append((name,"https://www.loteriasyapuestas.es/f/loterias/estaticos/json/"+name+".json"))
report=[]
for tag,url in queries:
    raw,net=fetch(url,retries=0)
    row={"tag":tag,"url":url,**net};report.append(row);print(json.dumps(row),flush=True)
    if raw is not None:
        (out/(tag+".raw")).write_bytes(raw)
        try:inspect(json.loads(raw))
        except (ValueError,UnicodeError):print("No JSON")
    (out/"informe.json").write_text(json.dumps(report,indent=2))
    time.sleep(5)
