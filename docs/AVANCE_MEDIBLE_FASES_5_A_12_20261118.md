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

## Actualización de inspección directa (19/20-11-2026) — corrección de gates PRACTICE y límites del 60%

**Hallazgo corregido y probado**: `auditar_consistencia_20_practice.py` admitía filas REAL/sin `modo_cuenta_configurado` y confundía `>= 60%` de aciertos con consistencia económica aun cuando el PNL de la ventana fuese negativo. Ahora la auditoría exige modo declarado PRACTICE y centavos válidos; conserva `cumple_60` como información separada, pero la consistencia global, por familia, bloques y ventanas móviles exige también **PNL estrictamente positivo**. Los descartes quedan explícitos y nunca se certifica procedencia broker u OOS por este cálculo.

La incorporación reveló dependencias de transporte de modo en `comparar_filtros_sombra_fase5_practice.py`, corregidas para preservar el modo en cada serie de 20, y en `validar_choch_bajista_prospectivo_practice.py`, donde la cohorte prospectiva ahora excluye REAL y modo no confirmado. Los tests sintéticos correspondientes declaran PRACTICE explícitamente y verifican que REAL, vacío y 12 WIN/20 con PNL negativo **no pasan**. Los cambios no alteran el Cerebro, señales, órdenes ni reglas de entrada.

Evidencia de CI sobre `81389d0fc1d31a813503ba04f461d7185c9d888d`:
- [Suite integral GitHub Actions #44643577858](https://github.com/luisAngeles12/bootIQ/actions/runs/44643577858): **729/729** tests generales, **3/3** tests de régimen, sintaxis de **347** archivos Python, verde.
- [Suite Fase 5 #44643578086](https://github.com/luisAngeles12/bootIQ/actions/runs/44643578086): verde.
- Comprobación directa del árbol completo de la rama: **no hay** blobs versionados `.csv`, `.jsonl`, `.parquet`, `.zip`, `.sqlite`, `.db` o `.xlsx` para acreditar un backtest con datasets de mercado originales ni un ledger exportado por IQ. Esto no dice que no existan archivos locales fuera de GitHub; solo delimita lo disponible para pruebas conectadas.

**Resultado económico histórico confirmado solo por salida local del operador**: 149 operaciones marcadas PRACTICE, 71 WIN / 78 LOSS = **47,65%**, PNL **−464,75**, expectativa observada **−3,1191** por operación, profit factor **0,7617**. Se atribuyen a `BOOTSTRAP_PRACTICE_SIN_HISTORIAL`, no prueban desempeño del Cerebro V3 con memoria validada. Falta certificado independiente del broker, aperturas/cierres UTC prospectivos y cohortes multi-jornada realmente OOS. **No declarar cierre de las fases 5–12 ni ventaja >=60% hasta adquirir esa evidencia.** Bootstrap sigue desactivado y no se permite REAL.
