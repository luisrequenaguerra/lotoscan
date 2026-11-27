import re,json,time,hashlib,urllib.request,urllib.error,urllib.parse
from pathlib import Path
from html.parser import HTMLParser
from actualizar_resultados_130 import HEADERS
out=Path("evidencias-web-navidad");out.mkdir(exist_ok=True)
hosts={"navidad.loteriasyapuestas.es","www.loteriasyapuestas.es","loteriasyapuestas.es"}
pattern=re.compile(r"pedrea|alambre|extraccionesDeCinco|numerosPremiados|premioDecimoWeb|terceros|\.json|/servicios/|widget",re.I)
class Links(HTMLParser):
    def __init__(self):super().__init__();self.urls=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        for k in ("src","href"):
            if k in a and a[k] and (tag in ("script","iframe") or re.search(r"navidad|terceros|widget|\.js(?:\?|$)",a[k],re.I)):self.urls.append(a[k])
queue=[("https://navidad.loteriasyapuestas.es/",0),("https://www.loteriasyapuestas.es/es/loteria-de-navidad",0),("https://www.loteriasyapuestas.es/es/webs-de-terceros",0)]
seen=set();report=[]
while queue and len(seen)<24:
    url,depth=queue.pop(0)
    if url in seen or urllib.parse.urlparse(url).hostname not in hosts:continue
    seen.add(url);row={"url":url}
    try:
        try:r=urllib.request.urlopen(urllib.request.Request(url,headers=HEADERS),timeout=25)
        except urllib.error.HTTPError as e:r=e
        with r:
            raw=r.read(8_000_001);row.update(http=r.status,final_url=r.geturl(),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
        if len(raw)>8_000_000:raise ValueError("too large")
        (out/f"{len(seen):02}.raw").write_bytes(raw)
        if row["http"]==200:
            s=raw.decode("utf-8",errors="replace")
            row["matches"]=list(dict.fromkeys(s[max(0,m.start()-90):m.end()+130] for m in pattern.finditer(s)))[:70]
            p=Links();p.feed(s)
            row["links"]=p.urls[:100]
            if depth<2:
                for link in p.urls:
                    u=urllib.parse.urljoin(row["final_url"],link).split("#")[0]
                    if urllib.parse.urlparse(u).hostname in hosts and u not in seen:queue.append((u,depth+1))
    except Exception as e:row["error"]=str(e)
    report.append(row);print(json.dumps(row,ensure_ascii=False),flush=True)
    (out/"informe.json").write_text(json.dumps(report,ensure_ascii=False,indent=2))
    time.sleep(5)
