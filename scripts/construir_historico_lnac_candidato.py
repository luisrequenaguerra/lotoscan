import json,pathlib,hashlib,time,re
from actualizar_resultados_130 import BASE,fetch
from actualizar_lnac_137 import extract
from motor_ordinario_lnac_validado import validate
root=pathlib.Path('salida_lnac_candidato')
root.mkdir(exist_ok=True)
report=[]
def store(d,source):
    summary=extract(d)
    validate(d)
    ident=summary['id_sorteo']
    raw=json.dumps(d,sort_keys=True,ensure_ascii=False,indent=2)+'\n'
    folder=root/ident
    folder.mkdir(exist_ok=True)
    target=folder/'original_resultados.json'
    if target.exists() and target.read_text()!=raw:
        old=target.read_bytes()
        (folder/('revision_'+hashlib.sha256(old).hexdigest()+'.json')).write_bytes(old)
    target.write_text(raw)
    summary['sha256']=hashlib.sha256(raw.encode()).hexdigest()
    summary['fuente']=source
    (folder/'consolidado.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    report.append({'id':ident,'fecha':summary['fecha_sorteo'],'estado':'validado estructuralmente','fuente':source})
for p in sorted(pathlib.Path('datos/lotoscan/loteria_nacional/historico_completo').glob('*/original_resultados.json')):
    store(json.loads(p.read_text()),'archivo previo SELAE')
seen=set()
url=BASE+'resultados1'
try:
    for i in range(7):
        raw,net=fetch(url,retries=0)
        if not raw:raise RuntimeError(str(net))
        d=json.loads(raw)
        ident=str(d.get('drawIdSorteo',''))
        if i and ident!=expected:raise ValueError('ID distinto del solicitado')
        if ident in seen:break
        seen.add(ident)
        try:store(d,url)
        except Exception as e:report.append({'id':ident,'estado':'rechazado','error':str(e)})
        expected=str(d.get('drawIdSorteoAnterior',''))
        if not re.fullmatch(r'\d{6,20}',expected) or expected in seen:break
        url=BASE+'resultados2?idsorteo='+expected
        time.sleep(5)
except Exception as e:report.append({'estado':'consulta interrumpida','error':str(e)})
(root/'informe.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps(report,ensure_ascii=False))
print('ARCHIVOS VALIDOS',len(list(root.glob('*/original_resultados.json'))))
if not seen:raise SystemExit(1)
