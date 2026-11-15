
"""LotoScan 0.49: staging multijuego, NO datos oficiales ni premios publicables."""
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path

INPUT = Path('informe-lotoscan-048.json')
STORE = Path('datos_revision/historico.json')
SUMMARY = Path('informe-lotoscan-049.json')
GAMES = ('euromillones','primitiva','bonoloto','loteria_nacional',
         'gordo_primitiva','eurodreams','quiniela','quinigol','lototurf','quintuple_plus')
CATS = {f'{a}+{b}' for a,b in [(5,2),(5,1),(5,0),(4,2),(4,1),(3,2),(4,0),(2,2),(3,1),(3,0),(1,2),(2,1),(2,0)]}

def valid_em(item):
    try:
        d = date.fromisoformat(item['fecha'])
        nums, stars = item['numeros'], item['estrellas']
        cats = item['categorias']
        if d.weekday() not in (1,4) or d > datetime.now(timezone.utc).date(): return False
        if not (len(nums)==5 and len(set(nums))==5 and all(type(x)==int and 1<=x<=50 for x in nums)): return False
        if not (len(stars)==2 and len(set(stars))==2 and all(type(x)==int and 1<=x<=12 for x in stars)): return False
        if not re.fullmatch(r'[A-Z]{3}\d{5}', item['el_millon']): return False
        if set(cats)!=CATS: return False
        if not all(isinstance(v,dict) and (v.get('importe_centimos') is None or
                   (type(v['importe_centimos'])==int and v['importe_centimos']>=0)) for v in cats.values()): return False
        return item.get('datos_validos') is True
    except (KeyError,TypeError,ValueError): return False

def main():
    source = json.loads(INPUT.read_text(encoding='utf-8'))
    if source.get('version')!='0.48' or source.get('publica_resultados') is not False:
        raise ValueError('Informe de origen inesperado')
    if STORE.exists():
        archive=json.loads(STORE.read_text(encoding='utf-8'))
        if archive.get('version')!='0.49' or archive.get('publicable') is not False:
            raise ValueError('Almacen incompatible')
    else:
        archive={'version':'0.49','publicable':False,'juegos':{g:{} for g in GAMES}}
    for g in GAMES: archive['juegos'].setdefault(g,{})
    summary={'version':'0.49','fecha_utc':datetime.now(timezone.utc).isoformat(),
             'publica_resultados':False,'nuevos':[],'sin_cambios':[],'conflictos':[],'rechazados':[]}
    for item in source.get('juegos',{}).get('euromillones',{}).get('sorteos',[]):
        day=item.get('fecha','desconocida')
        if not valid_em(item):
            summary['rechazados'].append(day); continue
        record={'fecha':day,'numeros':sorted(item['numeros']),'estrellas':sorted(item['estrellas']),
                'el_millon':item['el_millon'],
                'categorias':{k:item['categorias'][k]['importe_centimos'] for k in sorted(CATS)},
                'estado':'pendiente_verificacion_independiente',
                'fuente':'comprobarloteria.com (informe 0.48)'}
        previous=archive['juegos']['euromillones'].get(day)
        if previous is None:
            archive['juegos']['euromillones'][day]=record; summary['nuevos'].append(day)
        elif previous==record:
            summary['sin_cambios'].append(day)
        else:
            summary['conflictos'].append(day)  # Nunca sobrescribir silenciosamente
    STORE.parent.mkdir(parents=True,exist_ok=True)
    STORE.write_text(json.dumps(archive,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    SUMMARY.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False))
    if summary['conflictos']:
        raise SystemExit('Conflictos detectados: revisar antes de publicar')

if __name__=='__main__': main()

