# BootIQ V3 — Análisis temporal de 13 jornadas sombra PRACTICE

## Evidencia obtenida
Salida local comunicada por operador del archivo `auditoria_candidatas_sombra_practice.csv` (9.561 registros) utilizando `experimento_alineacion_sombra_practice.comparar` después del commit `f870163`.
La ejecución del paquete de regresión `test_experimento_alineacion_sombra_practice.py` devolvió **8 pruebas OK**. Los porcentajes son proxies sobre **candidatas rechazadas NO_OPERAR**, con `HIPOTETICO_VELA_COMPLETA_SIN_FILL`, y no operaciones cerradas en el bróker.

| Escenario | Oportunidades | WIN | LOSS | Empates | WR hipotético | Jornadas >=60% | Jornadas <60% |
|---|---:|---:|---:|---:|---:|---:|---:|
| BASE_SIN_FILTRO_NUEVO | 6908 | 3401 | 3451 | 56 | 49.23% | 0/13 | 13/13 |
| SOLO_A_FAVOR_TENDENCIA | 4130 | 2026 | 2074 | 30 | 49.06% | 0/13 | 13/13 |
| A_FAVOR_Y_NO_CALL_RESISTENCIA_SIN_RUPTURA | 2598 | 1295 | 1284 | 19 | 49.85% | 1/13 | 12/13 |
| EN_CONTRA_TENDENCIA | 2100 | 1065 | 1017 | 18 | 50.71% | 0/13 | 13/13 |

## Única jornada de 60%+
En el escenario `A_FAVOR_Y_NO_CALL_RESISTENCIA_SIN_RUPTURA`, día UTC epoch 20760, 35 oportunidades / 22 WIN / 13 LOSS = **62.86%**; apenas **19 minutos UTC distintos**, con 16 oportunidades simultáneas en otros activos. No es un bloque de 20 operaciones PRACTICE, no demuestra payout ni fill y no representa una ventaja estable.

## Simultaneidad y restricciones de inferencia
- Base: 6.908 oportunidades, solo 1.787 minutos UTC distintos, 5.121 oportunidades simultáneas con otros activos.
- A favor: 4.130 oportunidades, 1.616 minutos UTC, 2.514 simultáneas.
- A favor sin resistencia: 2.598 oportunidades, 1.356 minutos UTC, 1.242 simultáneas.
- En contra: 2.100 oportunidades, 1.241 minutos UTC, 859 simultáneas.
- Todas las jornadas observadas en esta muestra son parte del análisis retrospectivo: **ningún escenario está confirmado OOS ni en PRACTICE ejecutado**.
- Se preservan los descartes contabilizados: 368 sin resultado trazable y 563 conflictos de activo/minuto.
- La muestra es histórica y correlacionada; no se debe seleccionar una jornada favorable y extrapolar.

## Decisión
**NO_PROMOVER_NINGUN_FILTRO A PRODUCCION**. Ninguna de las cuatro hipótesis ofrece soporte para un 60% constante, y no se debe alterar TOP20, thresholds, restricciones de SUCIO/CAOTICO, capacidad, expiración o momentos de entrada con estos resultados.

Próxima investigación útil: examinar el CSV original por interacciones *pre-entrada* (tipo_mercado × accion_precio × patrón) usando partición cronológica previa y validación posterior retenida. Reportar todos los segmentos, tamaños, días distintos, simultaneidad, mejores/peores resultados; registrar por adelantado cualquier nueva regla y evaluar su rendimiento sin fills como hipótesis exclusivamente. No habilitar órdenes. Para la certificación del 60% son indispensables operaciones ejecutadas PRACTICE nuevas y conciliación de resultados, no proxies.

## Comprobación posterior de hipótesis congeladas — 2026-11-20

Se ejecutó `validacion_prospectiva_alineacion.py` sobre el CSV completo de 9.561 registros. El corte congelado fue `1793732820` (inclusive): 64 registros anteriores quedaron excluidos del tramo posterior y 9.497 posteriores fueron evaluados. Esta separación es temporal dentro de un archivo histórico; **no equivale a una captura nueva en vivo ni a una operación ejecutada**.

| Hipótesis congelada | Desarrollo | Posterior al corte | Cambio |
|---|---:|---:|---:|
| BASE_SIN_FILTRO_NUEVO | 51.11% | 49.22% | -1.89 pp |
| SOLO_A_FAVOR_TENDENCIA | 64.52% | 48.94% | -15.58 pp |
| A_FAVOR_Y_NO_CALL_RESISTENCIA_SIN_RUPTURA | 70.83% | 49.65% | -21.18 pp |

El tramo posterior cubre 13 días y 1.774 minutos UTC distintos. En el escenario base hubo 6.863 oportunidades hipotéticas y 5.089 oportunidades simultáneas en otros activos. No hay fills, payout ni PnL del bróker. La variante que pareció superar 70% durante desarrollo perdió su aparente ventaja al aplicar la regla congelada al tramo posterior.

La investigación por interacciones encontró 21 grupos con tamaño mínimo exploratorio, pero **ninguno alcanzó 60% tanto en desarrollo como en validación retenida**. Los grupos que superaron 60% solo en uno de los segmentos no se promueven: se inspeccionaron múltiples combinaciones y sus porcentajes son hipotéticos.

## Decisión actual

**No cambiar ni habilitar estrategias de producción con esta evidencia.** En particular, no activar el filtro de tendencia ni la exclusión de resistencia evaluada: ambos regresaron aproximadamente al 49% en el tramo posterior. Mantener deshabilitado el permiso bootstrap sin memoria y conservar PRACTICE exclusivamente.

La siguiente mejora debe evaluarse con señales y resultados PRACTICE nuevos, con timestamps, fills y payouts conciliados. Congelar por adelantado una sola hipótesis y comparar cada bloque completo de 20 operaciones; no cambiar filtros durante la evaluación ni excluir sesiones perdedoras. El resultado sombra actual sirve para descartar una hipótesis retrospectiva, no para afirmar rentabilidad ni garantizar que futuras sesiones superen 60%.
