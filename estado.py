# ============================================================
# ESTADO COMPARTIDO DEL BOT
# ============================================================
Iq = None
balance_inicial = 0
operaciones_abiertas = []
activos_invalidos = set()
cooldown_activos = {}
activos_cache = []
ultima_actualizacion_activos = 0

# Memoria de zonas operadas
zonas_operadas = {}
senales_pendientes = []
ultimo_reporte_mercados = 0
snapshot_mercados = {}

cooldown_estrategias = {}
metricas_ronda = {
    "mercados_analizados": 0,
    "senales_detectadas": 0,
    "senales_aprobadas": 0,
    "entradas_abiertas": 0,
    "bloqueos": {}
}