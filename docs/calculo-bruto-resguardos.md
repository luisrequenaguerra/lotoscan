# Cálculo bruto de resguardos

Nuevo módulo `scripts/calcular_resguardo.py`: recibe un sorteo normalizado y un resguardo con `game_id`, `id_sorteo`, `entries`, `validated`, `voided`, `multiple_draws`; Joker y El Millón se indican **una sola vez** en el nivel del resguardo. Comprueba cada apuesta ordinaria y calcula un total bruto **solo cuando no haya ningún bloqueo**.

Reglas de seguridad: no duplicar Joker/El Millón por cada apuesta; no multiplicar el reintegro por línea; bloquear reintegro premiado sin reglas verificadas de importe y multiplicidad; bloquear sorteos múltiples, Lluvia de Millones y datos incompletos. Se muestran componentes individuales incluso si el total queda bloqueado. Los datos `validated` y `voided` son **declaraciones de entrada**, no comprobaciones contra SELAE. Un `gross_eur` disponible es una **estimación no certificada**; `net_eur` permanece vacío. No incluye retenciones ni premios de sorteos no implementados.

Se conservan exclusivamente los datos oficiales JSON archivados; no se incorporan PDFs a la extracción de resultados.
