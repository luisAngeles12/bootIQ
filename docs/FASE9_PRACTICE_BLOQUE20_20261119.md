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

## R9-05 regresión posterior a suspensión

- Salida local reportada: 11/11 pruebas de `tests.test_bootstrap_practice` OK; la suite general corrió 620 casos y **falló 3**, todos en fixtures legados de `test_bootstrap_price_action_context` y `test_integracion_bootstrap_memoria_fase8` que esperaban la excepción sin activarla.
- Corrección limitada a tests: ambas clases habilitan el modo bootstrap explícitamente en `setUp` para conservar la cobertura de reglas estructurales y la integración histórica; el valor productivo `PERMITIR_BOOTSTRAP_SIN_MEMORIA=False` **no se cambia**.
- Regresión nueva: `test_r9_suspension_default_no_autoriza_a_traves_de_cerebro`, que demuestra el veto con el Cerebro unificado cuando el permiso se desactiva.
- **La nueva suite estimada es de 621 pruebas; ejecución local pendiente.** No declarar reparación confirmada antes de la salida completa.

## Validación R9-05 completada — 19-11-2026

- Fast-forward `0716a48..56e2274` confirmado por el usuario.
- `python -m unittest discover -s tests -p 'test_*.py' -q`: **621 pruebas, OK, 21.478 segundos**, cero fallos.
- Se confirma que las tres regresiones de fixtures anteriores se resolvieron con opt-in exclusivamente dentro de pruebas y que el modo productivo de bootstrap permanece desactivado por defecto.
- Las líneas `BLOQUE20 RESULTADO` de 60% en la salida corresponden a **fixtures de test** ejecutados dentro de la suite y no constituyen un nuevo bloque prospectivo de IQ Option.
- Próxima tarea: inventario local de insumos históricos y evaluación TRAIN/OOS; **no crear memoria de producción a partir de datos sin procedencia temporal validada**.

## R9-06 — inventario de insumos históricos sin modificar datos

- Tras las 621 regresiones aprobadas, se añadió `scripts/inventario_insumos_memoria_fase9.py` para inventariar únicamente nombre relativo, tamaño y columnas de CSV locales de historial, aprendizaje, resultados y ledger; omite `venv`, `.git` y dependencias, no importa `bot.py`, no modifica archivos ni consulta IQ.
- Reporta además si existe la ruta efectiva de memoria según `BOOTIQ_RUTA_APRENDIZAJE` / valor por defecto. **No construye memoria nueva** ni hace TRAIN/OOS con datos no verificados.
- Tres pruebas adicionales en `tests/test_inventario_insumos_memoria_fase9.py` comprueban invariancia de archivos, omisión de `venv` y detección de memoria por ruta configurada.
- **Pendiente ejecutar** las tres pruebas y la suite general (se esperan 624 casos); la única suite confirmada hasta ahora es 621 OK. Después, revisar inventario local y seleccionar fuente temporal validada.

## R9-06 confirmado y R9-07 en preparación (19-11-2026)

- Pull confirmado hasta `50958dd`; 3/3 regresiones de inventario y **624/624 pruebas generales OK (22.184 s)**.
- Inventario local efectivo: **solo un CSV coincidente con los patrones**, `historial_bot.csv`, de **1,046,685 bytes**. Posee `fecha`, `estado_operacion`, `order_id`, `resultado`, `modo_cuenta_configurado`, `origen_autoridad` y más columnas útiles para auditar procedencia.
- `aprendizaje_historico_bootiq_F4_CC2.csv` no existe en la ruta configurada al ejecutar el inventario. Los archivos en carpetas temporales generados por tests no representan una memoria productiva aprobada.
- Se incorpora `scripts/auditar_historial_fase9.py` para contar el universo por modo, estado, etiqueta, autoridad, repetición de `order_id` y disponibilidad de fechas. Las candidatas preliminares exigen `PRACTICE`, `order_id`, estado no pendiente y etiqueta `WIN/LOSS` sin transformar PNL numérico en resultado.
- El diagnóstico **no es generación automática de memoria** y no promete que los IDs pertenezcan a ejecuciones verificadas del broker. Duplicaciones (por ejemplo apertura+cierre de una misma orden) serán examinadas antes de deduplicar y separar TRAIN/OOS.
- Se agregaron 3 pruebas unitarias; suite estimada **627**. Aún sin nueva ejecución local. Bootstrap sigue desactivado; REAL no se habilita.

## R9-07 — auditoría local ejecutada y ampliación R9-08

- `git pull --ff-only` alcanzó `899bced`. Las 3 pruebas de auditoría y la suite completa dieron **627/627 OK, 22.059 s**.
- El `historial_bot.csv` contiene **580 filas**, 580 `order_id` distintos (0 duplicados), y todas tienen `estado_operacion=OPERADA_DIRECTA` y `origen_autoridad=BOOTSTRAP_PRACTICE_SIN_HISTORIAL`. **149** tienen modo `PRACTICE` explícito; **431** tienen modo ausente y no deben etiquetarse como PRACTICE por suposición.
- La columna `resultado` contiene **PNL monetario**, no etiquetas `WIN/LOSS`: -25.0 (291), 0.0 (4), 20.5 (5), 20.75 (240), 21.0 (2), 21.25 (1), 21.5 (11), 21.75 (26). Los 580 registros no son por sí mismos una muestra validada; en particular, las filas sin modo siguen sin procedencia suficiente.
- El diagnóstico anterior devolvió 0 candidatas porque evaluaba solo `WIN/LOSS` y fechas numéricas. `historial.actualizar_historial_cierre()` escribe `estado=CERRADA` y resultado numérico finito. Por ello, el diagnóstico ahora informa **por separado** estado de cierre explícito, PNL finito y formato ISO de la fecha, sin reinterpretar datos ni entrenar.
- Se introdujeron tres pruebas adicionales: fechas ISO y PNL, `estado=CERRADA` frente a apertura, y tratamiento de PNL no finito y modo sin verificar.
- **Pendiente ejecución** de las nuevas pruebas (se esperan 630 generales), así como confirmación de la columna `estado` y las fechas reales. Solo después estudiar transformación de resultados **auditados** a etiquetas, desduplicación temporal y TRAIN/OOS.
- No se cambió `historial.py`, `motor_aprendizaje_historico.py`, la estrategia ni el permiso de trading; bootstrap permanece desactivado por defecto y REAL prohibido.

## R9-08 CI verificado directamente por GitHub Actions

- Workflow `BootIQ - auditoria integral fases 5-12 SIN BROKER`: https://github.com/luisAngeles12/bootIQ/actions/runs/44578840527
- Commit de código `b178647361e5000d2abdac4e161d7f268e768c6e`; job `full-unittest`: **success**, 630/630 pruebas de toda la suite (10.058 s), más 3/3 pruebas de régimen (0.014 s). Compilación sintáctica del árbol versionado correcta.
- Último commit `d86a65a7c4507c8cdcee1cb998b8b5e96c08225c` cambió solo documentación; no modificó código probado.
- Desde ahora, consultar GitHub Actions directamente y no pedir ejecuciones locales para la suite replicable en CI. Para archivos locales no versionados (p. ej. `historial_bot.csv`) aún se requiere evidencia local o archivo aportado, sin afirmar pruebas que CI no puede ejecutar con esos datos.

## R9-09 — filtro estrictamente diagnóstico para secuencia TRAIN/OOS

- Se implementó clasificación en `scripts/auditar_historial_fase9.py` que reporta candidatas **preliminares** solo con modo PRACTICE explícito, `order_id`, `estado=CERRADA/CERRADO`, PNL finito de signo no cero y `fecha` ISO 8601 con offset. Se cuentan motivos de exclusión por separado; fechas sin offset **no se convierten silenciosamente** a UTC.
- Dos pruebas nuevas cubren offset `-04:00` / `Z`, empate, apertura, ausencia de modo y fecha sin zona.
- Commit de pruebas `f799d03e08bd7da831c712a838d94e009a662776`; GitHub Actions `44579835641`: **632/632 OK** (6.997 s), más 3/3 de auditoría de régimen, sintaxis OK, sin broker.
- El historial local de 580 filas no está en GitHub ni disponible para GitHub Actions: no afirmar cantidad de candidatas R9-09 para ese historial hasta evaluarlo directamente. Tampoco confundir candidatas preliminares con órdenes broker-verificadas ni con memoria lista para producción.
- Bootstrap desactivado por defecto, PRACTICE exclusivamente, no se modifica estrategia, timing, TOP20, stops ni expiración.

## R9-10 — corte temporal TRAIN/OOS de solo lectura (CI validado)

- Se añadió `scripts/auditar_particion_temporal_fase9.py` para auditar el posible corte TRAIN/OOS sobre cierres PRACTICE con modo explícito, estado de cierre, `order_id` único globalmente, PNL finito no cero y fecha ISO con offset. El diagnóstico rechaza por completo los IDs duplicados, cualquiera que sea su modo, y cuenta exclusiones.
- No divide órdenes con el mismo instante UTC. Exige por defecto al menos 20 registros para TRAIN y 20 OOS, y aproxima 70%/30% solo cuando respeta esos mínimos. La evaluación aún **no** se ejecuta y los resultados de la partición no constituyen validación prospectiva.
- `tests/test_auditar_particion_temporal_fase9.py` incorpora seis pruebas sintéticas sobre orden temporal, simultaneidad, duplicados, modos/estados/resultados excluidos, columnas faltantes y ausencia de corte.
- **Validación automática completada:** GitHub Actions `44581371569`, commit `36e8d47a596e434fb875a1a422efcfd921f766f1`: 638/638 pruebas generales OK (9.226 s), 3/3 pruebas de régimen OK (0.011 s), sintaxis correcta; sin iniciar `bot.py` ni conectar broker.
- `historial_bot.csv` real continúa siendo exclusivamente local. No afirmar conteos de partición real antes de inspeccionarlo. El historial previamente auditado contiene 580 filas, de las cuales 431 no tienen modo de cuenta explícito. No imputar esas filas a PRACTICE ni derivar de ellas un winrate operativo verificado.
- Bootstrap sigue desactivado por defecto. Sin cambios a estrategia, límites, TOP20, temporalidad crítica o modo REAL.

## R9-11 — precisión temporal: `fecha` de apertura sin zona

- Revisión causal en `operaciones.py`: `guardar_historial` persiste `fecha=datetime.now().strftime("%Y-%m-%d %H:%M:%S")` **al abrir la orden**, sin offset de zona. `historial.actualizar_historial_cierre()` actualiza `estado=CERRADA` y `resultado`, pero **no registra una marca de cierre conciliado** en esa columna. `tiempo_expiracion` es una configuración, no prueba del momento de liquidación. Por tanto, `fecha` NO debe describirse como instante probado de cierre, y un corte por aperturas no excluye solapamiento de resultados entre TRAIN y OOS.
- Se modificó **solo el auditor** `scripts/auditar_particion_temporal_fase9.py` para informar `fecha_columna_semantica=APERTURA_LOCAL_SIN_ZONA_SEGUN_OPERACIONES_PY`, `cierre_temporal_verificado=false` y `apto_para_memoria_productiva=false`. Se añadió `--offset-origen-minutos` opcional para evaluar una **hipótesis explícita** de zona al interpretar aperturas antiguas; no cambia archivos ni la configuración de zona del bot y no confirma la zona real.
- En modo predeterminado estricto las fechas sin offset siguen excluyéndose. En ambos modos, la salida de partición sigue siendo **PRELIMINAR_NO_VERIFICADO_IQ**, sin permiso de generación o despliegue de memoria.
- Se agregaron tres pruebas de fechas locales, offset inválido y fecha con zona real preservada.
- **CI comprobada directamente:** GitHub Actions https://github.com/luisAngeles12/bootIQ/actions/runs/44582407876 en commit `5734f4ab7d3319bcdf1593f11274d29b3260052d`: **641/641 pruebas generales OK** (8.298 s), 3/3 adicionales de régimen (0.010 s), sintaxis OK. No conecta IQ Option.
- **Próximo requisito:** para afirmar separación libre de leakage debe existir y auditarse una marca fiable de cierre/conciliación de cada order_id y la procedencia del modo PRACTICE. El CSV actual no incorpora fecha de cierre dedicada. No derivar cierre fiable sumando simplemente duración teórica a `fecha`.
