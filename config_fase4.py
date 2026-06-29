# ==============================
# CONFIGURACIÓN FASE 4 - BOOTIQ
# ==============================

MODO_BACKTEST = "BACKTEST"
MODO_REAL_OBSERVACION = "REAL_OBSERVACION"
MODO_REAL_ACTIVO = "REAL_ACTIVO"

MODO_FASE4 = MODO_BACKTEST

FASE4_ACTIVA = True

# Seguridad:
# False = el bot real NO bloquea operaciones todavía.
# True = el bot real puede bloquear operaciones.
FASE4_BLOQUEAR_EN_REAL = False

USAR_BASE_CONOCIMIENTO = True

RUTA_BACKTEST_RESULTADOS = "backtest_bot_real_resultados.csv"
RUTA_AUDITORIA = "data/auditoria_estadistica.json"
RUTA_BASE_CONOCIMIENTO = "data/base_conocimiento.json"