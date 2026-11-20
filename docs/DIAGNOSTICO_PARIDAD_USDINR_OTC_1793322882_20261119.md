# Diagnóstico causal de tres divergencias de arbitraje — USDINR-OTC

## Fuente
Salida local comunicada por el operador sobre `data_actual_practice/practice_1s_USDINR-OTC_1793322881_1793326482.csv`; 3599 velas consecutivas de 1 segundo. No se subió el CSV ni se ejecutaron órdenes.

## Cobertura comprobada
- 59 cierres en replay, 58 observables en flujo; el cierre `1793323500` quedó excluido por recepción tardía.
- De 3599 velas, 57 presentan retraso registrado.
- `coincidencia_cierres_elegibles=True`: los 58 cierres temporalmente elegibles coinciden en cobertura. **No equivale a paridad de diagnósticos**.
- 14 cierres con diferencia de diagnóstico, 10 de contexto, 12 de candidatos, tres de arbitraje.

## Tres diferencias del árbitro explicadas por el calentamiento

| Cierre UTC epoch | Replay | Flujo | Decisión en ambos |
|---|---|---|---|
| 1793324520 | RANGO; NINGUNA_ESTRATEGIA_CONFIRMADA | SIN_DATOS; CALENTAMIENTO_INSUFICIENTE; CONTEXTO_BLOQUEADO | NO_OPERAR |
| 1793324580 | RANGO; NINGUNA_ESTRATEGIA_CONFIRMADA | SIN_DATOS; CALENTAMIENTO_INSUFICIENTE; CONTEXTO_BLOQUEADO | NO_OPERAR |
| 1793324640 | RANGO; NINGUNA_ESTRATEGIA_CONFIRMADA | SIN_DATOS; CALENTAMIENTO_INSUFICIENTE; CONTEXTO_BLOQUEADO | NO_OPERAR |

El replay conservó información histórica posterior al minuto perdido, mientras el flujo causal no reconstruyó retroactivamente el contexto disponible antes de recibir las velas. Por ello diverge el motivo y contexto, **no** la decisión final. La separación es protectora y no autoriza reducir el calentamiento.

## Señales sombra observadas
Dos eventos de `RECHAZO_ZONA` en `put` con 24 minutos de contexto temporal verificado: uno `LOSS` y uno `WIN`, ambos `APERTURA_FUTURA_RETROSPECTIVA_NO_EJECUTADA`. 50% hipotético; no hay fill, payout ni PnL realizado, y `operaciones_autorizadas=False`. No usar como prueba de rentabilidad.

## Decisión de auditoría
- Explicación del trío de divergencias de arbitraje: **cerrada para esta captura**.
- Paridad general de diagnósticos: **no demostrada**; diferencias causales esperables no se maquillan como igualdad.
- No cambiar `TOP20`, mercados SUCIO/CAOTICO, expiración, autorizaciones ni thresholds.
- Próxima investigación: candidatas sombra y operaciones ejecutadas con la misma trazabilidad de contexto/resultado; la cifra objetivo de 60% en cuatro bloques PRACTICE sigue sin validarse.
