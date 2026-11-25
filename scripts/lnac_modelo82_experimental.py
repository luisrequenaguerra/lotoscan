"""Motor experimental LNAC 82. Importes en céntimos; no integrado."""
from collections import Counter

def motor(d):
    def require(ok):
        if not ok: raise ValueError('Datos incompletos o incompatibles')
    def number(n,k): return isinstance(n,str) and len(n)==k and n.isascii() and n.isdigit()
    require(d['modelDraw']==82 and d['precioDecimo']==15)
    a,b=[d[k]['decimo'] for k in ('primerPremio','segundoPremio')]
    require(number(a,5) and number(b,5) and a!=b)
    require(all(d[k]==[] for k in ('tercerosPremios','cuartosPremios','quintosPremios','extraccionesDeCincoCifras')))
    groups=[]
    for key,k,count,v in [('Cuatro',4,5,37500),('Tres',3,15,7500),('Dos',2,2,3000)]:
        rows=d['extraccionesDe'+key+'Cifras']; require(len(rows)==count and all(number(x['decimo'],k) and x['prize']==v for x in rows));groups.append((k,v,Counter(x['decimo'] for x in rows)))
    rows=d['reintegros'];require(len(rows)==3 and all(number(x['decimo'],1) and x['prize']==1500 for x in rows));r=Counter(x['decimo'] for x in rows);require(r[a[-1]]>=1)
    e=d['premioEspecial'];require(e['numero']==a and all(type(e[k]) is int and 1<=e[k]<=10 for k in ('serie','fraccion')))
    def base(n):
        require(number(n,5))
        return (13000000*(n==a)+2500000*(n==b)+sum(v*g[n[-k:]] for k,v,g in groups)+1500*(r[n[-1]]-(n==a))+7500*(n!=a and n[-3:]==a[-3:])+7500*(n!=a and n[-2:]==a[-2:])+sum(7500 for x in (a,b) if n!=x and n[:3]==x[:3])+sum(v for x,v in ((a,240000),(b,153250)) if (int(n)-int(x))%100000 in (1,99999)))
    require(base(a)==d['primerPremio']['prize'] and base(b)==d['segundoPremio']['prize'] and base(a)+1487000000==e['premio'])
    def calc(n,serie=None,fraccion=None):
        v=base(n)
        if n==a:
            require(all(type(x) is int and 1<=x<=10 for x in (serie,fraccion)))
            if (serie,fraccion)==(e['serie'],e['fraccion']):v+=1487000000
        return v
    return base,calc
