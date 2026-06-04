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