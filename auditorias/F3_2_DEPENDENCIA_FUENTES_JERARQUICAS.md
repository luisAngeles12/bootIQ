# BootIQ V3 — Fase 3: procedencia y dependencia de fuentes

Fecha: 27-oct-2026 UTC. Investigación exclusivamente offline/PRACTICE,
no altera memoria ni política de decisión.

## Evidencia de código

- `motor_aprendizaje_historico.py`, `generar_aprendizaje_desde_resultados`:
  cada resultado válido incrementa todas las claves jerárquicas
  (excepto `PROTOCOLO_*`). Por tanto, la misma observación **puede formar
  parte de varias memorias de distinto nivel**.
- `_seleccionar_fuente_principal` elige una fuente transferible;
  `_seleccionar_fuente_respaldo` busca otra de un grupo más general
  y mayor muestra. No existe una comprobación de independencia a nivel
  de IDs de observaciones entre ambas.
- `_combinar_fuentes` mezcla probabilidades con pesos efectivos,
  sin sumar directamente sus `total` como si fueran muestras independientes;
  publica como intervalo el de la principal. La dependencia requiere
  análisis de incertidumbre antes de cualquier cambio.

## Comprobación histórica

- Auditor de solo lectura: `auditoria_dependencia_fuentes_fase3.py`.
- Dataset: `auditoria_xpd_sep2026_autoridad.csv`.
- GitHub Actions [40546064836](https://github.com/luisAngeles12/bootIQ/actions/runs/40546064836):
  **195 tests OK** y auditoría ejecutada sin bróker.

| Medida histórica | Registros |
|---|---:|
| Filas con fuente principal y respaldo comparables | 2,280 |
| Respaldo con muestra numérica mayor | 2,276 |
| Principal con muestra numérica mayor | 4 |
| Pares con contadores WIN/LOSS exactamente iguales | 0 |
| Pares con igual clave textual | 0 |

Pares de niveles frecuentes:

- CONTEXTO_SETUP → FAMILIA_DIRECCION: 766
- CONTEXTO_SETUP → PA: 707
- CONTEXTO_TECNICO → FAMILIA_DIRECCION: 418
- FAMILIA_DIRECCION → MERCADO_EVIDENCIAS: 160
- PA_DIRECCION → MERCADO_EVIDENCIAS: 140

El respaldo general con más muestra es compatible con la jerarquía elegida.
Sin identificadores de los resultados que contribuyeron a cada clave,
**no es posible calcular el solapamiento efectivo** ni determinar que
una mezcla sea mala por este único hecho. Contadores distintos tampoco
prueban independencia.

## Comprobación ampliada de inclusión estructural

El generador `_claves_jerarquicas` agrega por definición `FAMILIA_DIRECCION|familia|direccion`
a cada registro que aporta a `CONTEXTO_SETUP|direccion|familia|...` o
`CONTEXTO_TECNICO|direccion|familia|...`. Por eso, **cuando ambas claves
coinciden en familia y dirección**, los registros de la fuente contextual
también pertenecen a la fuente de familia-dirección bajo la misma generación
de memoria. Esto demuestra inclusión, sin necesitar identificadores persistidos.

El auditor contrasta *las claves concretas*, no únicamente los nombres de nivel.
En [Actions 40548232762](https://github.com/luisAngeles12/bootIQ/actions/runs/40548232762)
se verificaron **197 tests OK** y sobre 2,280 pares comparables se identificaron
**1,184 pares de inclusión estructural demostrada** (766 CONTEXTO_SETUP y
418 CONTEXTO_TECNICO hacia FAMILIA_DIRECCION); **0 anomalías** con
muestra contextual superior a la familiar. Para los otros 1,096 pares,
este detector conservador no emite veredicto de independencia.

Esto refina la advertencia anterior: existe dependencia demostrada en
1,184 pares de fuentes históricas, pero **no cuantifica el sesgo o
la mejora de la probabilidad combinada** ni prueba rentabilidad.
La condición de no alterar el motor se mantiene.

## Decisión

**No alterar selección, pesos ni ajuste de probabilidades.**
Si se plantea un modelo de incertidumbre de mezcla, deberá conservar
trazabilidad de observaciones en una rama experimental y demostrar
mejor cobertura/calibración OOS, frecuencia útil y PNL PRACTICE.
El bot operativo y los filtros CORE4/TOP20/SUCIO permanecen intactos.
