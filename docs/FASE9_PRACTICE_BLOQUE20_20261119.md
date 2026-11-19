# Fase 9 — evidencia PRACTICE, bloque 20 del 19-11-2026

Fuente: registro local proporcionado por usuario, `Texto pegado(20261119-164202).txt`, 7,997 líneas. **Extracto de una ejecución**, empieza dentro del análisis, no desde el arranque. Archivo del informe producido por el bot: `reportes_bloques_20_practice/bloque20_20261119T143229263020Z.json` (su contenido no fue aportado; no atribuir sus 20 filas a los tres cierres visibles).

## Resultado oficial del bloque según mensaje BLOQUE20 RESULTADO

- 20 órdenes; 10 WIN, 10 LOSS, 0 empate.
- Winrate 50.0%; neto -41.25 unidades de balance; expectativa -2.0625/orden; ganancia media 20.88, pérdida media 25.00; profit factor 0.835; `positivo: false`.
- Meta prospectiva >=60% *y* neto positivo **no alcanzada**. Este bloque tampoco demuestra un 60% constante en ventanas de 20.

## Observaciones en el extracto

- 177 líneas `STEP7 V3 FUENTES` reportaron `SIN_DATOS_ESTADISTICOS`, prior 49.25 y `muestra:0` con principal/respaldo `n:0`; cada registro es una evaluación, **no una orden distinta ni una prueba de memoria global vacía**.
- Se identifican **tres** aperturas visibles autorizadas por `BOOTSTRAP_PRACTICE_SIN_HISTORIAL`: XPDUSD-OTC PUT (id 14466550529, +20.75); EOSUSD-OTC CALL (14466570538, -25); FWONA-OTC PUT (14466572978, -25). La suma de estos tres cierres es -29.25; los otros 17 resultados del bloque requieren el JSON oficial para ser atribuidos.
- Después de la conciliación de XPDUSD, aparecen dos reportes `R9-04 SOMBRA SECUENCIA CIERRE BALANCE: BALANCE_ANTERIOR_AL_CIERRE`, con edades del balance de **58.562 s y 89.969 s**. El balance mostrado en ese punto es 8664.75 con neto -37, mientras que el cierre observado era +20.75. La consulta posterior a 39 s se observa, pero una marca de lectura posterior no certifica reflejo contable del cierre.
- Se observan 41 líneas de edad del balance, 41 de timing de balance, tres eventos de conciliación R9-04 y 14 avisos `get_candles sin respuesta`. También se ven problemas de websocket/reconexión; no atribuir el rendimiento negativo a ellos sin vinculación por order_id.
- Hay operaciones con segundo de entrada 9 y duración de envío ~0.265–0.296 s. No hay evidencia de entrada fuera de ventana en los tres casos visibles.
- El bloqueo de mercados clasificados SUCIO sigue apareciendo; **no relajar**.
- El proceso reporta `BLOQUE_20_CERRADO` y finaliza; no proponer una continuación operativa automática del bloque fallido.

## Causa identificable y causa aún no demostrada

- `motor_aprendizaje_historico.py`: usa `BOOTIQ_RUTA_APRENDIZAJE` o `aprendizaje_historico_bootiq_F4_CC2.csv`; la principal exige al menos `MIN_MUESTRA_APORTE=5` y según nivel `MIN_MUESTRA_CONFIABLE=12` / 20. `SIN_DATOS_ESTADISTICOS` por señal puede corresponder a claves ausentes, muestras insuficientes, filtros de confianza u otras razones. **No está probado** que el archivo de memoria falte o se haya cargado vacío.
- `bootstrap_practice.py` habilita una excepción estrictamente PRACTICE si la decisión oficial era NO_OPERAR por ausencia de fuente, con filtros estructurales; los tres trades visibles muestran esa autoridad, pero **no se puede afirmar** que sea responsable del neto de todo el bloque.
- No hay evidencia suficiente para modificar estrategia, thresholds, TOP20, límites de exposición, vencimientos, veto SUCIO/CAOTICO o habilitar operaciones REAL.

## Próxima acción con criterio de evidencia

1. Auditar el JSON del bloque y las filas de historial correspondientes por `order_id`/fuente de autorización; separar las 20 órdenes y medir ganancias/pérdidas por bootstrap y por otras autoridades.
2. Verificar archivo efectivo de memoria y desglose `_buscar_fuentes_aprendizaje` por nivel/clave: SIN_DATOS, MUESTRA_INSUFICIENTE y fuentes sin autoridad OOS; investigar antes de cambiar el permiso bootstrap.
3. Vincular orden/cierre/balance con trazas de tiempo, preservando la distinción entre tiempo local y liquidación del broker.
4. Solo ante causa identificada: corrección mínima, regresiones, OOS independiente y siguiente bloque PRACTICE; no optimizar a posteriori sobre este bloque sin validación externa.

**Estado:** fase 9 abierta; 451/451 pruebas unitarias previas OK, pero bloque prospectivo 20 negativo. Sin cambios productivos por esta evidencia.

## Herramienta de diagnóstico agregada (sin modificar trading)

- `scripts/diagnostico_fuentes_fase9.py`: acepta el JSON del bloque como argumento y localiza una lista de operaciones identificadas por `order_id` (o equivalente); lista claves y cuenta autoridades/resultados solo cuando esos campos están presentes. No infiere causas si el formato no los contiene.
- También inspecciona el CSV que `motor_aprendizaje_historico.py` usa por defecto (`BOOTIQ_RUTA_APRENDIZAJE` o `aprendizaje_historico_bootiq_F4_CC2.csv`) y cuenta filas con `total >= 5/12/20`, sin modificar la memoria ni sustituir la comprobación de claves generadas por cada señal.
- `tests/test_diagnostico_fuentes_fase9.py`: cinco regresiones con datos sintéticos, incluida invariancia de bytes del CSV.
- Esta herramienta **no autoriza operaciones**, no entra en `bot.py` y no altera aprendizaje, estrategias ni los filtros. Si el JSON contiene únicamente agregados, se reporta `ruta_registros: null`, no un desglose imaginario.
- **Pruebas pendientes**: última suite 451/451. No afirmar 456/456 hasta tener salida local.

## R9-05 — diagnóstico del JSON oficial y suspensión de bootstrap (19-11-2026)

Salida local: `python scripts/diagnostico_fuentes_fase9.py reportes_bloques_20_practice/bloque20_20261119T143229263020Z.json`.

- **Suite previa confirmada: 619/619 OK (22.606 s)**. Cinco pruebas específicas del diagnóstico OK. Este número sustituye al último recuento documentado de 451, pero no representa un winrate.
- El JSON contiene exactamente 20 órdenes bajo `raiz.operaciones`; las 20 tienen `origen_autoridad = BOOTSTRAP_PRACTICE_SIN_HISTORIAL`. Resultados crudos: diez `-25.0`, ocho `20.75`, un `21.25` y un `21.5`. Total -41.25, 50% de WIN. En particular, este bloque **no contiene autorizaciones V3 con fuente estadística válida**.
- El diagnóstico encontró `aprendizaje_historico_bootiq_F4_CC2.csv` **inexistente** en el directorio y configuración efectivos de la ejecución del diagnóstico. No se puede atribuir a una memoria V3 válida el resultado del bloque ni asumir que exista alguna otra fuente aprobada hasta inspeccionar su procedencia.
- Causa operacional comprobada: el permiso excepcional sin fuente V3 ejecutó todo el bloque, y **la muestra prospectiva de esta excepción fue no rentable**. Esto no demuestra por sí solo que cada subfamilia del bootstrap sea mala ni predice su rendimiento futuro.
- Medida conservadora reversible: `config.PERMITIR_BOOTSTRAP_SIN_MEMORIA=False`; `bootstrap_practice.habilitable_sin_memoria()` retorna `False` sin evaluar ni autorizar una entrada cuando el permiso está desactivado. No afecta las decisiones con autorización V3 válida, stops, TOP20, expiraciones ni vetos SUCIO/CAOTICO.
- En `tests/test_bootstrap_practice.py`, la matriz estructural previa sigue probándose solo con habilitación explícita de bootstrap, y se añade regresión para confirmar veto del modo suspendido.
- **Pruebas de este nuevo cambio pendientes**. La suite confirmada de 619 pruebas es anterior a R9-05. El objetivo no es crear artificialmente un 60% reduciendo entradas a cero; para volver a operar con evidencia, hace falta construir/validar la memoria TRAIN y su rendimiento OOS independiente, luego correr PRACTICE nuevo.
- No activar bootstrap simplemente para obtener frecuencia; tampoco entrenar y evaluar sobre los mismos 20 resultados, ni declarar el 60% estable por un bloque favorable.
