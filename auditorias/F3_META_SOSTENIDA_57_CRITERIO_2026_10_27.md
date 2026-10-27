# Fase 3 — aceptación estricta de winrate sostenido >57%

Fecha: 27-oct-2026. Verificador offline de candidatos previamente
congelados, separado del motor operativo. No ejecuta órdenes.

Implementación: `auditoria_meta_sostenida_fase3.py`.
CI: [Actions 40553551657](https://github.com/luisAngeles12/bootIQ/actions/runs/40553551657),
**206 pruebas broker-free superadas**.

Para poder devolver `objetivo_57_sostenido_verificado=true` exige:

- Muestra de al menos 100 **operaciones PRACTICE ejecutadas y cerradas**,
  con resultado WIN/LOSS y PNL monetario finito explícitos.
- Al menos tres **días UTC independientes**, con al menos 30 operaciones
  por día y WIN rate **estrictamente superior** al 57% en cada día suficiente.
- WIN rate acumulado y límite inferior Wilson 95% **estrictamente mayores**
  al 57%, y PNL real cerrado total positivo.
- Señales posteriores al 26-oct-2026, sin IDs repetidos entre ventanas.
- Payout neto declarado y válido. No autoriza REAL.

Las pruebas sintéticas cubren una secuencia consistentemente fuerte,
una jornada excepcional con otra deficiente, pérdidas monetarias
pese a WR elevado, canceladas, cuenta REAL, ventanas duplicadas y
resultados anteriores al corte. **Los tests del verificador no prueban
que exista actualmente una estrategia que cumpla las condiciones.**

El experimento histórico reciente con filtro percentil 90 previo tuvo
55.83% acumulado, con días 42.50%, 70.73% y 53.85%. Por tanto, es
**RECHAZADO** según el criterio, aunque una sola fecha haya superado 57%.

Estado: **meta sostenida todavía NO demostrada**. Falta evaluación en
datos posteriores al corte y verdaderas operaciones PRACTICE cerradas.
No alterar estrategia, CORE4, TOP20, SUCIO/CAÓTICO o expiración.
