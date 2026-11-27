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
                from collections import Counter
                from consultar_navidad_119 import leer_json
                entries=[(n.zfill(5),int(t),int(w)) for n,t,w in re.findall(r"\[(\d{1,5})\]\s*=\s*(\d+):(\d+)\s*;",fragment)]
                counts=Counter(n for n,t,w in entries)
                row["extraction_count"]=len(entries)
                row["unique_count"]=len(counts)
                row["duplicates"]=[n for n,c in counts.items() if c>1]
                row["tables"]=dict(Counter(t for n,t,w in entries))
                year={"1259409102":"2024","1295909102":"2025"}.get(urllib.parse.parse_qs(urllib.parse.urlparse(url).query).get("drawId",[""])[0])
                if year:
                    try:
                        data=leer_json(int(year),None)
                        majors=[]
                        for k in ("primerPremio","segundoPremio","tercerosPremios","cuartosPremios","quintosPremios"):
                            v=data[k]
                            majors.extend(v if isinstance(v,list) else [v])
                        major_numbers={str(v["decimo"]).zfill(5) for v in majors}
                        pedreas=sorted(set(counts)-major_numbers)
                        row["major_count"]=len(major_numbers)
                        row["missing_majors"]=sorted(major_numbers-set(counts))
                        row["pedrea_count"]=len(pedreas)
                        row["structural_pass"]=len(entries)==len(counts)==1807 and len(major_numbers)==13 and not row["missing_majors"] and len(pedreas)==1794
                        (out/f"{year}.extracciones.json").write_text(json.dumps({"year":year,"entries":entries,"pedreas":pedreas,"structural_pass":row["structural_pass"]},indent=2))
                    except Exception as e:row["major_comparison_error"]=str(e)

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

# Independent documentary comparison; fail closed on any mismatch.
from auditar_integracion_navidad_117 import load,scan
from types import SimpleNamespace
from collections import Counter
for year in (2024,2025):
    web=json.loads((out/f"{year}.extracciones.json").read_text())
    assert web["structural_pass"]
    pdf=load(SimpleNamespace(historico=year,pdf=None,url=None))
    rows,pages=scan(pdf)
    candidates=[r["numero"] for r in rows if r["marca"] is None and r["estado"]=="asociacion_univoca" and r["importe_euros_billete"]==1000]
    counts=Counter(candidates)
    expected=set(web["pedreas"]); actual=set(counts)
    result={"year":year,"pdf_sha256":hashlib.sha256(pdf).hexdigest(),"pdf_rows":len(rows),"pdf_candidates":len(candidates),"pdf_unique":len(actual),"duplicates":[n for n,c in counts.items() if c>1],"matching":len(expected&actual),"only_web":sorted(expected-actual),"only_pdf":sorted(actual-expected),"page_warnings":[p for p in pages if p.get("advertencias")]}
    result["pass"]=len(candidates)==len(actual)==1794 and expected==actual and not result["page_warnings"]
    (out/f"{year}.contraste-pedreas.json").write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print("PEDREAS_CONTRASTE "+json.dumps(result,ensure_ascii=False),flush=True)
    if not result["pass"]:raise SystemExit("Contraste documental no superado")

# Compare every number against the independently parsed official PDF components.
from motor_navidad_108 import calculate
from consultar_navidad_119 import premios_mayores,leer_json
from collections import defaultdict
all_pass=True
for year in (2024,2025):
    web=json.loads((out/f"{year}.extracciones.json").read_text())
    majors=premios_mayores(leer_json(year,None))
    motor=calculate(majors,web["pedreas"])
    pdf=load(SimpleNamespace(historico=year,pdf=None,url=None))
    rows,pages=scan(pdf)
    components=defaultdict(list)
    for r in rows:
        assert r["estado"]=="asociacion_univoca" and r["importe_euros_billete"] is not None
        components[r["numero"]].append((r["marca"],r["importe_euros_billete"]*10))
    first=next(n for n,v in majors.items() if v[0]["categoria"]=="primer_premio")
    differences=[]; component_differences=[]; major_differences=[]; total=0; reference_total=0
    with (out/f"{year}.motor-108.jsonl").open("w") as stream:
        for i in range(100000):
            n=f"{i:05d}"; parts=motor.get(n,[]); value=sum(v for c,v in parts)
            # PDF ordinary rows are independent of the web extraction; major JSON may include reintegro.
            ordinary=sum(v for c,v in components[n])
            reference=ordinary+(2000 if n[-1]==first[-1] and n!=first else 0)
            if n in majors:
                reference=sum(int(v["prize_raw"]) for v in majors[n])
                if value!=reference:major_differences.append({"n":n,"motor":value,"json":reference,"pdf":components[n],"parts":parts})
            expected=Counter(components[n])
            actual=Counter((None if c=="pedrea" else "a" if c.startswith("aproximacion_") else "c" if c.startswith("centena_") else "t",v) for c,v in parts if c=="pedrea" or c.startswith(("aproximacion_","centena_","terminacion_")))
            if expected!=actual:component_differences.append({"n":n,"pdf":components[n],"motor":list(actual.elements())})
            if value!=reference:differences.append({"n":n,"motor":value,"reference":reference,"parts":parts})
            total+=value;reference_total+=reference
            stream.write(json.dumps({"n":n,"cents":value,"reference_cents":reference,"parts":parts})+"\n")
    report={"year":year,"numbers":100000,"total_cents":total,"reference_total_cents":reference_total,"amount_mismatches":len(differences),"component_mismatches":len(component_differences),"major_mismatches":len(major_differences),"examples":differences[:25],"component_examples":component_differences[:25],"major_examples":major_differences,"pdf_sha256":hashlib.sha256(pdf).hexdigest(),"reference_limit":"PDF ordinary rows plus major JSON and derived reintegro; not an independent full official payout table"}
    report["pass"]=not differences and not component_differences and total==140000000
    all_pass=all_pass and report["pass"]
    (out/f"{year}.motor-contraste.json").write_text(json.dumps({**report,"differences":differences,"component_differences":component_differences},indent=2))
    print("MOTOR_CONTRASTE "+json.dumps(report),flush=True)
if not all_pass:raise SystemExit("Motor experimental no conciliado")

# Cross-language verification using the Python output as the comparison oracle.
import subprocess
for year in (2024,2025):
    (out/f"{year}.mayores.json").write_text(json.dumps(premios_mayores(leer_json(year,None))))
subprocess.run(["node","scripts/probar_lnac_108.js",str(out)],check=True)
