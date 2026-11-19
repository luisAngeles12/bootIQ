# BootIQ V3 — Medición real de avance fases 5–12 (2026-11-18)

## Resultado verificable: ninguna mejora de rentabilidad demostrada

Baseline histórico disponible y consolidado en `docs/FASE5_AUDITORIA_ESTRATEGIAS_20261113.md`:

- 19 operaciones PRACTICE cerradas: **6 WIN, 13 LOSS**
- Acierto: **6/19 = 31.58 %**
- Beneficio neto: **−200.50** (en unidades monetarias del informe)
- Meta de consistencia: **al menos 12 WIN de cada 20 cerradas, neto > 0**, junto a validación por familias con muestra suficiente y evidencia OOS/prospectiva
- Distancia entre tasas: **60.00 − 31.58 = 28.42 puntos porcentuales**. No es estimación de mejora lograda: es la brecha pendiente.
- Faltan operaciones conciliadas nuevas y datasets históricos originales; la muestra inicial de 19 no contiene ninguna ventana completa de 20.
- Con una operación adicional hipotética, incluso si fuese WIN, esa secuencia terminaría con 7/20 = 35 %; no puede superar 60 % en su primer bloque. **No es predicción ni prueba nueva**.

## Fases 5–12: estado y bloqueador verificable

| Fase | Avance de herramientas / pruebas | Qué falta para certificar |
| --- | --- | --- |
| 5 Indicadores / Price Action | Auditoría y comparador de histórico, inspección de integridad OHLCV | Backtest causal reproducido con los CSV originales y datos nuevos OOS |
| 6 Cerebro único | Pruebas aisladas de arbitraje existentes | Medición pareada de decisiones y contradicciones con evidencia temporal |
| 7 Temporalidad y ejecución | Pruebas de paridad y conciliación existentes | Fills, precios de ejecución, payout y retrasos PRACTICE observados |
| 8 Memoria y aprendizaje | Pruebas de walk-forward/memoria existentes | Validación prospectiva sin filtración temporal ni selección retrospectiva |
| 9 Riesgo | Regresiones de stop, capacidad y balance existentes | Frescura contable del broker comprobada en PRACTICE |
| 10 Optimización | Exploración de patrones sombra y comparadores existentes | Hipótesis congeladas, OOS independiente, ablation/control de sobreajuste |
| 11 Consistencia | Evaluador de 20, intervalos, diagnóstico ledger e informe conjunto | Ledger de órdenes cerradas conciliadas, múltiples jornadas, muestras suficientes |
| 12 Extremo a extremo | Informe de solo lectura y CI configurada | Ejecución PRACTICE multi-jornada y conciliación de operaciones reales |

**Fases 5–12 totalmente certificadas: 0/8.** Esto NO significa que su implementación esté vacía; significa que carecemos de las evidencias finales de desempeño.

## Integridad de la evidencia / actualización

- El preflight F11/F12 ahora exige `estado` explícito, junto a los seis campos del ledger. El valor de cada fila debe ser `CERRADA`; no basta un CSV de resultados hipotéticos.
- `tests/test_diagnosticar_ledger_fases11_12_practice.py`: **10 pruebas definidas**.
- `tests/test_informe_integral_fases11_12_practice.py`: **6 pruebas definidas**.
- El workflow `consistencia-fases11-12-practice.yml` incluye estas baterías y el evaluador, pero la aprobación del último commit **no está comprobada** desde este entorno.
- No se ha alterado estrategia, TOP20, umbrales, tiempos, expiración ni bloqueo SUCIO/CAÓTICO.

## Prioridad de ejecución

1. Confirmar CI del HEAD y la suite completa sin broker.
2. Auditar CSV históricos originales: número de velas, continuidad, duplicados OHLCV y particiones train/valid/OOS.
3. Ejecutar el backtest causal oficial y contrastar versiones con mismo universo de señales.
4. Congelar hipótesis seleccionadas (p. ej., reacción vendedora en resistencia **55.46 % hipotético**), validar con OOS nuevo, y no activar estrategias de sombra.
5. Conciliar órdenes PRACTICE reales y evaluar todas las ventanas móviles y bloques no solapados de 20, netos y límites de incertidumbre; registrar frecuencia.
6. Solo cerrar las fases cuando la evidencia concreta de cada una supere sus requisitos. Ningún histórico puede garantizar 60 % de aciertos futuros.

Estado: **NO CERTIFICADO. PRACTICE exclusivamente; REAL prohibido.**
