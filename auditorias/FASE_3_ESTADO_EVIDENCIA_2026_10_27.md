# BootIQ V3 — Estado integrado de la fase 3

Corte de auditoría: 2026-10-27. Investigación exclusivamente PRACTICE/OOS, sin autorizar nuevas operaciones.

## Ramas examinadas

- F3.1: `audit/v3-fase31-causas-cerebro-20261025`, PR #7 (draft).
- F3.2: `audit/v3-fase32-candidatos-estrategias-20261025`, PR #8 (draft; apilado sobre #7).
- F3.3: `diagnostico-f33-breakout-retest-sombra`, investigación separada del commit operativo `2a33911`.
- Operativa: `bootiq-v3-auditoria`. Ninguna de las ramas experimentales F3 se ha fusionado con ella.

## Resultados verificables

### F3.1 — atribución de cancelaciones y CORE4

Ver descripción y registros del PR #7 (https://github.com/luisAngeles12/bootIQ/pull/7).

- Replay Oct12–13: 6,466 señales, 6,448 cancelaciones Cerebro, 16 directas y dos por protocolo.
- La revisión de 213 combinaciones de factores entre 17 activos comunes Sep/Oct no encontró ninguna con >=59% hipotético en ambos períodos.
- Evaluación separada CORE4: R1 solo 14W/4L n18; R1+R2 4W/1L n5; intervalos Wilson inferiores al objetivo. No ampliar autoridad.
- Señales canceladas no equivalen a PNL ejecutado y el corte Oct es temporalmente desequilibrado.

### F3.2 — hipótesis A/B, generalización y economía

Ver PR #8 (https://github.com/luisAngeles12/bootIQ/pull/8).

- A/B surgieron de explorar 1,171 combinaciones. Su aparente éxito inicial en 17 activos compartidos no constituye OOS independiente.
- En el replay ampliado Oct12–13, A=135W/110L (55.10% hipotético) y B=117W/96L (54.93%); ambas debajo del objetivo 59%.
- Hipótesis congeladas el 26-oct UTC. La prueba prospectiva exige ventanas nuevas posteriores al corte, muestra suficiente y límite inferior Wilson >=59%; ninguna validación pasada puede reutilizarse como futura.
- Sin payout y PNL monetario cerrado, el winrate hipotético no demuestra rentabilidad.
- Línea base de familias Oct12/Oct13 no alcanzó >=59% en ambos días.
- CI broker-free: un defecto del shell en `.github/workflows/test.yml` impidió la ejecución correcta de tres módulos finales. Corregido en commit `aac8835`; ejecución Actions 40530029790 completada **SUCCESS** con los 31 módulos listados existentes. La clave de caché `Pipefile` también fue corregida a `Pipfile` en commit `6d1bbc1`.

### F3.3 — Breakout + Retest pasivo

Ver informe detallado en la otra rama:
https://github.com/luisAngeles12/bootIQ/blob/diagnostico-f33-breakout-retest-sombra/auditorias/F3_3_BREAKOUT_RETEST_SOMBRA_OOS.md

- Comparación base vs diagnóstico: 39/39 filas, cero diferencias en campos originales.
- 14/14 tests locales OK; 425 ventanas, 104 patrones sombra (44 CALL/60 PUT).
- Resultados hipotéticos próximos: 44W/48L = 47.83%; al quitar segundas detecciones de siete rachas consecutivas: 41W/45L = 47.67%.
- No activa Breakout + Retest; la rama se mantiene sin integrar.

## Veredicto de fase general

**Aún NO se cumplen los requisitos para afirmar cierre productivo de fase 3.**

La auditoría identifica y prueba hipótesis; las investigadas no han demostrado simultáneamente >=59% estable, frecuencia útil, PNL económico real verificado y paridad de implementación LIVE PRACTICE. No confundir cierre de una hipótesis descartada con validación de la estrategia productiva completa.

## Siguientes condiciones de aceptación (sin relajar seguridad)

1. Evidencia realmente prospectiva independiente, posterior a la congelación de A/B; >=3 ventanas suficientemente pobladas y criterio Wilson exigido en el módulo.
2. Resultados reales cerrados PRACTICE con payout/PNL explícito, muestreo y diversidad temporal adecuados, sin convertir canceladas hipotéticas en operaciones.
3. Paridad BACKTEST/protocolo/LIVE y ausencia de divergencias regresivas para cualquier modificación de lógica (la paridad de CSV F3.3 sola no lo demuestra).
4. Respeto incondicional a CORE4, TOP20 máximo 20, mercados SUCIO/CAÓTICO vetados, aprendizaje y autorizaciones congeladas salvo causalidad directa.
5. Verificación de todas las pruebas broker-free y pruebas temporales relevantes antes de fusionar una rama; ni CI exitosa ni un WIN rate aislado autorizan REAL.

**No fusionar ni activar ninguna hipótesis sin cumplir los criterios.**
