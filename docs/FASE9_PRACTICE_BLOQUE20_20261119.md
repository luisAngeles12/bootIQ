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
