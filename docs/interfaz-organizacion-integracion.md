# Interfaz LotoScan: estructura y conexión de motores

Se conserva el diseño existente de `index.html` (cabecera, escáner, boletos, sorteos, resultados, formularios y estética). No se reemplaza por un prototipo nuevo.

## Organización de juegos
- Loterías de números: Bonoloto, La Primitiva, Euromillones, El Gordo, EuroDreams.
- Lotería Nacional: décimos y sorteos especiales.
- Pronósticos deportivos: La Quiniela (incluido Elige8) y El Quinigol.
- Hípicas: Lototurf y Quíntuple Plus.

Joker y El Millón son modalidades asociadas al resguardo, no tarjetas independientes.

## Próximo paso técnico: conexión real
Los motores de `scripts/` son Python de servidor y **no se ejecutan automáticamente en el navegador**. La pantalla actual tiene una lógica JavaScript histórica propia (`checkTicket38`) y un catálogo de resultados embebido. No debe afirmarse que el motor Python ya está conectado a la interfaz. Hace falta establecer un contrato de datos y un adaptador desplegable, o portar las reglas con pruebas de paridad entre Python y JS. Hasta entonces no sustituir estados pendientes por premios certificados.

Para validar la integración: test de paridad por juego, casos de Joker/El Millón, reintegros y bloqueo de casos ambiguos, verificación visual en iPhone y prueba de escaneo con resguardos reales anonimizados.
