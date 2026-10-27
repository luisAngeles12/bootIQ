# BootIQ V3 — Fase 3.3: cierre de la hipótesis Breakout + Retest (sombra)

Estado: **investigación estadística OOS terminada; activación rechazada**.
Fecha: 2026-10-27. Rama de diagnóstico: `diagnostico-f33-breakout-retest-sombra`.

## Alcance y restricciones

- Referencia operativa inalterada: `bootiq-v3-auditoria`, base `2a3391161d55df703ae4498bdac204e1a961a8ad`.
- El detector histórico es telemetría sin autoridad. No modifica CORE4, protocolos, TOP20, filtros SUCIO/CAÓTICO, expiración o rutas LIVE.
- Configuración del backtest: `OUT_OF_SAMPLE`, `FILTRADO`, aprendizaje desactivado, 17 archivos históricos de 205 velas (cada uno).

## Causa inspeccionada

`soporte_resistencia_zonas` en `zonas.py` selecciona soportes inferiores y resistencias superiores al precio actual; `breakout_retest` simultáneamente exige cierres que superen la resistencia (CALL) o perforen el soporte (PUT). En el camino usado por `estrategia.py`, eso impide que determinados patrones de ruptura y retest se reconozcan de forma coherente. La reconstrucción en sombra usa niveles establecidos antes de las dos velas finales.

**Importante:** demostrar una limitación del detector original no prueba que corregirlo mejoraría resultados operativos.

## Evidencia y reproducibilidad

- Tests: 14/14 exitosos en el entorno Windows/Git Bash de validación (10 del detector + 4 del evaluador).
- Auditor independiente: 425 ventanas, 44 CALL, 60 PUT y 321 neutrales.
- Comparación de salida BACKTEST original / rama sombra: 39 filas frente a 39; cuatro campos adicionales exclusivamente diagnósticos; cero campos originales ausentes y cero filas originales diferentes.
- BACKTEST hipotético oficial: 39 señales, 14 WIN / 25 LOSS; todas canceladas por el Cerebro Único; cero operaciones autorizadas.
- Intersección con las 39 señales: 9 registros con algún indicador sombra activado; solo 2 en la misma dirección, ambos LOSS hipotéticos; no eran elegibles estructuralmente por CORE4.
- Evaluación de todos los patrones contra **cierre de la vela siguiente**: 104 detecciones; 44 WIN, 48 LOSS, 3 empates, 9 sin futuro; WR hipotético 44/92 = **47.83%**.
- Por activo: 6/17 por encima del umbral de referencia de 59%, con muestras individuales diminutas (p. ej., 5W/0L). No se permite elegir activos ganadores a posteriori para autorizar la hipótesis.
- Agrupación descriptiva por activo y dirección en minutos consecutivos: 90 rachas unitarias y 7 dobles (97 rachas, 104 detecciones).
- Sensibilidad conservando solo la primera detección de cada racha: 41 WIN / 45 LOSS, 3 empates y 8 sin futuro; WR hipotético 41/86 = **47.67%**.

## Limitaciones explícitas

- Las ventanas de 181 velas se solapan y los activos pueden estar correlacionados; ni 104 detecciones ni 97 rachas representan necesariamente operaciones estadísticamente independientes.
- El resultado sombra toma el cierre de la vela de señal como entrada y el cierre siguiente como salida. **No** reconstruye latencia, precio real de ejecución, spread, payout, autorización CORE4 o PNL realizable.
- Los 17 datasets breves no permiten afirmar estabilidad futura ni extrapolar a otros regímenes.
- La tasa hipotética de 47.83% es inferior a la meta OOS de investigación (59%). No cambiar umbrales para justificar activación.

## Decisión

**No activar ni integrar Breakout + Retest sombra a decisiones operativas.**
Conservar la rama de investigación y este resultado negativo. No modificar el detector original sin una hipótesis causal nueva y validación independiente posterior.

## Pendientes para declarar completa la Fase 3 general

1. Recuperar el alcance y los criterios de aceptación aprobados para Fase 3 (el README original describe la librería IQ Option, no un plan de fase).
2. Inventariar y contrastar las otras hipótesis de calidad/frecuencia contra evidencia TRAIN/OOS ya cerrada, sin repetirlas.
3. Revisar evidencia de paridad LIVE PRACTICE del flujo final si forma parte del criterio de salida; la paridad CSV OOS actual no demuestra paridad LIVE.
4. Registrar los hallazgos y pruebas de cualquier nueva modificación en una rama aislada antes de elevar cambios a `bootiq-v3-auditoria`.

Este documento registra resultados de auditoría, no instrucciones para operar.
