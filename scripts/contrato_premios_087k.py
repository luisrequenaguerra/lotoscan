#!/usr/bin/env python3
"""LotoScan 0.87K: contrato SELAE -> boleto -> motor de premios.
Auditoría SOLO LECTURA. No calcula ni publica premios. Python 3.10+.
"""
import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / 'datos/selae_provisional/historico_provisional.json'
OUT = Path('informe_contrato_087k.json')

# Campos del resguardo necesarios para asociar un boleto a un sorteo y
# reconstruir sus apuestas. Son requisitos de producto, NO evidencia de que
# un código de barras los contenga ni de que el OCR pueda leerlos todavía.
COMMON = ['juego', 'identificador_sorteo_o_fecha', 'apuestas', 'tipo_apuesta']
SPECS = {
 'EMIL': {'nombre':'Euromillones','oficial':['combinacion','escrutinio','millon','escrutinio_millon'], 'boleto':['numeros_5','estrellas_2','codigo_el_millon','fechas_sorteos'], 'especiales':['El Millón','premios acumulables']},
 'LAPR': {'nombre':'La Primitiva','oficial':['combinacion','escrutinio','joker','escrutinio_joker'], 'boleto':['numeros_6','reintegro','participa_joker','codigo_joker','fechas_sorteos'], 'especiales':['Joker','reintegro']},
 'BONO': {'nombre':'Bonoloto','oficial':['combinacion','escrutinio'], 'boleto':['numeros_6','reintegro','fechas_sorteos'], 'especiales':['complementario','reintegro']},
 'ELGR': {'nombre':'El Gordo de la Primitiva','oficial':['combinacion','escrutinio'], 'boleto':['numeros_5','numero_clave','fecha_sorteo'], 'especiales':['numero clave']},
 'EDMS': {'nombre':'EuroDreams','oficial':['combinacion','escrutinio'], 'boleto':['numeros_6','numero_sueno','fecha_sorteo'], 'especiales':['premios periódicos y condiciones de cobro']},
 'LNAC': {'nombre':'Lotería Nacional','oficial':['combinacion','reintegros','escrutinio','tenthPrice'], 'boleto':['numero_5_digitos','serie','fraccion','fecha_sorteo','cantidad_decimos'], 'especiales':['terminaciones','aproximaciones','centenas','reintegros','premios especiales por serie/fracción']},
 'LAQU': {'nombre':'La Quiniela','oficial':['combinacion','escrutinio','partidos','escrutinioElige8'], 'boleto':['jornada','pronosticos_14','pleno_al_15','participa_elige8','seleccion_8_partidos','pronosticos_elige8'], 'especiales':['Pleno al 15','Elige8','múltiples']},
 'QGOL': {'nombre':'Quinigol','oficial':['combinacion','escrutinio','partidos'], 'boleto':['jornada','pronosticos_6_marcadores'], 'especiales':['M: tres o más goles','múltiples']},
 'LOTU': {'nombre':'Lototurf','oficial':['combinacion','escrutinio'], 'boleto':['numeros_6','caballo_ganador','reintegro','fecha_sorteo'], 'especiales':['caballo ganador','reintegro']},
 'QUPL': {'nombre':'Quíntuple Plus','oficial':['combinacion','escrutinio'], 'boleto':['ganadores_carreras_1_a_4','primero_carrera_5','segundo_carrera_5','fecha_sorteo'], 'especiales':['orden de las carreras','posiciones 1ª y 2ª en quinta carrera']},
}

# No asumir que las 10 respuestas incluyen todos los premios comprobables.
# Estas barreras no se desactivan por el hecho de que existan campos JSON.
BLOCKERS = {
 'EMIL':['verificar reglas de todas las categorías y El Millón con apuestas reales'],
 'LAPR':['verificar reintegro y Joker con casos reales'],
 'BONO':['verificar categorías, complementario y reintegro con casos reales'],
 'ELGR':['verificar categorías con número clave'],
 'EDMS':['verificar condiciones de premios periódicos'],
 'LNAC':['integrar y probar motor completo de premios por número, terminaciones y excepciones'],
 'LAQU':['verificar apuestas múltiples y acumulación de categorías; Elige8 por selección de partidos'],
 'QGOL':['verificar codificación y categorías de marcadores'],
 'LOTU':['verificar caballo ganador, reintegro y categorías'],
 'QUPL':['verificar premios especiales y orden de llegada'],
}

def present(value):
    return value is not None and value != '' and value != [] and value != {}

def extract_rows(data):
    if isinstance(data, dict) and data.get('esquema') == 1 and isinstance(data.get('registros'),list):
        for row in data['registros']:
            revisions = row.get('revisiones', [])
            if not revisions: continue
            item = revisions[-1].get('datos_oficiales')
            if isinstance(item,dict):
                yield row.get('juego'), str(row.get('id_sorteo','')), row.get('fecha'), item
    elif isinstance(data, list):
        for item in data:
            if isinstance(item,dict):
                yield item.get('game_id'), str(item.get('id_sorteo','')), str(item.get('fecha_sorteo',''))[:10], item
    else:
        raise ValueError('Entrada incompatible: histórico esquema 1 o lista de respuestas SELAE')

def audit(code, draw_id, date, item):
    spec = SPECS.get(code)
    if not spec: return {'juego':code,'id_sorteo':draw_id,'errores':['juego_desconocido'],'publicable':False}
    missing = [k for k in spec['oficial'] if not present(item.get(k))]
    errors = []
    if str(item.get('game_id')) != code: errors.append('juego_inconsistente')
    if str(item.get('id_sorteo')) != draw_id: errors.append('identificador_inconsistente')
    if not re.match(r'^\d{4}-\d{2}-\d{2}',str(date)): errors.append('fecha_no_iso')
    if not isinstance(item.get('escrutinio'),list) or not item['escrutinio']:
        errors.append('escrutinio_no_lista_o_vacio')
    if code == 'LNAC':
        if not isinstance(item.get('combinacion'),dict): errors.append('premios_principales_no_objeto')
        if not isinstance(item.get('reintegros'),list): errors.append('reintegros_no_lista')
    if code == 'LAQU':
        signs = [x.strip() for x in str(item.get('combinacion','')).split('-')]
        if len(signs) != 15: errors.append('pronosticos_quiniela_no_15')
    if code == 'QGOL':
        if len([x.strip() for x in str(item.get('combinacion','')).split('-')]) != 6:
            errors.append('marcadores_quinigol_no_6')
    return {'juego':code,'id_sorteo':draw_id,'fecha':date,
            'campos_oficiales_presentes':[k for k in spec['oficial'] if k not in missing],
            'campos_oficiales_ausentes':missing,'errores':errors,
            'bloqueos_validacion_premios':BLOCKERS[code], 'publicable':False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--historico',default=str(DEFAULT))
    p.add_argument('--muestras-dir',default='',help='Alternativa: carpeta de respuestas JSON oficiales (lista u objeto)')
    args=p.parse_args()
    report={'version':'0.87K','generado_utc':datetime.now(timezone.utc).isoformat(),
            'solo_lectura':True,'publicacion_habilitada':False,
            'contrato_version':1,'campos_comunes_boleto':COMMON,
            'juegos':{k:{**v,'campos_comunes_boleto':COMMON,'pendientes':BLOCKERS[k],
                          'motor_premios_validado_para_publicar':False} for k,v in SPECS.items()},
            'auditoria':[],'advertencias_generales':[
                'La presencia de campos no prueba la corrección de importes ni las reglas de premios.',
                'Los códigos de barras no se consideran descifrables sin muestras y especificación.',
                'Los boletos de varios sorteos requieren comprobar cada sorteo por separado.',
                'Las apuestas múltiples se representan como selecciones; no se expanden ni cobran aún.',
                'Sin datos completos del boleto o resultado, estado = pendiente; nunca sin premio.'
            ]}
    files = sorted(Path(args.muestras_dir).glob('*.json')) if args.muestras_dir else [Path(args.historico)]
    if not files or not all(f.is_file() for f in files):
        p.error('No se encontró el histórico ni las muestras JSON')
    for path in files:
        data=json.loads(path.read_text(encoding='utf-8'))
        for code, draw_id, date, item in extract_rows(data):
            entry=audit(code,draw_id,date,item)
            entry['archivo_fuente']=path.name
            report['auditoria'].append(entry)
    report['resumen']={'registros':len(report['auditoria']),
                       'por_juego':dict(sorted(Counter(r['juego'] for r in report['auditoria']).items())),
                       'sin_errores_basicos':sum(not r.get('errores') for r in report['auditoria']),
                       'con_campos_ausentes':sum(bool(r.get('campos_oficiales_ausentes')) for r in report['auditoria']),
                       'publicables':0}
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    Path('informe_contrato_087k.txt').write_text(
        'LotoScan 0.87K — CONTRATO DE DATOS (NO PUBLICABLE)\n'
        + json.dumps(report['resumen'],ensure_ascii=False,indent=2)+'\n'
        + 'Revisar informe_contrato_087k.json para campos por juego y bloqueos.\n',encoding='utf-8')
    print(json.dumps(report['resumen'],ensure_ascii=False))

if __name__=='__main__': main()
