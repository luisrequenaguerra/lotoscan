"""Motor experimental, no habilitado en producción. Importes en céntimos."""
from collections import Counter

def validar(d):
    def num(n,k):
        return isinstance(n,str) and len(n)==k and n.isascii() and n.isdigit()
    def exigir(ok):
        if not ok:
            raise ValueError('Datos incompletos o inconsistentes')
    exigir(d['modelDraw']==112)
    p=[d['primerPremio'],d['segundoPremio'],*d['tercerosPremios']]
    exigir(len(p)==3 and all(num(x['decimo'],5) for x in p))
    exigir(len({x['decimo'] for x in p})==3)
    for nombre,k,v,c in [('Cuatro',4,37500,4),('Tres',3,7500,11),('Dos',2,3000,5)]:
        filas=d['extraccionesDe'+nombre+'Cifras']
        exigir(all(num(x['decimo'],k) if x['prize']==v else num(x['decimo'],5) for x in filas))
        exigir(sum(x['prize']==v for x in filas)==c)
    cinco=d['extraccionesDeCincoCifras']
    exigir(all(num(x['decimo'],5) for x in cinco))
    exigir(len({x['decimo'] for x in cinco})==12)
    rein=d['reintegros']
    exigir(len(rein)==3 and all(num(x['decimo'],1) for x in rein))
    exigir(any(x['decimo']==p[0]['decimo'][-1] for x in rein))

def motor(d):
    validar(d)
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

def comprobar(d, n):
    """Adaptador experimental: nunca clasifica datos inválidos como no premiados."""
    try:
        importe = motor(d)(n)
    except (KeyError, TypeError, ValueError, AttributeError, IndexError):
        return {'estado': 'pendiente', 'importeCentimos': None}
    return {'estado': 'premiado' if importe else 'no_premiado', 'importeCentimos': importe}
