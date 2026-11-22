#!/usr/bin/env python3
"""LotoScan 1.37: captura el último LNAC por resultados1 y recupera anteriores por resultados2.
No calcula ni publica premios; conserva JSON original y un registro consolidado verificable.
"""
import argparse, datetime as dt, hashlib, json, pathlib, re, sys, time, urllib.error, urllib.parse, urllib.request

BASE='https://www.loteriasyapuestas.es/servicios/'
CAMPOS={'extraccionesDeCuatroCifras':4,'extraccionesDeTresCifras':3,'extraccionesDeDosCifras':2,'reintegros':1}

def get_json(endpoint, params=None):
    url=BASE+endpoint+('?' + urllib.parse.urlencode(params) if params else '')
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; LotoScan/1.37)','Accept':'application/json','Referer':'https://www.loteriasyapuestas.es/'})
    err=None
    for i in range(3):
        try:
            with urllib.request.urlopen(req,timeout=25) as r:
                data=r.read(2_000_001)
                if len(data)>2_000_000: raise ValueError('Respuesta demasiado grande')
                return json.loads(data.decode('utf-8-sig')),url
        except (urllib.error.URLError,TimeoutError,ValueError,UnicodeError) as e:
            err=str(e)
            if i<2: time.sleep(i+1)
    raise RuntimeError(f'{endpoint}: {err}')

def extract(d):
    if not isinstance(d,dict): raise ValueError('JSON no es objeto')
    ident=str(d.get('drawIdSorteo') or '')
    if not re.fullmatch(r'\d{6,20}',ident): raise ValueError('drawIdSorteo inválido')
    fecha=d.get('fechaSorteo')
    if not isinstance(fecha,str) or not re.match(r'^\d{4}-\d\d-\d\dT',fecha): raise ValueError('fechaSorteo inválida')
    if d.get('tipoSorteoGeneral') not in ('J','S'):
        raise ValueError('No es un sorteo ordinario J/S de Lotería Nacional')
    def premio(key):
        x=d.get(key)
        if not isinstance(x,dict) or not re.fullmatch(r'\d{5}',str(x.get('decimo',''))):
            raise ValueError(f'{key} ausente o inválido')
        return str(x['decimo'])
    p1,p2=premio('primerPremio'),premio('segundoPremio')
    extr={}
    for k,width in CAMPOS.items():
        rows=d.get(k)
        if not isinstance(rows,list) or not rows: raise ValueError(f'{k} vacío o ausente')
        nums=[]
        for row in rows:
            if not isinstance(row,dict) or not re.fullmatch(r'\d{'+str(width)+r'}',str(row.get('decimo',''))):
                raise ValueError(f'{k}: entrada inválida')
            nums.append(str(row['decimo']))
        extr[k]=nums
    return {'id_sorteo':ident,'fecha_sorteo':fecha,'tipo_sorteo':d['tipoSorteoGeneral'],
            'primer_premio':p1,'segundo_premio':p2,'extracciones':extr,
            'precio_decimo_original':d.get('precioDecimo'),
            'premios_verificados':False,'publicable':False,
            'fuente':'SELAE resultados1/resultados2; valores prize originales sin conversión'}

def save(root,d,summary,dry_run):
    ident=summary['id_sorteo']; folder=root/ident
    original=json.dumps(d,ensure_ascii=False,sort_keys=True,indent=2)+'\n'
    checksum=hashlib.sha256(original.encode()).hexdigest()
    target=folder/'original_resultados.json'
    if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest()==checksum:
        return 'sin_cambios'
    if not dry_run:
        folder.mkdir(parents=True,exist_ok=True)
        # Retener revisiones del original si SELAE rectifica.
        if target.exists():
            old=hashlib.sha256(target.read_bytes()).hexdigest()[:12]
            revision=folder/f'original_revision_{old}.json'
            if not revision.exists(): revision.write_bytes(target.read_bytes())
        target.write_text(original,encoding='utf-8')
        (folder/'consolidado.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return 'actualizado' if target.exists() else 'nuevo'

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--raiz',default='datos/lotoscan/loteria_nacional/historico_completo')
    ap.add_argument('--informe',default='salida_137')
    ap.add_argument('--retroceso',type=int,default=8,help='Máximo de sorteos anteriores a consultar mediante resultados2')
    ap.add_argument('--fixture',help='JSON local de resultados1 para pruebas sin red')
    ap.add_argument('--dry-run',action='store_true')
    args=ap.parse_args()
    root=pathlib.Path(args.raiz); report=pathlib.Path(args.informe);report.mkdir(parents=True,exist_ok=True)
    log={'version':'1.37','fecha_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
         'fuente_principal':'resultados1','respaldo':'resultados2',
         'registros':[],'avisos':[],'errores':[],'premios_verificados':False,'publicable':False}
    try:
        if args.fixture:
            latest=json.loads(pathlib.Path(args.fixture).read_text(encoding='utf-8'))
            source='fixture_local'
        else: latest,source=get_json('resultados1')
        current=latest
        seen=set()
        for step in range(max(0,min(args.retroceso,30))+1):
            if step:
                previous=str(current.get('drawIdSorteoAnterior') or '')
                if not re.fullmatch(r'\d{6,20}',previous) or previous in seen: break
                if args.fixture:
                    log['avisos'].append('Modo fixture: no se consultan sorteos anteriores');break
                try: current,source=get_json('resultados2',{'idsorteo':previous})
                except Exception as e:
                    log['avisos'].append(f'resultados2 no disponible para {previous}: {e}');break
                if str(current.get('drawIdSorteo'))!=previous:
                    log['errores'].append(f'resultados2 devolvió un sorteo diferente al solicitado: {previous}');break
            try:
                summary=extract(current)
            except ValueError as e:
                log['errores'].append(f'Sorteo {current.get("drawIdSorteo")}: {e}')
                break
            ident=summary['id_sorteo']
            if ident in seen: break
            seen.add(ident)
            status=save(root,current,summary,args.dry_run)
            log['registros'].append({'id_sorteo':ident,'fecha':summary['fecha_sorteo'],'origen':source,'estado':status,
                'extracciones':{k:len(v) for k,v in summary['extracciones'].items()}})
            # Una vez alcanzado un sorteo previamente archivado, los anteriores ya están capturados
            # salvo interrupciones: continuar hasta el límite para cubrir posibles huecos.
        log['total_registros']=len(log['registros'])
    except Exception as e: log['errores'].append(str(e))
    (report/'informe_137.json').write_text(json.dumps(log,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(log,ensure_ascii=False,indent=2))
    return 1 if log['errores'] or not log['registros'] else 0

if __name__=='__main__': sys.exit(main())
