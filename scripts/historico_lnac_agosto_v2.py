import json,pathlib,hashlib,time,re
from actualizar_resultados_130 import BASE,fetch
from actualizar_lnac_137 import extract
from motor_ordinario_lnac_v2 import validate,calc
from decimal import Decimal
root=pathlib.Path('salida_lnac_candidato')
root.mkdir(exist_ok=True)
report=[]
def numero5(value):
    value=str(value)
    if not re.fullmatch(r'[0-9]{1,5}',value):
        raise ValueError('Número de décimo inválido: '+value)
    return value.zfill(5)

def store(d,source):
    summary=extract(d)
    validate(d)
    ident=summary['id_sorteo']
    day=summary['fecha_sorteo'][:10].replace('-','')
    time.sleep(5)
    raw,net=fetch(BASE+'fecha2?game_id=LNAC&fecha_sorteo='+day,retries=0)
    if not raw:raise RuntimeError('STOP NETWORK '+str(net))
    f=next(x for x in json.loads(raw) if str(x['id_sorteo'])==ident)
    assert numero5(f['combinacion']['primer_premio'])==numero5(d['primerPremio']['decimo']), 'primer premio distinto'
    assert numero5(f['combinacion']['Segundo_premio'])==numero5(d['segundoPremio']['decimo']), 'segundo premio distinto'
    assert sorted(f['reintegros'])==sorted(x['decimo'] for x in d['reintegros'])
    assert Decimal(str(f['tenthPrice']))==Decimal(str(d['precioDecimo']))
    for k,n in [('extraccionesDeCuatroCifras',4),('extraccionesDeTresCifras',3),('extraccionesDeDosCifras',2)]:
        assert sorted(Decimal(x['premio'])*100 for x in f['escrutinio'] if x['tipo']==f'Extracción de {n} cifras')==sorted(Decimal(str(x['prize'])) for x in d[k])
    total=sum(calc(d,f'{n:05d}')['importe_centimos'] for n in range(100000))
    assert total==int(d['precioDecimo'])*7000000
    summary['contraste_fecha2']=True
    summary['total_centimos']=total
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
seen=set()
url=BASE+'resultados1'
try:
    for i in range(40):
        raw,net=fetch(url,retries=0)
        if not raw:raise RuntimeError(str(net))
        d=json.loads(raw)
        ident=str(d.get('drawIdSorteo',''))
        if i and ident!=expected:raise ValueError('ID distinto del solicitado')
        if d['fechaSorteo'][:10]<'2026-08-01':
            report.append({'estado':'limite agosto alcanzado','fecha':d['fechaSorteo']});break
        if ident in seen:break
        seen.add(ident)
        try:store(d,url)
        except Exception as e:
            report.append({'id':ident,'fecha':d.get('fechaSorteo'),'estado':'rechazado','error':str(e)})
            if 'STOP NETWORK' in str(e):break
        expected=str(d.get('drawIdSorteoAnterior',''))
        if not re.fullmatch(r'\d{6,20}',expected) or expected in seen:break
        url=BASE+'resultados2?idsorteo='+expected
        time.sleep(5)
except Exception as e:report.append({'estado':'consulta interrumpida','error':str(e)})
(root/'informe.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps(report,ensure_ascii=False))
print('ARCHIVOS VALIDOS',len(list(root.glob('*/original_resultados.json'))))
accepted={x['id'] for x in report if x['estado']=='validado estructuralmente'}
excluded={'1318109062','1321609072','1325309082','1327909090'}
assert any(x['estado']=='limite agosto alcanzado' for x in report), 'historico incompleto'
assert len(accepted)>=29 and seen-accepted==excluded, 'sorteos pendientes: '+str(seen-accepted-excluded)
print('PASS historical coverage',len(accepted))
