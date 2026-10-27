# BootIQ V3 — F3: contraste de selección por probabilidad (27-oct-2026)

**Solo diagnóstico histórico; sin trading, sin cambios de autoridad.**

Código: `auditoria_gate_probabilidad_fase3.py`; 3 pruebas nuevas,
[GitHub Actions 40551599516](https://github.com/luisAngeles12/bootIQ/actions/runs/40551599516):
**200 tests OK**. CSV histórico: `auditoria_xpd_sep2026_autoridad.csv`.

| Regla | WIN / n | WR hipotético | Wilson inferior 95% |
|---|---:|---:|---:|
| Todo el universo Sep15–18 | 1,149 / 2,280 | 50.39% | 48.34% |
| Probabilidad estimada >=57% | 1 / 3 | 33.33% | 6.15% |
| Percentil 90 fijado con el día anterior | 134 / 240 | 55.83% | 49.51% |

### Variación temporal del percentil 90 previo

| Día evaluado | Corte calculado día anterior | WIN / n | WR hipotético |
|---|---:|---:|---:|
| 16-sep | 53.91% | 34/80 | 42.50% |
| 17-sep | 53.91% | 58/82 | 70.73% |
| 18-sep | 53.91% | 42/78 | 53.85% |

El caso 17-sep supera 57% de forma aislada, pero no se reproduce
el 18-sep y el agregado no lo sostiene. No autoriza una nueva estrategia.

### Decisión

- **No incorporar** filtros probabilísticos >=57% ni percentil 90.
- No modificar pesos, Cerebro, CORE4, TOP20, veto SUCIO/CAÓTICO ni expiración.
- Repetir búsquedas de parámetros sobre estas mismas cuatro jornadas
  no constituye validación; para probar una mejora verdadera se requiere
  evidencia temporal no utilizada al diseñar los filtros.
- En el árbol actual no existen CSV versionados posteriores al 26-oct
  identificables como muestras prospectivas de fase 3. Las capturas
  PRACTICE del equipo de Luis están fuera del repositorio.
