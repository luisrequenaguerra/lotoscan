"""Auditoría no destructiva del Joker desde historico.json.
El resultado ganador procede de comprobarloteria.com vía monitor_resultados.py.
Los importes son una tabla fija de reglas, NO premios de boletos comprobados.
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

HISTORICO = Path('datos_revision/historico.json')
SALIDA = Path('informe-lotoscan-joker-080.json')
PREMIOS_CENTIMOS = {'7':100000000,'6':1000000,'5':100000,'4':30000,'3':5000,'2':500,'1':100}


def generar(data):
    juegos = data.get('juegos', {})
    primitiva = juegos.get('primitiva', {})
    if not isinstance(primitiva, dict):
        raise ValueError('Histórico de La Primitiva inválido')
    sorteos = {}
    for fecha, registro in sorted(primitiva.items()):
        numero = registro.get('joker') if isinstance(registro, dict) else None
        valido = isinstance(numero, str) and re.fullmatch(r'\d{7}', numero) is not None
        sorteos[fecha] = {
            'joker_ganador': numero if valido else None,
            'estado': 'numero_disponible_no_contrastado' if valido else 'sin_numero_valido',
            'fuente_resultado': registro.get('fuente') if isinstance(registro, dict) else None,
            'categorias_importes_fijos_centimos': PREMIOS_CENTIMOS if valido else None,
            'nota': 'No implica que los premios del Joker estén comprobados en los boletos.'
        }
    return {'version':'0.80','generado_utc':datetime.now(timezone.utc).isoformat(),
            'tipo':'diagnostico_no_publicable','sorteos':sorteos}


def main():
    datos = json.loads(HISTORICO.read_text(encoding='utf-8'))
    informe = generar(datos)
    SALIDA.write_text(json.dumps(informe, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(f'Joker: {len(informe["sorteos"])} sorteos revisados; informe no publicable')

if __name__ == '__main__':
    main()
