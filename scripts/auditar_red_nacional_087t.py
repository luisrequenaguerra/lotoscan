#!/usr/bin/env python3
"""Auditoría pasiva de recursos oficiales SELAE para Lotería Nacional.
No verifica décimos ni publica premios. Solo navega páginas públicas y registra
metadatos de respuestas y fragmentos pertinentes de recursos del dominio oficial.
"""
import json, re, hashlib, traceback, time
from pathlib import Path
from urllib.parse import urlparse, urljoin, parse_qsl
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright

OUT = Path('informes/087t'); OUT.mkdir(parents=True, exist_ok=True)
HOST = 'loteriasyapuestas.es'
TARGETS = [
 ('terceros', 'https://www.loteriasyapuestas.es/f/loterias/resultados/lnac.html?game_id=LNAC&fecha_sorteo=20261119'),
 ('tablas', 'https://www.loteriasyapuestas.es/es/loteria-nacional/tablas-y-alambres'),
]
KEYWORDS = re.compile(r'(?i)extracci[oó]n|alambre|premioDecimo|lnac|resultado|nacional|terminaci[oó]n|reintegro|centena|sorteo|webservice|\.json')
SENSITIVE = re.compile(r'(?i)(token|auth|secret|key|session|cookie|password|credential|jwt|signature)')
responses=[]; failures=[]; pages=[]; candidates=[]; seen=set()

def safe_url(u):
    p=urlparse(u)
    if not (p.hostname or '').lower().endswith(HOST): return '[fuera-del-dominio-oficial]'
    base=f'{p.scheme}://{p.netloc}{p.path}'
    if not p.query: return base
    parts=[f'{k}={"[redactado]" if SENSITIVE.search(k) else v[:80]}' for k,v in parse_qsl(p.query)][:12]
    return base+'?'+'&'.join(parts)

def sample_response(resp):
    req=resp.request
    p=urlparse(resp.url)
    if not (p.hostname or '').lower().endswith(HOST): return
    url=safe_url(resp.url)
    kind=resp.headers.get('content-type','').split(';')[0].lower()
    entry={'url':url,'status':resp.status,'method':req.method,'resource_type':req.resource_type,'content_type':kind}
    if kind in ('application/json','text/json') or kind.endswith('+json'):
        try:
            body=resp.body()[:2_000_000]
            data=json.loads(body)
            entry['json_detectado']=True
            entry['sha256_muestra']=hashlib.sha256(body).hexdigest()
            entry['claves_raiz']=list(data)[:80] if isinstance(data,dict) else []
            matches=[]
            def walk(x,path='',depth=0):
                if depth>7 or len(matches)>60:return
                if isinstance(x,dict):
                    for k,v in list(x.items())[:150]:
                        kp=(path+'.'+str(k)).strip('.')
                        if KEYWORDS.search(str(k)): matches.append({'ruta':kp,'tipo':type(v).__name__,'longitud':len(v) if isinstance(v,(list,dict)) else None})
                        walk(v,kp,depth+1)
                elif isinstance(x,list):
                    for i,v in enumerate(x[:3]):walk(v,path+f'[{i}]',depth+1)
            walk(data)
            entry['campos_candidatos']=matches
        except Exception as e:entry['error_json']=str(e)[:200]
    elif kind in ('application/javascript','text/javascript','text/html','application/x-javascript'):
        try:
            body=resp.body()[:1_000_000].decode('utf-8','replace')
            hits=list(dict.fromkeys(m.group(0)[:120] for m in re.finditer(r'(?i).{0,45}(?:extracciones|premioDecimoWeb|/servicios/|/api/|LNAC|alambres).{0,70}',body)))[:20]
            if hits:entry['referencias_relevantes']=hits
        except Exception as e:entry['error_lectura']=str(e)[:120]
    responses.append(entry)
    if entry.get('json_detectado') or entry.get('referencias_relevantes'):
        candidates.append({'url':url,'content_type':kind,'campos':entry.get('campos_candidatos',[]),'referencias':entry.get('referencias_relevantes',[])})

def main():
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
        context=browser.new_context(locale='es-ES',timezone_id='Europe/Madrid',viewport={'width':1366,'height':900},ignore_https_errors=False)
        context.on('response', lambda r: sample_response(r))
        context.on('requestfailed',lambda r:failures.append({'url':safe_url(r.url),'error':r.failure or 'desconocido'}))
        for label,url in TARGETS:
            pg=context.new_page(); info={'pagina':label,'url':url}
            try:
                resp=pg.goto(url,wait_until='domcontentloaded',timeout=45000)
                info['http_status']=resp.status if resp else None
                pg.wait_for_timeout(8000)
                pg.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                pg.wait_for_timeout(3500)
                info['titulo']=pg.title()[:160]
                info['texto_visible_fragmento']=pg.locator('body').inner_text(timeout=10000)[:2500]
                info['scripts_oficiales']=[safe_url(s) for s in pg.eval_on_selector_all('script[src]','els => els.map(x=>x.src)') if urlparse(s).hostname and urlparse(s).hostname.endswith(HOST)][:100]
                info['links_candidatos']=[safe_url(x) for x in pg.eval_on_selector_all('a[href]','els => els.map(x=>x.href)') if KEYWORDS.search(x) and urlparse(x).hostname and urlparse(x).hostname.endswith(HOST)][:60]
            except Exception as e: info['error']=repr(e)
            pages.append(info)
            pg.close()
        context.close(); browser.close()
    # Deduplicate and order for review
    dedup={}
    for r in responses:dedup[(r['url'],r['status'],r['content_type'])]=r
    rs=list(dedup.values())
    jsons=[r for r in rs if r.get('json_detectado')]
    full=[r for r in jsons if any('extracc' in x['ruta'].lower() for x in r.get('campos_candidatos',[]))]
    report={'version':'0.87T','fecha_utc':datetime.now(timezone.utc).isoformat(),'objetivo':'Identificar JSON de extracciones completas de Lotería Nacional en páginas oficiales SELAE','ambito':'Solo navegación pasiva de dos páginas públicas SELAE','paginas':pages,'total_respuestas_oficiales':len(rs),'total_respuestas_json':len(jsons),'json_con_campos_extracciones':len(full),'candidatos_extracciones':full,'respuestas':rs,'fallos_red':failures[:80],'conclusion':'CANDIDATOS_JSON_DETECTADOS_REQUIEREN_VALIDACION' if full else 'NO_SE_HA_DETECTADO_JSON_DE_EXTRACCIONES_EN_ESTA_NAVEGACION; NO_PRUEBA_INEXISTENCIA','historico_modificado':False,'publicables':0}
    (OUT/'informe_red_nacional_087t.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=[f"LotoScan 0.87T — auditoría pasiva SELAE",f"Páginas: {len(pages)}",f"Respuestas oficiales: {len(rs)}",f"Respuestas JSON: {len(jsons)}",f"JSON con claves de extracciones: {len(full)}",f"Conclusión: {report['conclusion']}",'','Páginas:']
    lines += [f"- {x['pagina']}: HTTP {x.get('http_status','?')}; error={x.get('error','ninguno')}" for x in pages]
    lines += ['','JSON observados:']+[f"- {x['url']} ({x['status']}) claves={x.get('claves_raiz',[])}" for x in jsons]
    (OUT/'resumen_087t.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('\n'.join(lines))

if __name__=='__main__':
    try:main()
    except Exception:
        (OUT/'error_087t.txt').write_text(traceback.format_exc(),encoding='utf-8')
        raise
