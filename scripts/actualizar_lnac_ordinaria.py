import json,pathlib,hashlib,time,re,os
from datetime import datetime,timedelta,date
from zoneinfo import ZoneInfo
from actualizar_resultados_130 import BASE,fetch
from actualizar_lnac_137 import extract
from motor_ordinario_lnac_v2 import validate,calc
from decimal import Decimal
root=pathlib.Path(os.environ.get('LNAC_ROOT','datos/lotoscan/lnac_ordinaria'))
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
    assert str(f['fecha_sorteo'])[:10]==summary['fecha_sorteo'][:10], 'fecha distinta'
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

def target_date(now):
    local=now.astimezone(ZoneInfo('Europe/Madrid'))
    w,h,m=local.weekday(),local.hour,local.minute
    if w==3 and h in (22,23) and m in (0,30):return local.date()
    if w==4 and h in (0,2) and m==0:return local.date()-timedelta(days=1)
    if w==5 and ((h in (14,15) and m in (0,30)) or (h in (16,18) and m==0)):return local.date()
    return None

def main():
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument('--date')
    p.add_argument('--slot')
    p.add_argument('--force',action='store_true')
    p.add_argument('--self-test',action='store_true')
    a=p.parse_args()
    if a.self_test:
        from datetime import timezone
        for stamp,expected in [('2026-11-26T21:00:00+00:00','2026-11-26'),('2026-11-27T01:00:00+00:00','2026-11-26'),('2026-07-02T20:30:00+00:00','2026-07-02'),('2026-07-04T16:00:00+00:00','2026-07-04'),('2026-11-28T13:00:00+00:00','2026-11-28'),('2026-11-28T12:00:00+00:00',None)]:
            result=target_date(datetime.fromisoformat(stamp))
            assert (str(result) if result else None)==expected,(stamp,result)
        print('PASS Madrid winter/summer and midnight')
        return
    if a.date:
        day=date.fromisoformat(a.date)
    else:
        now=datetime.now(ZoneInfo('UTC'))
        if a.slot:
            minute,hour=map(int,a.slot.split()[:2])
            slot=now.replace(hour=hour,minute=minute,second=0,microsecond=0)
            if slot>now:slot-=timedelta(days=1)
            if now-slot>timedelta(hours=3):raise RuntimeError('scheduled execution too late')
            now=slot
        day=target_date(now)
    if day is None:
        print('Outside Madrid schedule; no requests');return
    if day.weekday() not in (3,5):raise ValueError('Only Thursday/Saturday')
    for path in root.glob('*/consolidado.json'):
        v=json.loads(path.read_text())
        if v['fecha_sorteo'][:10]==str(day) and v.get('contraste_fecha2') and not a.force:
            print('Already validated; no requests',day);return
    raw,net=fetch(BASE+'resultados1',retries=0)
    if not raw:raise RuntimeError(str(net))
    d=json.loads(raw)
    if d['fechaSorteo'][:10]!=str(day):
        if not a.date:
            print('Awaiting publication',day);return
        time.sleep(5)
        raw,net=fetch(BASE+'fecha2?game_id=LNAC&fecha_sorteo='+day.strftime('%Y%m%d'),retries=0)
        if not raw:raise RuntimeError(str(net))
        matches=[x for x in json.loads(raw) if str(x.get('fecha_sorteo',''))[:10]==str(day)]
        if len(matches)!=1:raise ValueError('Missing or ambiguous draw')
        ident=str(matches[0]['id_sorteo'])
        if not re.fullmatch(r'[0-9]{6,20}',ident):raise ValueError('Invalid ID')
        time.sleep(5)
        raw,net=fetch(BASE+'resultados2?idsorteo='+ident,retries=0)
        if not raw:raise RuntimeError(str(net))
        d=json.loads(raw)
        assert str(d['drawIdSorteo'])==ident and d['fechaSorteo'][:10]==str(day)
        source=BASE+'resultados2?idsorteo='+ident
    else:source=BASE+'resultados1'
    if d.get('tipoSorteoGeneral') not in ('J','S'):
        print('Nonordinary draw deferred',day);return
    store(d,source)
    print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':main()
