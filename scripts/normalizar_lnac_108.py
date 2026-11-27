"""Adaptador LNAC 108. No escribe en el histórico público."""
import copy,re
from motor_navidad_108 import calculate
from consultar_navidad_119 import premios_mayores
def normalize(raw,entries,year,draw_id):
    if str(raw.get("drawIdSorteo"))!=str(draw_id) or raw.get("modelDraw")!=108 or not str(raw.get("fechaSorteo","")).startswith(f"{year}-12-22") or "NAVIDAD" not in raw.get("nombreDelSorteo","").upper():raise ValueError("Identidad del sorteo incorrecta")
    if len(entries)!=1807 or any(not re.fullmatch(r"[0-9]{5}",e[0]) for e in entries):raise ValueError("Extracciones incompletas")
    numbers={e[0] for e in entries}
    if len(numbers)!=1807:raise ValueError("Duplicados")
    majors=premios_mayores(raw)
    if not set(majors)<=numbers:raise ValueError("Faltan premios mayores")
    pedreas=sorted(numbers-set(majors))
    result=calculate(majors,pedreas)
    if sum(v for parts in result.values() for c,v in parts)!=140000000:raise ValueError("Total incorrecto")
    data=copy.deepcopy(raw)
    data["precioDecimo"]=20.0
    data["extraccionesDeCincoCifras"]=[{"decimo":n,"tabla":t,"alambre":a,"prize":10000,"prizeType":"P5","literalPremio":{"es":"Pedrea"}} for n,t,a in sorted(entries) if n in set(pedreas)]
    data["lotoscan"]={"schemaVersion":1,"complete":True,"source":"SELAE resultados2 + tablas-y-alambres","extractionCount":1807,"pedreaCount":1794}
    return data
