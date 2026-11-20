#!/usr/bin/env python3
"""LotoScan 0.87O2: pruebas reproducibles de Lototurf y Quíntuple Plus.
Muestras oficiales SELAE capturadas en 0.87E (15-11-2026), incrustadas para
que el test no dependa de la red ni del histórico provisional. Solo lectura.
"""
import base64
import hashlib
import importlib.util
import json
import sys
import zlib
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / 'scripts/completar_motores_087o.py'
SAMPLES = {'LOTU': {'sha256': '7beaf68400dc9e99ece897c3cbfce12d8036b58b95443420d3de3e710129d90d', 'payload': 'eNqVkMtqwzAQRX9FeJVQB/SybGebRTelhdCu0hIUS0kFsRT8WJSQf+/IYFcWBJrNYI0151zN7pocdfUt961rOu2SdUIxFStCViRDlKwpXmOcpIkycEXX0kq4olxt7MlB26i/QcJokWOGcwo/TrLWe6Og/fL2/gENaX9GOpwuja6N2x9cp/1kyTEeNJWqRpKfufS67WQLrZxw4VuNrmSvZGWcDbqVqw/Gjt0SrRApoFDqC4fCsC8EbRZiibaLYjll8HBWMuxTHZ1VQSiG2UDXbdX0nbEGHrC7Jp25DM/97DGWEqGFQK/++whPblyLntBGHuT57NAzrEu5Zol8RNnpk2sM7I+MbqDgYVfDNd0O51s6KegdRQyk/wWyCZg9mJkFCko4TzGJRCQU8TuiGMsDLKE8pWVEpSzEZhOWP5g/C0SMpZRHHj7ziDuemCoCqkjzODyns6XkE5U9mD4PPHlaFJGHiVn6rTYWRhs3hxThriOCEBlE/bp9/QKY4jCW'}, 'QUPL': {'sha256': '9f110532a5f05d6658099e1e459add0e69e434a885bf8b01ef27bfd1cc9a0a78', 'payload': 'eNqdkLFqwzAQhl9FeEqoA5Js2W7WULp0aIdOaQgXSXEFtmQkeygh795TUqfGZCgF36Dfd9930vaUHLX8hH1wvtcuWSec8mLF2IoJwoo1fpQmaaIMtugWLGCLcq2xtcPYqN9BlvGqpBUtOf6oodV7ozB+e399wQDs10jHU+d1a9z+4HqNYU4vDqnkiIkD3aBDDyFGtGAR6rWEQYE0zk5S6dqDsWNakBXhWCVWcanNgi1vyogTVRZ3ODqrbitEvw7SD72xBhfdnpLedHHjp9BpaaAhC0aCaxzxOtQDeOWI0oR9DJQCkA30SxKXgV7Xzht8JjY6f/A1Pp5yOH05n9ObYWQsBGIO0DQukGewDzzmB4gacW3ZgPfaw9zE/2ri903X5jk1+ys1G6n5P/fPJyaWV6koZzox1eX3dfcvISboiqcin5Efk/PuvPsGUA3mCg=='}}

def load_engine():
    if not ENGINE.is_file():
        raise FileNotFoundError(f'Falta el motor anterior: {ENGINE}')
    spec = importlib.util.spec_from_file_location('lotoscan_087o', ENGINE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def main():
    engine = load_engine()
    report = {'version':'0.87O2','fecha_utc':datetime.now(timezone.utc).isoformat(),
              'modo':'PRUEBA_HISTORICA_NO_PUBLICABLE','historico_modificado':False,
              'publicables':0,'muestras':[],'resumen':{'casos':0,'aprobados':0,'fallidos':0}}
    for game, spec in SAMPLES.items():
        original = zlib.decompress(base64.b64decode(spec['payload']))
        digest = hashlib.sha256(original).hexdigest()
        if digest != spec['sha256']:
            raise ValueError('La muestra oficial no supera la comprobación SHA-256')
        draws = json.loads(original)
        if not isinstance(draws,list) or len(draws)!=1 or draws[0]['game_id']!=game:
            raise ValueError('Muestra de sorteo inesperada')
        draw=draws[0]
        tests = []
        if game == 'LOTU':
            win = engine.ints(draw['combinacion'],6)
            horse=engine.extra(draw['combinacion'],'C')
            reintegro=engine.extra(draw['combinacion'],'R')
            # Tres aciertos y caballo ganador = categoría 7; cuatro sin caballo = categoría 6
            others=[n for n in range(1,50) if n not in win]
            tests = [
                ('seis_y_caballo_sin_ganadores',{'numeros':win,'caballo':horse,'reintegro':reintegro},1,'categoria_sin_ganadores_apuesta_hipotetica'),
                ('tres_y_caballo',{'numeros':win[:3]+others[:3],'caballo':horse,'reintegro':(reintegro+1)%10},7,'importe_unitario_oficial_no_pagadero_en_simulacion'),
                ('cuatro_sin_caballo',{'numeros':win[:4]+others[:2],'caballo':99 if horse!=99 else 98,'reintegro':reintegro},6,'importe_unitario_oficial_no_pagadero_en_simulacion'),
            ]
        else:
            win=engine.ints(draw['combinacion'],5)
            second=engine.extra(draw['combinacion'],'C')
            other=99 if 99 not in win else 98
            tests = [
                ('cinco_y_segundo_sin_ganadores',{'caballos':win,'segundo_quinta':second},2,'categoria_sin_ganadores_apuesta_hipotetica'),
                ('cuatro_y_segundo',{'caballos':win[:4]+[other],'segundo_quinta':second},4,'importe_unitario_oficial_no_pagadero_en_simulacion'),
                ('cuatro_sin_segundo',{'caballos':win[:4]+[other],'segundo_quinta':99 if second!=99 else 98},5,'importe_unitario_oficial_no_pagadero_en_simulacion'),
            ]
        entry={'juego':game,'id_sorteo':draw['id_sorteo'],'fecha_sorteo':draw['fecha_sorteo'],
               'origen':'respuesta oficial SELAE de 0.87E','sha256':digest,'casos':[]}
        for label,ticket,expected_cat,expected_state in tests:
            report['resumen']['casos']+=1
            try:
                result=engine.check(draw,ticket)
                award=result.get('premio') or {}
                passed=(result.get('categoria')==expected_cat and award.get('estado')==expected_state
                        and award.get('premio_eur') is None)
                detail={'caso':label,'correcto':passed,'categoria_esperada':expected_cat,
                        'categoria_obtenida':result.get('categoria'),'estado_premio':award.get('estado'),
                        'premio_publicable':False}
            except Exception as exc:
                passed=False
                detail={'caso':label,'correcto':False,'error':f'{type(exc).__name__}: {exc}'}
            report['resumen']['aprobados' if passed else 'fallidos']+=1
            entry['casos'].append(detail)
            print(f"{game} / {label}: {'OK' if passed else 'ERROR'}")
        report['muestras'].append(entry)
    Path('informe_hipica_087o2.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    Path('informe_hipica_087o2.txt').write_text(json.dumps(report['resumen'],ensure_ascii=False,indent=2)+'\nSIN PUBLICAR PREMIOS. No se comprueban reglas completas ni boletos reales.\n',encoding='utf-8')
    if report['resumen']['fallidos']:
        sys.exit(1)

if __name__=='__main__':
    main()
