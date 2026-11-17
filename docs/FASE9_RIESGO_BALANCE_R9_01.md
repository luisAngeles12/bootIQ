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
