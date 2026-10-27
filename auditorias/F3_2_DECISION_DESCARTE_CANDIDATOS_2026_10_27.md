# BootIQ V3 — Fase 3: decisión de descarte de candidatos

Fecha: 27-oct-2026. Decisión de investigación. **No cambia el bot operativo.**

## Objetivo

Detener la exploración de variantes que ya fallaron en la evaluación
ampliada, sin presentar una ganancia hipotética como rentabilidad real.

| Hipótesis | WIN | LOSS | n | WR hipotético | Payout neto mínimo de equilibrio |
|---|---:|---:|---:|---:|---:|
| A (F3.2) | 135 | 110 | 245 | 55.10 % | 81.48 % |
| B (F3.2) | 117 | 96 | 213 | 54.93 % | 82.05 % |
| Breakout + Retest F3.3 (sin rachas repetidas) | 41 | 45 | 86 | 47.67 % | 109.76 % |

Payout mínimo de equilibrio = LOSS / WIN; resultado unitario neto
de escenarios, **no payout observado ni PNL ejecutado**.

Si el payout neto fuera 80 %, el saldo unitario hipotético en
estas observaciones sería:

- A: 135×0.80 − 110 = **−2.00** unidades sobre 245 señales.
- B: 117×0.80 − 96 = **−2.40** unidades sobre 213 señales.
- F3.3: 41×0.80 − 45 = **−12.20** unidades sobre 86 eventos.

## Decisión ejecutiva

**DESCARTAR A, B y Breakout + Retest como mejoras listas para integrar**.
Ninguna logra el objetivo del 59 % en la evidencia ampliada disponible.
No invertir nuevos cambios de estrategia para «rescatar» estos parámetros
sobre las mismas muestras: eso sería ajuste retrospectivo.

No se demuestra que una estrategia completamente diferente sea imposible;
tampoco se demuestra que los resultados futuros sean idénticos. La
comparación A/B deriva de combinaciones exploradas en datos históricos,
y el F3.3 puede tener solapamientos fuera de las rachas adyacentes.

## Qué faltaría para afirmar una mejora real

1. Congelar **antes** de analizar resultados un candidato nuevo con
   hipótesis causal específica (no reoptimizar los 1,171 parámetros ya vistos).
2. Tres o más ventanas posteriores al corte sin solapamiento, con
   suficiente muestra y criterio Wilson de fase 3.
3. Contraste contra V3 sin alterar CORE4, TOP20, SUCIO/CAÓTICO, tiempos o
   expiración, y prueba de paridad BACKTEST/LIVE PRACTICE.
4. Payout y PNL **cerrados PRACTICE** sobre operaciones realmente ejecutadas,
   no predicciones de canceladas.

Hasta obtener esa evidencia no hay mejora validada que integrar.
**PRACTICE únicamente. Nunca REAL.**
