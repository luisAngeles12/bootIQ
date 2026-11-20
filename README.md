# BootIQ — reinicio controlado (27-oct-2026)

Esta rama contiene el núcleo del bot y **un único backtest oficial**:
`backtest_bot_real.py`. Se retiraron los históricos versionados, velas,
resultados, memoria entrenada, operaciones guardadas, otros backtests,
logs y documentación generada.

## Estado y seguridad

- La rama operativa `bootiq-v3-auditoria` y `main` no fueron modificadas
  por la primera limpieza.
- **PRACTICE únicamente. NUNCA REAL.**
- La limpieza **no certifica rentabilidad**, ni autoriza operaciones.
- Deben verificarse importaciones, pruebas y arranque en un entorno local
  controlado antes de usar esta rama como operativa.

## Archivos esenciales

- `bot.py`: punto de entrada V3.
- `estrategia.py` y `motor_estrategias.py`: generación y evaluación de señales.
- `mercado.py`, `contexto_mercado.py`, `indicadores.py`,
  `price_action.py`: datos y contexto.
- `motor_decision.py`, `motor_protocolos.py`, `entrada.py`,
  `operaciones.py`: autoridad, confirmación y ejecución.
- `backtest_bot_real.py`: **único backtest conservado**.
- `iqoptionapi/`: biblioteca necesaria para conexión.

## Datos nuevos

El repositorio no contiene ningún archivo CSV ni JSON de operaciones o
aprendizaje. El primer inicio de `bot.py` puede generar un historial
vacío localmente; los datos futuros quedan ignorados por Git.

La captura nueva de velas debe realizarse en **PRACTICE**, con validación
de cierre, continuidad temporal, frescura y TOP oficial completo.
No reutilizar datos de octubre ni resultados de experimentos anteriores.

La configuración privada `credenciales_local.py` nunca debe
subirse al repositorio.

## Backtest

El backtest toma los datos de `BOOTIQ_DATASET_DIR` si está definido,
o de `data_backtest_actual/` por defecto. Esa carpeta empieza vacía:
hasta disponer de velas nuevas válidas, un backtest carece de muestra
y no debe interpretarse como prueba de estrategia.

## Investigación de interacciones PRACTICE

Para analizar combinaciones de estrategia, mercado, Price Action y otras
características sin alterar las reglas del bot:

```powershell
.\venv\Scripts\python.exe analizar_interacciones_ejecutadas_practice.py .\historial_bot.zip
```

También acepta un CSV. Selecciona reglas solo con días de entrenamiento,
reporta por separado los días posteriores y nunca promueve una estrategia ni
autoriza operaciones. Los hallazgos que aparecen solo en el holdout se marcan
como post hoc y requieren una nueva validación prospectiva. Los cierres
PRACTICE antiguos sin modo explícito se identifican como declarados por el
usuario, no como verificados por el bróker.
