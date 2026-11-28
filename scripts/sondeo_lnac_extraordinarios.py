#!/usr/bin/env python3
"""Read-only result capture. No prize publication or completeness inference."""
import argparse
import datetime as dt
import json
import hashlib
from pathlib import Path
from zoneinfo import ZoneInfo
from actualizar_resultados_130 import BASE, fetch, write_json
from descubrir_calendario_lnac import metadata

MADRID=ZoneInfo('Europe/Madrid')
MODELS={82,101,105,112,113}
OFFSETS=(60,90,120,150,180,240,1440,2880)

def reconcile(registry,manifest,root):
    for entry in manifest.get('draws',[]):
        path=root/entry['file'].removeprefix('./')
        d=json.loads(path.read_text())
        ident=str(d.get('drawIdSorteo'))
        row=registry.get('draws',{}).get(ident)
        if row and row['date']==entry['date'] and row['model']==d.get('modelDraw'):
            row['status']='publicado'
    return registry

def due(row,now,attempts,clock_verified=False):
    if row.get('kind')!='extraordinario' or row.get('model') not in MODELS or row.get('status')=='publicado':
        return None
    if not clock_verified:return None
    start=dt.datetime.fromisoformat(row['source_time'].replace('Z','+00:00')).astimezone(MADRID)
    elapsed=(now-start).total_seconds()/60
    eligible=[x for x in OFFSETS if x<=elapsed and str(x) not in attempts]
    return max(eligible) if eligible else None

def capture(row,raw,root):
    d=json.loads(raw)
    m=metadata(d)
    if any(m[k]!=row[k] for k in ('id','date','model','price')):
        raise ValueError('Identidad de resultados incompatible')
    digest=hashlib.sha256(raw if isinstance(raw,bytes) else raw.encode()).hexdigest()
    path=root/row['id']/(digest+'.json')
    if not path.exists():write_json(path,d)
    return digest

def self_test():
    import tempfile
    row=dict(id='1330809098',date='2026-12-06',model=82,kind='extraordinario',price=15,status='programado',source_time='2026-12-06T21:00:00Z')
    start=dt.datetime.fromisoformat('2026-12-06T21:00:00+00:00')
    assert due(row,start,{},True) is None
    assert due(row,start+dt.timedelta(minutes=60),{},True)==60
    assert due(row,start+dt.timedelta(minutes=95),{'60':True},True)==90
    assert due(row,start+dt.timedelta(minutes=95),{},False) is None
    assert due(dict(row,status='publicado'),start+dt.timedelta(hours=2),{},True) is None
    assert due(dict(row,kind='navidad',model=108),start+dt.timedelta(hours=2),{},True) is None
    assert due(dict(row,model=999),start+dt.timedelta(hours=2),{},True) is None
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp)
        d=dict(drawIdSorteo=row['id'],fechaSorteo=row['source_time'],modelDraw=82,nombreDelSorteo='Constitución',precioDecimo=15)
        a=capture(row,json.dumps(d),root)
        assert capture(row,json.dumps(d),root)==a
        d['primerPremio']={'numero':'12345'}
        assert capture(row,json.dumps(d),root)!=a
        assert len(list(root.rglob('*.json')))==2
        d['modelDraw']=105
        try:capture(row,json.dumps(d),root)
        except ValueError:pass
        else:raise AssertionError('Identidad incorrecta aceptada')
        p=root/'result.json';write_json(p,dict(drawIdSorteo=row['id'],modelDraw=82))
        reg={'draws':{row['id']:row.copy()}}
        assert reconcile(reg,{'draws':[{'date':row['date'],'file':'./result.json'}]},root)['draws'][row['id']]['status']=='publicado'
    print('Pruebas de planificación, captura y reconciliación correctas')

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--self-test',action='store_true')
    p.add_argument('--registro',default='datos/lotoscan/lnac/calendario.json')
    args=p.parse_args()
    if args.self_test:return self_test()
    root=Path('.')
    registry=json.loads(Path(args.registro).read_text())
    reconcile(registry,json.loads(Path('resultados/lnac/manifest.json').read_text()),root)
    print(json.dumps(registry,ensure_ascii=False,indent=2))
    print('Modo diagnóstico: consultas de premios desactivadas hasta validar reloj y motores')

if __name__=='__main__':main()
