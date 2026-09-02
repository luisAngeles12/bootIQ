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
    "uso_cache_activos": 0,
    "fallback_cache_api": 0,
    "mercados_abiertos_recorridos": 0,
    "duplicados_omitidos": 0,
    "descartados_invalidos": 0,
    "descartados_cooldown": 0,
    "activos_evaluados_filtro": 0,
    "descartados_sin_datos": 0,
    "scan_candles_none": 0,
    "scan_velas_insuficientes": 0,
    "scan_formato_op": 0,
    "scan_formato_combinado": 0,
    "scan_calidad": 0,
    "scan_score": 0,
    "scan_tendencia_indefinida": 0,
    "scan_tendencia_debil": 0,
    "scan_rango_debil": 0,
    "scan_invalido_api": 0,
    "scan_excepcion": 0,
    "descartados_score": 0,
    "compatibles_antes_top": 0,
    "senales_detectadas": 0,
    "activos_con_candidatas": 0,
    "candidatas_generadas": 0,
    "familias_generadas": {},
    "candidatas_evaluadas_cerebro": 0,
    "candidatas_que_continuan": 0,
    "senales_aprobadas": 0,
    "cerebro_no_operar": 0,
    "cerebro_sin_autorizacion": 0,
    "autorizadas_directa": 0,
    "autorizadas_protocolo": 0,
    "directas_no_ejecutadas": 0,
    "entradas_abiertas": 0,
    "bloqueos": {}
}