# BootIQ V3 — Fase 3: evidencia y criterio de salida (26-oct-2026)

## Alcance

Auditoría de generación de señales, familias de estrategias, rescatadores
CORE4, causalidad de los protocolos, frecuencia, validez de resultados y
rentabilidad. Es un diagnóstico del sistema, no una autorización para operar.

La meta global **>=59% de winrate fuera de muestra con PNL neto positivo y
frecuencia útil** corresponde a la integración de las **siete fases**.
No es correcto exigir 59% a cada familia ni declarar un filtro apto porque
gane en una muestra elegida después de mirar los resultados.

## Datos y decisiones reproducibles

- Replay de 12–13 octubre: 6,466 señales, hasta 100 activos históricos
  (universo de auditoría, **no** un cambio de MAX20). 6,448 canceladas por
  cerebro, 16 operaciones directas simuladas y 2 canceladas por protocolo.
- Las 16 directas: **12 WIN/4 LOSS = 75%**, pero **solo 1 día**;
  límite inferior de Wilson 95% **50.50%**. Sin PNL/payout verificable.
  No constituye evidencia de un 59% estable ni frecuencia suficiente.
- CORE4: R1 sin veto 9W/3L sobre 12 directas (Wilson 46.77%);
  R1+R2 sin veto 3W/1L sobre 4 directas (Wilson 30.06%).
  Ninguna ruta reúne muestra ni cobertura temporal de validación.
- Las dos cancelaciones por protocolo se dieron en USDHKD-OTC y NOKJPY-OTC:
  ruptura de resistencia sin confirmación. El protocolo mantiene autoridad
  desactivada y telemetría sombra por evidencia consolidada previa
  **25W/29L = 46.30%**. No levantar ese guarda por dos WIN hipotéticos.
- Hipótesis exploratorias A/B: en 17 activos seleccionados parecían superar
  59% en SEP/OCT, pero al ampliar a 100 activos del replay OCT12–13:
  A 135W/110L = **55.10%** (245 señales, 83 activos);
  B 117W/96L = **54.93%** (213 señales, 87 activos).
  Búsqueda de 1,171 combinaciones: sesgo de selección. **No promocionar**.
- Las familias generales del replay permanecen próximas a 50%, sin
  generalización multiventana suficiente para abrir autoridad genérica.

## Hallazgos técnicos corregidos en el PR experimental

1. Narrativa EMA/CHOCH ahora distingue contexto confirmado y no confirmado;
   activadores y puntuaciones preservados. Paridad OOS 39/39.
2. El reporte económico separa WIN hipotético de cierre realmente ejecutado
   (incluyendo operaciones de protocolo), normaliza fechas Unix UTC, evita
   contar order_id repetidos y no certifica PNL positivo sin identidad fiable.
3. MAX20 es un máximo **simultáneo**, no un tope de símbolos diferentes
   acumulados a lo largo de días.
4. Las rutas CORE4 usan el cierre de la operación de protocolo, jamás el
   resultado hipotético de la señal antes de la entrada diferida.
5. La cobertura declarada exige incertidumbre Wilson 95%; un WR observado
   superior a 59% en pocas operaciones no basta.
6. Los tests retroactivos no otorgan autoridad LIVE. Pruebas integrales
   broker-free realizadas localmente: **184/184 aprobadas** al cierre de
   estas observaciones (no equivale a CI GitHub del último commit).

## Criterios para avanzar a validación de rendimiento inter-fases

- Hipótesis definidas **antes** de medir ventanas de validación.
- Múltiples periodos prospectivos, sin reusar señales exploradas; para A/B
  rige corte UTC 26-oct-2026 y mínimo ya fijado en
  `auditoria_hipotesis_fase32.py`.
- Comparar frecuencia de **entradas técnicamente autorizadas** y ejecutables,
  no número de WIN hipotéticos en señales canceladas. Controlar ranking TOP
  válido, capacidad, protocolos, tiempos y mercados SUCIO/CAÓTICO.
- Para rentabilidad, usar operaciones cerradas y deduplicadas con
  `order_id`, `resultado`, `pnl_real_cerrado` y payout neto verificable.
- Exigir WINRATE >=59% OOS con incertidumbre, PNL neto >0 y volumen
  operacional útil del sistema completo. Sin estos datos, la conclusión
  correcta es **NO VALIDADO**, no ajustar filtros para fabricar el indicador.

## Cierre de tres tareas pendientes (27-oct-2026)

### Integración del stack

PR #7 -> PR #8 -> PR #9 continúan en DRAFT sobre ramas experimentales. El
commit de reconciliación `0df969b74ca5c1b243d56adfad4c5e213cd60da7`
incorpora por ascendencia el commit CI tardío del PR #8 al PR #9 con el
**mismo árbol** que el PR #9 previo; `mergeable=True`. No se fusionó con
producción ni se habilitó ninguna regla de trading.

### Embudo de frecuencia observado, replay íntegro

| Estado de embudo | Total | 12-oct | 13-oct |
| --- | ---: | ---: | ---: |
| Señales | 6466 | 6229 | 237 |
| Coincidencia CORE4 previa | 140 | 134 | 6 |
| Elegible estructural CORE4 | 18 | 18 | 0 |
| Operación directa simulada | 16 | 16 | 0 |
| Rechazo de protocolo tras aprobación | 2 | 2 | 0 |
| Cancelación de cerebro | 6448 | 6211 | 237 |

De las 140 coincidencias CORE4, 122 se cancelaron por cerebro (con veto
selectivo marcado), 16 operaron directamente y 2 pasaron a protocolo sin
confirmación. Entre 6,326 señales sin coincidencia y otras 122 con veto, no
hubo operación. `cerebro_unico_bloquear_por_riesgo=True` en **cero** filas;
por tanto atribuir el cuello de botella únicamente a esa bandera sería falso.
El replay registra 100 activos y 796 minutos con señal el 12-oct; 45 activos
y 36 minutos el 13-oct. Las 16 directas del 12-oct se reparten entre 15 activos
y 15 minutos. Tasas: 16/6229 = 0.257% de señales y 16/796 = 2.01
operaciones directas por 100 minutos con señal. El 13-oct hubo cero entradas.
**Son operaciones del backtest, no cierres verificados del broker**. No consta
`order_id`, payout ni columna de PNL en este replay. Tampoco hay garantía de
que 100 activos históricos hubieran sido candidatos del TOP20 simultáneo LIVE.
Este embudo ubica la pérdida principal **antes del protocolo**, pero no prueba
que quitar un veto aumentaría ganancias: no se cambió autoridad.

### Protocolo de validación prospectiva congelado

1. Congelar SHA de código/configuración, familias/candidatos, ordenación TOP,
   ventana temporal de exclusión y criterio de frecuencia *antes* del nuevo
   replay. A/B descubiertas con SEP/OCT no pueden tomar esos mismos datos como
   confirmación. Corte de exclusión inicial: 2026-10-26 UTC.
2. Recoger velas independientes posteriores al corte, con cobertura de varios
   días y mercados representativos, y conservar hashes/manifiesto de origen,
   orden cronológico y datos de exposición accesibles al momento de señal.
   Mantener PRACTICE y aprendizaje desactivado para reproducibilidad.
3. Reproducir todos los pasos en paridad: señal, elegibilidad CORE4, decisión
   cerebro, confirmación temporal protocolo, ranking TOP20 íntegro, capacidad
   abierta, ejecución PRACTICE y cierre. Las señales canceladas nunca se
   convierten en operaciones solo por WIN hipotético.
4. Medir por fecha y activo: oportunidades, aprobadas, entradas realmente
   ejecutables, ejecuciones broker identificadas por `order_id`, cierres,
   WIN/LOSS, payout, PNL neto y frecuencia por tiempo efectivo. Registrar
   deslizamiento/errores de ejecución y ausencia de datos.
5. Para certificación retrospectiva mínima, reportar n >= 100 operaciones
   deduplicadas en >= 3 días y límite inferior Wilson 95% >= 59%, más PNL
   completo y positivo; esos mínimos internos NO sustituyen evaluación por
   períodos separados, ni garantizan rentabilidad futura. La frecuencia mínima
   práctica debe fijarse ex ante y evaluarse junto al límite MAX20.
6. Si la muestra sigue siendo escasa, faltan order_id/PNL, el límite Wilson
   cae bajo 59 o falla una subventana, resultado = **NO VALIDADO**. Nuevas
   hipótesis nacidas de fallos del bloque pasarán a otra validación futura,
   nunca se retestearán sobre el mismo bloque para proclamarlas OOS.

**Disponibilidad de datos:** al cierre de este reporte solo hay replay
histórico Oct12–13 y datos de exploración previos. No existe todavía un bloque
posterior independiente verificable con ejecuciones y PNL para afirmar éxito.

## Límites de autoridad

Cambios del PR #9 permanecen experimentales y apilados sobre PR #8.
No mezclar en LIVE, no REAL, no modificar TOP20/guardas SUCIO/CAÓTICO/
segundo 9/expiración/estrategias sin evidencia causal y paridad pertinente.

**Decisión:** diagnóstico técnico e integración documental completados; A/B y
apertura genérica RECHAZADAS por evidencia; evaluación prospectiva integral y
rentabilidad **pendientes**. Ninguna estrategia nueva queda autorizada.
