"""
BACKTEST OFICIAL BOOTIQ — CEREBRO UNICO.

Responsabilidad:
- cargar y seleccionar datasets;
- crear ventanas históricas;
- obtener señales desde estrategia.py;
- consultar una sola vez DecisionBootIQ/Cerebro Único;
- respetar NO_OPERAR inmediatamente;
- usar motor_protocolos.py solo para OPERAR_CON_PROTOCOLO;
- simular operaciones autorizadas;
- registrar resultados hipotéticos de señales canceladas;
- generar CSV, aprendizaje y reportes.

Este archivo no decide, no recalcula confianza y no aplica Fase 4 como
autoridad independiente.
"""

import csv
import os

import estado
import estrategia
from motor_protocolos import buscar_entrada_confirmada
from contexto_mercado import detectar_tipo_mercado, diagnostico_calidad_mercado, diagnostico_tendencia_avanzada
from motor_aprendizaje_historico import generar_aprendizaje_desde_resultados


CARPETA_DATA = "data_backtest"
SALIDA = "backtest_bot_real_resultados.csv"

MAX_ACTIVOS_ANALIZAR = 20
LIMITE_DATASETS = 160
PASO_RONDA = 1

# ============================================================
# MODOS OFICIALES DEL BACKTEST
# ============================================================

MODO_BACKTEST_FILTRADO = "FILTRADO"
MODO_BACKTEST_DIAGNOSTICO = "DIAGNOSTICO_COMPLETO"

# Cambiar únicamente esta línea para comparar universos.
MODO_BACKTEST = MODO_BACKTEST_FILTRADO

BUILD_ID = "BOOTIQ_BACKTEST_V4_SIN_DOBLE_DECISION_2026_07_17"
ACTUALIZAR_APRENDIZAJE = False
DATASETS_USADOS_BACKTEST = 0
AUDITORIA_DATASETS = {
    "cargados": 0,
    "validos_tecnicamente": 0,
    "compatibles_filtro": 0,
    "seleccionados": 0,
    "excluidos": {},
}
def reset_auditoria_datasets():
    AUDITORIA_DATASETS["cargados"] = 0
    AUDITORIA_DATASETS["validos_tecnicamente"] = 0
    AUDITORIA_DATASETS["compatibles_filtro"] = 0
    AUDITORIA_DATASETS["seleccionados"] = 0
    AUDITORIA_DATASETS["excluidos"] = {}


def registrar_exclusion_dataset(motivo):
    motivo = str(motivo or "MOTIVO_DESCONOCIDO").upper().strip()

    AUDITORIA_DATASETS["excluidos"][motivo] = (
        AUDITORIA_DATASETS["excluidos"].get(motivo, 0) + 1
    )
def leer_csv_velas(ruta):
    velas = []

    with open(ruta, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            velas.append({
                "tipo": row.get("tipo", ""),
                "activo": row.get("activo", ""),
                "from": int(float(row["from"])),
                "open": float(row["open"]),
                "close": float(row["close"]),
                "max": float(row["max"]),
                "min": float(row["min"]),
                "volume": float(row.get("volume", 0) or 0),
            })

    return sorted(velas, key=lambda x: x["from"])


def cargar_datasets():
    datasets = []

    for archivo in sorted(os.listdir(CARPETA_DATA)):
        if not archivo.endswith(".csv"):
            continue

        ruta = os.path.join(CARPETA_DATA, archivo)
        velas = leer_csv_velas(ruta)

        if len(velas) < 200:
            continue

        datasets.append({
            "tipo": velas[0].get("tipo", ""),
            "activo": velas[0].get("activo", archivo.replace(".csv", "")),
            "velas": velas
        })

    return datasets[:LIMITE_DATASETS]

def evaluar_estabilidad_dataset(dataset):
    """
    Diagnostica un dataset y calcula su score de selección.

    En modo FILTRADO puede marcarlo como no compatible.
    En modo DIAGNOSTICO_COMPLETO conserva todos los datasets
    técnicamente válidos, aunque el mercado sea deficiente.
    """

    velas = dataset.get("velas", [])
    activo = str(dataset.get("activo", "") or "").strip()

    if not activo:
        return None, "ACTIVO_VACIO"

    if len(velas) < 180:
        return None, "VELAS_INSUFICIENTES"

    ventana = velas[-180:]

    try:
        tipo_mercado, _ = detectar_tipo_mercado(ventana)
        diagnostico = diagnostico_calidad_mercado(ventana)
        tendencia = diagnostico_tendencia_avanzada(ventana)
    except Exception as exc:
        dataset["error_diagnostico_dataset"] = str(exc)
        return None, "ERROR_DIAGNOSTICO_MERCADO"

    diagnostico = (
        diagnostico if isinstance(diagnostico, dict) else {}
    )
    tendencia = (
        tendencia if isinstance(tendencia, dict) else {}
    )

    calidad = str(
        diagnostico.get("calidad", "SIN_DATOS")
    ).upper().strip()

    try:
        score = float(diagnostico.get("score", 0) or 0)
    except (TypeError, ValueError):
        score = 0.0

    estado_tendencia = str(
        tendencia.get("estado_tendencia", "INDEFINIDA")
    ).upper().strip()

    try:
        fuerza_tendencia = float(
            tendencia.get("fuerza_tendencia", 0) or 0
        )
    except (TypeError, ValueError):
        fuerza_tendencia = 0.0

    motivo_filtro = ""

    if "-op" in activo.lower():
        motivo_filtro = "ACTIVO_OP_NO_COMPATIBLE"

    elif "/" in activo:
        motivo_filtro = "FORMATO_ACTIVO_NO_COMPATIBLE"

    elif calidad not in {"LIMPIO", "NORMAL"}:
        motivo_filtro = "CALIDAD_MERCADO_NO_COMPATIBLE"

    elif score < 52:
        motivo_filtro = "SCORE_MERCADO_MENOR_52"

    elif estado_tendencia == "INDEFINIDA":
        motivo_filtro = "TENDENCIA_INDEFINIDA"

    elif "DEBIL" in estado_tendencia and score < 62:
        motivo_filtro = "TENDENCIA_DEBIL_SCORE_MENOR_62"

    elif (
        tipo_mercado == "RANGO"
        and "FUERTE" not in estado_tendencia
        and "NORMAL" not in estado_tendencia
    ):
        motivo_filtro = "RANGO_SIN_TENDENCIA_COMPATIBLE"

    score_filtro = score

    if calidad == "LIMPIO":
        score_filtro += 25

    if calidad == "NORMAL":
        score_filtro += 15

    if "FUERTE" in estado_tendencia:
        score_filtro += 25

    if "NORMAL" in estado_tendencia:
        score_filtro += 15

    if tipo_mercado in {
        "TENDENCIA_ALCISTA",
        "TENDENCIA_BAJISTA",
    }:
        score_filtro += 15

    if tipo_mercado == "RANGO":
        score_filtro -= 5

    if "-OTC" in activo.upper():
        score_filtro += 5
    # Mantener el filtro oficial original del backtest.
    if not motivo_filtro and score_filtro < 55:
        motivo_filtro = "SCORE_FILTRO_MENOR_55"

    dataset["score_filtro_dataset"] = score_filtro
    dataset["tipo_mercado_dataset"] = tipo_mercado
    dataset["calidad_mercado_dataset"] = calidad
    dataset["score_mercado_dataset"] = score
    dataset["estado_tendencia_dataset"] = estado_tendencia
    dataset["fuerza_tendencia_dataset"] = fuerza_tendencia

    dataset["compatible_filtro_dataset"] = not bool(
        motivo_filtro
    )
    dataset["motivo_exclusion_dataset"] = motivo_filtro

    if (
        MODO_BACKTEST == MODO_BACKTEST_FILTRADO
        and motivo_filtro
    ):
        return None, motivo_filtro

    return dataset, motivo_filtro

def seleccionar_top_datasets(datasets, limite=20):
    reset_auditoria_datasets()

    AUDITORIA_DATASETS["cargados"] = len(datasets)

    evaluados = []

    for dataset in datasets:
        evaluado, motivo = evaluar_estabilidad_dataset(dataset)

        if evaluado is None:
            registrar_exclusion_dataset(motivo)
            continue

        AUDITORIA_DATASETS["validos_tecnicamente"] += 1

        if evaluado.get("compatible_filtro_dataset") is True:
            AUDITORIA_DATASETS["compatibles_filtro"] += 1

        # Bloqueo real del modo filtrado.
        if MODO_BACKTEST == MODO_BACKTEST_FILTRADO:
            if evaluado.get("compatible_filtro_dataset") is not True:
                registrar_exclusion_dataset(
                    evaluado.get(
                        "motivo_exclusion_dataset",
                        motivo or "NO_COMPATIBLE_FILTRO",
                    )
                )
                continue

        elif motivo:
            registrar_exclusion_dataset(motivo)

        evaluados.append(evaluado)

    evaluados = sorted(
        evaluados,
        key=lambda x: (
            -float(x.get("score_filtro_dataset", 0)),
            str(x.get("activo", "")).upper(),
        ),
    )

    if MODO_BACKTEST == MODO_BACKTEST_FILTRADO:
        seleccionados = evaluados[:limite]
    else:
        seleccionados = evaluados[:LIMITE_DATASETS]

    AUDITORIA_DATASETS["seleccionados"] = len(seleccionados)

    print("\n===== DATASETS SELECCIONADOS PARA BACKTEST =====")
    print("Modo:", MODO_BACKTEST)
    print("Total datasets cargados:", len(datasets))
    print(
        "Datasets válidos técnicamente:",
        AUDITORIA_DATASETS["validos_tecnicamente"],
    )
    print(
        "Compatibles con filtro oficial:",
        AUDITORIA_DATASETS["compatibles_filtro"],
    )
    print("Datasets usados:", len(seleccionados))

    for d in seleccionados:
        print(
            d["activo"],
            "| tipo:", d.get("tipo", "N/A"),
            "| filtro:", round(
                d.get("score_filtro_dataset", 0),
                2,
            ),
            "| mercado:",
            d.get("tipo_mercado_dataset", "N/A"),
            "| calidad:",
            d.get("calidad_mercado_dataset", "N/A"),
            "| score mercado:",
            d.get("score_mercado_dataset", 0),
            "| tendencia:",
            d.get("estado_tendencia_dataset", "N/A"),
            "| fuerza:",
            round(
                d.get("fuerza_tendencia_dataset", 0),
                2,
            ),
            "| compatible:",
            d.get("compatible_filtro_dataset", False),
            "| exclusión:",
            d.get("motivo_exclusion_dataset", ""),
        )

    return seleccionados
def imprimir_auditoria_datasets():
    print("\n===== AUDITORIA DE DATASETS =====")
    print("Modo ejecutado:", MODO_BACKTEST)
    print(
        "Datasets cargados:",
        AUDITORIA_DATASETS["cargados"],
    )
    print(
        "Válidos técnicamente:",
        AUDITORIA_DATASETS["validos_tecnicamente"],
    )
    print(
        "Compatibles con filtro:",
        AUDITORIA_DATASETS["compatibles_filtro"],
    )
    print(
        "Datasets seleccionados:",
        AUDITORIA_DATASETS["seleccionados"],
    )

    print("\nExclusiones detectadas:")

    exclusiones = AUDITORIA_DATASETS["excluidos"]

    if not exclusiones:
        print("Ninguna exclusión registrada.")
        return

    for motivo, cantidad in sorted(
        exclusiones.items(),
        key=lambda item: (-item[1], item[0]),
    ):
        print(
            motivo,
            "| total:",
            cantidad,
        )
def reset_estado():
    estado.cooldown_activos = {}
    estado.zonas_operadas = {}
    estado.snapshot_mercados = {}
    estado.cooldown_estrategias = {}
    estado.senales_pendientes = []
    estado.operaciones_abiertas = []


def analizar_activo_con_ventana(activo, ventana):
    data = {
        "open": [v["open"] for v in ventana],
        "close": [v["close"] for v in ventana],
        "high": [v["max"] for v in ventana],
        "low": [v["min"] for v in ventana],
    }

    original_obtener_velas = estrategia.obtener_velas
    estrategia.obtener_velas = lambda activo_param: data

    try:
        senal = estrategia.analizar_activo(
            activo,
            modo_backtest_diagnostico=True
        )
    finally:
        estrategia.obtener_velas = original_obtener_velas

    return senal


def resultado_binario(velas, index_entrada, direccion):
    entrada = velas[index_entrada]["close"]
    vela_siguiente = velas[index_entrada + 1]

    cierre = vela_siguiente["close"]
    apertura_siguiente = vela_siguiente["open"]
    high_siguiente = vela_siguiente["max"]
    low_siguiente = vela_siguiente["min"]

    movimiento = cierre - entrada

    if direccion == "call":
        resultado = "WIN" if cierre > entrada else "LOSS"
        distancia_resultado = cierre - entrada
        excursion_favor = high_siguiente - entrada
        excursion_contra = entrada - low_siguiente

    elif direccion == "put":
        resultado = "WIN" if cierre < entrada else "LOSS"
        distancia_resultado = entrada - cierre
        excursion_favor = entrada - low_siguiente
        excursion_contra = high_siguiente - entrada

    else:
        resultado = "LOSS"
        distancia_resultado = 0
        excursion_favor = 0
        excursion_contra = 0

    cuerpo_siguiente = abs(cierre - apertura_siguiente)
    rango_siguiente = high_siguiente - low_siguiente

    if rango_siguiente > 0:
        fuerza_cierre = cuerpo_siguiente / rango_siguiente
    else:
        fuerza_cierre = 0

    return {
        "resultado": resultado,
        "movimiento": round(movimiento, 8),
        "distancia_resultado": round(distancia_resultado, 8),
        "excursion_favor": round(excursion_favor, 8),
        "excursion_contra": round(excursion_contra, 8),
        "fuerza_cierre_siguiente": round(fuerza_cierre, 4),
        "open_siguiente": apertura_siguiente,
        "close_siguiente": cierre,
        "high_siguiente": high_siguiente,
        "low_siguiente": low_siguiente,
    }

def _texto(valor):
    if isinstance(valor, list):
        return " | ".join(str(x) for x in valor)
    if valor is None:
        return ""
    return str(valor)


def crear_registro_resultado(
    senal,
    velas,
    idx,
    idx_entrada,
    motivo_ejecucion,
    estado_operacion,
    decision_bootiq=None,
):
    """
    Construye una fila del CSV sin volver a evaluar la señal.

    Para señales canceladas se calcula un resultado hipotético usando la vela
    inmediatamente posterior a la señal. Ese resultado sirve para medir la
    calidad del filtro, pero no convierte la señal en una operación ejecutada.
    """

    if idx_entrada is None:
        idx_entrada = idx

    if idx + 1 >= len(velas):
        raise IndexError(
            "No existe una vela posterior a la señal para "
            "calcular el resultado hipotético."
        )

    if idx_entrada + 1 >= len(velas):
        raise IndexError(
            "No existe una vela posterior a la entrada para "
            "calcular el resultado real."
        )

    direccion = senal.get("direccion", "")

    # Resultado fijo del universo:
    # siempre se calcula desde la vela donde nació la señal.
    info_hipotetico = resultado_binario(
        velas,
        idx,
        direccion,
    )

    # Resultado de la entrada usada por la operación.
    # Para canceladas, idx_entrada normalmente será igual a idx.
    info_resultado = resultado_binario(
        velas,
        idx_entrada,
        direccion,
    )
    decision_bootiq = (
        decision_bootiq
        if isinstance(decision_bootiq, dict)
        else {}
    )
    decision_bootiq_plana = {}

    decision_oficial = str(
        senal.get("cerebro_unico_decision", "NO_OPERAR")
        or "NO_OPERAR"
    ).upper().strip()

    registro = {
        "tipo": senal.get("tipo", ""),
        "activo": senal.get("activo", ""),
        "fecha": velas[idx_entrada]["from"],
        "direccion": senal.get("direccion", ""),
        "patron": senal.get("patron", ""),
        "puntaje": senal.get("puntaje", 0),
        "prioridad": senal.get("prioridad", 0),
        "score_final": senal.get("score_final", 0),

        "consenso": senal.get("consenso", 0),
        "nivel_consenso": senal.get("nivel_consenso", ""),
        "ajuste_consenso": senal.get("ajuste_consenso", 0),
        "razones_consenso": _texto(
            senal.get("razones_consenso", "")
        ),
        "calidad": senal.get("calidad", ""),
        "rsi": senal.get("rsi", ""),

        "tipo_mercado": senal.get("tipo_mercado", ""),
        "calidad_mercado": senal.get("calidad_mercado", ""),
        "score_mercado": senal.get("score_mercado", 0),
        "estado_tendencia": senal.get("estado_tendencia", ""),
        "fuerza_tendencia": senal.get("fuerza_tendencia", 0),
        "direccion_tendencia": senal.get("direccion_tendencia", ""),

        "accion_precio": senal.get("accion_precio", ""),
        "razon_accion_precio": _texto(
            senal.get("razon_accion_precio", "")
        ),
        "pa_tipo": senal.get("pa_tipo", ""),
        "pa_direccion": senal.get("pa_direccion", ""),
        "pa_fuerza": senal.get("pa_fuerza", 0),
        "pa_razon": _texto(senal.get("pa_razon", "")),

        "base_estrategia": senal.get("base_estrategia", ""),
        "riesgos_base": _texto(senal.get("riesgos_base", "")),
        "fortalezas_base": _texto(
            senal.get("fortalezas_base", "")
        ),

        "ruptura_confirmada": senal.get(
            "ruptura_confirmada", False
        ),
        "tipo_ruptura": senal.get("tipo_ruptura", ""),
        "razon_ruptura": _texto(
            senal.get("razon_ruptura", "")
        ),

        "tipo_setup": senal.get("tipo_setup", "INDEFINIDO"),
        "calidad_setup": senal.get("calidad_setup", "MEDIA"),
        "modo_entrada_setup": senal.get(
            "modo_entrada_setup", "DIRECTA"
        ),
        "puntaje_extra_setup": senal.get(
            "puntaje_extra_setup", 0
        ),
        "riesgo_extra_setup": senal.get(
            "riesgo_extra_setup", 0
        ),
        "balance_setup": senal.get("balance_setup", 0),
        "a_favor_tendencia": senal.get(
            "a_favor_tendencia", False
        ),
        "razones_setup": _texto(
            senal.get("razones_setup", "")
        ),
        "familia_setup": senal.get("familia_setup", ""),
        "subtipo_setup": senal.get("subtipo_setup", ""),
        "protocolo_sugerido": senal.get(
            "protocolo_sugerido", ""
        ),
        "nivel_setup": senal.get("nivel_setup", ""),
        "estado_setup": senal.get("estado_setup", ""),
        "confianza_setup": senal.get("confianza_setup", 0),
        "razones_clasificador_setup": _texto(
            senal.get("razones_clasificador_setup", "")
        ),
        "riesgo_protocolo": senal.get("riesgo_protocolo", 0),
        "nivel_riesgo_protocolo": senal.get(
            "nivel_riesgo_protocolo", ""
        ),
        "razon_riesgo_protocolo": _texto(
            senal.get("razon_riesgo_protocolo", "")
        ),

        "indice_confirmacion_ia": senal.get(
            "indice_confirmacion_ia", 0
        ),
        "nivel_confirmacion_ia": senal.get(
            "nivel_confirmacion_ia", ""
        ),
        "accion_confirmacion_ia": senal.get(
            "accion_confirmacion_ia", ""
        ),
        "razon_confirmacion_ia": _texto(
            senal.get("razon_confirmacion_ia", "")
        ),

        "idx_senal": idx,
        "idx_entrada": idx_entrada,
        "motivo_ejecucion": motivo_ejecucion,
        "estado_operacion": estado_operacion,
        "espera_velas": idx_entrada - idx,

        # Campos oficiales del Cerebro Único.
        "cerebro_unico_decision": decision_oficial,
        "cerebro_unico_decision_legacy": senal.get(
            "cerebro_unico_decision_legacy", decision_oficial
        ),
        "cerebro_unico_operar": bool(
            senal.get("cerebro_unico_operar", False)
        ),
        "cerebro_unico_confianza": senal.get(
            "cerebro_unico_confianza", 0
        ),
        "cerebro_unico_requiere_protocolo": bool(
            senal.get(
                "cerebro_unico_requiere_protocolo", False
            )
        ),
        "cerebro_unico_modo_ejecucion": senal.get(
            "cerebro_unico_modo_ejecucion", "BLOQUEADA"
        ),
        "cerebro_unico_bloquear_por_riesgo": bool(
            senal.get(
                "cerebro_unico_bloquear_por_riesgo", False
            )
        ),
        "cerebro_unico_riesgo": senal.get(
            "cerebro_unico_riesgo", ""
        ),
        "cerebro_unico_riesgo_puntos": senal.get(
            "cerebro_unico_riesgo_puntos", 0
        ),
        "cerebro_unico_motivos": _texto(
            senal.get("cerebro_unico_motivos", "")
        ),

        # Alias legacy. Solo reflejan al Cerebro Único.
        "fase4_evaluada": senal.get("fase4_evaluada", True),
        "fase4_permitir_operacion": bool(
            senal.get(
                "fase4_permitir_operacion",
                senal.get("cerebro_unico_operar", False),
            )
        ),
        "fase4_modo": senal.get(
            "fase4_modo",
            senal.get(
                "cerebro_unico_modo_ejecucion", "BLOQUEADA"
            ),
        ),
        "fase4_confianza": senal.get(
            "fase4_confianza",
            senal.get("cerebro_unico_confianza", 0),
        ),
        "fase4_decision": senal.get(
            "fase4_decision", decision_oficial
        ),
        "fase4_debe_bloquear": bool(
            senal.get(
                "fase4_debe_bloquear",
                not senal.get("cerebro_unico_operar", False),
            )
        ),
        "fase4_motivo": _texto(
            senal.get(
                "fase4_motivo",
                senal.get("cerebro_unico_motivos", ""),
            )
        ),

        "resultado": info_resultado["resultado"],
        "resultado_hipotetico": info_hipotetico["resultado"],

        "fecha_senal": velas[idx]["from"],
        "precio_entrada_hipotetico": velas[idx]["close"],
        "precio_cierre_hipotetico": velas[idx + 1]["close"],

        "precio_entrada": velas[idx_entrada]["close"],
        "precio_cierre": velas[idx_entrada + 1]["close"],

        "movimiento": info_resultado["movimiento"],
        "distancia_resultado": info_resultado[
            "distancia_resultado"
        ],
        "excursion_favor": info_resultado["excursion_favor"],
        "excursion_contra": info_resultado["excursion_contra"],
        "fuerza_cierre_siguiente": info_resultado[
            "fuerza_cierre_siguiente"
        ],
        "open_siguiente": info_resultado["open_siguiente"],
        "close_siguiente": info_resultado["close_siguiente"],
        "high_siguiente": info_resultado["high_siguiente"],
        "low_siguiente": info_resultado["low_siguiente"],

        "decision_unificada_accion": senal.get(
            "decision_unificada_accion", decision_oficial
        ),
        "decision_unificada_score": senal.get(
            "decision_unificada_score", 0
        ),
        "decision_unificada_confianza": senal.get(
            "decision_unificada_confianza", 0
        ),
        "decision_unificada_razones": _texto(
            senal.get("decision_unificada_razones", "")
        ),
        "decision_unificada_advertencias": _texto(
            senal.get("decision_unificada_advertencias", "")
        ),
        "decision_unificada_bloqueos": _texto(
            senal.get("decision_unificada_bloqueos", "")
        ),
        "razon": _texto(senal.get("razon", "")),
        "ajuste_ponderacion": senal.get(
            "ajuste_ponderacion", 0
        ),
        "motivos_ponderacion": _texto(
            senal.get("motivos_ponderacion", "")
        ),
        "pesos_aplicados": _texto(
            senal.get("pesos_aplicados", "")
        ),
        "confianza_final_cerebro": senal.get(
            "confianza_final_cerebro",
            senal.get("cerebro_unico_confianza", 0),
        ),
         # ==================================================
        # AUDITORÍA INTERNA DEL CEREBRO ÚNICO
        # ==================================================

        "auditoria_confianza_base": senal.get(
            "auditoria_confianza_base",
            0,
        ),

        "auditoria_ajuste_aprendizaje": senal.get(
            "auditoria_ajuste_aprendizaje",
            0,
        ),

        "auditoria_ajuste_price_action": senal.get(
            "auditoria_ajuste_price_action",
            0,
        ),

        "auditoria_ajuste_mercado": senal.get(
            "auditoria_ajuste_mercado",
            0,
        ),

        "auditoria_ajuste_estrategia": senal.get(
            "auditoria_ajuste_estrategia",
            0,
        ),

        "auditoria_ajuste_evidencias": senal.get(
            "auditoria_ajuste_evidencias",
            0,
        ),

        "auditoria_ajuste_ponderacion": senal.get(
            "auditoria_ajuste_ponderacion",
            0,
        ),

        "auditoria_confianza_antes_ponderacion": senal.get(
            "auditoria_confianza_antes_ponderacion",
            0,
        ),

        "auditoria_confianza_final": senal.get(
            "auditoria_confianza_final",
            senal.get("cerebro_unico_confianza", 0),
        ),

        "auditoria_motivos_price_action": senal.get(
            "auditoria_motivos_price_action",
            "",
        ),

        "auditoria_motivos_mercado": senal.get(
            "auditoria_motivos_mercado",
            "",
        ),

        "auditoria_motivos_estrategia": senal.get(
            "auditoria_motivos_estrategia",
            "",
        ),
    }

    registro.update(decision_bootiq_plana)
    return registro


def ejecutar_backtest(datasets):
    """
    Orquestador oficial del backtest BootIQ.

    Flujo:
        estrategia -> DecisionBootIQ/Cerebro Único
        -> cancelación inmediata de NO_OPERAR
        -> protocolo solo cuando sea requerido
        -> entrada directa cuando sea autorizada
        -> simulación y registro

    Este archivo no crea decisiones propias.
    """

    resultados = []

    if not datasets:
        print("No hay datasets cargados en data_backtest.")
        return resultados

    max_len = min(len(d["velas"]) for d in datasets)
    total_rondas = len(range(180, max_len - 2, PASO_RONDA))
    ronda = 0

    for i in range(180, max_len - 2, PASO_RONDA):
        ronda += 1

        if ronda % 25 == 0:
            print("Progreso:", ronda, "/", total_rondas)

        senales_ronda = []

        for data in datasets:
            activo = data["activo"]
            tipo = data["tipo"]
            velas = data["velas"]
            ventana = velas[i - 180:i + 1]

            senal = analizar_activo_con_ventana(activo, ventana)

            if senal is None:
                continue

            if not isinstance(senal, dict):
                continue

            senal["tipo"] = tipo
            senal["_velas"] = velas
            senal["_index"] = i
            senales_ronda.append(senal)

        senales_ronda.sort(
            key=lambda x: (
                x.get("score_final", 0),
                x.get("prioridad", 0),
                x.get("puntaje", 0),
            ),
            reverse=True,
        )

        if ronda % 100 == 0:
            print(
                "Ronda:",
                ronda,
                "Señales:",
                len(senales_ronda),
            )

        for senal in senales_ronda[:MAX_ACTIVOS_ANALIZAR]:
            velas = senal["_velas"]
            idx = senal["_index"]

            # La señal ya viene evaluada por estrategia.py usando el contexto
            # real de mercado. Aquí NO se vuelve a llamar al Cerebro Único.
            decision_bootiq = {}

            decision_oficial = str(
                senal.get(
                    "cerebro_unico_decision",
                    senal.get("decision_unificada_accion", "NO_OPERAR"),
                )
                or "NO_OPERAR"
            ).upper().strip()

            operar = bool(
                senal.get(
                    "cerebro_unico_operar",
                    decision_oficial in {"OPERAR", "OPERAR_CON_PROTOCOLO"},
                )
            )

            requiere_protocolo = bool(
                senal.get(
                    "cerebro_unico_requiere_protocolo",
                    decision_oficial == "OPERAR_CON_PROTOCOLO",
                )
            )

            modo_por_decision = {
                "OPERAR": "DIRECTA",
                "OPERAR_CON_PROTOCOLO": "PROTOCOLO",
                "NO_OPERAR": "BLOQUEADA",
                "ERROR": "BLOQUEADA",
            }

            modo_ejecucion = str(
                senal.get(
                    "cerebro_unico_modo_ejecucion",
                    modo_por_decision.get(decision_oficial, "BLOQUEADA"),
                )
                or modo_por_decision.get(decision_oficial, "BLOQUEADA")
            ).upper().strip()

            # Normaliza contratos antiguos incompletos sin crear otra decisión.
            if decision_oficial == "OPERAR":
                operar = True
                requiere_protocolo = False
                modo_ejecucion = "DIRECTA"
            elif decision_oficial == "OPERAR_CON_PROTOCOLO":
                operar = True
                requiere_protocolo = True
                modo_ejecucion = "PROTOCOLO"
            else:
                operar = False
                requiere_protocolo = False
                modo_ejecucion = "BLOQUEADA"

            senal["cerebro_unico_operar"] = operar
            senal["cerebro_unico_requiere_protocolo"] = requiere_protocolo
            senal["cerebro_unico_modo_ejecucion"] = modo_ejecucion

            # Cierre seguro ante cualquier inconsistencia.
            if (
                not operar
                or decision_oficial in {"NO_OPERAR", "ERROR"}
                or modo_ejecucion == "BLOQUEADA"
            ):
                resultados.append(
                    crear_registro_resultado(
                        senal=senal,
                        velas=velas,
                        idx=idx,
                        idx_entrada=idx,
                        motivo_ejecucion=(
                            "CANCELADA_CEREBRO_UNICO_"
                            + decision_oficial
                        ),
                        estado_operacion="CANCELADA_CEREBRO",
                        decision_bootiq=decision_bootiq,
                    )
                )
                continue

            # Solo las operaciones condicionadas pasan al protocolo.
            if (
                requiere_protocolo
                or decision_oficial == "OPERAR_CON_PROTOCOLO"
                or modo_ejecucion == "PROTOCOLO"
            ):
                idx_entrada, motivo_ejecucion = (
                    buscar_entrada_confirmada(
                        velas,
                        idx,
                        senal,
                    )
                )

                if idx_entrada is None:
                    resultados.append(
                        crear_registro_resultado(
                            senal=senal,
                            velas=velas,
                            idx=idx,
                            idx_entrada=idx,
                            motivo_ejecucion=motivo_ejecucion,
                            estado_operacion=(
                                "CANCELADA_PROTOCOLO"
                            ),
                            decision_bootiq=decision_bootiq,
                        )
                    )
                    continue

                resultados.append(
                    crear_registro_resultado(
                        senal=senal,
                        velas=velas,
                        idx=idx,
                        idx_entrada=idx_entrada,
                        motivo_ejecucion=motivo_ejecucion,
                        estado_operacion="OPERADA_PROTOCOLO",
                        decision_bootiq=decision_bootiq,
                    )
                )
                continue

            # OPERAR directo: no debe pasar por motor_protocolos.py.
            if decision_oficial == "OPERAR":
                resultados.append(
                    crear_registro_resultado(
                        senal=senal,
                        velas=velas,
                        idx=idx,
                        idx_entrada=idx,
                        motivo_ejecucion=(
                            "OPERACION_DIRECTA_CEREBRO_UNICO"
                        ),
                        estado_operacion="OPERADA_DIRECTA",
                        decision_bootiq=decision_bootiq,
                    )
                )
                continue

            # Toda salida no reconocida se bloquea.
            resultados.append(
                crear_registro_resultado(
                    senal=senal,
                    velas=velas,
                    idx=idx,
                    idx_entrada=idx,
                    motivo_ejecucion=(
                        "CANCELADA_SALIDA_CEREBRO_NO_RECONOCIDA_"
                        + decision_oficial
                    ),
                    estado_operacion="CANCELADA_CEREBRO",
                    decision_bootiq=decision_bootiq,
                )
            )

    return resultados


def guardar_resultados(resultados):
    campos = [
        "tipo",
        "activo",
        "fecha",
        "direccion",
        "patron",
        "puntaje",
        "prioridad",
        "score_final",
        "consenso",
        "nivel_consenso",
        "ajuste_consenso",
        "razones_consenso",
        "calidad",
        "rsi",

        "tipo_mercado",
        "calidad_mercado",
        "score_mercado",
        "estado_tendencia",
        "fuerza_tendencia",
        "direccion_tendencia",

        "accion_precio",
        "razon_accion_precio",
        "pa_tipo",
        "pa_direccion",
        "pa_fuerza",
        "pa_razon",

        # =========================
        # NUEVO DIAGNOSTICO BASE
        # =========================
        "base_estrategia",
        "riesgos_base",
        "fortalezas_base",

        "ruptura_confirmada",
        "tipo_ruptura",
        "razon_ruptura",
        
        "tipo_setup",
        "calidad_setup",
        "modo_entrada_setup",
        "puntaje_extra_setup",
        "riesgo_extra_setup",
        "balance_setup",
        "a_favor_tendencia",
        "razones_setup",
        "familia_setup",
        "subtipo_setup",
        "protocolo_sugerido",
        "nivel_setup",
        "estado_setup",
        "confianza_setup",
        "razones_clasificador_setup",
        "riesgo_protocolo",
        "nivel_riesgo_protocolo",
        "razon_riesgo_protocolo",
        
        "indice_confirmacion_ia",
        "nivel_confirmacion_ia",
        "accion_confirmacion_ia",
        "razon_confirmacion_ia",
        "rango_indice_confirmacion_ia",
        "idx_senal",
        "idx_entrada",
        "motivo_ejecucion",
        "estado_operacion",
        "espera_velas",

        "cerebro_unico_decision",
        "cerebro_unico_decision_legacy",
        "cerebro_unico_operar",
        "cerebro_unico_confianza",
        "cerebro_unico_requiere_protocolo",
        "cerebro_unico_modo_ejecucion",
        "cerebro_unico_bloquear_por_riesgo",
        "cerebro_unico_riesgo",
        "cerebro_unico_riesgo_puntos",
        "cerebro_unico_motivos",

        "fase4_evaluada",
        "fase4_permitir_operacion",
        "fase4_modo",
        "fase4_confianza",
        "fase4_decision",
        "fase4_debe_bloquear",
        "fase4_motivo",

        "resultado",
        "resultado_hipotetico",
        "fecha_senal",
        "precio_entrada_hipotetico",
        "precio_cierre_hipotetico",
        "precio_entrada",
        "precio_cierre",
        "movimiento",
        "distancia_resultado",
        "excursion_favor",
        "excursion_contra",
        "fuerza_cierre_siguiente",
        "open_siguiente",
        "close_siguiente",
        "high_siguiente",
        "low_siguiente",

        "bootiq_identidad_activo",
        "bootiq_identidad_tipo",
        "bootiq_identidad_direccion",
        "bootiq_identidad_patron",

        "bootiq_estrategia_puntaje",
        "bootiq_estrategia_prioridad",
        "bootiq_estrategia_score_final",
        "bootiq_estrategia_calidad",

        "bootiq_mercado_tipo_mercado",
        "bootiq_mercado_calidad_mercado",
        "bootiq_mercado_score_mercado",
        "bootiq_mercado_estado_tendencia",
        "bootiq_mercado_fuerza_tendencia",
        "bootiq_mercado_direccion_tendencia",

        "bootiq_price_action_accion_precio",
        "bootiq_price_action_pa_tipo",
        "bootiq_price_action_pa_direccion",
        "bootiq_price_action_pa_fuerza",

        "bootiq_setup_tipo_setup",
        "bootiq_setup_calidad_setup",
        "bootiq_setup_modo_entrada_setup",
        "bootiq_setup_balance_setup",
        "bootiq_setup_familia_setup",
        "bootiq_setup_subtipo_setup",

        "bootiq_consenso_consenso",
        "bootiq_consenso_nivel_consenso",

        "bootiq_protocolo_protocolo_sugerido",
        "bootiq_protocolo_nivel_riesgo_protocolo",
        "bootiq_protocolo_indice_confirmacion_ia",
        "bootiq_protocolo_accion_confirmacion_ia",

        "bootiq_fase4_fase4_confianza",
        "bootiq_fase4_fase4_decision",
        "bootiq_fase4_fase4_debe_bloquear",

        "bootiq_decision_unificada_accion",
        "bootiq_decision_unificada_score",
        "bootiq_decision_unificada_confianza",
        
        "ajuste_ponderacion",
        "motivos_ponderacion",
        "pesos_aplicados",
        "confianza_final_cerebro",
        
        "auditoria_confianza_base",
        "auditoria_ajuste_aprendizaje",
        "auditoria_ajuste_price_action",
        "auditoria_ajuste_mercado",
        "auditoria_ajuste_estrategia",
        "auditoria_ajuste_evidencias",
        "auditoria_ajuste_ponderacion",
        "auditoria_confianza_antes_ponderacion",
        "auditoria_confianza_final",
        "auditoria_motivos_price_action",
        "auditoria_motivos_mercado",
        "auditoria_motivos_estrategia",

        "bootiq_resultado_estado_operacion",
        "bootiq_resultado_motivo_ejecucion",
        "bootiq_resultado_resultado",
        "razon",
    ]
    with open(SALIDA, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=campos, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(resultados)

def resumen_por_campo(
    resultados,
    campo,
    campo_resultado="resultado_hipotetico",
):
    """
    Agrupa registros por un campo y calcula el winrate usando
    el resultado indicado.

    Por defecto utiliza resultado_hipotetico, porque los reportes
    generales deben medir la calidad de la señal original.
    """

    grupos = {}

    for r in resultados:
        clave = r.get(campo, "")

        if clave not in grupos:
            grupos[clave] = {
                "total": 0,
                "win": 0,
            }

        grupos[clave]["total"] += 1

        if r.get(campo_resultado) == "WIN":
            grupos[clave]["win"] += 1

    filas = []

    for clave, datos in grupos.items():
        total = datos["total"]
        wins = datos["win"]
        losses = total - wins

        winrate = (
            round((wins / total) * 100, 2)
            if total
            else 0
        )

        filas.append(
            (
                clave,
                total,
                wins,
                losses,
                winrate,
            )
        )

    return sorted(
        filas,
        key=lambda x: x[4],
        reverse=True,
    )

def resumen_por_lista(
    resultados,
    campo,
    campo_resultado="resultado_hipotetico",
):
    """
    Descompone valores separados por | y calcula su rendimiento.

    Por defecto usa resultado_hipotetico para no mezclar la entrada
    original con la entrada confirmada por protocolo.
    """

    grupos = {}

    for r in resultados:
        valor = r.get(campo, "")

        if not valor:
            continue

        items = str(valor).split("|")

        for item in items:
            item = item.strip()

            if not item:
                continue

            if item not in grupos:
                grupos[item] = {
                    "total": 0,
                    "win": 0,
                }

            grupos[item]["total"] += 1

            if r.get(campo_resultado) == "WIN":
                grupos[item]["win"] += 1

    filas = []

    for clave, datos in grupos.items():
        total = datos["total"]
        wins = datos["win"]
        losses = total - wins

        winrate = (
            round((wins / total) * 100, 2)
            if total
            else 0
        )

        filas.append(
            (
                clave,
                total,
                wins,
                losses,
                winrate,
            )
        )

    return sorted(
        filas,
        key=lambda x: x[1],
        reverse=True,
    )

def imprimir_tabla_resumen(titulo, filas, limite=20):
    print("\n=====", titulo, "=====")

    for clave, total, win, loss, winrate in filas[:limite]:
        print(
            clave,
            "| total:", total,
            "| win:", win,
            "| loss:", loss,
            "| winrate:", str(winrate) + "%"
        )

def imprimir_impacto_cerebro(resultados):
    if not resultados:
        return

    def calcular_wr(filas, campo="resultado"):
         total = len(filas)
         wins = sum(
             1 for r in filas
             if r.get(campo) == "WIN"
         )
         losses = total - wins
         wr = round((wins / total) * 100, 2) if total else 0
         return total, wins, losses, wr
    autorizadas = [
        r for r in resultados
        if r.get("cerebro_unico_operar") is True
    ]
    rechazadas = [
        r for r in resultados
        if r.get("cerebro_unico_operar") is not True
    ]
    directas = [
        r for r in resultados
        if r.get("estado_operacion") == "OPERADA_DIRECTA"
    ]
    por_protocolo = [
        r for r in resultados
        if r.get("estado_operacion") == "OPERADA_PROTOCOLO"
    ]
    canceladas_protocolo = [
        r for r in resultados
        if r.get("estado_operacion") == "CANCELADA_PROTOCOLO"
    ]

    # Universo y decisiones del Cerebro:
    # se evalúan desde la señal original.
    total, wins, losses, wr = calcular_wr(
        resultados,
        campo="resultado_hipotetico",
    )
    
    a_total, a_win, a_loss, a_wr = calcular_wr(
        autorizadas,
        campo="resultado_hipotetico",
    )
    
    r_total, r_win, r_loss, r_wr = calcular_wr(
        rechazadas,
        campo="resultado_hipotetico",
    )
    
    # Operaciones ejecutadas:
    # se evalúan desde la entrada real.
    d_total, d_win, d_loss, d_wr = calcular_wr(
        directas,
        campo="resultado",
    )
    
    p_total, p_win, p_loss, p_wr = calcular_wr(
        por_protocolo,
        campo="resultado",
    )
    
    # Canceladas por protocolo:
    # se evalúan hipotéticamente desde la señal original.
    cp_total, cp_win, cp_loss, cp_wr = calcular_wr(
        canceladas_protocolo,
        campo="resultado_hipotetico",
    )

    precision_bloqueo = (
        round((r_loss / r_total) * 100, 2)
        if r_total
        else 0
    )

    print("\n===== IMPACTO CEREBRO UNICO =====")
    print("Señales evaluadas:", total)
    print("WIN hipotéticos:", wins)
    print("LOSS hipotéticos:", losses)
    print("Winrate universo:", str(wr) + "%")
    print("----------------------------")
    print("Autorizadas:", a_total)
    print("WIN autorizadas:", a_win)
    print("LOSS autorizadas:", a_loss)
    print("Winrate autorizadas:", str(a_wr) + "%")
    print("----------------------------")
    print("Rechazadas:", r_total)
    print("WIN rechazadas:", r_win)
    print("LOSS rechazadas:", r_loss)
    print("Winrate rechazadas:", str(r_wr) + "%")
    print("Precisión del bloqueo:", str(precision_bloqueo) + "%")
    print("----------------------------")
    print(
        "Operadas directas:",
        d_total,
        "| winrate:",
        str(d_wr) + "%",
    )
    print(
        "Operadas por protocolo:",
        p_total,
        "| winrate:",
        str(p_wr) + "%",
    )
    print(
        "Canceladas por protocolo:",
        cp_total,
        "| winrate hipotético:",
        str(cp_wr) + "%",
    )
    print("================================\n")


def clasificar_indice_confirmacion_ia(valor):
    try:
        valor = float(valor)
    except Exception:
        return "SIN_INDICE"

    if valor >= 90:
        return "90_100_PREMIUM"
    if valor >= 75:
        return "75_89_ALTO"
    if valor >= 60:
        return "60_74_MEDIO"
    if valor >= 45:
        return "45_59_BAJO"
    return "0_44_MUY_BAJO"
def imprimir_resumen(resultados):
    operadas = [
        r for r in resultados
        if str(r.get("estado_operacion", "")).startswith("OPERADA")
    ]
    for r in resultados:
        r["rango_indice_confirmacion_ia"] = clasificar_indice_confirmacion_ia(
            r.get("indice_confirmacion_ia", 0)
        )
    total = len(operadas)
    wins = sum(1 for r in operadas if r["resultado"] == "WIN")
    losses = total - wins
    wr = round((wins / total) * 100, 2) if total else 0
    print("\n===== BACKTEST BOT REAL =====")
    print("Datasets:", DATASETS_USADOS_BACKTEST)
    print("Paso ronda:", PASO_RONDA)
    print("Total operaciones:", total)
    print("Ganadas:", wins)
    print("Perdidas:", losses)
    print("Winrate:", wr, "%")
    print("============================\n")
    imprimir_impacto_cerebro(resultados)
    print("Total señales evaluadas:", len(resultados))
    print("Operadas:", len(operadas))
    print("Canceladas Cerebro:", len([r for r in resultados if r.get("estado_operacion") == "CANCELADA_CEREBRO"]))
    print("Canceladas Protocolo:", len([r for r in resultados if r.get("estado_operacion") == "CANCELADA_PROTOCOLO"]))
    reportes = [
        ("POR ESTRATEGIA", "patron"),
        ("POR BASE ESTRATEGIA", "base_estrategia"),
        ("POR ACCION PRECIO", "accion_precio"),
        ("POR PA PROFESIONAL", "pa_tipo"),
        ("POR DIRECCION PA", "pa_direccion"),
        ("POR RUPTURA", "tipo_ruptura"),
        ("POR TIPO SETUP", "tipo_setup"),
        ("POR FAMILIA SETUP", "familia_setup"),
        ("POR SUBTIPO SETUP", "subtipo_setup"),
        ("POR PROTOCOLO SUGERIDO", "protocolo_sugerido"),
        ("POR NIVEL SETUP", "nivel_setup"),
        ("POR ESTADO SETUP", "estado_setup"),
        ("POR CALIDAD SETUP", "calidad_setup"),
        ("POR MODO ENTRADA SETUP", "modo_entrada_setup"),
        ("POR NIVEL RIESGO PROTOCOLO", "nivel_riesgo_protocolo"),
        ("POR NIVEL CONFIRMACION IA", "nivel_confirmacion_ia"),
        ("POR ACCION CONFIRMACION IA", "accion_confirmacion_ia"),
        ("POR INDICE CONFIRMACION IA", "rango_indice_confirmacion_ia"),
        ("POR SCORE FINAL", "score_final"),
        ("POR NIVEL CONSENSO", "nivel_consenso"),
        ("POR DECISION BOOTIQ", "decision_unificada_accion"),
        ("POR CONFIANZA BOOTIQ", "decision_unificada_confianza"),
        ("POR TIPO", "tipo"),
        ("POR MERCADO", "tipo_mercado"),
        ("POR CALIDAD MERCADO", "calidad_mercado"),
        ("POR TENDENCIA", "estado_tendencia"),
        ("POR ACTIVO", "activo"),
        ("POR EVIDENCIA PA", "bootiq_evidencias_price_action"),
        ("POR EVIDENCIA MERCADO", "bootiq_evidencias_mercado"),
        ("POR CEREBRO UNICO DECISION", "cerebro_unico_decision"),
        ("POR CEREBRO UNICO RIESGO", "cerebro_unico_riesgo"),
        (
            "POR CEREBRO UNICO MODO EJECUCION",
            "cerebro_unico_modo_ejecucion",
        ),
        (
            "POR CEREBRO UNICO REQUIERE PROTOCOLO",
            "cerebro_unico_requiere_protocolo",
        ),
        ("POR AJUSTE PONDERACION", "ajuste_ponderacion"),
        ("POR CONFIANZA FINAL CEREBRO", "confianza_final_cerebro"),
        (
            "AUDITORIA POR CONFIANZA BASE",
            "auditoria_confianza_base",
        ),
        (
            "AUDITORIA POR AJUSTE APRENDIZAJE",
            "auditoria_ajuste_aprendizaje",
        ),
        (
            "AUDITORIA POR AJUSTE PRICE ACTION",
            "auditoria_ajuste_price_action",
        ),
        (
            "AUDITORIA POR AJUSTE MERCADO",
            "auditoria_ajuste_mercado",
        ),
        (
            "AUDITORIA POR AJUSTE ESTRATEGIA",
            "auditoria_ajuste_estrategia",
        ),
        (
            "AUDITORIA POR AJUSTE EVIDENCIAS",
            "auditoria_ajuste_evidencias",
        ),
        (
            "AUDITORIA POR AJUSTE PONDERACION",
            "auditoria_ajuste_ponderacion",
        ),
        (
            "AUDITORIA CONFIANZA ANTES PONDERACION",
            "auditoria_confianza_antes_ponderacion",
        ),
        (
            "AUDITORIA CONFIANZA FINAL",
            "auditoria_confianza_final",
        ),
    ]

    imprimir_tabla_resumen(
        "POR ESTADO OPERACION",
        resumen_por_campo(
            resultados,
            "estado_operacion",
            campo_resultado="resultado",
        ),
        limite=10,
    )

    for titulo, campo in reportes:
        imprimir_tabla_resumen(
            titulo,
            resumen_por_campo(
                resultados,
                campo,
                campo_resultado="resultado_hipotetico",
            ),
            limite=20,
        )

    # Reportes de ejecución real.
    imprimir_tabla_resumen(
        "POR MOTIVO EJECUCION",
        resumen_por_campo(
            resultados,
            "motivo_ejecucion",
            campo_resultado="resultado",
        ),
        limite=30,
    )

    imprimir_tabla_resumen(
        "POR ESPERA VELAS",
        resumen_por_campo(
            resultados,
            "espera_velas",
            campo_resultado="resultado",
        ),
        limite=20,
    )

    imprimir_tabla_resumen(
        "POR RIESGOS BASE",
        resumen_por_lista(
            resultados,
            "riesgos_base",
            campo_resultado="resultado_hipotetico",
        ),
        limite=30,
    )

    imprimir_tabla_resumen(
        "POR FORTALEZAS BASE",
        resumen_por_lista(
            resultados,
            "fortalezas_base",
            campo_resultado="resultado_hipotetico",
        ),
        limite=30,
    )
    imprimir_tabla_resumen(
        "POR RIESGOS BASE",
        resumen_por_lista(resultados, "riesgos_base"),
        limite=30
    )

    imprimir_tabla_resumen(
        "POR FORTALEZAS BASE",
        resumen_por_lista(resultados, "fortalezas_base"),
        limite=30
    )
def main():
    print("BUILD:", BUILD_ID)
    reset_estado()

    datasets = cargar_datasets()
    datasets = seleccionar_top_datasets(
        datasets,
        limite=MAX_ACTIVOS_ANALIZAR
    )

    # Auditoría de los datasets seleccionados
    imprimir_auditoria_datasets()

    global DATASETS_USADOS_BACKTEST
    DATASETS_USADOS_BACKTEST = len(datasets)

    print("Datasets cargados:", len(datasets))
    print("Ejecutando backtest usando analizar_activo() real...")

    resultados = ejecutar_backtest(datasets)

    guardar_resultados(resultados)

    if ACTUALIZAR_APRENDIZAJE:
        generar_aprendizaje_desde_resultados(resultados)
    else:
        print(
            "Aprendizaje histórico congelado: "
            "no se sobrescribió durante esta prueba."
        )

    imprimir_resumen(resultados)

    print("Archivo generado:", SALIDA)
if __name__ == "__main__":
    main()