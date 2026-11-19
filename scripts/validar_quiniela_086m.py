#!/usr/bin/env python3
"""LotoScan 0.86M: diagnostico Quiniela + Elige8 con seleccion explicita.
No publica resultados, no escanea boletos ni modifica historico.json.
Requiere validar_quiniela_086l.py en scripts/ y PDFs en datos/quiniela/.
"""
import argparse
import importlib.util
import json
import sys
from pathlib import Path


def load_previous():
    path = Path(__file__).with_name('validar_quiniela_086l.py')
    if not path.is_file():
        raise FileNotFoundError('Falta scripts/validar_quiniela_086l.py')
    spec = importlib.util.spec_from_file_location('quiniela_086l', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def comprobar_elige8(resultado, pronosticos, partidos_elegidos):
    """Comprueba UNA apuesta Elige8: 8 indices 1..14, y signos de esos partidos.

    pronosticos: secuencia de 14 signos 1/X/2 (columna de La Quiniela).
    partidos_elegidos: 8 numeros de partido, indexados desde 1.
    El PDF solo contiene resultados y premio; los partidos elegidos vienen del boleto.
    """
    if not isinstance(pronosticos, (list, tuple, str)) or len(pronosticos) != 14:
        raise ValueError('Se requieren exactamente 14 pronosticos')
    if any(x not in ('1', 'X', '2') for x in pronosticos):
        raise ValueError('Pronosticos invalidos; use 1, X o 2')
    if not isinstance(partidos_elegidos, (list, tuple)) or len(partidos_elegidos) != 8:
        raise ValueError('Elige8 requiere exactamente 8 partidos seleccionados')
    if any(type(i) is not int or not 1 <= i <= 14 for i in partidos_elegidos):
        raise ValueError('Indices de partido invalidos: deben ser enteros entre 1 y 14')
    if len(set(partidos_elegidos)) != 8:
        raise ValueError('No se puede seleccionar dos veces el mismo partido')
    if len(resultado['signos']) != 14:
        raise ValueError('Resultado oficial incompleto')
    datos = resultado.get('elige8')
    if not isinstance(datos, dict) or type(datos.get('acertantes')) is not int:
        raise ValueError('Faltan datos oficiales de Elige8')
    importe = datos.get('premio_centimos')
    if importe is None or type(importe) is not int or importe < 0:
        raise ValueError('Importe oficial Elige8 no disponible o invalido')
    aciertos = sum(pronosticos[i-1] == resultado['signos'][i-1] for i in partidos_elegidos)
    return {
        'partidos_elegidos': list(partidos_elegidos),
        'aciertos': aciertos,
        'premiado': aciertos == 8 and importe > 0,
        'importe_centimos': importe if aciertos == 8 else 0,
        'modalidad': 'Elige8',
        'aviso': 'Solo una apuesta simple de Elige8; no representa multiples ni lectura de boleto',
    }


def pruebas_elige8(resultado):
    signos = resultado['signos']
    indices = [1, 2, 3, 4, 5, 6, 7, 8]
    premio = comprobar_elige8(resultado, signos, indices)
    cambio = {'1': 'X', 'X': '2', '2': '1'}
    fallida = list(signos)
    fallida[0] = cambio[fallida[0]]
    no_premio = comprobar_elige8(resultado, fallida, indices)
    otro_grupo = [7, 8, 9, 10, 11, 12, 13, 14]
    premio_otra_seleccion = comprobar_elige8(resultado, signos, otro_grupo)
    errores = []
    esperado = resultado['elige8']['premio_centimos']
    if premio['aciertos'] != 8 or premio['importe_centimos'] != esperado:
        errores.append('Elige8 con ocho aciertos no coincide con importe oficial')
    if no_premio['aciertos'] != 7 or no_premio['importe_centimos'] != 0:
        errores.append('Elige8 con siete aciertos no se ha rechazado')
    if premio_otra_seleccion['aciertos'] != 8 or premio_otra_seleccion['importe_centimos'] != esperado:
        errores.append('Elige8 con otra seleccion valida no coincide')
    for invalidos in ([1]*8, [1,2,3,4,5,6,7,15], [1,2,3,4,5,6,7]):
        try:
            comprobar_elige8(resultado, signos, invalidos)
            errores.append('No se rechazo una seleccion invalida')
        except ValueError:
            pass
    return {'ocho_aciertos': premio, 'siete_aciertos': no_premio,
            'ocho_aciertos_otra_seleccion': premio_otra_seleccion,
            'selecciones_invalidas_rechazadas': not errores, 'errores': errores}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pdf-dir', default='datos/quiniela')
    parser.add_argument('--out', default='informe_quiniela_086m.json')
    args = parser.parse_args()
    previous = load_previous()
    paths = sorted(Path(args.pdf_dir).glob('*.pdf'))
    informe = {'version': '0.86M', 'modalidad': 'La Quiniela + Elige8',
               'pdf_encontrados': len(paths), 'resultados': [], 'errores': [],
               'publicable': False, 'lectura_boletos_implementada': False,
               'apuestas_multiples_implementadas': False}
    for path in paths:
        try:
            datos = previous.audit(previous.parse(path))
            if not datos['validado_para_diagnostico']:
                raise ValueError('; '.join(datos['errores']))
            pruebas = pruebas_elige8(datos)
            if pruebas['errores']:
                raise ValueError('; '.join(pruebas['errores']))
            informe['resultados'].append({
                'archivo': path.name, 'fecha': datos['fecha'],
                'jornada': datos['jornada'], 'signos': ''.join(datos['signos']),
                'pleno_15': datos['pleno_15'],
                'elige8_oficial': datos['elige8'],
                'pruebas_elige8': pruebas, 'validado_para_diagnostico': True,
                'publicable': False,
            })
            print(f"{path.name}: jornada {datos['jornada']}, Elige8 OK")
        except Exception as exc:
            informe['errores'].append({'archivo': path.name, 'error': str(exc)})
            print(f'{path.name}: ERROR: {exc}')
    jornadas = {r['jornada'] for r in informe['resultados']}
    informe['diagnostico_completo'] = len(paths) == 3 and jornadas == {19, 20, 21} and not informe['errores']
    Path(args.out).write_text(json.dumps(informe, ensure_ascii=False, indent=2), encoding='utf-8')
    if not informe['diagnostico_completo']:
        print('Diagnostico incompleto. No se publica nada.')
        return 1
    print('Elige8: 3 jornadas comprobadas. No publicable; falta lectura real del boleto.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
