# Contrato de datos SELAE → LotoScan (borrador 0.1)

## Evidencia y límites
Inspeccionadas respuestas archivadas `actual.json` de los nueve juegos, con ejemplos completos de noviembre de 2026. El script `scripts/catalogar_campos_selae.py` genera el inventario **real** por juego, presencia, tipos, ejemplos y columnas de escrutinios. Los campos observados no son una garantía de permanencia. Guardar siempre JSON original, ID, fecha, versión SHA256 y procedencia. **No calcular premios aún**.

## Campos compartidos
- `game_id`, `id_sorteo`, `fecha_sorteo`, `dia_semana`, `anyo`, `cdc`: identidad y calendario.
- `combinacion`: **cadena específica de juego**, nunca asumir que es una lista homogénea.
- `escrutinio[]`: `tipo` (texto de categoría), `ganadores` (acertantes), `premio` (importe textual), a veces `categoria` (orden), `ganadores_eu` (ámbito europeo), `multiplicador`.
- `apuestas`, `recaudacion`, `premios`, `fondo_bote`, `premio_bote`: métricas económicas; **no equivalen automáticamente al premio de un boleto**. Cantidades frecuentemente como cadenas y con coma decimal.
- `null`, lista vacía y ausencia del campo tienen significados distintos; conservarlos.

## Extracción observada por juego
| Juego | Combinación / especiales observados | Premios y tablas |
|---|---|---|
| EMIL Euromillones | `combinacion` 5 números + 2 estrellas (7 valores separados por guiones); `millon.combinacion` código El Millón; `lluvia` y campos `mw_*` (eventos especiales) | `escrutinio`, `escrutinio_millon`, `escrutinio_lluvia`; `ganadores_eu` |
| LAPR Primitiva | 6 números, `C(n)` complementario, `R(n)` reintegro; `joker.combinacion` código Joker | `escrutinio`, `escrutinio_joker` |
| BONO Bonoloto | 6 números, `C(n)` complementario, `R(n)` reintegro | `escrutinio` |
| ELGR El Gordo | 5 números, `R(n)` número clave | `escrutinio` |
| EDMS EuroDreams | 6 números y `C(n)` número Sueño (etiqueta C en cadena observada; **no tratar como complementario de Bonoloto**) | `escrutinio`, a veces `ganadores_eu` |
| LAQU Quiniela | 14 signos 1/X/2 y Pleno al 15 en `combinacion`; `partidos[]` con `local`, `visitante`, `signo`, `marcador`, a veces `fecha`; `elige8` identifica sorteo asociado | `escrutinio`, `escrutinioElige8` |
| QGOL Quinigol | 6 marcadores codificados (0,1,2,M); `partidos[]` con equipos, marcador y signo | `escrutinio` |
| LOTU Lototurf | 6 números, `C(n)` y `R(n)`; **verificar semántica oficial de C y R antes de asignar nombres al modelo** | `escrutinio`, categorías describen caballo ganador |
| QUPL Quíntuple Plus | 5 caballos ganadores y `C(n)` (segundo clasificado de quinta carrera: validar con reglas oficiales) | `escrutinio` |

## Modelo normalizado propuesto (no implementado aún)
```json
{
  "schema_version": "0.1",
  "source": {"provider": "SELAE", "endpoint": "fechav3", "raw_sha256": null},
  "draw": {"game_id": null, "id_sorteo": null, "date": null, "jornada": null, "temporada": null},
  "publication": {"state": "unverified", "observed_at": null},
  "result": {
    "numbers": [], "stars": [], "complementary": null, "reintegro": null,
    "dream": null, "key_number": null, "joker": null, "millon": null,
    "quiniela_signs": [], "pleno_15": null, "elige8": null,
    "quinigol_scores": [], "races": [], "raw_combination": null
  },
  "prizes": [{"product": null, "category_code": null, "category_label": null,
              "winners_spain": null, "winners_europe": null,
              "amount_eur": null, "raw_amount": null}],
  "economics": {"bets": null, "revenue": null, "jackpot": null},
  "raw": {}
}
```

## Reglas de seguridad de datos
1. Parseo **por juego** y sin pérdida: `raw` y `raw_combination` siempre disponibles.
2. Los valores `premio` usan coma decimal: parsear con `Decimal`, sin floats ni redondeo implícito; distinguir `0` de dato ausente.
3. No confundir `ganadores` con `ganadores_eu` ni `premios` agregado con importe por apuesta.
4. Joker, El Millón, Elige8 y promociones extraordinarias son **productos/categorías independientes** dentro del sorteo.
5. No interpretar `C(n)` ni `R(n)` globalmente: su significado depende del juego.
6. Un escrutinio presente no certifica que sea definitivo ni que cubra todas las categorías.
7. Para verificar boletos: falta documentar modalidades, apuestas múltiples, importes, reglas de acierto, premios fijos/variables y la estructura de cada boleto; validar con reglamentos oficiales y ejemplos reales.
8. Lotería Nacional y Navidad quedan fuera de este inventario de nueve juegos y mantienen sus circuitos propios.
