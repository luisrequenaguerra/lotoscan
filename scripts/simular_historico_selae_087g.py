#!/usr/bin/env python3
"""LotoScan 0.87G: propuesta NO PUBLICABLE de histórico SELAE.

Ejecuta 0.87F, clasifica sus candidatos y genera una propuesta separada.
No modifica historico.json, no promueve candidatos a resultados validados.
"""
import argparse
import datetime as dt
import hashlib
import json
import pathlib
import re
import subprocess
import sys
from collections import Counter

GAMES = {'EMIL','LAPR','BONO','ELGR','EDMS','LNAC','LAQU','QGOL','LOTU','QUPL'}
OUT = pathlib.Path('simulacion_selae_087g')


def load_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def normalized_date(value):
    s = str(value or '')
    try:
        return dt.date.fromisoformat(s[:10]).isoformat()
    except ValueError:
        return None


def money(value):
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value) if value >= 0 else None
    s = str(value).strip().replace('€','').replace(' ','')
    if not s:
        return None
    if ',' in s:
        s = s.replace('.','').replace(',','.')
    try:
        n = float(s)
        return n if n >= 0 and n < 1e13 else None
    except ValueError:
        return None


def assess(item, expected_game, expected_date, expected_id):
    errors = []
    if not isinstance(item, dict):
        return ['documento_no_objeto']
    if item.get('game_id') != expected_game or expected_game not in GAMES:
        errors.append('juego_no_coincide')
    if normalized_date(item.get('fecha_sorteo')) != expected_date:
        errors.append('fecha_no_coincide')
    if str(item.get('id_sorteo') or '') != expected_id or not re.fullmatch(r'\d{6,20}',expected_id):
        errors.append('id_no_coincide')
    combo = item.get('combinacion')
    if expected_game == 'LNAC':
        if not isinstance(combo, dict) or not all(re.fullmatch(r'\d{5}',str(combo.get(k) or '')) for k in ('primer_premio','Segundo_premio')):
            errors.append('premios_mayores_invalidos')
        if not isinstance(item.get('reintegros'),list) or len(item['reintegros']) != 3 or any(not re.fullmatch(r'\d',str(x)) for x in item['reintegros']):
            errors.append('reintegros_invalidos')
    elif not isinstance(combo,str) or not combo.strip():
        errors.append('combinacion_ausente')
    rows = item.get('escrutinio')
    if not isinstance(rows,list) or not rows:
        errors.append('escrutinio_ausente')
    else:
        for i,row in enumerate(rows):
            if not isinstance(row,dict) or not str(row.get('tipo') or '').strip() or money(row.get('premio')) is None:
                errors.append(f'categoria_invalida_{i}')
                break
    return errors


def extract_history(raw):
    """Solo índices inequívocos; nunca se altera ni se normaliza el histórico real."""
    if isinstance(raw,list):
        return raw, 'lista'
    if isinstance(raw,dict):
        for key in ('sorteos','resultados','historico'):
            if isinstance(raw.get(key),list):
                return raw[key], f'objeto.{key}'
    return None, 'estructura_desconocida'


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--dias',type=int,default=4)
    p.add_argument('--fecha-fin',default='')
    p.add_argument('--historico',default='historico.json')
    p.add_argument('--sin-red',action='store_true',help='Reutilizar informe y candidatos 0.87F ya presentes')
    args=p.parse_args()
    OUT.mkdir(exist_ok=True)
    if not args.sin_red:
        cmd=[sys.executable,'scripts/actualizar_resultados_selae_087f.py','--dias',str(args.dias),'--fecha-fin',args.fecha_fin]
        run=subprocess.run(cmd,check=False)
        if run.returncode:
            raise SystemExit(f'0.87F falló (código {run.returncode}); no hay propuesta fiable')
    source = pathlib.Path('informe_selae_087f.json')
    if not source.is_file():
        raise SystemExit('Falta informe_selae_087f.json')
    report=load_json(source)
    entries=report.get('candidatos',[])
    history_path=pathlib.Path(args.historico)
    history_exists=history_path.is_file()
    history_hash=hashlib.sha256(history_path.read_bytes()).hexdigest() if history_exists else None
    existing=[]
    history_format='ausente'
    if history_exists:
        raw=load_json(history_path)
        existing,history_format=extract_history(raw)
    indexed={}
    unindexed=0
    if existing is not None:
        for row in existing:
            if not isinstance(row,dict):
                unindexed+=1; continue
            game=str(row.get('game_id') or row.get('juego_id') or '')
            draw=str(row.get('id_sorteo') or '')
            if game in GAMES and re.fullmatch(r'\d{6,20}',draw):
                indexed.setdefault((game,draw),[]).append(row)
            else:
                unindexed+=1
    proposed=[]
    seen={}
    for candidate in entries:
        game=str(candidate.get('game_id') or '')
        draw=str(candidate.get('id_sorteo') or '')
        date=normalized_date(candidate.get('fecha'))
        filename=str(candidate.get('archivo') or '')
        path=pathlib.Path('diagnostico_selae_087f')/pathlib.Path(filename).name
        issues=[]
        if pathlib.Path(filename).name != filename or not path.is_file():
            issues=['archivo_candidato_ausente_o_ruta_invalida']; item=None
        else:
            try:
                item=load_json(path)
                issues=assess(item,game,date,draw)
            except (ValueError,UnicodeError):
                issues=['json_candidato_invalido'];item=None
        key=(game,draw)
        if key in seen:
            issues.append('id_duplicado_en_lote')
        seen[key]=seen.get(key,0)+1
        if existing is None:
            state='historico_formato_no_reconocido'
        elif issues:
            state='rechazado_estructura'
        elif key in indexed:
            state='ya_existe_pendiente_comparacion'
        else:
            state='nuevo_pendiente_validacion_premios'
        proposed.append({'game_id':game,'id_sorteo':draw,'fecha':date,'estado':state,
                         'incidencias':issues,'archivo_origen':filename,
                         'validacion_estructura_basica':not issues,
                         'validacion_premios_completa':False,'publicable':False})
    summary=dict(Counter(x['estado'] for x in proposed))
    output={'version':'0.87G','modo':'simulacion_solo_lectura','origen':'SELAE via 0.87F',
            'fecha_generacion_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
            'historico':{'ruta':str(history_path),'existe':history_exists,'sha256_antes':history_hash,
                         'formato':history_format,'filas':len(existing) if existing is not None else None,
                         'filas_sin_clave_identificable':unindexed},
            'fuente_087f':{'candidatos':len(entries),'consultas':len(report.get('consultas',[]))},
            'resumen':{'candidatos_evaluados':len(proposed),'estados':summary,
                       'incorporados_al_historico':0,'publicables':0},
            'propuesta':proposed,
            'advertencias':['Ninguna comprobacion de premios completa implementada en 0.87G.',
                            'La ausencia de clave reconocible en historico impide detectar todos los duplicados.',
                            'La coincidencia de un id no prueba igualdad de contenido.',
                            'No se escribe ni sustituye historico.json.']}
    if history_exists and hashlib.sha256(history_path.read_bytes()).hexdigest()!=history_hash:
        raise SystemExit('El histórico cambió durante la ejecución; abortando')
    (OUT/'propuesta_historico_087g.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    lines=['LotoScan 0.87G - SIMULACION, SIN PUBLICACION',
           f'Candidatos: {len(proposed)}',f'Histórico: {history_format}',
           f'Resumen: {json.dumps(summary,ensure_ascii=False)}',
           'Incorporados: 0. Publicables: 0. historico.json intacto.','']
    lines.extend(f"{x['fecha']} {x['game_id']} {x['id_sorteo']}: {x['estado']}" for x in proposed)
    (OUT/'informe_087g.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('\n'.join(lines))

if __name__=='__main__':
    main()
