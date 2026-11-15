# BootIQ V3 — Plan integral de mejora (reconstrucción de trabajo, 12 fases)

> Documento de coordinación reconstruido a partir del objetivo expresado por el usuario y el código inspeccionado. NO se afirma que sea una transcripción del plan histórico original.

## Objetivo del proyecto
Elevar la calidad del sistema completo para INVESTIGAR si alcanza, en PRACTICE, al menos 60% de aciertos en cada ventana móvil de 20 operaciones cerradas, tanto en el conjunto como en las familias con muestra suficiente, con resultado monetario neto positivo y evidencia prospectiva independiente. No se garantiza ni se declara alcanzada la meta sin pruebas. Se reporta frecuencia: no perseguir winrate ocultando la caída de operaciones. Mantener mercados SUCIO/CAOTICO bloqueados y todas las protecciones existentes.

## Reglas transversales
- PRACTICE exclusivamente: nunca habilitar REAL.
- Comparar baseline congelado, entrenamiento, validación temporal y prospectiva sin mirar el futuro.
- No introducir cambios a estrategia, thresholds, expiración, TOP20, límites, timing ni permisos de órdenes sin evidencia causal y prueba de regresión.
- Probar tanto señales hipotéticas como órdenes realmente ejecutadas, sin mezclarlas en tasas.
- Considerar payout, coste, pérdida, beneficio y drawdown. Un 60% de WIN no garantiza rentabilidad si payout insuficiente.
- En cada etapa: diagnóstico -> hipótesis causal -> cambio mínimo -> pruebas -> backtest temporal -> OOS -> PRACTICE prospectivo. Revertir si no generaliza.

## Fases y entregables
1. **Integridad de datos** — velas cerradas, relojes, huecos, timestamps, intervalos, identidad y causalidad; baseline reproducible.
2. **Infraestructura y ejecución** — conexión IQ, PRACTICE, TOP20 íntegro, caché, reintentos, protocolos, fills y cierre; paridad BACKTEST/LIVE.
3. **Mercado y regímenes** — clasificar limpio/rango/tendencia/volatilidad y auditar segmentación sin relajar vetos SUCIO/CAÓTICO.
4. **Patrones y familias** — CHOCH, ruptura/retest, rechazo, continuación, reversión, sweep; medir cada familia y oportunidades independientes.
5. **Indicadores y Price Action integrados** — EMA9/EMA21, RSI, Bollinger(20,2), soporte/resistencia, vela, mechas, presión, volumen solo si la fuente lo soporta; comprobar datos, contradicciones y uso efectivo por el Cerebro. **FASE ACTUAL.**
6. **Cerebro único / arbitraje** — consistencia de evidencias y conflictos CALL/PUT, explicabilidad, sin doble conteo ni voto por resultados futuros.
7. **Entradas y temporalidad** — confirmación por vela cerrada, retrasos, ventana de entrada, paridad de ejecución, protocolo, tasa de fill y payout.
8. **Memoria y aprendizaje** — separación por niveles, salud muestral, ausencia de leakage y generalización TRAIN/OOS.
9. **Riesgo y frecuencia** — tamaño, pérdida por sesión, cooldown, límites operativos, oportunidades descartadas; sin habilitar REAL.
10. **Optimización experimental** — comparaciones predefinidas y registradas de combinaciones multiseñal, ablación por componente y búsqueda controlada sin sobreajuste.
11. **Validación de consistencia** — ventanas móviles y bloques no solapados de 20; conjunto y cada familia, muestra mínima, jornadas distintas, intervalos de confianza, neto y frecuencia.
12. **Validación prospectiva de extremo a extremo** — PRACTICE multi-jornada, recuperaciones, fallas, conciliación con broker, informe reproducible y decisión de continuar iterando; no autoriza REAL.

## Estado verificado al 15-11-2026
- Suite previa ejecutada localmente: 364/364 OK; esto no certifica rendimiento.
- Ledger sombra: 7,560 candidatas, 7,412 con procedencia validada, 148 excluidas, 279 sin resolución hipotética; no imputar resultados.
- Fase 5: diagnóstico en sombra para EMA/Bollinger y transporte de indicadores implementados previamente; corrección de bandas colapsadas agregada; medición de consistencia móvil por estrategia agregada.
- **Pendiente**: ejecutar pruebas posteriores a los commits, revisión de contribución marginal de todos los componentes y validación OOS con datasets reales suficientes. NO se ha demostrado 60% sostenido.

## Referencias metodológicas
Bailey et al., The Probability of Backtest Overfitting (Journal of Computational Finance, 2017); Arian et al., Backtest overfitting in the machine learning era (Knowledge-Based Systems, 2024). Las hipótesis seleccionadas a posteriori no constituyen pruebas prospectivas.
