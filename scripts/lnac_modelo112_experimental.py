"""Motor experimental, no habilitado en producción. Importes en céntimos."""
from collections import Counter

def motor(d):
    if d['modelDraw'] != 112:
        raise ValueError('Modelo no admitido')
    a = [x['decimo'] for x in [d['primerPremio'], d['segundoPremio'], *d['tercerosPremios']]]
    if len(a) != 3:
        raise ValueError('Premios principales incompletos')
    f = a[0]
    groups = [Counter(x['decimo'] for x in d['extraccionesDe'+k+'Cifras'] if x['prize']==v) for k,v in [('Cuatro',37500),('Tres',7500),('Dos',3000)]]
    five = {x['decimo'] for x in d['extraccionesDeCincoCifras']}
    rein = Counter(x['decimo'] for x in d['reintegros'])
    def calc(n):
        if not isinstance(n,str) or len(n)!=5 or not n.isascii() or not n.isdigit():
            raise ValueError('Número inválido')
        return (sum(v for x,v in zip(a,[15000000,3000000,1500000]) if n==x)
                +750000*(n in five)
                +sum(g[n[-k:]]*v for g,k,v in zip(groups,[4,3,2],[37500,7500,3000]))
                +1500*(rein[n[-1:]]-(n==f))
                +7500*(n!=f and n[-3:]==f[-3:])
                +3000*(n!=f and n[-2:]==f[-2:])
                +sum(7500 for x in a if n!=x and n[:3]==x[:3])
                +sum(v for x,v in zip(a,[210000,120000,62250]) if (int(n)-int(x))%100000 in (1,99999)))
    return calc
