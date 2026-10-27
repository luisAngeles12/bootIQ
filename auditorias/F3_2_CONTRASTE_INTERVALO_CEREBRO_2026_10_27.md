# BootIQ V3 — Fase 3: contraste pasivo estimación puntual vs intervalo

Fecha: 2026-10-27 UTC. Rama experimental F3.2, **no operativa**.

## Pregunta causal

El clasificador estadístico V3 en `motor_decision.py` autoriza según la probabilidad
puntual (55 % para `OPERAR_SOMBRA`, 50 % para
`OPERAR_CON_PROTOCOLO_SOMBRA`). Registra intervalos inferior y superior,
pero no exige que el límite inferior supere el umbral. Se investigó si
una selección por límite inferior podría ser una hipótesis prometedora **sin
alterar el clasificador operativo**.

## Experimento histórico reproducible

- Código pasivo: `auditoria_intervalo_cerebro_fase3.py`.
- Dataset archivado: `auditoria_xpd_sep2026_autoridad.csv`.
- Comando offline ejecutado automáticamente en GitHub Actions, sin bróker:
  `pipenv run python auditoria_intervalo_cerebro_fase3.py auditoria_xpd_sep2026_autoridad.csv`.
- Evidencia: [Actions 40544057222](https://github.com/luisAngeles12/bootIQ/actions/runs/40544057222),
  suite broker-free: **191 tests OK**; contraste ejecutado correctamente.
- Resultados de canceladas, cuando los hay, son **hipotéticos**, no PNL.
- Este análisis histórico no constituye OOS prospectivo de A/B.

| Clasificación original | Cohorte intervalo | N | WIN hipotéticos | LOSS hipotéticas | WR hipotético | Wilson inferior 95 % | Días UTC | Activos distintos |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| OPERAR_CON_PROTOCOLO_SOMBRA | Solo estimación puntual | 610 | 307 | 303 | 50.33 % | 46.37 % | 4 | 20 |
| OPERAR_SOMBRA | Solo estimación puntual | 201 | 108 | 93 | 53.73 % | 46.83 % | 4 | 20 |
| Ambas | Intervalo sostiene umbral | **0** | 0 | 0 | No evaluable | No evaluable | — | — |

Otras 1,469 filas no tenían autorización estadística y se excluyeron
del contraste. Los grupos de 20 activos miden **diversidad histórica**, no
cantidad simultánea en el TOP oficial.

## Alcance exacto del intervalo: hallazgo de procedencia

Inspección estática de `motor_aprendizaje_historico.py`,
función `_combinar_fuentes`: la `probabilidad_estimada` puede mezclar
probabilidad de fuente principal con respaldo o prior, mientras que
`intervalo_inferior` e `intervalo_superior` se copian de **la fuente
principal**. Por tanto, el intervalo no se ha calculado como intervalo
estadístico de la mezcla y no debe presentarse como tal.

Se amplió el diagnóstico para contar estimaciones finales que queden fuera
del intervalo de la principal. En la misma muestra histórica hubo
**0 de 811 fuera**, con **0 intervalos superiores inválidos**. Esa
coincidencia empírica no corrige la discrepancia de procedencia ni valida
su cobertura nominal. Prueba broker-free: **192 tests OK**,
[Actions 40544746521](https://github.com/luisAngeles12/bootIQ/actions/runs/40544746521).

No recalcular ni cambiar intervalos del motor en esta fase sin contrastes
causales de cobertura y calibración OOS independientes.

## Veredicto de esta hipótesis

**No promover una regla de veto por límite inferior del intervalo con estos datos.**
En el archivo histórico, exigir que el límite inferior sostenga el umbral
eliminaría las 811 señales estadísticamente autorizadas, sin ofrecer ninguna
cohorte en que medir el WR o la frecuencia resultante.

Tampoco puede afirmarse que la regla puntual original sea rentable: WR hipotéticos
50.33 % y 53.73 % no demuestran PNL realizado ni ventaja estable. La
diferencia por categoría no es prueba causal de mejora.

Este resultado orienta la siguiente investigación hacia fuentes, calibración,
diversidad temporal y evidencia ejecutada independiente, **sin cambiar**
umbrales, CORE4, vetos SUCIO/CAÓTICO, TOP20 ni autorización del Cerebro.

Estado: **hipótesis de filtro por intervalo descartada en esta evidencia histórica;
sin cambios operativos**.
