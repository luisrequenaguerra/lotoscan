#!/usr/bin/env python3
"""Discovery only: never publishes prizes or modifies existing results."""
import argparse
import datetime as dt
import json
import re
import time
from pathlib import Path
from zoneinfo import ZoneInfo
from actualizar_resultados_130 import BASE, fetch, write_json

MODELS={88:'ordinario',102:'ordinario',82:'extraordinario',101:'extraordinario',105:'extraordinario',112:'extraordinario',113:'extraordinario',108:'navidad'}
MADRID=ZoneInfo('Europe/Madrid')

def identity(value):
    s=str(value or '')
    return s if re.fullmatch(r'[0-9]{6,20}',s) else None

def metadata(d):
    ident=identity(d.get('drawIdSorteo'))
    date=dt.date.fromisoformat(d['fechaSorteo'][:10])
    model=d.get('modelDraw')
    name=' '.join(str(d.get('nombreDelSorteo') or '').split())
    price=d.get('precioDecimo')
    if not ident or not name or type(model) is not int or type(price) not in (int,float) or not 0<price<1000:
        raise ValueError('Metadatos incompletos')
    return dict(id=ident,date=date.isoformat(),model=model,name=name,price=price,
                kind=MODELS.get(model,'desconocido'),source_time=d['fechaSorteo'],
                next_id=identity(d.get('drawIdSorteoSiguiente')))

def discover(registry,request,today,limit=8):
    rows=dict(registry.get('draws',{}))
    issues=[]
    seen=set()
    expected=None
    previous=None
    d=request('resultados1')
    for i in range(limit+1):
        if not isinstance(d,dict):
            issues.append('respuesta_no_disponible');break
        try: m=metadata(d)
        except (ValueError,TypeError,KeyError):
            issues.append('metadatos_invalidos');break
        ident=m['id']
        if ident in seen or (expected and ident!=expected):
            issues.append('cadena_invalida');break
        if previous and (identity(d.get('drawIdSorteoAnterior'))!=previous['id'] or m['date']<=previous['date']):
            issues.append('enlace_o_fecha_inconsistente');break
        seen.add(ident)
        if m['date']>=today.isoformat():
            old=rows.get(ident)
            if old and any(old.get(k)!=m[k] for k in ('date','model','price','name')):
                issues.append('cambio_metadatos:'+ident)
                break
            if not old:
                rows[ident]={**m,'status':'programado' if m['date']>today.isoformat() else 'pendiente'}
        expected=m['next_id']
        if not expected or i==limit:break
        if expected in seen:
            issues.append('cadena_circular');break
        previous=m
        d=request('resultados2?idsorteo='+expected)
    return {'version':1,'draws':rows},issues

def self_test():
    today=dt.date(2026,11,28)
    def item(i,date,model,nxt,prev=None):
        return dict(drawIdSorteo=i,fechaSorteo=date+'T21:00:00Z',modelDraw=model,nombreDelSorteo='Prueba',precioDecimo=15,drawIdSorteoSiguiente=nxt,drawIdSorteoAnterior=prev)
    a=item('100000','2026-11-28',102,'100001')
    b=item('100001','2026-12-03',88,'100002','100000')
    c=item('100002','2026-12-06',82,None,'100001')
    fixtures={'resultados1':a,'resultados2?idsorteo=100001':b,'resultados2?idsorteo=100002':c}
    reg,issues=discover({},fixtures.get,today)
    assert not issues and reg['draws']['100002']['kind']=='extraordinario'
    assert discover(reg,fixtures.get,today)[0]==reg
    assert discover(reg,lambda _:None,today)[0]==reg
    c['drawIdSorteoSiguiente']='100001'
    assert 'cadena_circular' in discover(reg,fixtures.get,today)[1]
    c['modelDraw']=999
    assert discover({},fixtures.get,today)[0]['draws']['100002']['kind']=='desconocido'
    assert discover(reg,fixtures.get,today)[0]==reg
    print('6 pruebas de descubrimiento correctas')

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--self-test',action='store_true')
    p.add_argument('--registro',default='datos/lotoscan/lnac/calendario.json')
    p.add_argument('--limite',type=int,default=8,choices=range(1,9))
    p.add_argument('--guardar',action='store_true')
    args=p.parse_args()
    if args.self_test:return self_test()
    path=Path(args.registro)
    registry=json.loads(path.read_text()) if path.exists() else {}
    def request(endpoint):
        raw,net=fetch(BASE+endpoint,retries=0)
        print(endpoint,net,flush=True)
        time.sleep(8)
        if not raw:return None
        try:return json.loads(raw)
        except ValueError:return None
    result,issues=discover(registry,request,dt.datetime.now(MADRID).date(),args.limite)
    print(json.dumps({'registry':result,'issues':issues},ensure_ascii=False,indent=2))
    if args.guardar:write_json(path,result)

if __name__=='__main__':main()
