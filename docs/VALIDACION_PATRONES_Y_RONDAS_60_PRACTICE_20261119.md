# BootIQ V3 — patrones, discrepancias y validacion repetida PRACTICE (2026-11-19)

## Hallazgo causal de alcance de muestras

El historial local comunicado contiene 580 filas: 149 con modo PRACTICE y 431 sin modo declarado. Los 149 registros evaluables se atribuyen a `BOOTSTRAP_PRACTICE_SIN_HISTORIAL`: 71 WIN, 78 LOSS, 47.65%, neto -464.75; cinco de siete bloques completos y 102 de 130 ventanas moviles no alcanzaron 60% con neto positivo.

Comparacion exploratoria con `docs/FASE5_AUDITORIA_ESTRATEGIAS_20261113.md`:

| Familia | Bootstrap PRACTICE ejecutado | Sombra hipotetica rechazada |
|---|---|---|
| CHOCH bajista | 15/27 = 55.56%, +11.25 | 265/606 = 43.73% proxy |
| Reaccion vendedora en resistencia | 8/20 = 40%, -133.75 | 127/229 = 55.46% proxy |
| Pullback alcista EMA | 15/32 = 46.88%, -110.00 | 467/923 = 50.60% proxy |
| CHOCH alcista | 7/15 = 46.67%, -53.00 | 307/653 = 47.01% proxy |

Estas cohortes difieren en autorizacion y sesgo de seleccion: **no son un experimento pareado**, ni autorizan transferir el mejor porcentaje sombra a ordenes LIVE. No hay evidencia para alcanzar 60% cambiando las reglas. Las cifras de 149 operaciones son agregados proporcionados por el operador, no una lectura directa del CSV en GitHub.

## Software de analisis incorporado

- `investigar_patrones_practice.py`: clasifica filas por autoridad y patron, retiene las perdidas, verifica modo/IDs/cierre, divide cronologicamente cada familia con >=20 operaciones en tres tramos, presenta porcentajes y PnL por tramo. **No** considera esos tramos independientes ni OOS.
- `validar_rondas_60_practice.py`: exige CSV PRACTICE prospectivo con fecha de congelacion UTC anterior a las operaciones, ordenes unicas, cierres UTC estrictamente crecientes, origen no bootstrap, tres o cuatro rondas consecutivas identificadas, exactamente 20 operaciones por ronda, al menos 12 WIN y neto positivo por ronda; exige ademas operaciones en al menos dos dias UTC.
- Ninguno de los dos programas cambia `bot.py`, señales, thresholds, TOP20, expiracion, capacidad, bloqueo SUCIO/CAOTICO o `config`. Ambos son de solo lectura.

## Forma del CSV para el gate prospectivo

Encabezados requeridos (puede haber columnas adicionales):

```csv
ronda_id,order_id,fecha_cierre,estado,tipo_cuenta,resultado,neto,familia,origen_autoridad
```

Cada fila debe representar una orden PRACTICE cerrada: `fecha_cierre` con zona horaria UTC y `neto` monetario realizado. La marca `origen_autoridad` nunca debe ser bootstrap. No inventar timestamps de cierre a partir de fecha de señal, ni derivar `WIN` de velas sin fill.

Comando read-only para el ultimo gate, **solo tras contar con un CSV prospectivo real y congelacion documentada**:

```bash
python validar_rondas_60_practice.py rondas_practice.csv --congelacion-utc 2026-11-19T00:00:00Z --rondas 4
```

La fecha indicada es **ilustrativa**: reemplazar por el sello UTC verificable en que se congelo la version efectivamente probada, anterior a las operaciones.

## Comprobaciones ejecutadas y limites

- 730/730 pruebas generales comunicadas por el operador antes de este cambio.
- 18/18 pruebas locales ejecutadas sobre las dos nuevas herramientas (13 de rondas y 5 de patrones), mas `py_compile` de las rondas, en un entorno sin broker; no son operaciones.
- GitHub Actions ampliado en la rama; la aprobacion del workflow del HEAD **no se ha verificado**.
- No hay datasets originales locales en `data_backtest_actual` segun inspeccion del operador; el CSV de 149 operaciones solo esta en su equipo. Por ello no se ejecuto un backtest causal nuevo ni cuatro rondas PRACTICE reales.
- `resultado_observado_3_4_rondas=CUMPLE` significa exclusivamente que el CSV presentado pasa la aritmetica y cronologia; el propio reporte deja `procedencia_broker_certificada=False` e `independencia_estadistica_certificada=False`.

## Criterio de continuidad

Primero: adquirir velas y ledger prospectivos sin omitir perdidas. Segundo: congelar el candidato sin ajustar parametros a la muestra futura. Tercero: evaluar PnL real y las 4 rondas sin seleccionar las mas favorables. Si falla cualquier ronda, se reporta como fallo, no se descarta. Ninguna ronda valida un 60% futuro garantizado. Modo REAL prohibido.
