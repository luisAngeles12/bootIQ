# BootIQ F3 — Último experimento de pullback estricto secuencial

Fecha: 27-oct-2026. Investigación pasiva; sin credenciales, órdenes
ni cambios del motor operativo.

## Hallazgo de código directamente verificable

En `motor_protocolos.py`, `_rechazo` exige una mecha a favor
de al menos 1.3 cuerpos y `_impulso` exige cuerpo/rango >=0.58.
Como rango >= cuerpo+mecha, si se cumple rechazo entonces
cuerpo/rango <= 1/2.3 = 43.48%, incompatible con 58%.
Por tanto las rutas que requieren **ambas en la MISMA vela** son
inalcanzables con OHLC válido. Otras rutas del protocolo de pullback
pueden seguir confirmando, por lo que no implica bloqueo completo.

## Hipótesis probada sin alterar thresholds

`auditoria_pullback_secuencial_f3.py` evalúa **rechazo en la vela
anterior** y **recuperación+impulso en la vela actual**, siguiendo
los predicados de `motor_protocolos.py`, con desenlace hipotético
al cierre de la vela siguiente. Es una prueba reducida de patrón
en velas: **NO aplica TODO el contexto/tendencia/autoridad
del V3 y no son operaciones ejecutadas**.

- Fuente: `data_backtest_9x14_oos_post_9w_alineado_17`, 17 CSV,
  3,485 velas, fecha observada 02-oct-2026.
- [GitHub Actions 40557643937](https://github.com/luisAngeles12/bootIQ/actions/runs/40557643937),
  **212 pruebas OK**, módulo ejecutado offline.
- Rechazo+impulso simultáneo sobre la misma vela: **0**.
- Secuencia propuesta: **166 eventos**, 75 WIN, 90 LOSS,
  1 EMPATE, WR hipotético (sin empate) **45.45%**.
- Límite inferior Wilson 95%: **38.05%**.
- Un solo día de velas, no tres ventanas independientes.

## Decisión final de esta hipótesis

**RECHAZADA**. No demuestra >57%, no ofrece rentabilidad
y no permite extrapolar a LIVE. **No integrar** el cambio a los
protocolos operativos ni añadir operaciones. Mantener
bot, Cerebro, CORE4, TOP20, veto SUCIO/CAÓTICO y expiración intactos.

El defecto lógico de condiciones inalcanzables está identificado,
pero una eventual reparación en producción requeriría una prueba
de regresión/paridad y efecto causal específico; este experimento
no la justifica como mejora de rendimiento.

A petición del usuario, se detiene esta línea de exploración
sin seguir buscando filtros retrospectivos.
