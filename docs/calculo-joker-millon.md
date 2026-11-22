# Joker y El Millón: cálculo bruto y resguardos

## Joker
Se aplica **literalmente la tabla del Anexo II** de las normas oficiales de Joker, con los máximos aciertos consecutivos de primeras y últimas cifras. Se usa el importe acumulado de la tabla, **no** la suma de todas las categorías inferiores.

Fuente normativa: https://www.loteriasyapuestas.es/f/loterias/documentos/normativa/Normativa%20de%20los%20juegos/Normas_de_Joker_Octubre_2018.pdf

Ejemplos: 7 → 1.000.000 €; 5-1 → 1.001 €; 4-2 → 305 €; 3-3 → 100 €; 1-1 → 2 €. Se requiere escrutinio de categoría correspondiente.

## El Millón
Se comprueba el código ganador y el importe publicado en el escrutinio. La normativa oficial prevé un premio por resguardo con código premiado, y permite importes superiores o varios premios en determinadas condiciones. Por ello no se codifica como importe universal inmutable.

Fuente normativa: https://www.loteriasyapuestas.es/f/loterias/documentos/normativa/Normativa%20de%20los%20juegos/Normas_de_El_Millon_Abril_2025.pdf

## Límites de autenticación
`verificar_resguardo_asociado.py` valida coherencia entre juego, sorteo, código, participación declarada y estado declarado. **No existe integración con el sistema de validación de SELAE**, por lo que un usuario podría falsificar estos campos. No se certifica titularidad ni derecho de cobro. Los importes son **brutos**, no netos de impuestos, y no se agregan al total del resguardo.
