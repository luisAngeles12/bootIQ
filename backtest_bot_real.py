import csv
import os

import estado
import estrategia
from evaluador_fase4 import evaluar_senal_fase4
from motor_protocolos import buscar_entrada_confirmada
from motor_setup import enriquecer_senal_con_setup, aplicar_setup_decision
from contexto_mercado import detectar_tipo_mercado, diagnostico_calidad_mercado, diagnostico_tendencia_avanzada
from motor_aprendizaje_historico import generar_aprendizaje_desde_resultados
from decision_bootiq import crear_decision_bootiq, aplanar_decision_bootiq
from motor_decision_unificado import evaluar_decision_bootiq
from motor_consenso import aplicar_consenso_decision
from motor_confirmacion import aplicar_confirmacion_decision

CARPETA_DATA = "data_backtest"
SALIDA = "backtest_bot_real_resultados.csv"

MAX_ACTIVOS_ANALIZAR = 20
LIMITE_DATASETS = 160
PASO_RONDA = 1


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

    for archivo in os.listdir(CARPETA_DATA):
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
    velas = dataset["velas"]

    if len(velas) < 180:
        return None

    ventana = velas[-180:]

    tipo_mercado, _ = detectar_tipo_mercado(ventana)
    diagnostico = diagnostico_calidad_mercado(ventana)
    tendencia = diagnostico_tendencia_avanzada(ventana)

    calidad = diagnostico.get("calidad", "SIN_DATOS")
    score = diagnostico.get("score", 0)
    estado_tendencia = tendencia.get("estado_tendencia", "INDEFINIDA")
    fuerza_tendencia = tendencia.get("fuerza_tendencia", 0)

    activo = dataset.get("activo", "")

    if "-op" in activo.lower():
        return None

    if "/" in activo:
        return None

    if calidad not in ["LIMPIO", "NORMAL"]:
        return None

    if score < 52:
        return None

    if estado_tendencia == "INDEFINIDA":
        return None

    if "DEBIL" in estado_tendencia and score < 62:
        return None

    if tipo_mercado == "RANGO" and "FUERTE" not in estado_tendencia and "NORMAL" not in estado_tendencia:
        return None

    score_filtro = score

    if calidad == "LIMPIO":
        score_filtro += 25

    if calidad == "NORMAL":
        score_filtro += 15

    if "FUERTE" in estado_tendencia:
        score_filtro += 25

    if "NORMAL" in estado_tendencia:
        score_filtro += 15

    if tipo_mercado in ["TENDENCIA_ALCISTA", "TENDENCIA_BAJISTA"]:
        score_filtro += 15

    if tipo_mercado == "RANGO":
        score_filtro -= 5

    if "-OTC" in activo:
        score_filtro += 5

    dataset["score_filtro_dataset"] = score_filtro
    dataset["tipo_mercado_dataset"] = tipo_mercado
    dataset["calidad_mercado_dataset"] = calidad
    dataset["score_mercado_dataset"] = score
    dataset["estado_tendencia_dataset"] = estado_tendencia
    dataset["fuerza_tendencia_dataset"] = fuerza_tendencia

    return dataset


def seleccionar_top_datasets(datasets, limite=20):
    evaluados = []

    for dataset in datasets:
        evaluado = evaluar_estabilidad_dataset(dataset)

        if evaluado is not None:
            evaluados.append(evaluado)

    evaluados = sorted(
        evaluados,
        key=lambda x: x.get("score_filtro_dataset", 0),
        reverse=True
    )

    seleccionados = evaluados[:limite]

    print("\n===== DATASETS SELECCIONADOS PARA BACKTEST =====")
    print("Total datasets cargados:", len(datasets))
    print("Datasets compatibles:", len(evaluados))
    print("Datasets usados:", len(seleccionados))

    for d in seleccionados:
        print(
            d["activo"],
            "| tipo:",
            d.get("tipo", "N/A"),
            "| filtro:",
            round(d.get("score_filtro_dataset", 0), 2),
            "| mercado:",
            d.get("tipo_mercado_dataset", "N/A"),
            "| calidad:",
            d.get("calidad_mercado_dataset", "N/A"),
            "| score mercado:",
            d.get("score_mercado_dataset", 0),
            "| tendencia:",
            d.get("estado_tendencia_dataset", "N/A"),
            "| fuerza:",
            round(d.get("fuerza_tendencia_dataset", 0), 2)
        )

    return seleccionados
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
        senal = estrategia.analizar_activo(activo)
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

def crear_registro_resultado(senal, velas, idx, idx_entrada, motivo_ejecucion, evaluacion_fase4, estado_operacion):
    if idx_entrada is None:
        idx_entrada = idx

    info_resultado = resultado_binario(
        velas,
        idx_entrada,
        senal["direccion"]
    )

    # =========================
    # DECISION BOOTIQ V2
    # =========================
    decision_bootiq = crear_decision_bootiq(senal)
    decision_bootiq = aplicar_consenso_decision(decision_bootiq)
    decision_bootiq = aplicar_setup_decision(decision_bootiq)
    decision_bootiq = aplicar_confirmacion_decision(decision_bootiq)

    decision_unificada = evaluar_decision_bootiq(decision_bootiq)

    senal["decision_unificada_accion"] = decision_unificada.get("accion", "")
    senal["decision_unificada_score"] = decision_unificada.get("score", 0)
    senal["decision_unificada_confianza"] = decision_unificada.get("confianza", "")
    senal["decision_unificada_razones"] = " | ".join(decision_unificada.get("razones", []))
    senal["decision_unificada_advertencias"] = " | ".join(decision_unificada.get("advertencias", []))
    senal["decision_unificada_bloqueos"] = " | ".join(decision_unificada.get("bloqueos", []))

    decision_bootiq = crear_decision_bootiq(senal)
    decision_bootiq = aplicar_consenso_decision(decision_bootiq)
    decision_bootiq = aplicar_confirmacion_decision(decision_bootiq)
    decision_bootiq_plana = aplanar_decision_bootiq(decision_bootiq)

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
        "razones_consenso": senal.get("razones_consenso", ""),
        "calidad": senal.get("calidad", ""),
        "rsi": senal.get("rsi", ""),

        "tipo_mercado": senal.get("tipo_mercado", ""),
        "calidad_mercado": senal.get("calidad_mercado", ""),
        "score_mercado": senal.get("score_mercado", 0),
        "estado_tendencia": senal.get("estado_tendencia", ""),
        "fuerza_tendencia": senal.get("fuerza_tendencia", 0),
        "direccion_tendencia": senal.get("direccion_tendencia", ""),

        "accion_precio": senal.get("accion_precio", ""),
        "razon_accion_precio": senal.get("razon_accion_precio", ""),
        "pa_tipo": senal.get("pa_tipo", ""),
        "pa_direccion": senal.get("pa_direccion", ""),
        "pa_fuerza": senal.get("pa_fuerza", 0),
        "pa_razon": senal.get("pa_razon", ""),

        "base_estrategia": senal.get("base_estrategia", ""),
        "riesgos_base": senal.get("riesgos_base", ""),
        "fortalezas_base": senal.get("fortalezas_base", ""),

        "ruptura_confirmada": senal.get("ruptura_confirmada", False),
        "tipo_ruptura": senal.get("tipo_ruptura", ""),
        "razon_ruptura": senal.get("razon_ruptura", ""),

        "tipo_setup": senal.get("tipo_setup", "INDEFINIDO"),
        "calidad_setup": senal.get("calidad_setup", "MEDIA"),
        "modo_entrada_setup": senal.get("modo_entrada_setup", "DIRECTA"),
        "puntaje_extra_setup": senal.get("puntaje_extra_setup", 0),
        "riesgo_extra_setup": senal.get("riesgo_extra_setup", 0),
        "balance_setup": senal.get("balance_setup", 0),
        "a_favor_tendencia": senal.get("a_favor_tendencia", False),
        "razones_setup": senal.get("razones_setup", ""),
        "familia_setup": senal.get("familia_setup", ""),
        "subtipo_setup": senal.get("subtipo_setup", ""),
        "protocolo_sugerido": senal.get("protocolo_sugerido", ""),
        "nivel_setup": senal.get("nivel_setup", ""),
        "estado_setup": senal.get("estado_setup", ""),
        "confianza_setup": senal.get("confianza_setup", 0),
        "razones_clasificador_setup": senal.get("razones_clasificador_setup", ""),
        "riesgo_protocolo": senal.get("riesgo_protocolo", 0),
        "nivel_riesgo_protocolo": senal.get("nivel_riesgo_protocolo", ""),
        "razon_riesgo_protocolo": senal.get("razon_riesgo_protocolo", ""),

        "indice_confirmacion_ia": senal.get("indice_confirmacion_ia", 0),
        "nivel_confirmacion_ia": senal.get("nivel_confirmacion_ia", ""),
        "accion_confirmacion_ia": senal.get("accion_confirmacion_ia", ""),
        "razon_confirmacion_ia": senal.get("razon_confirmacion_ia", ""),

        "idx_senal": idx,
        "idx_entrada": idx_entrada,
        "motivo_ejecucion": motivo_ejecucion,
        "estado_operacion": estado_operacion,
        "espera_velas": idx_entrada - idx,

        "fase4_evaluada": evaluacion_fase4.get("fase4_evaluada", False),
        "fase4_permitir_operacion": evaluacion_fase4.get("fase4_permitir_operacion", True),
        "fase4_modo": evaluacion_fase4.get("fase4_modo", ""),
        "fase4_confianza": evaluacion_fase4.get("fase4_confianza", 50.0),
        "fase4_decision": evaluacion_fase4.get("fase4_decision", ""),
        "fase4_debe_bloquear": evaluacion_fase4.get("fase4_debe_bloquear", False),
        "fase4_motivo": evaluacion_fase4.get("fase4_motivo", ""),

        "resultado": info_resultado["resultado"],
        "resultado_hipotetico": info_resultado["resultado"],

        "precio_entrada": velas[idx_entrada]["close"],
        "precio_cierre": velas[idx_entrada + 1]["close"],

        "movimiento": info_resultado["movimiento"],
        "distancia_resultado": info_resultado["distancia_resultado"],
        "excursion_favor": info_resultado["excursion_favor"],
        "excursion_contra": info_resultado["excursion_contra"],
        "fuerza_cierre_siguiente": info_resultado["fuerza_cierre_siguiente"],
        "open_siguiente": info_resultado["open_siguiente"],
        "close_siguiente": info_resultado["close_siguiente"],
        "high_siguiente": info_resultado["high_siguiente"],
        "low_siguiente": info_resultado["low_siguiente"],
        "decision_unificada_accion": senal.get("decision_unificada_accion", ""),
        "decision_unificada_score": senal.get("decision_unificada_score", 0),
        "decision_unificada_confianza": senal.get("decision_unificada_confianza", ""),
        "decision_unificada_razones": senal.get("decision_unificada_razones", ""),
        "decision_unificada_advertencias": senal.get("decision_unificada_advertencias", ""),
        "decision_unificada_bloqueos": senal.get("decision_unificada_bloqueos", ""),
        "razon": senal.get("razon", ""),
        "cerebro_unico_decision": senal.get("cerebro_unico_decision", ""),
        "cerebro_unico_operar": senal.get("cerebro_unico_operar", False),
        "cerebro_unico_confianza": senal.get("cerebro_unico_confianza", 0),
        "cerebro_unico_riesgo": senal.get("cerebro_unico_riesgo", ""),
    }

    registro.update(decision_bootiq_plana)

    return registro

def ejecutar_backtest(datasets):
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

            senal["tipo"] = tipo
            senal = enriquecer_senal_con_setup(senal)

            senal["_velas"] = velas
            senal["_index"] = i
            senales_ronda.append(senal)

        senales_ronda = sorted(
            senales_ronda,
            key=lambda x: (
                x.get("score_final", 0),
                x.get("prioridad", 0),
                x.get("puntaje", 0)
            ),
            reverse=True
        )

        if ronda % 100 == 0:
            print("Ronda:", ronda, "Señales:", len(senales_ronda))

        for senal in senales_ronda[:MAX_ACTIVOS_ANALIZAR]:
            velas = senal["_velas"]
            idx = senal["_index"]

            evaluacion_fase4 = evaluar_senal_fase4(senal)

            senal["fase4_confianza"] = evaluacion_fase4.get("fase4_confianza", 50.0)
            senal["fase4_decision"] = evaluacion_fase4.get("fase4_decision", "")
            senal["fase4_modo"] = evaluacion_fase4.get("fase4_modo", "")
            senal["fase4_debe_bloquear"] = evaluacion_fase4.get("fase4_debe_bloquear", False)
            
            if evaluacion_fase4.get("fase4_debe_bloquear", False):
                resultados.append(
                    crear_registro_resultado(
                        senal=senal,
                        velas=velas,
                        idx=idx,
                        idx_entrada=idx,
                        motivo_ejecucion="CANCELADA_FASE4",
                        evaluacion_fase4=evaluacion_fase4,
                        estado_operacion="CANCELADA_FASE4"
                    )
                )
                continue

            idx_entrada, motivo_ejecucion = buscar_entrada_confirmada(
                velas,
                idx,
                senal
            )

            if idx_entrada is None:
                resultados.append(
                    crear_registro_resultado(
                        senal=senal,
                        velas=velas,
                        idx=idx,
                        idx_entrada=idx,
                        motivo_ejecucion=motivo_ejecucion,
                        evaluacion_fase4=evaluacion_fase4,
                        estado_operacion="CANCELADA_PROTOCOLO"
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
                    evaluacion_fase4=evaluacion_fase4,
                    estado_operacion="OPERADA"
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
        "fase4_evaluada",
        "fase4_permitir_operacion",
        "fase4_modo",
        "fase4_confianza",
        "fase4_decision",
        "fase4_debe_bloquear",
        "fase4_motivo",

        "resultado",
        "resultado_hipotetico",
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

        "bootiq_resultado_estado_operacion",
        "bootiq_resultado_motivo_ejecucion",
        "bootiq_resultado_resultado",
        "razon",
    ]
    with open(SALIDA, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=campos, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(resultados)

def resumen_por_campo(resultados, campo):
    grupos = {}

    for r in resultados:
        clave = r.get(campo, "")

        if clave not in grupos:
            grupos[clave] = {"total": 0, "win": 0}

        grupos[clave]["total"] += 1

        if r["resultado"] == "WIN":
            grupos[clave]["win"] += 1

    filas = []

    for clave, d in grupos.items():
        wr = round((d["win"] / d["total"]) * 100, 2)
        filas.append((clave, d["total"], d["win"], d["total"] - d["win"], wr))

    return sorted(filas, key=lambda x: x[4], reverse=True)

def resumen_por_lista(resultados, campo):
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
                grupos[item] = {"total": 0, "win": 0}

            grupos[item]["total"] += 1

            if r["resultado"] == "WIN":
                grupos[item]["win"] += 1

    filas = []

    for clave, d in grupos.items():
        wr = round((d["win"] / d["total"]) * 100, 2) if d["total"] else 0
        filas.append((clave, d["total"], d["win"], d["total"] - d["win"], wr))

    return sorted(filas, key=lambda x: x[1], reverse=True)


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

def imprimir_resumen_fase4(resultados):
    if not resultados:
        return

    evaluadas = [r for r in resultados if str(r.get("fase4_evaluada", "")).lower() == "true" or r.get("fase4_evaluada") is True]

    permitidas = [
        r for r in resultados
        if str(r.get("fase4_permitir_operacion", "")).lower() == "true"
        or r.get("fase4_permitir_operacion") is True
    ]

    bloqueadas = [
        r for r in resultados
        if str(r.get("fase4_debe_bloquear", "")).lower() == "true"
        or r.get("fase4_debe_bloquear") is True
    ]

    def calcular_wr(filas):
        total = len(filas)
        wins = sum(1 for r in filas if r.get("resultado") == "WIN")
        losses = total - wins
        wr = round((wins / total) * 100, 2) if total else 0
        return total, wins, losses, wr

    total_original, wins_original, losses_original, wr_original = calcular_wr(resultados)
    total_permitidas, wins_permitidas, losses_permitidas, wr_permitidas = calcular_wr(permitidas)
    total_bloqueadas, wins_bloqueadas, losses_bloqueadas, wr_bloqueadas = calcular_wr(bloqueadas)

    precision_bloqueo = round((losses_bloqueadas / total_bloqueadas) * 100, 2) if total_bloqueadas else 0

    print("\n===== IMPACTO FASE 4 =====")
    print("Operaciones originales:", total_original)
    print("WIN originales:", wins_original)
    print("LOSS originales:", losses_original)
    print("Winrate original:", str(wr_original) + "%")
    print("----------------------------")
    print("Operaciones evaluadas Fase 4:", len(evaluadas))
    print("Permitidas por Fase 4:", total_permitidas)
    print("WIN permitidas:", wins_permitidas)
    print("LOSS permitidas:", losses_permitidas)
    print("Winrate permitidas:", str(wr_permitidas) + "%")
    print("----------------------------")
    print("Bloqueadas por Fase 4:", total_bloqueadas)
    print("WIN bloqueadas:", wins_bloqueadas)
    print("LOSS bloqueadas:", losses_bloqueadas)
    print("Winrate bloqueadas:", str(wr_bloqueadas) + "%")
    print("Precisión del bloqueo:", str(precision_bloqueo) + "%")
    print("==========================\n")

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
    operadas = [r for r in resultados if r.get("estado_operacion") == "OPERADA"]
    for r in resultados:
        r["rango_indice_confirmacion_ia"] = clasificar_indice_confirmacion_ia(
            r.get("indice_confirmacion_ia", 0)
        )
    total = len(operadas)
    wins = sum(1 for r in operadas if r["resultado"] == "WIN")
    losses = total - wins
    wr = round((wins / total) * 100, 2) if total else 0
    print("\n===== BACKTEST BOT REAL =====")
    print("Datasets:", LIMITE_DATASETS)
    print("Paso ronda:", PASO_RONDA)
    print("Total operaciones:", total)
    print("Ganadas:", wins)
    print("Perdidas:", losses)
    print("Winrate:", wr, "%")
    print("============================\n")
    imprimir_resumen_fase4(resultados)
    print("Total señales evaluadas:", len(resultados))
    print("Operadas:", len(operadas))
    print("Canceladas Fase 4:", len([r for r in resultados if r.get("estado_operacion") == "CANCELADA_FASE4"]))
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
        ("POR MOTIVO EJECUCION", "motivo_ejecucion"),
        ("POR NIVEL RIESGO PROTOCOLO", "nivel_riesgo_protocolo"),
        ("POR NIVEL CONFIRMACION IA", "nivel_confirmacion_ia"),
        ("POR ACCION CONFIRMACION IA", "accion_confirmacion_ia"),
        ("POR INDICE CONFIRMACION IA", "rango_indice_confirmacion_ia"),
        ("POR ESPERA VELAS", "espera_velas"),
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
    ]

    imprimir_tabla_resumen(
        "POR ESTADO OPERACION",
        resumen_por_campo(resultados, "estado_operacion"),
        limite=10
    )

    for titulo, campo in reportes:
        imprimir_tabla_resumen(
            titulo,
            resumen_por_campo(resultados, campo),
            limite=20
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
    reset_estado()

    datasets = cargar_datasets()
    datasets = seleccionar_top_datasets(datasets, limite=MAX_ACTIVOS_ANALIZAR)
    print("Datasets cargados:", len(datasets))
    print("Ejecutando backtest usando analizar_activo() real...")

    resultados = ejecutar_backtest(datasets)

    guardar_resultados(resultados)
    generar_aprendizaje_desde_resultados(resultados)
    imprimir_resumen(resultados)

    print("Archivo generado:", SALIDA)


if __name__ == "__main__":
    main()