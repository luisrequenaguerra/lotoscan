
#!/usr/bin/env python3
"""Diagnostico de peticiones reales del navegador a SELAE; solo lectura."""
import asyncio, datetime, json, re
from pathlib import Path
from urllib.parse import urlparse
from playwright.async_api import async_playwright

ROOT='https://www.loteriasyapuestas.es/es/resultados/'
GAMES=['gordo-primitiva','quiniela','bonoloto','euromillones','primitiva','eurodreams','loteria-nacional','quinigol','lototurf','quintuple-plus']
OUT=Path('informe_selae_085r.json')
HOSTS={'www.loteriasyapuestas.es','loteriasyapuestas.es'}
KEY=re.compile(r'nota.{0,30}prensa|\.pdf\b|resultad|reparto|premio|drawId|servicios/',re.I)

def excerpt(s, n=300):
    m=KEY.search(s)
    return ' '.join(s[max(0,m.start()-90):m.start()+n].split())[:n] if m else ''

async def main():
    report={'version':'0.85R','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(), 'solo_lectura':True,'juegos':[]}
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True)
        context=await browser.new_context(locale='es-ES',timezone_id='Europe/Madrid',accept_downloads=False)
        for game in GAMES:
            item={'juego':game,'url':ROOT+game,'peticiones':[],'pdfs':[],'enlaces_visibles':[],'errores':[]}
            page=await context.new_page()
            pending=[]
            async def on_response(resp):
                try:
                    u=resp.url
                    parsed=urlparse(u)
                    if parsed.hostname not in HOSTS: return
                    ct=resp.headers.get('content-type','')
                    if not (re.search(r'json|html|pdf',ct,re.I) or KEY.search(u)): return
                    rec={'url':u[:650],'status':resp.status,'tipo':ct[:100]}
                    if 'pdf' in ct.lower() or '.pdf' in parsed.path.lower():
                        item['pdfs'].append(rec)
                    elif 'json' in ct.lower() or '/servicios/' in u:
                        try:
                            body=(await resp.text())[:150000]
                            rec['indicio']=excerpt(body)
                            rec['longitud_muestra']=len(body)
                            rec['contiene_pdf']=bool(re.search(r'\.pdf\b',body,re.I))
                            rec['contiene_premios']=bool(re.search(r'premio|reparto|acertantes',body,re.I))
                            # retain only a short evidence snippet; no full pages
                        except Exception as exc: rec['error_lectura']=str(exc)[:160]
                        item['peticiones'].append(rec)
                except Exception as exc: item['errores'].append(str(exc)[:160])
            page.on('response',lambda response: pending.append(asyncio.create_task(on_response(response))))
            try:
                nav=await page.goto(item['url'],wait_until='domcontentloaded',timeout=35000)
                item['http_pagina']=nav.status if nav else None
                await page.wait_for_timeout(7500)
                # Look for the exact visible 'Nota de prensa' anchors after JS renders.
                item['enlaces_visibles']=await page.locator('a').evaluate_all('''els => els.filter(a => /nota de prensa|\\.pdf/i.test((a.innerText||'')+' '+(a.href||''))).slice(0,15).map(a=>({texto:(a.innerText||'').trim().slice(0,110),url:a.href}))''')
                item['texto_indicio']=excerpt((await page.locator('body').inner_text(timeout=8000))[:18000])
                item['titulos_resultados']=(await page.locator('body').inner_text(timeout=8000))[:700]
            except Exception as exc: item['errores'].append(f'{type(exc).__name__}: {exc}'[:400])
            await asyncio.gather(*pending,return_exceptions=True)
            await page.close()
            item['peticiones']=item['peticiones'][:45]
            item['pdfs']=item['pdfs'][:25]
            report['juegos'].append(item)
            print(game,'HTTP',item.get('http_pagina'),'peticiones',len(item['peticiones']),'enlaces',len(item['enlaces_visibles']),'errores',len(item['errores']),flush=True)
        await browser.close()
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['LotoScan 0.85R - captura de red de navegador SELAE (solo lectura)','']
    for x in report['juegos']:
        lines.append(f"{x['juego']}: HTTP={x.get('http_pagina')} peticiones={len(x['peticiones'])} enlaces_notas={len(x['enlaces_visibles'])} errores={len(x['errores'])}")
        for a in x['enlaces_visibles'][:5]: lines.append('  NOTA: '+a['url'])
        for r in x['peticiones'][:15]:
            if r.get('contiene_pdf') or r.get('contiene_premios') or 'result' in r['url'].lower(): lines.append('  SERVICIO: '+r['url']+' | '+r.get('indicio','')[:120])
        for e in x['errores'][:2]: lines.append('  ERROR: '+e[:150])
    Path('informe_selae_085r.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')

if __name__=='__main__': asyncio.run(main())
