#!/usr/bin/env python3
"""LotoScan 0.87J: puerta de calidad del histórico PROVISIONAL. Solo lectura.
No acredita el cálculo de premios ni autoriza publicar boletos.
"""
import argparse
import datetime as dt
import importlib.util
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / 'datos/selae_provisional/historico_provisional.json'
OUT = Path('informe_selae_087j.json')
GAMES = {'EMIL','LAPR','BONO','ELGR','EDMS','LNAC','LAQU','QGOL','LOTU','QUPL'}
EXPECTED_MIN = {'EMIL':13,'LAPR':7,'BONO':6,'ELGR':9,'EDMS':6,'LNAC':20,'LAQU':6,'QGOL':5,'LOTU':8,'QUPL':5}


def money(value):
    if isinstance(value, bool) or value is None:
        raise ValueError('importe vacío')
    s = str(value).strip().replace('€','').replace(' ','')
    if ',' in s:
        s = s.replace('.','').replace(',','.')
    d = Decimal(s)
    if not d.is_finite() or d < 0:
        raise ValueError('importe negativo/no finito')
    return d


def natural(value):
    s = str(value).strip()
    if not re.fullmatch(r'\d+',s):
        raise ValueError('recuento no entero')
    return int(s)


def load_audit():
    path = ROOT / 'scripts/validar_resultados_selae_087h.py'
    if not path.exists():
        raise FileNotFoundError(f'Falta dependencia: {path}')
    spec = importlib.util.spec_from_file_location('audit087h',path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def audit_revision(row, rev, module):
    errors, warnings = [], []
    item = rev.get('datos_oficiales')
    if not isinstance(item,dict):
        return ['datos_oficiales_ausentes'],warnings
    code = row['juego']
    try:
        day = dt.date.fromisoformat(row['fecha'])
        e,w,_ = module.validate(item,code,day)
        errors.extend(e)
        warnings.extend(w)
    except Exception as exc:
        errors.append(f'error_validador:{type(exc).__name__}:{exc}')
    if str(item.get('id_sorteo')) != str(row['id_sorteo']):
        errors.append('id_inconsistente')
    if item.get('game_id') != code:
        errors.append('juego_inconsistente')
    entries = item.get('escrutinio')
    if not isinstance(entries,list) or len(entries) < EXPECTED_MIN.get(code,999):
        errors.append('categorias_insuficientes')
    else:
        seen = set()
        for i, entry in enumerate(entries):
            if not isinstance(entry,dict):
                errors.append(f'categoria_{i}_no_objeto');continue
            cat = str(entry.get('categoria','')).strip()
            if not cat:
                cat = f'posicion:{i}'
                warnings.append('categorias_sin_identificador_explicito')
            if cat in seen:
                errors.append(f'categoria_{i}_identificador_duplicado')
            seen.add(cat)
            try:
                money(entry.get('premio'))
            except (ValueError,InvalidOperation):
                errors.append(f'categoria_{i}_premio_invalido')
            try:
                natural(entry.get('ganadores'))
            except ValueError:
                errors.append(f'categoria_{i}_ganadores_invalidos')
    if code == 'LAPR' and not isinstance(item.get('escrutinio_joker'),list):
        warnings.append('joker_escrutinio_no_disponible')
    if code == 'LAQU' and not isinstance(item.get('escrutinioElige8'),(list,dict)):
        warnings.append('elige8_escrutinio_no_disponible')
    if code == 'EMIL' and not item.get('millon'):
        warnings.append('millon_no_disponible')
    if code == 'LNAC':
        warnings.append('nacional_requiere_motor_completo_de_premios_por_numero')
    return sorted(set(errors)),sorted(set(warnings))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--historico',default=str(STORE))
    parser.add_argument('--fallar-si-errores',action='store_true')
    args = parser.parse_args()
    module = load_audit()
    path = Path(args.historico)
    if not path.exists():
        raise SystemExit(f'No existe el histórico provisional: {path}')
    store = json.loads(path.read_text(encoding='utf-8'))
    if store.get('esquema') != 1 or not isinstance(store.get('registros'),list):
        raise SystemExit('Esquema de histórico incompatible; no se modifica nada')
    results = []
    keys = set()
    for row in store['registros']:
        code = row.get('juego')
        key = (code,str(row.get('id_sorteo')))
        issues = []
        if code not in GAMES: issues.append('juego_desconocido')
        if key in keys: issues.append('registro_duplicado')
        keys.add(key)
        revisions = row.get('revisiones')
        if not isinstance(revisions,list) or not revisions:
            issues.append('sin_revisiones'); revisions=[]
        rev_results=[]
        for index,rev in enumerate(revisions):
            if not isinstance(rev,dict):
                rev_results.append({'numero':index+1,'errores':['revision_invalida'],'advertencias':[]});continue
            e,w = audit_revision(row,rev,module) if code in GAMES else (['juego_desconocido'],[])
            if rev.get('publicable') is not False:
                e.append('marca_publicable_insegura')
            rev_results.append({'numero':index+1,'errores':e,'advertencias':w})
        current = rev_results[-1] if rev_results else {'errores':['sin_revisiones'],'advertencias':[]}
        results.append({'juego':code,'id_sorteo':row.get('id_sorteo'),'fecha':row.get('fecha'),
                        'estado':'rechazado' if issues or current['errores'] else 'auditoria_estructural_aprobada_no_publicable',
                        'errores_registro':issues,'revision_actual':current,'numero_revisiones':len(revisions)})
    failures = sum(r['estado']=='rechazado' for r in results)
    report = {'version':'0.87J','origen':str(path),'solo_lectura':True,'publicacion_habilitada':False,
              'validacion_calculo_premios':False,'resumen':{'registros':len(results),'rechazados':failures,
              'auditoria_estructural_aprobada':len(results)-failures,'juegos_presentes':sorted({r['juego'] for r in results})},
              'resultados':results,
              'nota':'La aprobación estructural NO valida premios por boleto ni permite publicar. La lotería nacional requiere motor exhaustivo.'}
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    Path('informe_selae_087j.txt').write_text('LotoScan 0.87J — AUDITORÍA, NO PUBLICABLE\n'+json.dumps(report['resumen'],ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report['resumen'],ensure_ascii=False,indent=2))
    if failures and args.fallar_si_errores:
        raise SystemExit(1)

if __name__=='__main__':
    main()
