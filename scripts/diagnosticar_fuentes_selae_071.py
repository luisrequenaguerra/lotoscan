#!/usr/bin/env python3
"""Diagnóstico de acceso público SELAE: solo lectura, sin publicar ni modificar datos."""
import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

BASE="https://www.loteriasyapuestas.es"
GAMES=["EMIL","LAPR","BONO","ELGR","EDMS","LAQU","QGOL","LOTU","QUPL"]
PDFS=[
"/f/loterias/documentos/Lotería Nacional/listas de premios/SM_LISTAOFICIAL.A2026.S092.pdf",
"/f/loterias/documentos/Lotería Nacional/listas de premios/SM_LISTAOFICIAL.A2026.S093.pdf",
"/f/loterias/documentos/Lotería Nacional/listas de premios/SM_LISTAOFICIAL.A2026.S094.pdf",
]
HEADERS={"User-Agent":"LotoScan-diagnostico/0.71 (+lectura publica)","Accept":"*/*"}
def probe(name,url):
    req=urllib.request.Request(url,headers=HEADERS)
    result={"name":name,"url":url}
    try:
        with urllib.request.urlopen(req,timeout=15) as response:
            data=response.read(250001)
            result.update(status=response.status,content_type=response.headers.get("Content-Type",""),bytes_sample=len(data))
            result["pdf_signature"]=data.startswith(b"%PDF-")
            if b"json" in response.headers.get("Content-Type","").encode().lower():
                try:
                    obj=json.loads(data)
                    result["json_keys"]=sorted(obj.keys()) if isinstance(obj,dict) else ["array"]
                except (ValueError,UnicodeDecodeError):
                    result["json_keys"]=[]
            if data[:100].lstrip().lower().startswith((b"<!doctype html",b"<html")):
                result["html_response"]=True
    except urllib.error.HTTPError as exc:
        result.update(status=exc.code,content_type=exc.headers.get("Content-Type",""),error="HTTP")
    except (urllib.error.URLError,TimeoutError) as exc:
        result.update(error=type(exc).__name__)
    print(json.dumps(result,ensure_ascii=False,sort_keys=True),flush=True)
    return result

def main():
    results=[]
    for code in GAMES:
        url=BASE+"/f/loterias/resultados/"+code.lower()+".html?"+urllib.parse.urlencode({"game_id":code})
        results.append(probe("terceros_"+code,url))
    for path in PDFS:
        url=BASE+urllib.parse.quote(path,safe="/")
        results.append(probe("lista_oficial_"+path.rsplit("/",1)[-1],url))
    print("RESUMEN",json.dumps({"fecha_utc":datetime.now(timezone.utc).isoformat(),"total":len(results),"http_200":sum(x.get("status")==200 for x in results),"pdf_validos":sum(x.get("pdf_signature",False) for x in results)},ensure_ascii=False))
if __name__=="__main__":
    main()
