
"""LotoScan 0.57: normaliza el informe exploratorio 0.56 sin tocar el histórico."""
import json
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

INPUT = Path('informe-lotoscan-056.json')
OUTPUT = Path('informe-lotoscan-057.json')
MONTHS = {m: i for i, m in enumerate(('enero','febrero','marzo','abril','mayo','junio','julio','agosto','septiembre','octubre','noviembre','diciembre'), 1)}


def money(text):
    """Importes simples en euros; rentas y 'sin acertantes' quedan sin valor."""
    match = re.fullmatch(r'\s*([\d.]+,\d{2})\s*€\s*', text)
    if not match:
        return None
    try:
        return int(Decimal(match.group(1).replace('.', '').replace(',', '.')) * 100)
    except InvalidOperation:
        return None


def date_from_headings(headings):
    for h in headings:
        m = re.search(r'\b(\d{1,2}) de (\w+) de (20\d{2})\b', h.get('texto','').lower())
        if m and m.group(2) in MONTHS:
            return f'{int(m.group(3)):04}-{MONTHS[m.group(2)]:02}-{int(m.group(1)):02}'
    return None


def rows(table):
    return [[c['texto'].strip() for c in row] for row in table]


def parse_prizes(table):
    data = rows(table)
    if not data or data[0] != ['Categoría','Acertantes','Premio']:
        raise ValueError('Cabeceras de premios inesperadas')
    result = []
    for row in data[1:]:
        if len(row) != 3 or not re.fullmatch(r'[\d.]+', row[1]):
            raise ValueError('Fila de premios inesperada')
        result.append({'categoria':row[0], 'acertantes':int(row[1].replace('.','')),
                       'premio_texto':row[2], 'importe_centimos':money(row[2])})
    return result


def parse_game(game, raw):
    if raw.get('estado') != 'datos_brutos_obtenidos':
        return {'estado':'pendiente','motivo':'No hay HTML exploratorio disponible'}
    day = date_from_headings(raw.get('titulos',[]))
    tables = raw.get('tablas',[])
    if not day:
        return {'estado':'pendiente','motivo':'Fecha no reconocida'}
    base = {'fecha':day,'fuente':raw.get('url'),'validado_oficialmente':False,'publicable':False}
    if game in ('eurodreams','gordo_primitiva','quiniela'):
        if not tables:
            return {**base,'estado':'pendiente','motivo':'No se encontró tabla de premios'}
        try:
            base['categorias'] = parse_prizes(tables[0])
        except ValueError as e:
            return {**base,'estado':'pendiente','motivo':str(e)}
        # Los fragmentos de texto del 0.56 están truncados y no garantizan
        # todos los números, ni el pleno al 15. No se adivinan combinaciones.
        return {**base,'estado':'premios_parciales','motivo':'Combinación completa no estructurada en el informe 0.56'}
    if game == 'loteria_nacional':
        if len(tables) < 2:
            return {**base,'estado':'pendiente','motivo':'Faltan tablas'}
        first, endings = rows(tables[0]), rows(tables[1])
        if first[0] != ['Categoría','Premio'] or endings[0] != ['Terminación','Tipo','Por décimo']:
            return {**base,'estado':'pendiente','motivo':'Cabeceras inesperadas'}
        prizes = []
        for row in first[1:]:
            if len(row) != 2:
                return {**base,'estado':'pendiente','motivo':'Premio principal incompleto'}
            m = re.fullmatch(r'(Primer|Segundo) premio · (\d{5})',row[0])
            if not m or money(row[1]) is None:
                return {**base,'estado':'pendiente','motivo':'Premio principal no interpretable'}
            prizes.append({'tipo':m.group(1).lower(),'numero':m.group(2),'importe_centimos':money(row[1])})
        terminaciones = []
        for row in endings[1:]:
            if len(row)!=3 or not row[0].isdigit() or money(row[2]) is None:
                return {**base,'estado':'pendiente','motivo':'Terminación no interpretable'}
            terminaciones.append({'terminacion':row[0], 'tipo':row[1], 'importe_centimos':money(row[2])})
        return {**base,'estado':'premios_parciales','premios_principales':prizes,
                'terminaciones':terminaciones,
                'motivo':'Falta validar reglas de acumulación, décimos, serie y fracción'}
    return {'estado':'pendiente','motivo':'Juego no soportado'}


def main():
    data = json.loads(INPUT.read_text(encoding='utf-8'))
    if data.get('version') != '0.56' or data.get('modifica_historico') is not False:
        raise ValueError('Informe de entrada inesperado')
    result = {'version':'0.57','generado_utc':datetime.now(timezone.utc).isoformat(),
              'modifica_historico':False,'publica_resultados':False,'juegos':{}}
    for game in ('eurodreams','gordo_primitiva','loteria_nacional','quiniela'):
        result['juegos'][game] = parse_game(game,data.get('juegos',{}).get(game,{}))
    OUTPUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Informe 0.57 generado:',OUTPUT)
    for game,item in result['juegos'].items():
        print(game,item['estado'])

if __name__ == '__main__':
    main()

