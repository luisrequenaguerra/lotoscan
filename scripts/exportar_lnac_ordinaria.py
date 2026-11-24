import json,pathlib,hashlib
from motor_ordinario_lnac_v2 import validate
root=pathlib.Path('datos/lotoscan/lnac_ordinaria')
out=pathlib.Path('resultados/lnac')
out.mkdir(parents=True,exist_ok=True)
draws=[]
for p in sorted(root.glob('*/original_resultados.json')):
    raw=p.read_bytes()
    d=json.loads(raw)
    s=json.loads((p.parent/'consolidado.json').read_text())
    validate(d)
    assert s['sha256']==hashlib.sha256(raw).hexdigest()
    assert s['contraste_fecha2'] is True
    assert str(d['drawIdSorteo'])==p.parent.name
    name=p.parent.name+'.json'
    (out/name).write_bytes(raw)
    draws.append({'date':d['fechaSorteo'][:10],'file':'./resultados/lnac/'+name})
assert len(draws)>=29
assert len({x['date'] for x in draws})==len(draws)
(out/'manifest.json').write_text(json.dumps({'version':1,'draws':sorted(draws,key=lambda x:x['date'],reverse=True)},indent=2))
print('Exported LNAC',len(draws))
