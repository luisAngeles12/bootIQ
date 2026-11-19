# ============================================================
# CONFIGURACIÓN GENERAL DEL BOT
# ============================================================
# Cambia estos valores por los tuyos.
from credenciales_local import EMAIL, PASSWORD


MODO_CUENTA = "PRACTICE"  # PRACTICE o REAL
# Sesion PRACTICE: maximo 20 aperturas IQ confirmadas, luego conciliar
# cierres, emitir informe y detener el proceso antes de otra orden.
CONTROL_BLOQUES_20_PRACTICE = True
# R9: suspensión del permiso de entrada sin memoria tras bloque PRACTICE
# de 20/20 órdenes bootstrap, 50 % WR y neto -41.25.
# Solo habilitar en un experimento separado con evidencia OOS y autorización
# explícita; nunca confiere permisos REAL.
PERMITIR_BOOTSTRAP_SIN_MEMORIA = False
TIPOS_MERCADO = ["turbo"]  # Tipos de mercado a operar
MONTO_BASE = 25
TIEMPO_EXPIRACION = 1
CANDLE_TIME = 60
CANDLE_NUMBER = 3000
MAX_OPERACIONES_ABIERTAS = 5
STOP_LOSS = -1000
STOP_WIN = 3000
PUNTAJE_MINIMO = 7
MOSTRAR_ESTADISTICAS_CADA_RONDAS = 50
MODO_ENTRADA = "NORMAL"

VENTANA_ENTRADA_INICIO = 0
VENTANA_ENTRADA_FIN = 30
MARGEN_ENVIO_IQ_SEGUNDOS = 2

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
PARIDAD_LIVE_CSV = "auditoria_paridad_live.csv"
OPERACIONES_PENDIENTES_JSON = "operaciones_abiertas.json"
