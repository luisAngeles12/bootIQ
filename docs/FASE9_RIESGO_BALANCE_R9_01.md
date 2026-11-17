# Fase 9 — Hallazgo R9-01: fuente de balance para stops de sesión

Estado: **abierto; evidencia estática del código, sin confirmación prospectiva de exceder el stop**.

## Evidencia reproducible en `bootiq-v3-auditoria`

- `conexion.py`: en la conexión inicial, si `get_balance()` falla, `estado.balance_inicial = None`.
- `bot.py`: `balance_actual` se inicializa con el balance inicial, o `None`.
- `bot.py`: las consultas periódicas de balance ocurren solo en segundos 35 a 45, separadas por al menos 10 segundos y condicionadas además a la existencia de caché de activos u operaciones abiertas.
- `bot.py`: cuando alguno de los balances no está disponible, `ganancia_neta = 0.0`. Los dos stops solo se activan si **ambos** balances son distintos de `None`.
- `bot.py`: el procesamiento de señales pendientes está antes de la actualización del balance de mantenimiento y de las comprobaciones de stop. Las entradas directas también se procesan más adelante en el bucle.
- `operaciones.py`: `abrir_operacion` verifica autorización y paridad temporal, pero no reconsulta ni compara el balance de sesión.
- `config.py`: `MODO_CUENTA = PRACTICE`, `STOP_LOSS = -1000`, `STOP_WIN = 3000`, `MONTO_BASE = 25`. No se cambian.

## Consecuencia demostrable y límites de la evidencia

1. Si falta un balance, el mecanismo de stop dependiente de esa fuente no puede detectar un umbral alcanzado. No hay prueba de que la pérdida alcanzara realmente el umbral.
2. Si el último balance conocido es anterior a cierres de operaciones, el stop puede evaluar un valor desactualizado hasta una siguiente consulta válida. No hay medición prospectiva de la antigüedad real en los 52 cierres PRACTICE.
3. Una solución que solo añada un `continue` después de comprobar los stops **no** cubre las señales pendientes, procesadas antes. Una solución que llame `get_balance()` dentro de la ventana 0–30 puede romper la paridad temporal de envío; se descarta sin evidencia y pruebas.
4. El control de capacidad por expiración y el modo PRACTICE son controles distintos: no sustituyen el stop de sesión.

## Próxima validación de regresión antes de corregir la ejecución

- Simular balance inicial ausente con camino de señales pendientes y camino directo; verificar fallo seguro y recuperación solo tras una observación válida del broker.
- Simular fallo/transitoriedad de balance en mantenimiento y cierre en curso, sin llamadas bloqueantes durante la ventana de entrada.
- Simular reconexión y verificar coherencia del balance inicial frente al de sesión.
- Comprobar que el cambio no modifica `MAX_OPERACIONES_ABIERTAS`, TOP20, timing, expiración ni estrategia.
- Evaluar por separado la antigüedad del balance, sin confundir la falta de balance con balance desactualizado.

**Decisión actual:** no modificar código de compra ni umbrales hasta disponer de regresiones que cubran tanto pendientes como directas. Ninguna de las pruebas existentes acredita rentabilidad, 60% sostenido ni ausencia real de cruces de stop.

## Intervención puntual R9-01A — arranque sin baseline

- Commit de producción: `0a19dd4` (ajuste de importación `52bd95b`).
- `conexion.conectar()` ahora falla antes del escáner si el balance inicial no puede obtenerse o no es un valor finito/no negativo. No envía órdenes ni consulta balance dentro de la ventana crítica.
- Regresión añadida: `tests/test_balance_inicial_fase9.py`, commit `d1ddd4b`, con fallos de `get_balance`, `None`, `NaN`, negativo y lectura válida.
- **Validación automatizada local pendiente**. No declarar cierre hasta que las pruebas se ejecuten y pasen.
- La posible antigüedad del balance durante la sesión y el orden de comprobación respecto a señales pendientes permanecen **abiertos**. No se modificaron otros límites ni autorizaciones.

## Intervención puntual R9-01B — guardia antes de señales pendientes

- `riesgo_sesion.py`: evaluador puro de `STOP_LOSS` y `STOP_WIN` sobre el último balance conocido, con rechazo de balances ausentes/no finitos o negativos; no llama al broker.
- `bot.py`: ejecuta el evaluador en el bucle después de confirmar conectividad y **antes** de `procesar_senales_pendientes`. Así evita saltar los stops conocidos al procesar pendientes. Los stops originales posteriores continúan intactos para comprobar los balances recién consultados.
- `tests/test_riesgo_sesion_fase9.py`: cinco regresiones para límites, datos inválidos, ausencia de consultas al broker y orden anterior a pendientes.
- `tests/test_balance_inicial_fase9.py`: ampliada cobertura a infinito positivo y negativo.
- Limitación **abierta**: un último balance formalmente válido puede estar desactualizado respecto al broker. El guardia no detecta pérdidas posteriores a la última consulta y no certifica que el stop nunca se sobrepase. No se añadió `get_balance()` en la ventana crítica.
- **Pendiente de ejecutar**: las nuevas pruebas aisladas y toda la suite local antes de cerrar R9-01A/B.

## Validación local reportada (17-11-2026)

- Fast-forward desde `4062a85` hasta `aeb24bc` confirmado.
- `python -m unittest tests.test_balance_inicial_fase9 tests.test_riesgo_sesion_fase9 -v`: **8/8 OK**.
- `python -m unittest discover -s tests -p 'test_*.py' -q`: **436/436 OK**, 21.697 s.
- No es una prueba LIVE PRACTICE ni certifica stops de sesión bajo balance desactualizado; R9-01 sigue parcialmente abierto.

## Intervención R9-02 — defensa final de exposición

- Evidencia: `bot.py` y `entrada.py` verifican cupos/activo antes de la llamada, pero `operaciones.abrir_operacion()` enviaba la orden sin revalidar esos límites. Ambos caminos terminan en esa función.
- `operaciones.py` ahora vuelve a consultar `contar_operaciones_activas()` y `activo_con_operacion_activa()` inmediatamente antes de `estado.Iq.buy(...)` o `buy_digital_spot_v2(...)`.
- No se modifican `MAX_OPERACIONES_ABIERTAS`, `MONTO_BASE`, expiración, estrategia, stop, TOP20 ni temporización. No se introduce una llamada de balance.
- `tests/test_capacidad_gateway_fase9.py`: cinco casos de regresión para quinto cupo, duplicado de activo, ruta de protocolo, posiciones expiradas y cuarto cupo permitiendo el quinto. Utiliza mocks, no opera.
- Limitación: la revalidación no pretende garantizar atomicidad frente a múltiples hilos que llamen simultáneamente a `abrir_operacion`; el recorrido ordinario de envío del bot está secuenciado y esta modificación no introduce cerraduras en la ruta crítica.
- **Validación local de regresiones y suite pendiente**. No declarar el límite probado en runtime hasta obtener resultados.

## Validación local reportada R9-02 (17-11-2026)

- Fast-forward `aeb24bc..cb73947` confirmado en Git Bash.
- `python -m unittest tests.test_capacidad_gateway_fase9 -v`: **5/5 OK**.
- `python -m unittest discover -s tests -p 'test_*.py' -q`: **441/441 OK**, 21.556 s.
- Estos resultados confirman la regresión con mocks; no sustituyen una prueba prospectiva PRACTICE. El riesgo de balance desactualizado continúa abierto.

## Secuencia temporal observada al revisar R9-03

- `bot.main`: `revisar_operaciones_abiertas()` corre en segundos 40–44 y precede a `get_balance()` dentro del mismo ciclo, mientras que la consulta de balance se permite en segundos 35–45 con intervalo mínimo de 10 s.
- Una lectura de balance anterior a liquidar un resultado puede permanecer como última fuente conocida durante la siguiente entrada; no se puede cuantificar retraso máximo real sin trazas de tiempo y broker.
- `riesgo_sesion.motivo_bloqueo_sesion` no afirma que la observación sea fresca: evalúa stops sobre la última observación válida. Ningún nuevo umbral de antigüedad está autorizado con la evidencia actual.
- **Decisión:** no modificar los stops, el calendario de llamadas a `get_balance` ni el calendario de cierre; obtener primero datos de antigüedad y comprobar si las consultas realmente quedan retrasadas. No declarar la fase 9 cerrada por 441 pruebas.

## Intervención R9-03 — antigüedad observada (solo sombra)

- `riesgo_sesion.antiguedad_observacion_balance()` calcula una edad desde timestamps monotónicos, devuelve `None` si faltan valores o son inválidos y no consulta al broker.
- `bot.main` inicia la referencia monotónica tras el arranque con balance conocido y la actualiza solo tras lecturas de balance válidas. No se actualiza si el request lanza excepción o entrega `None`.
- Antes de procesar pendientes, se emite una línea `R9-03 SOMBRA ANTIGUEDAD BALANCE` como máximo una vez por bucket de 60 segundos monotónicos. La etiqueta `SIN_LECTURA` significa que no existe una observación aceptable.
- Esta edad representa **antigüedad de la respuesta recibida**, no la fecha de liquidación contable ni el instante en que el broker hizo efectivo un cierre. Tampoco refleja garantías de frescura del backend.
- No se agregaron umbrales de frescura, stops nuevos ni llamadas `get_balance`; no se modificaron autorización, secuencia de cierres, ventanas críticas ni límites de exposición.
- `tests/test_antiguedad_balance_fase9.py` agrega cuatro pruebas (valor monotónico, valores inválidos, orden de telemetría anterior a pendientes y aceptación únicamente de respuestas válidas).
- **Pruebas locales todavía pendientes**: última suite confirmada 441 OK. No extrapolar a capacidad de reacción del Stop Loss antes de la próxima entrada ni a desempeño PRACTICE.

## R9-03B — lectura no finita en el mismo ciclo

- Causa: la protección original en `bot.main` se ejecutaba antes de la consulta de mantenimiento. Si esta devolvía `NaN` o `Inf`, se asignaba a `balance_actual` y las comparaciones de los stops con `NaN` no activaban el bloqueo durante esa misma vuelta, mientras el bucle todavía podía llegar a entradas directas.
- Corrección: una comprobación sin llamadas al broker después de la consulta de mantenimiento detiene la vuelta con `break` si el balance es negativo o no finito; aplica antes de recorrer señales directas.
- Prueba agregada a `tests/test_antiguedad_balance_fase9.py`: asegura la posición de esta defensa en el recorrido y comprueba la condición numérica. No representa una prueba completa de extremo a extremo con el broker.
- R9-03 sigue abierto para observaciones de antigüedad en PRACTICE; esta defensa no garantiza frescura del último balance válido.
- **Estado de validación:** cambios de código y regresiones subidos, suite local pendiente. Última suite confirmada: 441/441.

## R9-03C — respuesta vacía de balance

- Evidencia de código: `estado.Iq.get_balance()` puede devolver `None`; en ese caso `balance_actual` conserva la lectura previa y no se reinicia el reloj de observación.
- Se añadió **solo telemetría** `R9-03 SOMBRA CONSULTA BALANCE SIN RESPUESTA` cuando se recibe `None`, diferenciando silencio del broker y una observación válida. No se alteran la frecuencia de consultas, la ventana ni la autorización.
- Regresión adicional en `tests/test_antiguedad_balance_fase9.py`. **Última suite local confirmada 441 OK; seis pruebas nuevas de R9-03 pendientes de ejecución.**
- Las lecturas con excepción ya eran visibles por `No se pudo actualizar balance`. La antigüedad sigue siendo de la última respuesta recibida, no de la liquidación contable.

## Validación local de R9-03 (17-11-2026)

- `git pull --ff-only origin bootiq-v3-auditoria` actualizó `32ac6e2..3457af1` mediante fast-forward.
- `python -m unittest tests.test_antiguedad_balance_fase9 -v`: **6/6 OK**, 0.008 s.
- `python -m unittest discover -s tests -p 'test_*.py' -q`: **447/447 OK**, 21.787 s.
- La corrección de la prueba `test_telemetria_antes_de_pendientes_y_sin_veto_por_edad` evitó detectar como veto el operador ternario usado para imprimir la edad.
- Esto valida regresiones unitarias y estructurales, **no** una medición LIVE PRACTICE de antigüedad real ni el cumplimiento prospectivo del stop bajo fallos del broker. El hallazgo R9-03 permanece abierto a esa evidencia.

## R9-04 — cronología cierre conciliado y balance (sombra)

- En `operaciones.revisar_operaciones_abiertas`, después de persistir con éxito el cierre de una orden, se marca `estado.ultima_conciliacion_cierre_monotonic` y se imprime `R9-04 SOMBRA CIERRE CONCILIADO` con el `order_id`. El control de cierre existente no se altera.
- En el reporte de balance, como máximo una vez por minuto, `bot.main` muestra `R9-04 SOMBRA SECUENCIA CIERRE BALANCE` y clasifica si la última respuesta válida al balance fue antes o después de la última conciliación, sin hacer llamadas extra.
- `riesgo_sesion.secuencia_balance_tras_cierre` es una función pura. El resultado `RESPUESTA_BALANCE_POSTERIOR_AL_CIERRE` **no acredita** que IQ Option haya contabilizado el resultado; únicamente compara horas locales de los eventos.
- `tests/test_secuencia_balance_cierre_fase9.py`: cuatro pruebas unitarias/estructurales, sin operaciones ni red.
- No se modificaron stops, TOP20, estrategia, límite de cinco posiciones, monto, expiración ni horario de llamadas a IQ. Aún no se ha demostrado frescura contable del broker.
- **Validación local pendiente**; la última suite ejecutada y aprobada fue de 447 pruebas.

## Validación local R9-04 (17-11-2026)

- Fast-forward `3457af1..6eab92d` confirmado.
- `python -m unittest tests.test_secuencia_balance_cierre_fase9 -v`: **4/4 OK**, 0.006 s.
- `python -m unittest discover -s tests -p 'test_*.py' -q`: **451/451 OK**, 21.341 s.
- Se observó `R9-04 SOMBRA CIERRE CONCILIADO` en un test simulado; **no prueba conciliación de IQ real**.
- Próxima evidencia requerida: sesión `python bot.py` con cuenta PRACTICE confirmada; examinar R9-03/R9-04 y relación entre cierre persistido, respuesta balance y nueva entrada. El hallazgo no se declara cerrado todavía.
