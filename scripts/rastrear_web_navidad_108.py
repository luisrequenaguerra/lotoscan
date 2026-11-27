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
queue=[("https://www.loteriasyapuestas.es/es/loteria-nacional/tablas-y-alambres.provisional",2)]+[("https://www.loteriasyapuestas.es/es/loteria-nacional/tablas-y-alambres?drawId="+i,2) for i in ("1259409102","1295909102")]+[("https://www.loteriasyapuestas.es/servicios/fechav3?game_id=LNAC&fecha_sorteo="+d,2) for d in ("20241222","20251222","20261222")]+[("https://www.loteriasyapuestas.es/f/loterias/resultados/lnac.html?game_id=LNAC&fecha_sorteo=20261222",2)]
seen=set();report=[]
while queue and len(seen)<45:
    url,depth=queue.pop(0)
    if url in seen or urllib.parse.urlparse(url).hostname not in hosts:continue
    seen.add(url);row={"url":url}
    try:
        try:r=urllib.request.urlopen(urllib.request.Request(url,headers=HEADERS),timeout=25)
        except urllib.error.HTTPError as e:r=e
        with r:
            row["headers"]={k:r.headers.get(k) for k in ("Date","Last-Modified","ETag","Age","Cache-Control","Content-Type")};raw=r.read(8_000_001);row.update(http=r.status,final_url=r.geturl(),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
        if len(raw)>8_000_000:raise ValueError("too large")
        (out/f"{len(seen):02}.raw").write_bytes(raw)
        if row["http"]==200:
            s=raw.decode("utf-8",errors="replace")
            row["matches"]=list(dict.fromkeys(s[max(0,m.start()-90):m.end()+130] for m in pattern.finditer(s)))[:180]
            p=Links();p.feed(s)
            row["links"]=p.urls[:100]
            try:
                obj=json.loads(s)
                row["json_keys"]=list(obj) if isinstance(obj,dict) else []
                if isinstance(obj,dict):
                    entries=obj.get("compruebe",[])
                    row["drawIdSorteo"]=obj.get("drawIdSorteo")
                    row["entries"]=len(entries)
                    row["sample"]=entries[:5]
                    row["unique_decimos"]=len(set(str(e.get("decimo")) for e in entries if isinstance(e,dict)))
            except (ValueError,TypeError):pass
            row["table_markers"]={k:s.find(k) for k in ("startSimpleTablas","endSimpleTablas")}
            a=s.find("startSimpleTablas");b=s.find("endSimpleTablas",a+1)
            if a>=0 and b>a:
                fragment=s[a:b]
                (out/f"{len(seen):02}.tablas.html").write_text(fragment)
                row["fragment_bytes"]=len(fragment.encode())
                row["fragment_sample"]=fragment[:2500]
                row["fragment_five_digit_tokens"]=len(re.findall(r"(?<!\d)\d{5}(?!\d)",fragment))
            if "fechav3" in url:row["date_response"]=s[:5000]
            row["five_digit_tokens"]=len(re.findall(r"(?<!\d)\d{5}(?!\d)",s))
            if depth<2:
                for link in sorted(p.urls,key=lambda v: (not bool(re.search(r'lnac|navidad|comprobar|resultado|premio|tercero',v,re.I)),not bool(re.search(r'\.js(?:\?|$)',v,re.I)))):
                    u=urllib.parse.urljoin(row["final_url"],link).split("#")[0]
                    if urllib.parse.urlparse(u).hostname in hosts and u not in seen and re.search(r'\.js(?:\?|$)|lnac|navidad|comprobar|resultado|tercero|widget',u,re.I):queue.append((u,depth+1))
    except Exception as e:row["error"]=str(e)
    report.append(row);print(json.dumps(row,ensure_ascii=False),flush=True)
    (out/"informe.json").write_text(json.dumps(report,ensure_ascii=False,indent=2))
    time.sleep(5)
