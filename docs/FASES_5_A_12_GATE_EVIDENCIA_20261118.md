# BootIQ V3 — Gate de fases 5 a 12 (2026-11-18)

**Estado: NO CERTIFICADO. PRACTICE exclusivamente, nunca REAL.**

Este documento registra una evaluación con los datos disponibles, no el cierre de fases ni la afirmación de que BootIQ haya alcanzado la rentabilidad objetivo.

## Evidencia disponible

- Auditoría de estrategias de 2026-11-13: 19 operaciones PRACTICE, 6 WIN y 13 LOSS, neto -200.50. No hay 20 órdenes cerradas en esa muestra.
- 5,895 resultados sombra evaluables son hipotéticos, no compras con fill/payout conciliados. No pueden sumarse al winrate de operaciones.
- La auditoría histórica F5.9 y sus comparadores no sustituyen los datasets locales originales ni la validación posterior.
- El archivo `docs/PLAN_INTEGRAL_12_FASES_V3.md` establece que cada ventana móvil de 20 operaciones debe alcanzar como mínimo 60% y resultado monetario neto positivo, tanto globalmente como en familias con muestra suficiente.

## Fases 5–12: brechas para la salida

| Fase | Evidencia / faltante | Estado |
| --- | --- | --- |
| 5 | Integridad de indicadores y comparador trabajados; sin backtest reproducible en históricos originales recientes | Abierta |
| 6 | Cerebro único/arbitraje con pruebas unitarias; pendiente validación causal de decisiones multi-señal | Abierta |
| 7 | Entrada, tiempos y reconciliación con pruebas aisladas; faltan fills y payouts PRACTICE prospectivos | Abierta |
| 8 | Herramientas memoria/walk-forward; falta muestra OOS independiente y evaluación de sesgo | Abierta |
| 9 | Protecciones de riesgo probadas con mocks; sigue abierta la frescura contable del saldo del broker | Abierta |
| 10 | Hipótesis de patrones exploradas; falta selección predefinida, validación temporal y comparación justa | Abierta |
| 11 | Pendiente ledger real de órdenes cerradas para ventanas móviles y bloques no solapados de 20 | Abierta |
| 12 | Pendiente validación PRACTICE de extremo a extremo, multi-jornada, con conciliación | Abierta |

## Hipótesis de estrategia, solo para estudio (sombra rechazada)

- Reacción vendedora en resistencia: 127/229, 55.46% hipotético.
- Pullback bajista EMA: 520/1004, 51.79% hipotético.
- Continuación bajista: 378/732, 51.64% hipotético.

Ninguna alcanza 60% en estos datos; seleccionar la mejor entre diez familias introduce sesgo. No modificar thresholds, TOP20, expiración, reglas de veto SUCIO/CAOTICO ni órdenes.

## Criterio de confirmación

Se exige histórico original sin duplicados/leakage, baseline congelada, validación OOS posterior independiente, operaciones PRACTICE conciliadas con monto/payout/fill, todas las ventanas de 20 (y bloques no solapados) con por lo menos 12 WIN y neto positivo, familias con muestra suficiente, intervalos de incertidumbre, frecuencia y pérdida máxima. Una muestra favorable no garantiza resultados futuros.

Un evaluador aislado de consistencia PRACTICE por ventanas y familia fue ejecutado localmente con **10/10 pruebas sintéticas OK**; estas pruebas NO son una ejecución con datos locales del usuario, NO son pruebas del broker y NO certifican las fases. Sus archivos se entregaron como artefacto de esta conversación y no se asume que formen parte del repositorio.

**Limitación actual:** los CSV originales y el ledger conciliado no se encuentran en GitHub. No declarar éxito sin ellos.
