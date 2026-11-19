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

## R9-12 — marca UTC del resultado conciliado y persistido (19-11-2026)

- Causa: el campo `fecha` se asigna al abrir la operación, sin huso horario; la función de cierre solo actualizaba `estado` y `resultado`. No existía marca inequívoca de observación local del resultado ya disponible para persistencia.
- Cambio mínimo: añadir `fecha_conciliacion_local_utc` a `COLUMNAS_HISTORIAL`, capturada con `datetime.now(timezone.utc).isoformat()` durante `actualizar_historial_cierre` e incluida en el **mismo archivo temporal y reemplazo atómico** del resultado. Si falla `os.replace`, se preserva el archivo original y la orden sigue pendiente de persistencia como antes.
- La marca solo se escribe cuando la columna está presente; se preserva compatibilidad con archivos legados no migrados. Reintentos con marca existente no la sobrescriben. La inicialización del esquema al arrancar lleva la columna a CSV existentes y deja vacías las marcas históricas que **no pueden reconstruirse**.
- Semántica estricta: timestamp **del sistema local, cercano a la persistencia**, no hora de expiración ni prueba de liquidación contable del broker; tampoco se confunde con el `time.monotonic()` en memoria usado por R9-04.
- Validación: pruebas nuevas para aislamiento por `order_id`, UTC explícito, persistencia atómica fallida e historial legado. GitHub Actions [ejecución 44583076993](https://github.com/luisAngeles12/bootIQ/actions/runs/44583076993), código `44f84bcb9e7e91224d44dd4d1c712a085a6c4012`: **644/644 pruebas generales OK** (7.874 s), **3/3** régimen OK, **335** fuentes Python compiladas. CI sin broker.
- No se alteran estrategias, thresholds, TOP20, autorización bootstrap (sigue desactivado), mercados SUCIO/CAÓTICO, balance, límites, expiración, segundo de entrada ni cuenta (PRACTICE exclusivamente).
- Pendiente: validar orden temporal **fin TRAIN (conciliación local)** anterior a **inicio OOS (apertura)** con evidencia de sesiones/horarios y contraste real por `order_id`. Los registros históricos previos al campo no adquieren una fecha ficticia. No activar memoria productiva aún.

## R9-13 — verificación cronológica local: cierre TRAIN antes de apertura OOS

- Causa: R9-10 elegía un corte entre horas de apertura, pero desconocía si las etiquetas de resultados TRAIN ya estaban disponibles cuando comenzaba OOS. La marca `fecha_conciliacion_local_utc` añadida en R9-12 permite comprobar esa secuencia para nuevas órdenes, **sin afirmar una hora de liquidación broker**.
- El auditor `scripts/auditar_particion_temporal_fase9.py` ahora lee opcionalmente esa columna y presenta, de forma read-only, `separacion_local_sin_fuga`, cantidad de resultados TRAIN sin marca, cierres TRAIN iguales o posteriores al inicio OOS, máximo cierre TRAIN local y fechas inválidas/anteriores a apertura. La desigualdad es estricta: `ultimo_cierre_train_local_utc < inicio_oos_utc`.
- La nueva condición falla cerrada si falta alguna marca TRAIN, existe conflicto cronológico o se asumió la zona horaria de aperturas. En todo caso `apto_para_memoria_productiva=false` y `estado=PRELIMINAR_NO_VERIFICADO_IQ`: el control local de no-leakage **no confirma** por sí solo las etiquetas del broker ni autoriza entrenar o desplegar.
- Cinco pruebas nuevas: TRAIN anterior a OOS; cierre igual a primera apertura OOS; marcas de cierre ausentes; marcas inválidas o anteriores a apertura; offset supuesto que no puede certificar.
- CI verificada directamente: GitHub Actions https://github.com/luisAngeles12/bootIQ/actions/runs/44586352076 con commit `576b78875a52d670c6767050ae5550cd9a42efa9`: **649/649 pruebas generales OK (10.180 s)**, 3/3 régimen OK, 335 archivos Python con sintaxis OK, sin broker.
- Pendiente: validación de la fuente real `historial_bot.csv`, conciliación IQ por `order_id`, y medición de rentabilidad OOS con muestras independientes. No permitir REAL ni reactivar el bootstrap sin memoria.

## R9-14 — métricas OOS descriptivas y consistencia por bloques de 20

- Se creó `scripts/evaluar_oos_descriptivo_fase9.py`, de **solo lectura**. Reutiliza el corte de R9-13 y **no emite métricas** si falla `separacion_local_sin_fuga`. También rechaza los resultados OOS sin marca UTC de conciliación o cuya marca precede a la apertura.
- Sobre filas PRACTICE cerradas con importe numérico finito no nulo, reporta bloques completos no solapados de 20 y ventanas móviles de 20: WIN/LOSS por signo del PNL, tasa de acierto, neto, expectativa y profit factor. Exige simultáneamente **al menos 12 WIN en 20 y neto positivo** por ventana. No convierte los resultados en memoria ni analiza señales hipotéticas como ejecuciones reales.
- Distingue explícitamente `DESCRIPTIVO_HISTORICO_NO_VALIDA_POLITICA_V3`: las observaciones se produjeron con la política histórica (por ejemplo bootstrap), por lo que una evaluación descriptiva posterior al corte **no equivale a probar una estrategia V3 entrenada en TRAIN ni demuestra selección contrafactual de operaciones**.
- Añadidas seis pruebas sintéticas sobre ventanas positivas, 60% con neto negativo, leakage de TRAIN, ausencia de cierre OOS, tamaño insuficiente y ventanas móviles.
- Evidencia GitHub Actions https://github.com/luisAngeles12/bootIQ/actions/runs/44587219365, commit de código `91d00575d70f54f7e7ba300b3a2afc1bafb9e10e`: **655/655 pruebas generales OK (9.314 s)**, 3/3 pruebas de régimen OK (0.011 s), 337 archivos Python con sintaxis correcta. Sin conexión al broker.
- El historial local todavía no fue aportado y no está versionado; la herramienta no se ha corrido sobre las 580 filas reales. El 60% consistente con neto positivo sigue **NO DEMOSTRADO**. Bootstrap sin memoria sigue suspendido y REAL prohibido.

## R9-14 — timestamp UTC del registro de apertura, sin cambios de trading

- `operaciones.py` ahora escribe `fecha_apertura_registro_local_utc = datetime.now(timezone.utc).isoformat()` junto al registro original `fecha` de apertura; la nueva marca se toma en el momento de persistencia, no es fill del broker. El campo se añadió a `historial.COLUMNAS_HISTORIAL`. La fecha antigua se conserva sin convertirla ni reescribir registros previos.
- `scripts/auditar_particion_temporal_fase9.py` prioriza la marca nueva cuando existe, contabiliza aperturas UTC explícitas versus `fecha` legacy, y falla cerrada si la marca explícita resulta inválida o carece de huso horario. `--offset-origen-minutos` solo afecta fechas legacy sin zona, nunca marcas UTC explícitas.
- Tres pruebas nuevas verifican prioridad, prohibición de fallback silencioso y que la marca está en la telemetría del registro de apertura.
- **GitHub Actions verificado**: https://github.com/luisAngeles12/bootIQ/actions/runs/44587290025 en commit `54ad1cb7598ecb33fbb27ecf9f4ca8ba98379032`, suite **658/658 OK** (9.280 s), 3/3 regresiones de régimen OK, sintaxis de 337 fuentes Python OK. No conecta al broker.
- Se mantiene `apto_para_memoria_productiva=false`, no se confirma cierre real del broker ni la rentabilidad del 60%. Cuenta PRACTICE únicamente, bootstrap sin memoria bloqueado.

## R9-15 — conciliación offline por `order_id` con exportación independiente de IQ

- Se añadió `scripts/conciliar_exportacion_iq_fase9.py`, herramienta **offline y de solo lectura** para cotejar `historial_bot.csv` contra una exportación independiente del broker **previamente normalizada** a las columnas exactas `order_id,modo_cuenta,estado,pnl,fecha_cierre_utc`. La exportación no está incluida en el repositorio ni disponible en CI; el script no obtiene credenciales ni llama IQ.
- Requiere `order_id` único en cada archivo, cierre explícito, modo `PRACTICE` en ambos, mismo PNL al centavo sin redondeo automático, hora de cierre con offset y marca local de conciliación posterior o igual a la del broker. Rechaza duplicaciones, datos numéricos no finitos, archivos malformados, timestamps ambiguos y comparación de un archivo consigo mismo. No borra ni corrige filas del usuario.
- El estado `COINCIDENCIAS_OFFLINE_NO_CERTIFICADAS` **no verifica la procedencia externa del archivo aportado**, el broker en línea, la exactitud del corte TRAIN/OOS, la memoria V3 ni la rentabilidad. Contadores de conciliación son **preliminares**, no afirmaciones de órdenes verificadas por conexión.
- Pruebas nuevas: cotejo determinista de PNL, cuentas REAL, IDs duplicados, horas invertidas, cierres ausentes, ordenes extras, fichero propio y esquemas incompletos; y rechazos adicionales de fracciones de centavo, NaN e infinito.
- **CI ejecutada por GitHub Actions**, commit `00c4e65442b6e892e0803d3de65f55cd7ebbea16`, [workflow 44588634564](https://github.com/luisAngeles12/bootIQ/actions/runs/44588634564): **669/669 tests generales OK** (11.015 s); **3/3 tests de régimen** (0.014 s); **339 archivos Python** sintácticamente correctos.
- No se ha conectado el bot ni lanzado operaciones; la cuenta REAL sigue prohibida y `PERMITIR_BOOTSTRAP_SIN_MEMORIA=False`. Requiere la exportación independiente y el historial local para cotejar órdenes efectivas, y medición TRAIN/OOS real posterior antes de cualquier cambio de autoridad.

## R9-16 — mismo universo OOS en el corte temporal, el informe y el cotejo offline

- Causa comprobada: `scripts/evaluar_oos_descriptivo_fase9.py` seguía leyendo `fecha` legacy, incluso cuando `scripts/auditar_particion_temporal_fase9.py` ya priorizaba `fecha_apertura_registro_local_utc`. Esto podía introducir disparidad entre la población que pasó el corte y la realmente evaluada.
- Corrección: el evaluador descriptivo OOS prioriza la marca UTC explícita; si está presente pero corrupta o sin offset, devuelve `NO_APTO`, sin recuperar silenciosamente la fecha legacy. Dos pruebas cubren precedencia y marca inválida.
- El comparador offline `conciliar_exportacion()` acepta ahora `ids_objetivo` para cotejar exclusivamente el conjunto OOS determinado por el evaluador, conservando identificadores textuales y exclusión de duplicados. Informa si el universo objetivo está conciliado por completo, sin afirmar validación en línea del broker.
- `evaluar_oos(..., exportacion_iq=...)` opcionalmente exige que **todas** las órdenes OOS observadas coincidan en el export normalizado (modo PRACTICE, cierre, PNL al centavo y secuencia temporal). Si falta alguna o hay discrepancias, retorna `NO_APTO / OOS_DIFIERE_BROKER_OFFLINE` y **no emite métricas del tramo**. Cuando coinciden, las métricas siguen expresamente **descriptivas y no certificadas**, porque el CSV de exportación no demuestra su procedencia independiente y no valida una política V3 entrenada.
- Tres pruebas nuevas cubren cotejo íntegro, diferencia de PNL y ausencia de una orden OOS. Las pruebas usan fixtures sintéticos que no representan resultados PRACTICE reales.
- Evidencia CI comprobada: [GitHub Actions 44590239031](https://github.com/luisAngeles12/bootIQ/actions/runs/44590239031), commit `ab92cfe54973cc9b555d01034ad2f105676d9291`: **674/674 pruebas generales OK** (10.834 s), **3/3** régimen OK, **339** archivos Python con sintaxis validada. Sin broker.
- Sin modificaciones de thresholds, TOP20, mercados SUCIO/CAÓTICO, expiración, autorización, memoria productiva ni REAL. El próximo cuello de botella es la disponibilidad del historial y la exportación real para cotejo retrospectivo; el objetivo 60% sostenido y neto positivo continúa sin demostrarse.

## R9-17 — riesgo observado y consistencia realista en OOS descriptivo

- En `scripts/evaluar_oos_descriptivo_fase9.py`, el desglose observacional de PNL OOS informa ahora `drawdown_maximo_unidades` (caída máxima desde el pico del PNL acumulado, no porcentaje de balance), `racha_maxima_perdidas`, `resumen_oos_descriptivo`, `peor_winrate_ventana_20`, `peor_neto_ventana_20`, `bloques_20_que_incumplen`, número de bloques completos y número de operaciones restantes sin bloque completo.
- Se evita declarar que bloques sintéticos, históricos o parciales demuestran consistencia: `evidencia_sostenida_60_pct=false` y `calidad_evidencia=DESCRIPTIVO_HISTORICO_NO_INDEPENDIENTE` siguen incluso si todas las ventanas observadas obtienen >=60% y PNL positivo. El cumplimiento descriptivo de bloques y ventanas se mantiene separado del criterio de evidencia independiente.
- Cuatro nuevas pruebas cubren drawdown y rachas, la muestra parcial, no certificación de un solo bloque positivo y un bloque con 60% WIN pero PNL negativo.
- Validación GitHub Actions [44597328913](https://github.com/luisAngeles12/bootIQ/actions/runs/44597328913), commit de pruebas `2c6e52397ffac48f2391d1af2560c9d1731a48a3`: **678/678 pruebas generales OK** (10.852 s), **3/3** de régimen OK (0.013 s), 339 archivos Python con sintaxis OK; sin broker.
- No se conectó IQ ni se ejecutó bot.py. Ningún ajuste a estrategia, entradas, TOP20, SUCIO/CAÓTICO, expiración, capital, bloqueos, bootstrap o modo REAL. El objetivo >=60% sostenido con beneficio neto positivo sigue sin verificarse en PRACTICE independiente.

## R9-18 — evaluación descriptiva por familia y exclusiones OOS visibles

- El evaluador `scripts/evaluar_oos_descriptivo_fase9.py` ahora desglosa cada `familia_setup` presente en las operaciones OOS: número de operaciones, métricas monetarias y de winrate descriptivas, bloques completos de 20, ventanas móviles de 20 y conteos que cumplen. Una familia con menos de 20 se marca `SIN_MUESTRA_MINIMA_20` y **no puede figurar como consistente**. La ausencia de familia se informa explícitamente bajo `SIN_FAMILIA` sin atribuir una estrategia inventada.
- Para no elevar artificialmente el winrate al eliminar observaciones, cuando en el tramo OOS inspeccionado existen operaciones PRACTICE pendientes o cierres PRACTICE con PNL cero/ausente/no finito, se devuelve `NO_APTO / OOS_CON_RESULTADOS_OMITIDOS` y la razón cuantificada en `exclusiones_oos`, sin publicar bloques. La selección histórica de la ventana sigue basada en candidatas válidas del auditor temporal; resta auditar en una etapa posterior los casos omitidos que pudieran alterar la propia posición del corte temporal.
- No modifica las reglas de entrada, filtros, montos ni el motor de aprendizaje; no crea memoria, no arranca bot y no habilita REAL.
- Cinco pruebas nuevas cubren familias submuestreadas, familia ausente, familia con 20 registros, empate dentro de OOS y operación pendiente. Validación CI: [GitHub Actions 44598153294](https://github.com/luisAngeles12/bootIQ/actions/runs/44598153294), commit `c65d69b95b40c1d9eb3ff8e0752afef99e9785c8`: **683/683** pruebas generales OK (10.884 s), **3/3** régimen OK (0.013 s), sintaxis de 339 Python OK.
- Estos casos son sintéticos. El objetivo de >=60% sostenido y neto positivo sigue sin evidencia real suficiente.

## R9-19 — integridad del universo PRACTICE ANTES del corte TRAIN/OOS

- Hallazgo causal: el corte TRAIN/OOS se obtenía de filas ya filtradas a `estado=CERRADA` y PNL distinto de cero. Empates, operaciones abiertas o fechas inválidas previas al corte podían desplazar la posición de OOS, permitiendo un denominador sesgado.
- `scripts/auditar_particion_temporal_fase9.py` contabiliza ahora `filas_practice_declaradas`, `filas_sin_modo`, `filas_practice_no_admisibles` y `universo_practice_completo`. Las filas sin modo permanecen de origen INDETERMINADO, nunca se promueven a PRACTICE.
- `scripts/evaluar_oos_descriptivo_fase9.py` impide publicar métricas (`NO_APTO / UNIVERSO_PRACTICE_INCOMPLETO`) cuando existen filas PRACTICE excluidas por cualquier causa, incluso **antes** del primer OOS, o filas sin modo que impiden establecer el universo completo. La partición sigue siendo diagnóstica para explicar exclusiones, no licencia de entrenamiento.
- Tres pruebas de regresión cubren empate anterior al corte, fecha PRACTICE inválida antes del corte y cuenta sin modo. Se ajustaron tres expectativas anteriores para reconocer el nuevo bloqueo anticipado.
- La primera ejecución CI detectó una expectativa antigua en una prueba de apertura corrupta (`OOS_APERTURA_UTC_INVALIDA`); se corrigió la expectativa porque ahora se bloquea antes con `UNIVERSO_PRACTICE_INCOMPLETO`. No se relajó la validación.
- CI final **verificada por GitHub Actions**: commit `3ef9efddc1dabf95138bc90d47763ee0db105821`, [run 44598993687](https://github.com/luisAngeles12/bootIQ/actions/runs/44598993687): **686/686 pruebas generales OK** (10.117s), **3/3** de régimen OK (0.012s), 339 Python verificados sintácticamente, sin broker.
- Sin cambios en estrategia, TOP20, umbrales, SUCIO/CAÓTICO, temporización, expiración, órdenes, memoria productiva ni permisos REAL. La meta >=60% sostenible y PNL positivo permanece sin prueba PRACTICE independiente.

## R9-20 a R9-22 — triage, reporte reproducible y corte escalable (19-11-2026)

- **R9-20:** se añadió `scripts/clasificar_historial_fase9.py`, diagnóstico de solo lectura que coloca cada fila del historial en **un grupo excluyente**: cuenta desconocida, no PRACTICE, PRACTICE no apta, PRACTICE solo descriptiva sin cierre conciliado, o PRACTICE candidata no certificada. Los conteos cierran con `integridad_conteo`; los modos sin evidencia no se imputan. Identificadores repetidos (incluidos ceros iniciales), fechas sin zona, PNL cero/no finito y cierres anteriores a apertura nunca se promocionan para entrenamiento. Cinco pruebas con archivos temporales sintéticos.
- **R9-21:** se añadió `scripts/reporte_integral_fase9.py`, agrega clasificación + partición temporal + métricas OOS descriptivas y opcionalmente cotejo IQ CSV. Siempre `memoria_generada=false`, `habilita_trading=false`, `evidencia_rentabilidad_sostenida=false` y advertencias de procedencia y falta de validación de política V3. Incluso `DIAGNOSTICO_COMPLETO_SIN_CERTIFICACION` **no** equivale a broker verificado ni a 60% real. Cuatro pruebas de read-only, modo desconocido, empate y esquema incompleto.
- **R9-22:** en `scripts/auditar_particion_temporal_fase9.py` el corte TRAIN/OOS pasó de recontar todas las órdenes para cada timestamp a barrido acumulativo tras ordenar: **O(n) tras sort**, manteniendo la misma prioridad de minimización `(distancia del 70%, timestamp)` y sin partir órdenes del mismo instante. Prueba de 1.200 órdenes sintéticas con marcas repetidas: TRAIN 840 / OOS 360 y ningún solapamiento.
- **Validación CI final** para commit `8f30e271d7dd122a037161f74119e1b608564eb7`: [GitHub Actions 44600165929](https://github.com/luisAngeles12/bootIQ/actions/runs/44600165929) completó **696/696 pruebas generales OK (10.944 s)**, **3/3 de régimen OK (0.013 s)** y sintaxis correcta de 343 archivos Python. No se ejecutó `bot.py` ni se conectó un broker. Los fixtures de pruebas no representan operaciones reales.
- **Limitación decisiva:** el historial real `historial_bot.csv` (antes observado con 580 filas, 431 sin modo explícito) no está versionado ni accesible en CI. Tampoco existe una exportación de cierres IQ de procedencia independiente en el repositorio. Ni el clasificador ni el reporte pueden rehabilitar esos registros por inferencia. Sigue pendiente el cotejo independiente y, después, evaluación de la política entrenada frente a una versión congelada en OOS prospectivo.
- Reglas preservadas: PRACTICE exclusivamente; bootstrap sin memoria desactivado; sin cambios en estrategia, thresholds, TOP20, SUCIO/CAÓTICO, timing, expiración, riesgo ni autorizaciones REAL.

## R9-23 — integridad de las fuentes durante el informe integral (19-11-2026)

- Causa: `reporte_integral_fase9.py` lee el historial en clasificación, partición y OOS por separado. En PRACTICE, `historial_bot.csv` puede cambiar entre esas lecturas. Sin comprobación, los resultados podían provenir de **versiones distintas del archivo** y publicarse como si fueran una sola muestra.
- Se añadió `_huella` (SHA-256, lectura por bloques de 1 MiB) y comparación de huellas del historial y, si se proporciona, del CSV IQ antes y después de cada etapa. Si alguna huella cambia, retorna `NO_APTO_PARA_VALIDACION / FUENTE_MODIFICADA_DURANTE_AUDITORIA` sin adjuntar métricas compuestas. Si falta alguno de los archivos, retorna `FUENTE_NO_DISPONIBLE`. La huella no autentica al broker; solo detecta diferencias del contenido observado.
- Los resultados sin cambios incluyen `huellas_fuentes_sha256` e `integridad_fuentes_estable=true` para trazabilidad y reproducción. La auditoría no escribe archivos.
- Se incorporaron cinco pruebas de archivo estable, mutación tras clasificación, mutación tras partición, mutación del CSV del broker durante evaluación y archivo inexistente.
- **GitHub Actions** [run 44603515159](https://github.com/luisAngeles12/bootIQ/actions/runs/44603515159), commit `b2c38f7b2a3454db9086c4d412397919632d782a`: **701/701 tests generales OK** (10.882 s), **3/3 régimen** (0.013 s), sintaxis de 343 Python OK. No se ejecutó `bot.py` ni se conectó IQ.
- Continúa pendiente el historial real y la exportación independiente de IQ. La fase 9 sigue sin evidencia suficiente del 60% sostenido con neto positivo. PRACTICE exclusivamente; bootstrap no habilitado; sin cambios de estrategia ni autoridad de ejecución.

## R9-24 — instantáneas privadas y consistentes para la auditoría integral

- Hallazgo: comparar SHA-256 antes y después de cada etapa reduce el riesgo de detectar cambios, pero no evita que cada etapa lea directamente un CSV activo. La auditoría podía analizar contenido diferente si se modificaba durante la lectura, incluso con comprobaciones espaciadas.
- `scripts/reporte_integral_fase9.py` ahora copia `historial_bot.csv` y, si está presente, el export IQ a una carpeta temporal aislada, comprueba que las copias y los originales tienen las mismas huellas SHA-256, y ejecuta clasificación, partición temporal y OOS **contra la misma copia privada**. Vuelve a verificar copias y originales después de cada etapa, sin escribir los archivos fuente. Destruye las copias temporales al finalizar.
- Bloquea `NO_APTO_PARA_VALIDACION / FUENTE_MODIFICADA_DURANTE_AUDITORIA` cuando original o copia cambian, y `MISMO_ARCHIVO_NO_ES_EXPORTACION_INDEPENDIENTE` si se introduce exactamente el mismo archivo como historial y broker. La huella no acredita procedencia de IQ ni autenticidad de los datos.
- Tres pruebas nuevas: mismas copias en todas las etapas, cambio externo del CSV original y rechazo de un mismo archivo utilizado como exportación. Se preservaron pruebas anteriores de modificación, ausencia de archivo y no escritura de fuentes. Una primera prueba asumía incorrectamente que el clasificador devuelve el campo `archivo`, que no forma parte de su contrato: se retiró esa aserción, sin reducir las comprobaciones de integridad.
- CI final confirmada: [GitHub Actions 44616322136](https://github.com/luisAngeles12/bootIQ/actions/runs/44616322136), commit de código/pruebas `c532bfea75bd6d748be3bc35fa3d0df6e0dba056`: **704/704 tests generales OK** (10.911 s), **3/3** tests de régimen OK (0.013 s), 343 fuentes Python con sintaxis correcta. Sin ejecución `bot.py` ni conexiones a broker.
- No se cambió estrategia, thresholds, TOP20, bloqueo SUCIO/CAÓTICO, expiración, timing ni memoria. PRACTICE exclusivamente; objetivo >=60% sostenido y PNL neto positivo aún sin verificación externa.

## R9-25.13 — validación monetaria consistente y hallazgos reales PRACTICE (19-11-2026)

- Datos históricos proporcionados por el operador (solo observación local, sin CSV de IQ cotejado): **580** registros de los cuales **149** declaran PRACTICE (16–19 nov), **431** sin modo explícito (10–14 nov); 149 IDs presentes y no duplicados; faltan las columnas nuevas de UTC apertura y conciliación. Las 149 PRACTICE registradas arrojan **71 WIN / 78 LOSS, 47,65% y neto -464,75** en la unidad del CSV. Las cuatro jornadas 16–19 nov son negativas. Todas las 149 declaran autoridad `BOOTSTRAP_PRACTICE_SIN_HISTORIAL`; no atribuir esto a rentabilidad de V3. Ningún resultado fue cotejado con broker.
- Desglose descriptivo suministrado: reacción zona 32 operaciones neto -204; continuación 44 neto -180,25; reversión estructural 42 neto -41,75; reversión 31 neto -38,75. Régimen `TENDENCIA_SUCIA` (distinto de `calidad_mercado=SUCIO`) 60 operaciones con neto -306; allí `tipo_mercado` es tendencia alcista/bajista, `calidad_mercado` NORMAL (56) o LIMPIO (4), y el bootstrap estaba autorizado históricamente. No demuestra saltarse un veto SUCIO/CAÓTICO.
- Causa de código identificada para mejora offline: `conciliar_exportacion_iq_fase9._monto` ya exige exactitud de centavos con Decimal, pero `clasificar_historial_fase9` y `auditar_particion_temporal_fase9` permitían PNL numérico finito con fracciones de centavo. Una muestra podía aparecer admisible en TRAIN/OOS, pero ser invalidada al conciliar el mismo monto con IQ.
- R9-25.13 comparte `_monto` estricta en clasificación y partición temporal: no se redondea la muestra, ni se modifica el historial original. Las nuevas pruebas cubren cantidades ordinarias, 0,01, notación científica exacta, fracciones de centavo, no finitos, importes ausentes y empates. El resultado del historial real **no se recalificó** ni se alteró.
- [CI final 44638323351](https://github.com/luisAngeles12/bootIQ/actions/runs/44638323351), commit `dbbd2474fe2332095b7b36caaee25c126ce5e4ac`: **707/707** tests generales, **3/3** de régimen; sintaxis **344** fuentes Python. PRACTICE; no bot.py, no IQ, no cambios en reglas, mercados, bootstrap, memoria o ejecución.
- Pendiente esencial: exportación original independiente de IQ PRACTICE, persistencia nueva de apertura y conciliación UTC en futuras operaciones y OOS prospectivo sin fuga; no aceptar 47,65% como evidencia certificada ni fabricar cierres/fechas retrospectivos.

## R9-25.14 — diagnóstico descriptivo reproducible de pérdidas bootstrap (19-11-2026)

- Nuevo CLI offline, **solo lectura**, `python -m scripts.diagnostico_bootstrap_practice_fase9 historial_bot.csv`, en `scripts/diagnostico_bootstrap_practice_fase9.py`. Reproduce en una sola ejecución resultados por día declarado, familia, régimen/dirección, triple familia-régimen-dirección y autoridad. El día del histórico no lleva zona horaria confirmada y **no** se convierte a UTC; no se infiere procedencia del broker.
- Cada fila obtiene una sola categoría: modo ausente, no PRACTICE, identificador ausente/duplicado globalmente, estado no cerrado, PNL inválido/fraccionario de centavo/no finito, empate, fecha inválida o PRACTICE descriptiva válida. Se verifican `conteo_conservado` y suma de todos los subgrupos con importes Decimal. Se preservan los ceros iniciales del ID, sin publicarlos en el resumen.
- Los resultados con `n < 20` llevan la marca `muestra_menor_20`; incluso grupos grandes **no acreditan ventaja OOS** dado que se descubrieron retrospectivamente. La salida indica `procedencia_iq_verificada=false`, `validacion_oos=false`, `permite_reconfigurar_estrategia=false`, `habilita_trading=false`, `memoria_generada=false`.
- Cinco pruebas nuevas prueban integridad sin escritura, exclusiones exhaustivas, duplicados e IDs vacíos, ausencia de optimismo en muestras minúsculas, esquema incompleto y archivo inexistente. Corrección de una aserción de test que no contaba el ID vacío, sin cambios de lógica de producción.
- **GitHub Actions** [44639002096](https://github.com/luisAngeles12/bootIQ/actions/runs/44639002096), commit de código/pruebas `9c0eefc43122666de167bc9c99eef3c7e18d7402`: **712/712** tests generales, **3/3** régimen, sintaxis **346** Python OK. Sin ejecutar bot.py, IQ, ni alterar estrategias, reglas de mercado, memoria, bootstrap o historial original.
- Para continuar con el CSV local aún sin subir, basta sincronizar los commits nuevos y ejecutar el comando de diagnóstico; la exportación independiente IQ y la cronología UTC prospectiva siguen siendo necesarias para cualquier validación de 60% sostenido y PNL neto positivo.

## R9-25.15–16 — salida histórica PRACTICE reproducida y cronología broker (19-11-2026)

- Resultado proporcionado por el operador del CLI `python -m scripts.diagnostico_bootstrap_practice_fase9 historial_bot.csv`: `DESCRIPTIVO_NO_VERIFICADO_BROKER`, 580 filas conservadas, 149 PRACTICE descriptivas, 431 excluidas por `CUENTA_DESCONOCIDA`, 71 WIN, 78 LOSS, **47,65%** de aciertos y **-464,75** neto. Cuatro días 16–19 nov netos negativos; las 149 operaciones se atribuyen al bootstrap histórico, no al V3 certificado. Se confirman desgloses por familia/régimen/dirección anteriores; las muestras diminutas y la búsqueda retrospectiva no habilitan estrategia.
- Riesgo detectado directamente en `scripts/conciliar_exportacion_iq_fase9.py`: el cotejo permitía que `fecha_cierre_utc` de broker fuese anterior a la apertura explícita `fecha_apertura_registro_local_utc` del bot, siempre que fuese anterior a `fecha_conciliacion_local_utc`. Esa coincidencia era cronológicamente imposible para una misma orden.
- R9-25.16 agrega comprobación **condicional y estricta** de apertura UTC explícita: si el campo tiene valor, su timestamp debe contener zona válida y el cierre broker debe ser posterior o igual al inicio. Ante incompatibilidad, el ID queda fuera de `conciliadas_preliminares` con causas `BOT_APERTURA_UTC_INVALIDA` o `CIERRE_BROKER_ANTERIOR_APERTURA_BOT`. Registros legacy sin la columna o sin marca continúan como contraste **preliminar no certificado**, sin fabricar aperturas ni zonas.
- Cinco pruebas nuevas verifican cierre anterior a apertura, equivalencia UTC entre zonas, marca explícita sin zona, cronología imposible y compatibilidad legacy. Ninguna ruta usa IQ online ni modifica historial, memoria, filtros o autorización.
- **GitHub Actions** [run 44639781769](https://github.com/luisAngeles12/bootIQ/actions/runs/44639781769), código/pruebas commit `6e12558ceddc583b2b4d13f7bf2ea1c62674fa21`: **717/717** tests generales, **3/3** régimen, 346 archivos Python con sintaxis OK. Sin `bot.py`, sin REAL y sin acceso a broker.
- Requisitos pendientes: exportación genuina independiente de IQ y apertura/cierre UTC prospectivos. El objetivo de 60% sostenido con beneficio neto no está demostrado.
