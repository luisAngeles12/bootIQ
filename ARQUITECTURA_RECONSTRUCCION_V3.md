# BootIQ V3 — arquitectura de reconstruccion (PRACTICE)

Estado: investigacion y diagnosticos, **no estrategia validada ni permiso para operar**.

## Criterios verificables

1. **Fuente y tiempo:** un flujo de eventos con hora de cierre y hora real de llegada. Rechazar velas abiertas, tardias, duplicadas, discontinuas o corruptas.
2. **Escalas:** observar velas 1s para microestructura; consolidar 60 velas 1s en 1m SOLO si el minuto esta completo. Ningun calculo usa una vela futura.
3. **Regimen:** primero separar tendencia alcista/bajista, rango, mercado mixto y SUCIO/CAOTICO. Las categorias preliminares son descriptivas y deben ser calibradas fuera de muestra; SUCIO/CAOTICO permanecen bloqueados.
4. **Estructura de precio:** soportes y resistencias construidos exclusivamente con velas previas; distinguir rechazo, ruptura, retest y continuation. Cada estrategia tiene su propio contrato y condiciones de abstencion.
5. **Indicadores complementarios:** RSI de Wilder para impulso; ATR para volatilidad; ADX para fuerza de tendencia. No acumular indicadores correlacionados como votos independientes.
6. **Motor de decision:** condiciones verificadas + contexto apropiado + tiempo de confirmacion + ausencia de contradicciones => candidato sombra, nunca orden automatica.
7. **Evaluacion:** comparar resultados de expiracion sobre entradas posibles, con intervalos no solapados, latencia, empate, sin futuro, costo/payout y abstenciones; nunca optimizar contra los datos reservados para validacion.
8. **Seguridad PRACTICE:** la capa de investigacion NO importa broker ni emite ordenes; solo una capa operativa independiente, y previa comprobacion de modo PRACTICE, podria ejecutar despues de autorizacion y evidencia suficiente.

## Orden de desarrollo

- [x] Reinicio sin memorias ni backtests antiguos.
- [x] Stream PRACTICE 1s y captura fresca.
- [x] Evaluacion causal hipotetica + latencia + no-solapamiento.
- [x] Contexto fresco: consolidacion 1m completa y clasificacion preliminar; **sin operaciones**.
- [ ] Reglas independientes para estrategias de ruptura-retest, rechazo de zona y continuacion de tendencia.
- [ ] Comparacion prospectiva y walk-forward en varias sesiones/activos, con datos sin solapamiento de entrenamiento/validacion.
- [ ] Reconciliacion de entrada simulada vs PRACTICE y payout real.
- [ ] Verificacion operativa completa del bot oficial, exclusivamente PRACTICE.

## Fuentes primarias de referencia

- QuantConnect LEAN, temporalidad/look-ahead: https://www.quantconnect.com/docs/v2/writing-algorithms/importing-data/streaming-data/custom-securities/key-concepts
- QuantConnect LEAN, modelos de fills/costos/ordenes: https://www.quantconnect.com/docs/v2/writing-algorithms/live-trading/trading-and-orders
- QuantConnect LEAN, diferencias backtest/live y latencia: https://www.quantconnect.com/docs/v2/writing-algorithms/live-trading/reconciliation
- TA-Lib, RSI: https://ta-lib.org/functions/rsi.html
- TA-Lib, ADX: https://ta-lib.org/functions/adx.html
- QuantConnect LEAN, ATR: https://www.quantconnect.com/docs/v2/writing-algorithms/indicators/supported-indicators/average-true-range
- Estudio original de patrones de vela (limitaciones): https://arxiv.org/abs/2501.12239
- Estudio original de sesgos por multiples estrategias: https://arxiv.org/abs/1811.06766

**Advertencia:** No hay ninguna estrategia “mejor” por definicion. El 37.84% de la primera hora de microrechazos es evidencia desfavorable para esa variante, no para todos los posibles modelos. Una clasificacion exitosa de mercado NO implica beneficio de operaciones.
