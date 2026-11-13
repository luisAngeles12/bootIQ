# BootIQ V3 — Fase 5, auditoría estratégica consolidada (2026-11-13)

## Alcance y fuentes
- Rama: `bootiq-v3-auditoria`.
- Fuente 1: 19 operaciones PRACTICE ejecutadas, 6 WIN, 13 LOSS, resultado neto -200.50 (importe 25 por operación; payout observado 20.75 en ganancias).
- Fuente 2: 6154 candidatas sombra rechazadas; 5895 evaluables WIN/LOSS; resultados hipotéticos de apertura/cierre de vela posterior SIN_FILL, no son órdenes.
- Fuente 3: inspección de `bootstrap_practice.py`, `decision_bootiq.py`, `motor_decision.py`, `backtest_bot_real.py`, `experimento_alineacion_sombra_practice.py`, `diagnostico_causal_prospectivo.py` y `reporte_candidatas_sombra_practice.py`.
- Las cifras de candidatas son las salidas agregadas facilitadas por el usuario; el CSV local no está disponible en GitHub. No se realizaron backtests nuevos sobre velas locales.

## Operaciones ejecutadas
| Régimen | WIN | LOSS | Neto |
|---|---:|---:|---:|
| RANGO_LIMPIO | 3 | 3 | -12.75 |
| TENDENCIA_LIMPIA | 2 | 3 | -33.50 |
| TENDENCIA_SUCIA | 1 | 7 | -154.25 |
| **Total** | **6** | **13** | **-200.50** |

`TENDENCIA_SUCIA` NO equivale a `calidad_mercado=SUCIO`: nunca autorizar mercados SUCIO/CAOTICO. Las 8 operaciones del primer grupo tenían autoridad `BOOTSTRAP_PRACTICE_SIN_HISTORIAL`. Su concentración de pérdidas es una señal de investigación, no validación causal del bloqueo. El bootstrap existe exclusivamente para PRACTICE, requiere calidad NORMAL/LIMPIO, controles técnicos y falta de fuente estadística.

## Diez familias de estrategias: 5895 resultados hipotéticos
La columna inferior de Wilson 95% es una aproximación **sin corrección por dependencia temporal, simultaneidad entre activos ni selección múltiple**: NO autoriza una regla.

| Familia | WIN/N | Winrate proxy | Inferior Wilson 95% (ingenuo) | EV proxy con payout 83% por unidad apostada |
|---|---:|---:|---:|---:|
| Reaccion vendedora en resistencia | 127/229 | 55.46% | 48.98% | 1.49% |
| Pullback bajista EMA | 520/1004 | 51.79% | 48.70% | -5.22% |
| Continuacion bajista | 378/732 | 51.64% | 48.02% | -5.50% |
| Liquidity sweep alcista | 172/338 | 50.89% | 45.58% | -6.88% |
| Pullback alcista EMA | 467/923 | 50.60% | 47.37% | -7.41% |
| Liquidity sweep bajista | 189/381 | 49.61% | 44.61% | -9.22% |
| Continuacion alcista | 420/859 | 48.89% | 45.56% | -10.52% |
| CHOCH alcista | 307/653 | 47.01% | 43.21% | -13.96% |
| Reaccion compradora en soporte | 75/170 | 44.12% | 36.87% | -19.26% |
| CHOCH bajista | 265/606 | 43.73% | 39.83% | -19.98% |

Payout de equilibrio para 83%: **54.64%**. En el mejor grupo, reacción vendedora en resistencia, el winrate proxy 55.46% supera marginalmente el equilibrio, pero su Wilson inferior ingenuo es 48.98%, claramente inferior. Sin fill, sin payout real por señal y con correlaciones, ni siquiera ese grupo demuestra ventaja.

## Sensibilidad: 60 escenarios aritméticos (10 familias × 6 payouts)
Estas son **60 evaluaciones algebraicas**, no 60 backtests ni 60 experimentos independientes. EV proxy = pWIN × payout − (1 − pWIN); empate y latencia no modelados.

| Payout hipotético | Winrate requerido para equilibrio | Familias con EV proxy puntual positivo | Familias con EV proxy positivo usando Wilson inferior ingenuo |
|---|---:|---|---:|
| 70% | 58.82% | Ninguna | 0 |
| 75% | 57.14% | Ninguna | 0 |
| 80% | 55.56% | Ninguna | 0 |
| 83% | 54.64% | Reaccion vendedora en resistencia | 0 |
| 85% | 54.05% | Reaccion vendedora en resistencia | 0 |
| 90% | 52.63% | Reaccion vendedora en resistencia | 0 |

## Riesgos metodológicos confirmados
1. Las 6154 candidatas tienen `decision=NO_OPERAR`. No representan la muestra de aprobadas y existe sesgo de selección.
2. Varios patrones pueden compartir activo/minuto; depurar con `experimento_alineacion_sombra_practice.depurar` antes de atribuir efectividad.
3. Resultados `HIPOTETICO_VELA_COMPLETA_SIN_FILL` no comprueban precio del broker, latencia, expiración ni payout.
4. Los conjuntos de velas 9x14 de 2026-10-02 replicados en cinco carpetas son idénticos, NO cinco muestras independientes. OOS4 del 2026-10-24 ya fue examinado; no es OOS fresco al generar hipótesis retrospectivas.
5. Las cinco capturas USDINR-OTC del 2026-10-28/31 son segmentos discontinuos en días separados, insuficientes para reproducir el requisito de 181 velas por segmento en LIVE.
6. Probar decenas de reglas en el mismo histórico infla el riesgo de sobreajuste; registrar hipótesis, fecha de congelación y muestra futura antes de validación.

## Estado de las líneas de investigación
- **Prioridad alta:** operaciones bootstrap en TENDENCIA_SUCIA: 1/8 WIN, -154.25. Congelar la hipótesis de que las condiciones técnicas específicas pueden discriminar estas pérdidas, sin bloquear ni recalibrar aún.
- **Prioridad media:** reacción vendedora en resistencia: 127/229 WIN proxy (55.46%); estable entre las dos mitades observadas pero con resultados diarios variables y sin certeza suficiente. No activar por ganar entre rechazadas.
- **Prioridad media:** pullback bajista y continuación bajista: 51.79% y 51.64% proxy, inferiores al umbral de equilibrio a 83%.
- **Prioridad media:** reacciones compradoras en soporte y CHOCH: desempeño proxy inferior. No reinterpretar muestra de rechazadas como prueba para modificar vetos establecidos.
- **Conservar:** TOP20, thresholds, restricciones temporales, capacidad, expiración, mercados SUCIO/CAOTICO y aprendizaje histórico desactivado.

## Correctivos de trazabilidad ya implementados y validados
Commits `2317896`, `21b55d6`, `8eea59c`, `04f9619`: conservar motivos completos, priorizar el motivo oficial y pruebas de regresión. Última batería local comunicada: 321/321 pruebas aprobadas. No son validación de estrategia rentable.

## Criterio de salida / trabajo pendiente
La auditoría de código y de estadística descriptiva puede cerrarse; **no se puede declarar una estrategia ganadora ni fase 5 de validación de rentabilidad completa** sin muestras nuevas de velas, decisiones prospectivas congeladas, operaciones PRACTICE con fill y payout, ventanas OOS realmente posteriores, análisis de dependencia/agrupación y comparaciones pareadas contra la versión base.

No se modifican reglas productivas hasta superar estas condiciones. Cualquier activación con dinero REAL queda prohibida.
