# BootIQ V3 — Evidencia F11: historial local y brecha al 60 % (2026-11-19)

## Fuente y alcance
Salida facilitada por el operador desde `historial_bot.csv`, sin volcar el archivo ni credenciales al repositorio. 580 registros, 120 columnas. 431 sin modo de cuenta declarado; 149 con modo `PRACTICE`. Todas las filas indican `CERRADA`, `OPERADA_DIRECTA` y `BOOTSTRAP_PRACTICE_SIN_HISTORIAL`. El modo declarado no acredita conciliacion independiente con IQ.

## Cohorte elegible para evaluacion exploratoria
`auditar_consistencia_20_practice.evaluar_filas` sobre la salida del operador:
- Filas validas: 149; descartadas: 431 (`MODO_NO_VERIFICADO_PRACTICE`).
- WIN: 71; LOSS: 78; win rate: 47.65 %; PnL total: -464.75.
- Bloques completos de 20: 7; bajo objetivo economico: 5.
- Ventanas moviles de 20: 130; bajo objetivo economico: 102.
- Consistencia observada: `False`. Meta 60 %: brecha 12.35 puntos porcentuales.
- Ninguna de estas operaciones identifica autoridad validada del Cerebro V3; son bootstrap.

## Familias (solo diagnostico, NO seleccion de estrategias)
| Familia | N | WIN | LOSS | WR % | PnL |
|---|---:|---:|---:|---:|---:|
| CHOCH alcista | 15 | 7 | 8 | 46.67 | -53.00 |
| CHOCH bajista | 27 | 15 | 12 | 55.56 | +11.25 |
| continuacion alcista con tendencia | 5 | 2 | 3 | 40.00 | -33.50 |
| continuacion bajista con tendencia | 1 | 1 | 0 | 100.00 | +20.75 |
| liquidity sweep alcista | 19 | 10 | 9 | 52.63 | -15.25 |
| liquidity sweep bajista | 12 | 6 | 6 | 50.00 | -23.50 |
| pullback alcista a EMA | 32 | 15 | 17 | 46.88 | -110.00 |
| pullback bajista a EMA | 6 | 2 | 4 | 33.33 | -57.50 |
| reaccion compradora en soporte | 12 | 5 | 7 | 41.67 | -70.25 |
| reaccion vendedora en resistencia | 20 | 8 | 12 | 40.00 | -133.75 |

Las diferencias de muestra impiden inferir ventaja causal o seleccionar ganadoras. Un solo WIN de una muestra N=1 no acredita nada.

## Cambios de control de evidencia
`auditar_consistencia_20_practice.py` ahora expone conteos por origen, `operaciones_bootstrap`, `operaciones_no_bootstrap`, y `valida_rentabilidad_cerebro_v3=False`. Se preservan metricas exploratorias sin promoverlas a certificacion V3. Regresiones nuevas en `tests/test_consistencia_20_practice.py`; CI sin broker ampliada en `.github/workflows/practice-auditor-validation.yml`.

## Bloqueos y siguientes evidencias
- No existe la carpeta local `data_backtest_actual` en la inspeccion facilitada; 0 CSV de velas para backtest causal oficial.
- Se requieren datos prospectivos de mercado con tiempos de recepcion, historial de ordenes PRACTICE conciliado y payouts de preentrada para atribuir resultados a V3.
- No alterar filtros SUCIO/CAOTICO, TOP20, tiempos de entrada, thresholds ni expiracion sin prueba causal.
- Las fases 5–12 no pueden certificarse y el objetivo constante de 60 % **NO** esta demostrado.
- PRACTICE exclusivamente, no REAL.
