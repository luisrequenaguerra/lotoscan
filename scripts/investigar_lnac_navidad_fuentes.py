import hashlib,json,time,urllib.request,urllib.error,urllib.parse
from pathlib import Path
from datetime import datetime,timezone
BASE="https://www.loteriasyapuestas.es"
OUT=Path("evidencias-navidad"); OUT.mkdir(exist_ok=True)
report=[]
def get(tag,url):
    row={"tag":tag,"url":url,"utc":datetime.now(timezone.utc).isoformat()}
    try:
        req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0","Accept":"application/json,application/pdf,*/*"})
        try: response=urllib.request.urlopen(req,timeout=40)
        except urllib.error.HTTPError as e: response=e
        with response as r:
            raw=r.read(30_000_001)
            row.update(http=r.status,final_url=r.geturl(),content_type=r.headers.get("Content-Type"),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
        if len(raw)>30_000_000: raise ValueError("Respuesta demasiado grande")
        (OUT/(tag+".raw")).write_bytes(raw)
        if row["http"]!=200: return None
        try:
            obj=json.loads(raw)
            row["schema"]=schema(obj)
            return obj
        except (ValueError,UnicodeError): row["pdf"]=raw.startswith(b"%PDF")
    except Exception as e: row["error"]=str(e)
    finally:
        report.append(row)
        (OUT/"informe.json").write_text(json.dumps(report,ensure_ascii=False,indent=2))
        print(json.dumps(row,ensure_ascii=False),flush=True)
        time.sleep(3)
def schema(x,depth=0):
    if depth>5:return type(x).__name__
    if isinstance(x,dict):return {k:(v if k in ("modelDraw","drawIdSorteo","fechaSorteo","nombreDelSorteo","urlListadoOficial","precioDecimo") else schema(v,depth+1)) for k,v in x.items()}
    if isinstance(x,list):return {"count":len(x),"sample":schema(x[0],depth+1) if x else None}
    return type(x).__name__
for year,id_ in [(2024,"1259409102"),(2025,"1295909102")]:
    for param in ("fecha","fecha_sorteo"):
        get(f"{year}_fecha2_{param}",BASE+"/servicios/fecha2?"+urllib.parse.urlencode({"game_id":"LNAC",param:f"{year}1222"}))
    obj=get(f"{year}_resultados2",BASE+"/servicios/resultados2?idsorteo="+id_)
    for d in obj if isinstance(obj,list) else [obj]:
        if not isinstance(d,dict) or str(d.get("drawIdSorteo"))!=id_:continue
        p=d.get("urlListadoOficial")
        if isinstance(p,str):
            url=urllib.parse.urljoin(BASE,urllib.parse.quote(p,safe="/:%?=&"))
            if urllib.parse.urlparse(url).hostname=="www.loteriasyapuestas.es":get(f"{year}_lista_oficial",url)
get("resultados1",BASE+"/servicios/resultados1")
get("fechav3",BASE+"/servicios/fechav3")
