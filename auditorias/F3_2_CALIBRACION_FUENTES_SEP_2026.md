# BootIQ V3 — Fase 3: calibración descriptiva de fuentes históricas

Fecha: 2026-10-27 UTC. Experimento **offline**, sin broker y sin órdenes.

## Código y evidencia

- Motor inspeccionado: `motor_aprendizaje_historico.py`.
  - `_seleccionar_fuente_principal` prioriza niveles transferibles y tamaño
    de muestra, no el WR para escoger la principal.
  - `_buscar_fuentes_aprendizaje` pondera nivel, muestra y estabilidad.
  - `_combinar_fuentes` mezcla principal con respaldo/prior, pero publica
    el intervalo de la principal (no un intervalo posterior de la mezcla).
- Auditor existente ejecutado sobre
  `auditoria_xpd_sep2026_autoridad.csv`:
  `auditoria_generalizacion_fuentes.py`.
- GitHub Actions [40545103766](https://github.com/luisAngeles12/bootIQ/actions/runs/40545103766):
  suite broker-free **SUCCESS**, 192 pruebas y auditorías históricas OK.
- Cuatro días históricos 15–18 sept 2026. Los resultados de
  canceladas son **hipotéticos**. No sustituye nuevas ventanas OOS.

## Cohortes de mayor tamaño

| Fuente principal | n | Probabilidad media | WR hipotético | Brier modelo | Brier prior | Días |
|---|---:|---:|---:|---:|---:|---:|
| CONTEXTO_SETUP PUT, reversión estructural CHOCH bajista con PA | 417 | 51.65 % | 48.44 % | 0.25050 | 0.24982 | 4 |
| CONTEXTO_SETUP CALL, reversión estructural CHOCH alcista con PA | 335 | 54.86 % | 55.22 % | 0.24874 | 0.25084 | 4 |
| CONTEXTO_SETUP PUT, continuación/pullback genérico | 218 | 45.86 % | 50.46 % | 0.25209 | 0.25013 | 4 |
| CONTEXTO_TECNICO PUT, continuación bajista normal | 148 | 46.89 % | 53.38 % | 0.25307 | 0.25056 | 4 |
| CONTEXTO_SETUP CALL, continuación simple | 132 | 42.39 % | 53.03 % | 0.26040 | 0.25051 | 4 |

Entre las **25 claves más frecuentes** que muestra el auditor, **10** tuvieron
Brier del modelo menor que el prior; **15**, mayor. Son comparaciones
exploratorias por clave, no pruebas de causalidad ni garantía de
generalización. Menor Brier es mejor; las diferencias deben comprobarse
en cortes temporales independientes.

El grupo CHOCH CALL (n335) varió:
49.35 % (15-sep), 45.68 % (16-sep), 65.52 % (17-sep)
y 58.89 % (18-sep), por lo que un WR agregado de 55.22 % no demuestra
estabilidad >=59 %. La fuente CHOCH PUT (n417) registró 48.44 % y
Brier algo peor que el prior.

## Veredicto

**No promocionar fuentes ni modificar pesos, prioridades, memoria o umbrales.**
Esta evidencia identifica familias que merecen investigación sobre
calibración y cambios de régimen, pero ninguna ventaja productiva
transferible. Para cualquier cambio operacional se requieren nuevas
ventanas temporales, comparaciones honestas antes/después y PNL
cerrado PRACTICE. No confundir 20 activos presentes a lo largo
del archivo con simultaneidad de TOP20.

En particular, no usar el intervalo de la principal como si fuera el
intervalo válido de la mezcla sin verificar su construcción y cobertura.
