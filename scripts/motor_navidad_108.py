"""Motor experimental: importes en céntimos por décimo, sin PDF en cálculo."""
import re
from collections import defaultdict,Counter
BASE={"primer_premio":40000000,"segundo_premio":12500000,"tercer_premio":5000000,"cuarto_premio":2000000,"quinto_premio":600000}
QUOTAS=dict(zip(BASE,(1,1,1,2,8)))
def calculate(majors,pedreas):
    if len(majors)!=13 or len(pedreas)!=1794 or len(set(pedreas))!=1794 or set(majors)&set(pedreas):raise ValueError("Extracciones incompletas o duplicadas")
    if any(not isinstance(n,str) or not re.fullmatch(r"[0-9]{5}",n) for n in list(majors)+list(pedreas)):raise ValueError("Número inválido")
    cats={n:v[0]["categoria"] for n,v in majors.items() if len(v)==1}
    if Counter(cats.values())!=QUOTAS:raise ValueError("Categorías inválidas")
    result=defaultdict(list)
    def add(n,c,v):result[n].append((c,v))
    for n,c in cats.items():add(n,c,BASE[c])
    for n in pedreas:add(n,"pedrea",10000)
    for n,c in cats.items():
        i=int(n)
        if c in ("primer_premio","segundo_premio","tercer_premio"):
            for j in ((i-1)%100000,(i+1)%100000):add(f"{j:05d}","aproximacion_"+c,{"primer_premio":200000,"segundo_premio":125000,"tercer_premio":96000}[c])
            for j in range(int(n[-2:]),100000,100):
                if j!=i:add(f"{j:05d}","terminacion_"+c,10000)
        if c!="quinto_premio":
            for j in range(i//100*100,i//100*100+100):
                if j!=i:add(f"{j:05d}","centena_"+c,10000)
        if c=="primer_premio":
            for j in range(i%10,100000,10):
                if j!=i:add(f"{j:05d}","reintegro",2000)
    return dict(result)
