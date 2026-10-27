# Fase 3 — ¿El Cerebro discrimina señales con ventaja estable?

Fecha: 27-oct-2026. Auditoría descriptiva sin órdenes ni cambios de estrategia.

Código: `auditoria_discriminacion_cerebro_fase3.py`, pruebas:
`tests/test_auditoria_discriminacion_cerebro_fase3.py`.
[GitHub Actions 40555701636](https://github.com/luisAngeles12/bootIQ/actions/runs/40555701636):
**209 pruebas broker-free OK**.

Datos: `auditoria_xpd_sep2026_autoridad.csv`, jornadas 15-18 septiembre.
La autorización viene de `decision_estadistica_sombra`; los resultados
son **hipotéticos**, también para canceladas.

| Cohorte | WIN | LOSS | Total | WR hipotético |
|---|---:|---:|---:|---:|
| Autorizada estadísticamente | 415 | 396 | 811 | 51.17% |
| No autorizada estadísticamente | 734 | 735 | 1,469 | 49.97% |
| Universo | 1,149 | 1,131 | 2,280 | 50.39% |

Diferencia autorizadas - rechazadas: **+1.21 puntos porcentuales**,
intervalo descriptivo aproximado 95% **[-3.08, +5.49]**.
No hay evidencia de ventaja discriminativa positiva estadísticamente clara.

| Día | WR autorizadas | WR rechazadas | Diferencia |
|---|---:|---:|---:|
| 15-sep | 47.67% | 49.84% | -2.16 pp |
| 16-sep | 48.05% | 54.35% | -6.30 pp |
| 17-sep | 56.31% | 48.98% | +7.33 pp |
| 18-sep | 52.48% | 46.76% | +5.71 pp |

De 79 estratos comparables por día y activo, 40 tuvieron diferencia
positiva, 37 negativa y 2 empataron. La composición por familia,
tipo de patrón, hora y calidad también puede confundir el contraste;
**no equivale a un experimento causal aleatorizado**.

## Decisión

- No afirmar que el Cerebro actual aporta +1.21pp en producción.
- No relajar el Cerebro ni permitir operaciones rechazadas; tampoco
  liberar mercados SUCIO/CAÓTICO.
- No ajustar pesos en estas mismas cuatro jornadas.
- Investigar primero si los patrones generados presentan ventaja
  genuina en datos posteriores al corte. Si no la hay, calibrar la
  probabilidad no puede fabricar rentabilidad.
- Mantener la exigencia de >57% sostenido con PNL PRACTICE positivo.
