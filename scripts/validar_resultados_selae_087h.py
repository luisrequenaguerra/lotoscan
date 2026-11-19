#!/usr/bin/env python3
"""LotoScan 0.87H: auditoría conservadora de JSON oficiales; NUNCA publica.

Reutiliza el sondeo 0.87F y verifica identidad, combinaciones, anexos y
escrutinios. La validación estructural NO garantiza exactitud de cada premio.
"""
import argparse
import datetime as dt
import importlib.util
import json
import pathlib
import re
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

ROOT=pathlib.Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('sondeo_087f', ROOT/'scripts'/'actualizar_resultados_selae_087f.py')
if SPEC is None or SPEC.loader is None: raise RuntimeError('Falta scripts/actualizar_resultados_selae_087f.py')
sondeo=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(sondeo)
OUT=pathlib.Path('auditoria_selae_087h')
MIN_CATS={'EMIL':13,'LAPR':7,'BONO':6,'ELGR':9,'EDMS':6,'LNAC':20,'LAQU':6,'QGOL':5,'LOTU':8,'QUPL':5}


def amount(value):
    if isinstance(value,bool) or value is None:return None
    s=str(value).strip().replace('€','').replace(' ','')
    if not s:return None
    if ',' in s:s=s.replace('.','').replace(',','.')
    try:
        n=Decimal(s)
        return n if n.is_finite() and n>=0 else None
    except InvalidOperation:return None


def integer(value):
    s=str(value).strip()
    return int(s) if re.fullmatch(r'\d+',s) else None


def numbers(text):
    return [int(x) for x in re.findall(r'\d+',text)]


def validate(item,code,day):
    errors=[];warnings=[];evidence={}
    def need(cond,reason):
        if not cond:errors.append(reason)
    need(isinstance(item,dict),'objeto_invalido')
    if not isinstance(item,dict):return errors,warnings,evidence
    need(item.get('game_id')==code,'juego_no_coincide')
    need(str(item.get('fecha_sorteo',''))[:10]==day.isoformat(),'fecha_no_coincide')
    need(bool(re.fullmatch(r'\d{6,20}',str(item.get('id_sorteo','')))),'id_invalido')
    comb=item.get('combinacion');c=comb.strip() if isinstance(comb,str) else ''
    nums=numbers(c)
    if code=='LNAC':
        need(isinstance(comb,dict),'combinacion_nacional_no_objeto')
        if isinstance(comb,dict):
            for k in ('primer_premio','Segundo_premio'):
                need(bool(re.fullmatch(r'\d{5}',str(comb.get(k,'')))),'nacional_'+k+'_invalido')
        rein=item.get('reintegros')
        need(isinstance(rein,list) and len(rein)==3 and len(set(map(str,rein)))==3 and all(re.fullmatch(r'\d',str(x)) for x in rein),'nacional_reintegros_invalidos')
        need(amount(item.get('tenthPrice')) is not None and amount(item.get('tenthPrice'))>0,'nacional_precio_decimo_invalido')
        # Este JSON NO contiene la lista exhaustiva de números premiados.
        warnings.append('nacional_sin_lista_exhaustiva_de_premios_por_numero')
    elif code in ('EMIL','LAPR','BONO','ELGR','EDMS','LOTU','QUPL'):
        expected={'EMIL':7,'LAPR':8,'BONO':8,'ELGR':6,'EDMS':7,'LOTU':8,'QUPL':6}[code]
        need(len(nums)==expected,'cantidad_de_numeros_incorrecta')
        primary={'EMIL':5,'LAPR':6,'BONO':6,'ELGR':5,'EDMS':6,'LOTU':6,'QUPL':5}[code]
        if code!='QUPL':need(len(set(nums[:primary]))==primary,'numeros_principales_repetidos')
        ranges={'EMIL':(1,50),'LAPR':(1,49),'BONO':(1,49),'ELGR':(1,54),'EDMS':(1,40),'LOTU':(1,31),'QUPL':(1,99)}
        lo,hi=ranges[code];need(all(lo<=n<=hi for n in nums[:primary]),'numeros_fuera_de_rango')
        if code=='EMIL':need(all(1<=n<=12 for n in nums[5:]) and len(set(nums[5:]))==2,'estrellas_invalidas')
        if code in ('LAPR','BONO'):
            need(bool(re.search(r'C\(\d+\)\s*R\(\d\)',c)),'complementario_o_reintegro_ausente')
            if len(nums)==8:need(nums[6] not in nums[:6] and 1<=nums[6]<=49 and 0<=nums[7]<=9,'complementario_o_reintegro_invalido')
        if code=='ELGR':need(bool(re.search(r'R\(\d\)',c)) and 0<=nums[-1]<=9,'clave_invalida')
        if code=='EDMS':need(bool(re.search(r'C\(\d+\)',c)) and 1<=nums[-1]<=5,'sueno_invalido')
        if code=='LOTU':need(bool(re.search(r'C\(\d+\)\s*R\(\d\)',c)),'caballo_o_reintegro_ausente')
        if code=='QUPL':need(bool(re.search(r'C\(\d+\)',c)),'segundo_caballo_ausente')
    elif code=='LAQU':
        tokens=[t.strip().upper() for t in c.split('-')]
        need(len(tokens)==15 and all(t in ('1','X','2') for t in tokens[:14]) and bool(re.fullmatch(r'[012M][012M]',tokens[-1])),'quiniela_signos_o_pleno_invalidos')
        matches=item.get('partidos')
        need(isinstance(matches,list) and len(matches)==15,'quiniela_partidos_incompletos')
        if isinstance(matches,list) and len(matches)>=14 and len(tokens)==15:
            need(all(isinstance(m,dict) and str(m.get('signo','')).strip().upper()==tokens[i] for i,m in enumerate(matches[:14])),'quiniela_signos_partidos_no_coinciden')
        e8=item.get('escrutinioElige8')
        need(isinstance(e8,list) and len(e8)>=1,'elige8_escrutinio_ausente')
        if isinstance(e8,list):
            for row in e8:need(isinstance(row,dict) and amount(row.get('premio')) is not None and integer(row.get('ganadores')) is not None,'elige8_fila_invalida')
    elif code=='QGOL':
        tokens=[t.strip().upper() for t in c.split('-')]
        # Quinigol se expresa como 21 - 10 - 2M ... (dos caracteres por partido).
        need(len(tokens)==6 and all(re.fullmatch(r'[012M]{2}',t) for t in tokens),'quinigol_marcadores_invalidos')
        matches=item.get('partidos');need(isinstance(matches,list) and len(matches)==6,'quinigol_partidos_incompletos')
        if isinstance(matches,list) and len(matches)==6 and len(tokens)==6:
            need(all(isinstance(m,dict) and str(m.get('signo','')).replace('-','').replace(' ','').upper()==tokens[i] for i,m in enumerate(matches)),'quinigol_partidos_no_coinciden')
    else:errors.append('juego_desconocido')
    rows=item.get('escrutinio')
    need(isinstance(rows,list) and len(rows)>=MIN_CATS[code],'escrutinio_incompleto')
    if isinstance(rows,list):
        evidence['categorias']=len(rows)
        for idx,row in enumerate(rows):
            if not isinstance(row,dict):errors.append(f'escrutinio_fila_{idx}_no_objeto');continue
            if not str(row.get('tipo','')).strip():errors.append(f'escrutinio_fila_{idx}_sin_tipo')
            if amount(row.get('premio')) is None:errors.append(f'escrutinio_fila_{idx}_premio_invalido')
            if integer(row.get('ganadores')) is None:errors.append(f'escrutinio_fila_{idx}_ganadores_invalidos')
        if code!='LNAC':
            ids=[integer(r.get('categoria')) for r in rows if isinstance(r,dict) and r.get('categoria') is not None]
            if ids and len(set(ids))!=len(ids):errors.append('categorias_duplicadas')
    if code=='EMIL':
        millon=item.get('millon');need(isinstance(millon,dict) and bool(re.fullmatch(r'[A-Z]{3}\d{5}',str(millon.get('combinacion','')))),'millon_codigo_invalido')
        need(isinstance(item.get('escrutinio_millon'),list) and len(item['escrutinio_millon'])>=1,'millon_escrutinio_ausente')
    if code=='LAPR':
        joker=item.get('joker');need(isinstance(joker,dict) and bool(re.fullmatch(r'\d{7}',str(joker.get('combinacion','')))),'joker_invalido')
        need(isinstance(item.get('escrutinio_joker'),list) and len(item['escrutinio_joker'])>=1,'joker_escrutinio_ausente')
    # Coherencia estructural no demuestra que las cuantías sean definitivas.
    warnings.append('premios_no_contrastados_individualmente_con_pdf')
    evidence['id_sorteo']=str(item.get('id_sorteo',''))
    return sorted(set(errors)),sorted(set(warnings)),evidence


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--dias',type=int,default=4)
    ap.add_argument('--fecha-fin',default='')
    ap.add_argument('--offline-zip',default='',help='ZIP de respuestas históricas 0.87E para prueba local')
    args=ap.parse_args()
    if not 1<=args.dias<=14:ap.error('dias fuera de rango')
    OUT.mkdir(exist_ok=True)
    report={'version':'0.87H','publicable':False,'historico_modificado':False,'validacion_premios_definitiva':False,'resultados':[]}
    jobs=[]
    if args.offline_zip:
        import zipfile
        with zipfile.ZipFile(args.offline_zip) as z:
            for name in z.namelist():
                if name.endswith('_historico.respuesta.txt'):
                    raw=z.read(name);payload=json.loads(raw)
                    if isinstance(payload,list) and len(payload)==1 and isinstance(payload[0],dict):
                        item=payload[0];code=item.get('game_id');day=dt.date.fromisoformat(item['fecha_sorteo'][:10]);jobs.append((code,day,item,'offline'))
    else:
        if args.fecha_fin:
            try:end=dt.datetime.strptime(args.fecha_fin,'%Y%m%d').date()
            except ValueError:ap.error('fecha-fin incorrecta')
        else:end=dt.datetime.now(ZoneInfo('Europe/Madrid')).date()
        for offset in range(args.dias):
            day=end-dt.timedelta(days=offset)
            for _,code in sondeo.GAMES:
                endpoint='fecha2' if code=='LNAC' else 'fechav3'
                import urllib.parse
                url=f'{sondeo.BASE}/servicios/{endpoint}?'+urllib.parse.urlencode({'game_id':code,'fecha_sorteo':day.strftime('%Y%m%d')})
                net,raw=sondeo.get(url)
                if raw is None:
                    report['resultados'].append({'juego':code,'fecha':day.isoformat(),'estado':'error_red','http':net.get('http'),'errores':[net.get('error','sin_respuesta')]});continue
                status,item,issues=sondeo.evaluate(raw,code,day)
                if item is None:
                    report['resultados'].append({'juego':code,'fecha':day.isoformat(),'estado':status,'errores':issues});continue
                jobs.append((code,day,item,'online'))
    seen=set()
    for code,day,item,source in jobs:
        errors,warnings,evidence=validate(item,code,day)
        key=(code,evidence.get('id_sorteo'))
        if key in seen:errors.append('sorteo_duplicado')
        seen.add(key)
        status='estructura_coherente_pendiente_contraste' if not errors else 'rechazado_estructura'
        report['resultados'].append({'juego':code,'fecha':day.isoformat(),'estado':status,'errores':errors,'advertencias':warnings,'evidencia':evidence,'publicable':False})
        print(f'{day} {code}: {status} ({len(errors)} incidencias)')
    states={}
    for r in report['resultados']:states[r['estado']]=states.get(r['estado'],0)+1
    report['resumen']={'consultas_o_resultados':len(report['resultados']),'estados':states,'publicados':0}
    pathlib.Path('informe_selae_087h.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    pathlib.Path('informe_selae_087h.txt').write_text('LotoScan 0.87H - AUDITORIA SOLO LECTURA\n'+json.dumps(report['resumen'],ensure_ascii=False,indent=2)+'\n\n'+ '\n'.join(f"{r['fecha']} {r['juego']}: {r['estado']} / {', '.join(r.get('errores',[]))}" for r in report['resultados'])+'\n',encoding='utf-8')
    print(json.dumps(report['resumen'],ensure_ascii=False))

if __name__=='__main__':main()
