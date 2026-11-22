# Acumulación y compatibilidad de premios — estado de validación

Fuentes oficiales SELAE consultadas: 
- https://www.loteriasyapuestas.es/es/centro-de-ayuda/como-se-juega/jugar-a-bonoloto
- https://www.loteriasyapuestas.es/es/centro-de-ayuda/como-se-juega/jugar-a-la-primitiva
- https://www.loteriasyapuestas.es/es/centro-de-ayuda/como-se-juega/jugar-a-euromillones

## Reglas respaldadas por la información pública
- La Primitiva: seis números más reintegro es la categoría especial, no dos categorías principales simultáneas. Joker es un juego asociado opcional.
- Bonoloto y La Primitiva: el reintegro corresponde al valor de la apuesta diaria del resguardo; no debe calcularse como importe fijo por cada línea sin modelar el resguardo.
- Euromillones: las 13 categorías principales se definen por números y estrellas. El Millón es un juego asociado con código de resguardo; las promociones Lluvia de Millones requieren tratamiento específico.
- Joker: las categorías por primeras o últimas cifras requieren implementar coincidencia parcial y verificar exclusividad y compatibilidad de categorías.

## Bloqueos para cálculo definitivo
1. Modelar resguardo, precio diario, apuestas múltiples y múltiples sorteos.
2. Verificar normativas completas, no solo páginas divulgativas, para acumulación de categorías principales, reintegros y premios asociados.
3. Identificar y validar el premio aplicable cuando coinciden prefijos y sufijos del Joker.
4. Verificar categorías e importes oficiales contra un corpus de sorteos históricos con ganadores.
5. Incorporar el efecto de Lluvia de Millones, promociones y revisiones de escrutinio.

Hasta completar estas comprobaciones, `reglas_acumulacion.assess` y `assess_receipt` devuelven `total_eur: null` y `prize_certified: false`. **No mostrar premios totales definitivos en la app.**
