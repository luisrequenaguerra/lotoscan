# Joker y El Millón: estado de verificación

Fuentes oficiales consultadas:
- Joker: https://www.loteriasyapuestas.es/es/centro-de-ayuda/como-se-juega/como-jugar-a-el-joker
- Euromillones y El Millón: https://www.loteriasyapuestas.es/es/centro-de-ayuda/como-se-juega/jugar-a-euromillones

**Importante:** Joker **sí permite premios acumulados**, según SELAE. Por tanto, NO se debe escoger solo la categoría más alta. La implementación devuelve cada coincidencia por primeras/últimas cifras, su categoría y su importe de escrutinio. El total sigue bloqueado hasta contrastar exhaustivamente la tabla oficial de premios acumulados, especialmente cuando coinciden ambos extremos y todas las cifras.

El Millón: código de tres letras y cinco dígitos asociado a una participación en Euromillones. Se identifica coincidencia exacta y se extrae el premio del escrutinio; **no** se certifica titularidad del resguardo ni pago.

Las pruebas usan resultados JSON archivados de SELAE; no hay PDFs en el flujo de extracción ni comprobación de resultados. No hay cálculo de importe neto fiscal ni verificación documental del resguardo. `total_eur` permanece `null` y `prize_certified` permanece `false`.
