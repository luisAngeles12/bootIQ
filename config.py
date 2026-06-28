# ============================================================
# CONFIGURACIÓN GENERAL DEL BOT
# ============================================================
# Cambia estos valores por los tuyos.
EMAIL = "luisangelestejada@gmail.com"
PASSWORD = "R@putim120799"

MODO_CUENTA = "PRACTICE"  # PRACTICE o REAL
TIPOS_MERCADO = ["binary", "digital", "turbo"]  # Tipos de mercado a operar
MONTO_BASE = 25
TIEMPO_EXPIRACION = 1
CANDLE_TIME = 60
CANDLE_NUMBER = 180
MAX_OPERACIONES_ABIERTAS = 5
STOP_LOSS = -1000
STOP_WIN = 100000
PUNTAJE_MINIMO = 7
MOSTRAR_ESTADISTICAS_CADA_RONDAS = 100
MODO_ENTRADA = "NORMAL"

VENTANA_ENTRADA_INICIO = 0
VENTANA_ENTRADA_FIN = 59

MIN_PRIORIDAD_OPERAR = 3
PERMITIR_ENTRADA_PENDIENTE = True

BLOQUEAR_VELA_CONTRARIA_SOLO_SI_ES_FUERTE = True
PERMITIR_ENTRADA_CON_CONTEXTO_FUERTE = True
# ============================================================
# PARÁMETROS DE ENTRADA - FASE 1
# ============================================================
PUNTAJE_SENAL_PREMIUM = 21
PUNTAJE_CONTEXTO_FUERTE = 17

FUERZA_MAXIMA_VELA_NORMAL = 0.78
SEGUNDO_MAXIMO_VELA_CORRIDA = 18

CALIDADES_OPERABLES = ["A", "A+"]
CALIDADES_MERCADO_OPERABLES = [ "LIMPIO", "NORMAL" ]
# ============================================================
# CONFIGURACIÓN DE ARCHIVOS
# ============================================================
HISTORIAL_JSON = "historial_bot.json"
HISTORIAL_CSV = "historial_bot.csv"
OPERACIONES_PENDIENTES_JSON = "operaciones_abiertas.json"
