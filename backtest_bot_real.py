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
import copy
import hashlib

import estado
import estrategia
from motor_protocolos import buscar_entrada_confirmada
import motor_protocolos as motor_protocolos_mod
from contexto_mercado import detectar_tipo_mercado, diagnostico_calidad_mercado, diagnostico_tendencia_avanzada
from motor_aprendizaje_historico import (
    generar_aprendizaje_desde_resultados,
    actualizar_aprendizaje_post_protocolo,
)
from motor_candidatos import ordenar_candidatas_v3
from motor_decision import evaluar_decision_post_protocolo
from decision_bootiq import aplanar_decision_bootiq
CARPETA_DATA = "data_backtest_oos"

MAX_ACTIVOS_ANALIZAR = 20
MAX_SENALES_POR_RONDA = 20
LIMITE_DATASETS = 160
PASO_RONDA = 1

# ============================================================
# MODOS OFICIALES DEL BACKTEST
# ============================================================

MODO_BACKTEST_FILTRADO = "FILTRADO"
MODO_BACKTEST_DIAGNOSTICO = "DIAGNOSTICO_COMPLETO"

# Cambiar únicamente esta línea para comparar universos.
MODO_BACKTEST = MODO_BACKTEST_FILTRADO

# ============================================================
# PARTICIÓN OFICIAL TRAIN / VALIDACIÓN
# ============================================================

MODO_EXPERIMENTO_AUDITORIA_TRAIN = "AUDITORIA_TRAIN"
MODO_EXPERIMENTO_VALIDACION = "VALIDACION"
MODO_EXPERIMENTO_OUT_OF_SAMPLE = "OUT_OF_SAMPLE"

MODO_EXPERIMENTO = MODO_EXPERIMENTO_VALIDACION

# ============================================================
# F5.7-D4.2A — SALIDA COHERENTE CON EL MODO EXPERIMENTAL
# ============================================================
if MODO_EXPERIMENTO == MODO_EXPERIMENTO_AUDITORIA_TRAIN:
    SALIDA = "backtest_bootiq_F5_7_D4_2_TRAIN.csv"

elif MODO_EXPERIMENTO == MODO_EXPERIMENTO_VALIDACION:
    SALIDA = "backtest_bootiq_F5_7_D4_2_VALID.csv"

elif MODO_EXPERIMENTO == MODO_EXPERIMENTO_OUT_OF_SAMPLE:
    SALIDA = "backtest_bootiq_F5_7_D4_2_OOS.csv"

else:
    raise RuntimeError(
        f"MODO_EXPERIMENTO inválido: {MODO_EXPERIMENTO}"
    )
TOTAL_DATASETS_EXPERIMENTO = 16
TOTAL_DATASETS_TRAIN = 11
TOTAL_DATASETS_VALIDACION = 5

BUILD_ID = "BOOTIQ_BACKTEST_V5_SOMBRA_ESTADISTICA_2026_08_01"
ACTUALIZAR_APRENDIZAJE = False
# ============================================================
# C-C2 — ACTUALIZACIÓN EXCLUSIVA POST-PROTOCOLO
# ============================================================

ACTUALIZAR_APRENDIZAJE_PROTOCOLO = False

if MODO_EXPERIMENTO == MODO_EXPERIMENTO_OUT_OF_SAMPLE:
    ACTUALIZAR_APRENDIZAJE = False
    ACTUALIZAR_APRENDIZAJE_PROTOCOLO = False

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

def evaluar_estabilidad_dataset(
    dataset,
    indice_actual=None,
):
    """
    Diagnostica un dataset y calcula su score de selección.

    En modo FILTRADO puede marcarlo como no compatible.
    En modo DIAGNOSTICO_COMPLETO conserva todos los datasets
    técnicamente válidos, aunque el mercado sea deficiente.

    Cuando recibe indice_actual, reproduce de forma causal
    la ventana usada por el scanner LIVE:
    120 velas solicitadas - 1 vela abierta = 119 cerradas.
    """

    velas = dataset.get("velas", [])
    activo = str(dataset.get("activo", "") or "").strip()

    if not activo:
        return None, "ACTIVO_VACIO"

    # ========================================================
    # VENTANA DE SELECCION
    # ========================================================

    if indice_actual is None:
        # Selección experimental inicial.
        # Se conserva esta ruta para mantener el universo
        # histórico 12 TRAIN + 4 VALIDACION ya definido.
        if len(velas) < 180:
            return None, "VELAS_INSUFICIENTES"

        ventana = velas[-180:]

    else:
        # LIVE solicita 120 velas y descarta la última
        # porque todavía está abierta.
        #
        # En BACKTEST todas las velas almacenadas ya son
        # históricas/cerradas, por lo que usamos exactamente
        # 119 velas cerradas terminando en indice_actual.
        if (
            indice_actual < 118
            or indice_actual >= len(velas)
        ):
            return None, "INDICE_HISTORICO_INVALIDO"

        ventana = velas[
            indice_actual - 118:
            indice_actual + 1
        ]

        if len(ventana) < 119:
            return None, "VELAS_INSUFICIENTES"

    try:
        tipo_mercado, _ = detectar_tipo_mercado(
            ventana
        )

        diagnostico = diagnostico_calidad_mercado(
            ventana
        )

        tendencia = diagnostico_tendencia_avanzada(
            ventana
        )

    except Exception as exc:
        dataset["error_diagnostico_dataset"] = str(exc)

        return None, "ERROR_DIAGNOSTICO_MERCADO"

    diagnostico = (
        diagnostico
        if isinstance(diagnostico, dict)
        else {}
    )

    tendencia = (
        tendencia
        if isinstance(tendencia, dict)
        else {}
    )

    calidad = str(
        diagnostico.get(
            "calidad",
            "SIN_DATOS",
        )
    ).upper().strip()

    try:
        score = float(
            diagnostico.get(
                "score",
                0,
            )
            or 0
        )
    except (TypeError, ValueError):
        score = 0.0

    estado_tendencia = str(
        tendencia.get(
            "estado_tendencia",
            "INDEFINIDA",
        )
    ).upper().strip()

    try:
        fuerza_tendencia = float(
            tendencia.get(
                "fuerza_tendencia",
                0,
            )
            or 0
        )
    except (TypeError, ValueError):
        fuerza_tendencia = 0.0

    motivo_filtro = ""

    if "-op" in activo.lower():
        motivo_filtro = "ACTIVO_OP_NO_COMPATIBLE"

    elif "/" in activo:
        motivo_filtro = "FORMATO_ACTIVO_NO_COMPATIBLE"

    elif calidad not in {
        "LIMPIO",
        "NORMAL",
    }:
        motivo_filtro = (
            "CALIDAD_MERCADO_NO_COMPATIBLE"
        )

    elif score < 52:
        motivo_filtro = (
            "SCORE_MERCADO_MENOR_52"
        )

    elif estado_tendencia == "INDEFINIDA":
        motivo_filtro = "TENDENCIA_INDEFINIDA"

    elif (
        "DEBIL" in estado_tendencia
        and score < 62
    ):
        motivo_filtro = (
            "TENDENCIA_DEBIL_SCORE_MENOR_62"
        )

    elif (
        tipo_mercado == "RANGO"
        and "FUERTE" not in estado_tendencia
        and "NORMAL" not in estado_tendencia
    ):
        motivo_filtro = (
            "RANGO_SIN_TENDENCIA_COMPATIBLE"
        )

    # ========================================================
    # SCORE FINAL DE SELECCION
    # ========================================================

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

    # Mantener el mismo mínimo utilizado
    # por el scanner LIVE.
    if (
        not motivo_filtro
        and score_filtro < 55
    ):
        motivo_filtro = (
            "SCORE_FILTRO_MENOR_55"
        )

    # ========================================================
    # AUDITORIA DEL DATASET
    # ========================================================

    dataset["score_filtro_dataset"] = (
        score_filtro
    )

    dataset["tipo_mercado_dataset"] = (
        tipo_mercado
    )

    dataset["calidad_mercado_dataset"] = (
        calidad
    )

    dataset["score_mercado_dataset"] = (
        score
    )

    dataset["estado_tendencia_dataset"] = (
        estado_tendencia
    )

    dataset["fuerza_tendencia_dataset"] = (
        fuerza_tendencia
    )

    dataset["compatible_filtro_dataset"] = (
        not bool(motivo_filtro)
    )

    dataset["motivo_exclusion_dataset"] = (
        motivo_filtro
    )

    if (
        MODO_BACKTEST
        == MODO_BACKTEST_FILTRADO
        and motivo_filtro
    ):
        return None, motivo_filtro

    return dataset, motivo_filtro
def seleccionar_top_datasets(
    datasets,
    limite=20,
    indice_actual=None,
    mostrar=True,
):
    reset_auditoria_datasets()

    AUDITORIA_DATASETS["cargados"] = len(datasets)

    evaluados = []

    for dataset in datasets:
        evaluado, motivo = evaluar_estabilidad_dataset(
            dataset,
            indice_actual=indice_actual,
        )

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
            -float(
                x.get(
                    "score_filtro_dataset",
                    0,
                )
            ),
            str(
                x.get(
                    "activo",
                    "",
                )
            ).upper(),
        ),
    )

    if MODO_BACKTEST == MODO_BACKTEST_FILTRADO:
        seleccionados = evaluados[:limite]
    else:
        seleccionados = evaluados[:LIMITE_DATASETS]

    AUDITORIA_DATASETS["seleccionados"] = len(
        seleccionados
    )

    if mostrar:
        print(
            "\n===== DATASETS SELECCIONADOS PARA BACKTEST ====="
        )

        print(
            "Modo:",
            MODO_BACKTEST,
        )

        print(
            "Total datasets cargados:",
            len(datasets),
        )

        print(
            "Datasets válidos técnicamente:",
            AUDITORIA_DATASETS[
                "validos_tecnicamente"
            ],
        )

        print(
            "Compatibles con filtro oficial:",
            AUDITORIA_DATASETS[
                "compatibles_filtro"
            ],
        )

        print(
            "Datasets usados:",
            len(seleccionados),
        )

        for d in seleccionados:
            print(
                d["activo"],
                "| tipo:",
                d.get(
                    "tipo",
                    "N/A",
                ),
                "| filtro:",
                round(
                    d.get(
                        "score_filtro_dataset",
                        0,
                    ),
                    2,
                ),
                "| mercado:",
                d.get(
                    "tipo_mercado_dataset",
                    "N/A",
                ),
                "| calidad:",
                d.get(
                    "calidad_mercado_dataset",
                    "N/A",
                ),
                "| score mercado:",
                d.get(
                    "score_mercado_dataset",
                    0,
                ),
                "| tendencia:",
                d.get(
                    "estado_tendencia_dataset",
                    "N/A",
                ),
                "| fuerza:",
                round(
                    d.get(
                        "fuerza_tendencia_dataset",
                        0,
                    ),
                    2,
                ),
                "| compatible:",
                d.get(
                    "compatible_filtro_dataset",
                    False,
                ),
                "| exclusión:",
                d.get(
                    "motivo_exclusion_dataset",
                    "",
                ),
            )

    return seleccionados
def dividir_datasets_experimento(datasets_seleccionados):
    """
    Divide automáticamente los datasets entre TRAIN y VALIDACIÓN.

    La pertenencia se determina por el nombre del activo,
    no por score, ranking, mercado o posición.

    De esta forma un activo no cambia de TRAIN a VALIDACIÓN
    simplemente porque cambie su diagnóstico técnico.

    Aproximadamente:
        80% TRAIN
        20% VALIDACIÓN
    """

    if not datasets_seleccionados:
        raise RuntimeError(
            "No existen datasets disponibles para dividir."
        )

    train = []
    validacion = []

    for dataset in datasets_seleccionados:

        activo = str(
            dataset.get("activo", "") or ""
        ).upper().strip()

        if not activo:
            continue

        # Hash estable del nombre del activo.
        hash_activo = hashlib.sha256(
            activo.encode("utf-8")
        ).hexdigest()

        # Convertimos una parte del hash en número 0-99.
        bucket = int(hash_activo[:8], 16) % 100

        # 80% TRAIN / 20% VALIDACIÓN.
        if bucket < 80:
            train.append(dataset)
        else:
            validacion.append(dataset)

    # Protección para universos pequeños:
    # debe existir información en ambos grupos.
    if not train or not validacion:
        raise RuntimeError(
            "La división automática no produjo suficientes "
            "datasets en TRAIN y VALIDACIÓN."
        )

    universo = train + validacion

    print("\n===== SPLIT EXPERIMENTAL AUTOMATICO =====")
    print(f"Universo: {len(universo)}")
    print(f"TRAIN: {len(train)}")
    print(f"VALIDACION: {len(validacion)}")
    print("----------------------------------------")

    print("TRAIN:")
    for dataset in train:
        print(
            f"  {dataset.get('activo', 'SIN_ACTIVO')}"
        )

    print("----------------------------------------")

    print("VALIDACION:")
    for dataset in validacion:
        print(
            f"  {dataset.get('activo', 'SIN_ACTIVO')}"
        )

    print("========================================\n")

    return universo, train, validacion

def seleccionar_datasets_experimento(datasets_seleccionados):
    # ========================================================
    # PASO 6 — OUT OF SAMPLE
    # ========================================================
    if (
        MODO_EXPERIMENTO
        == MODO_EXPERIMENTO_OUT_OF_SAMPLE
    ):
        usados = list(datasets_seleccionados)

        if not usados:
            raise RuntimeError(
                "OUT_OF_SAMPLE no recibió datasets válidos."
            )

        print(
            "\n===== CONFIGURACION OUT OF SAMPLE ====="
        )
        print(
            "Modo:",
            MODO_EXPERIMENTO
        )
        print(
            "Datasets nuevos usados:",
            len(usados)
        )
        print(
            "Aprendizaje general:",
            ACTUALIZAR_APRENDIZAJE
        )
        print(
            "Aprendizaje protocolo:",
            ACTUALIZAR_APRENDIZAJE_PROTOCOLO
        )
        print(
            "========================================"
        )

        print(
            "\nDATASETS OUT OF SAMPLE:"
        )

        for d in usados:
            print(
                " -",
                d.get("activo", "")
            )

        return usados

    # ========================================================
    # TRAIN / VALIDACION AUTOMATICOS
    # ========================================================
    universo, train, validacion = (
        dividir_datasets_experimento(
            datasets_seleccionados
        )
    )

    if (
        MODO_EXPERIMENTO
        == MODO_EXPERIMENTO_AUDITORIA_TRAIN
    ):
        usados = train

    elif (
        MODO_EXPERIMENTO
        == MODO_EXPERIMENTO_VALIDACION
    ):
        usados = validacion

    else:
        raise RuntimeError(
            f"Modo experimental inválido: "
            f"{MODO_EXPERIMENTO}"
        )

    # ========================================================
    # FASE 2.6
    # Ya no exigimos 12 TRAIN + 4 VALIDACION.
    #
    # El tamaño depende de los datasets válidos que
    # existan y de la partición determinista automática.
    # Solo exigimos que el grupo correspondiente exista.
    # ========================================================
    if not usados:
        raise RuntimeError(
            f"{MODO_EXPERIMENTO} no recibió "
            "datasets para ejecutar."
        )

    if not train:
        raise RuntimeError(
            "El split automático no produjo "
            "datasets TRAIN."
        )

    if not validacion:
        raise RuntimeError(
            "El split automático no produjo "
            "datasets VALIDACION."
        )

    print(
        "\n===== CONFIGURACION EXPERIMENTO ====="
    )
    print(
        "Modo:",
        MODO_EXPERIMENTO
    )
    print(
        "Universo experimental:",
        len(universo)
    )
    print(
        "TRAIN reservados:",
        len(train)
    )
    print(
        "VALIDACION reservados:",
        len(validacion)
    )
    print(
        "Datasets usados ahora:",
        len(usados)
    )
    print(
        "===================================="
    )

    print("\nTRAIN:")
    for d in train:
        print(
            " -",
            d.get("activo", "")
        )

    print("\nVALIDACION RESERVADA:")
    for d in validacion:
        print(
            " -",
            d.get("activo", "")
        )

    return usados

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

        # PASO 5.5A
        # Mantener identidad temporal exacta también en BACKTEST.
        "from": [
            int(v["from"])
            for v in ventana
        ],
    }

    original_obtener_velas = estrategia.obtener_velas

    estrategia.obtener_velas = (
        lambda activo_param: data
    )

    try:
        senal = estrategia.analizar_activo(
            activo,
            modo_backtest_diagnostico=True
        )
    finally:
        estrategia.obtener_velas = (
            original_obtener_velas
        )

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
def _tipos_evidencias(valor):
    """
    Convierte una lista de evidencias estructuradas en una cadena
    con los tipos utilizados, apta para CSV y auditoría.
    """

    if not isinstance(valor, list):
        return ""

    tipos = []

    for evidencia in valor:
        if not isinstance(evidencia, dict):
            continue

        tipo = str(evidencia.get("tipo", "") or "").strip()

        if tipo and tipo not in tipos:
            tipos.append(tipo)

    return " | ".join(tipos)
def _texto(valor):
    if isinstance(valor, list):
        return " | ".join(str(x) for x in valor)

    if valor is None:
        return ""

    return str(valor)
def _tipos_evidencias(evidencias):
    """
    Convierte evidencias estructuradas en una cadena:
    TIPO_1 | TIPO_2 | TIPO_3
    """

    if not isinstance(evidencias, list):
        return ""

    tipos = []

    for evidencia in evidencias:
        if not isinstance(evidencia, dict):
            continue

        tipo = str(
            evidencia.get("tipo", "")
            or ""
        ).strip()

        if tipo and tipo not in tipos:
            tipos.append(tipo)

    return " | ".join(tipos)
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

    # ==================================================
    # RESULTADOS
    # ==================================================

    # Resultado fijo del universo:
    # siempre se calcula desde la vela donde nació la señal.
    info_hipotetico = resultado_binario(
        velas,
        idx,
        direccion,
    )

    # Resultado real según la entrada utilizada.
    info_resultado = resultado_binario(
        velas,
        idx_entrada,
        direccion,
    )

    # ==================================================
    # DECISIÓN BOOTIQ
    # ==================================================

    decision_bootiq = (
        decision_bootiq
        if isinstance(decision_bootiq, dict)
        else {}
    )
    
    # ============================================================
    # FASE 3.4-A — AUDITORÍA DEL CONTRATO BOOTIQ
    # ============================================================
    # La decisión ya fue calculada en estrategia.py.
    # Aquí únicamente aplanamos el snapshot exacto conservado allí.
    # NO se vuelve a llamar al Cerebro Único.
    snapshot_bootiq = senal.get(
        "_decision_bootiq_snapshot",
        {},
    )
    
    if not isinstance(snapshot_bootiq, dict):
        snapshot_bootiq = {}
    
    decision_bootiq_plana = aplanar_decision_bootiq(
        snapshot_bootiq
    )

    decision_oficial = str(
        senal.get("cerebro_unico_decision", "NO_OPERAR")
        or "NO_OPERAR"
    ).upper().strip()

    # ==================================================
    # C-C2 — FUENTES POST-PROTOCOLO
    # ==================================================
    #
    # IMPORTANTE:
    # motor_aprendizaje_historico entrega estas fuentes
    # como diccionarios completos.
    #
    # Ejemplo:
    #
    # {
    #     "nivel": "...",
    #     "clave": "...",
    #     "total": ...,
    #     "wins": ...,
    #     "losses": ...,
    #     "winrate": ...,
    #     ...
    # }
    #
    # Antes la auditoría buscaba campos separados y terminaba
    # mostrando SIN_NIVEL | SIN_CLAVE.
    # ==================================================

    fuente_cc2_principal = senal.get(
        "fuente_post_protocolo_principal",
        {},
    )

    if not isinstance(fuente_cc2_principal, dict):
        fuente_cc2_principal = {}

    fuente_cc2_respaldo = senal.get(
        "fuente_post_protocolo_respaldo",
        {},
    )

    if not isinstance(fuente_cc2_respaldo, dict):
        fuente_cc2_respaldo = {}

    registro = {
        # ==================================================
        # DATOS GENERALES
        # ==================================================

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

        # ==================================================
        # MERCADO
        # ==================================================

        "tipo_mercado": senal.get("tipo_mercado", ""),
        "calidad_mercado": senal.get("calidad_mercado", ""),
        "score_mercado": senal.get("score_mercado", 0),
        "estado_tendencia": senal.get("estado_tendencia", ""),
        "fuerza_tendencia": senal.get("fuerza_tendencia", 0),
        "direccion_tendencia": senal.get(
            "direccion_tendencia",
            "",
        ),

        # ==================================================
        # PRICE ACTION
        # ==================================================

        "accion_precio": senal.get("accion_precio", ""),

        "razon_accion_precio": _texto(
            senal.get("razon_accion_precio", "")
        ),

        "pa_tipo": senal.get("pa_tipo", ""),
        "pa_direccion": senal.get("pa_direccion", ""),
        "pa_fuerza": senal.get("pa_fuerza", 0),

        "pa_razon": _texto(
            senal.get("pa_razon", "")
        ),

        "bootiq_evidencias_price_action": _tipos_evidencias(
            senal.get("pa_evidencias", [])
        ),

        "bootiq_evidencias_mercado": _tipos_evidencias(
            senal.get("mercado_evidencias", [])
        ),

        "evidencia_pa": _tipos_evidencias(
            senal.get("pa_evidencias", [])
        ),

        "evidencia_mercado": _tipos_evidencias(
            senal.get("mercado_evidencias", [])
        ),

        "pa_evidencias_detalle": _texto(
            senal.get("pa_evidencias", [])
        ),

        "mercado_evidencias_detalle": _texto(
            senal.get("mercado_evidencias", [])
        ),

        # ==================================================
        # ESTRATEGIA BASE
        # ==================================================

        "base_estrategia": senal.get(
            "base_estrategia",
            "",
        ),

        "riesgos_base": _texto(
            senal.get("riesgos_base", "")
        ),

        "fortalezas_base": _texto(
            senal.get("fortalezas_base", "")
        ),

        # ==================================================
        # RUPTURA
        # ==================================================

        "ruptura_confirmada": senal.get(
            "ruptura_confirmada",
            False,
        ),

        "tipo_ruptura": senal.get(
            "tipo_ruptura",
            "",
        ),

        "razon_ruptura": _texto(
            senal.get("razon_ruptura", "")
        ),

        # ==================================================
        # SETUP
        # ==================================================

        "tipo_setup": senal.get(
            "tipo_setup",
            "INDEFINIDO",
        ),

        "calidad_setup": senal.get(
            "calidad_setup",
            "MEDIA",
        ),

        "modo_entrada_setup": senal.get(
            "modo_entrada_setup",
            "DIRECTA",
        ),

        "requiere_ruptura_setup": bool(
            senal.get(
                "requiere_ruptura_setup",
                False,
            )
        ),

        "requiere_confirmacion_setup": bool(
            senal.get(
                "requiere_confirmacion_setup",
                False,
            )
        ),

        "riesgo_estructural_critico_setup": bool(
            senal.get(
                "riesgo_estructural_critico_setup",
                (
                    "no_operar"
                    in str(
                        senal.get(
                            "modo_entrada_setup",
                            "",
                        )
                        or ""
                    ).lower()
                    or
                    "cancelar"
                    in str(
                        senal.get(
                            "modo_entrada_setup",
                            "",
                        )
                        or ""
                    ).lower()
                ),
            )
        ),

        "puntaje_extra_setup": senal.get(
            "puntaje_extra_setup",
            0,
        ),

        "riesgo_extra_setup": senal.get(
            "riesgo_extra_setup",
            0,
        ),

        "balance_setup": senal.get(
            "balance_setup",
            0,
        ),

        "a_favor_tendencia": senal.get(
            "a_favor_tendencia",
            False,
        ),

        "razones_setup": _texto(
            senal.get("razones_setup", "")
        ),

        "familia_setup": senal.get(
            "familia_setup",
            "",
        ),

        "subtipo_setup": senal.get(
            "subtipo_setup",
            "",
        ),

        "protocolo_sugerido": senal.get(
            "protocolo_sugerido",
            "",
        ),

        "nivel_setup": senal.get(
            "nivel_setup",
            "",
        ),

        "estado_setup": senal.get(
            "estado_setup",
            "",
        ),

        "confianza_setup": senal.get(
            "confianza_setup",
            0,
        ),

        "razones_clasificador_setup": _texto(
            senal.get(
                "razones_clasificador_setup",
                "",
            )
        ),

        # ==================================================
        # RIESGO PROTOCOLO
        # ==================================================

        "riesgo_protocolo": senal.get(
            "riesgo_protocolo",
            0,
        ),

        "nivel_riesgo_protocolo": senal.get(
            "nivel_riesgo_protocolo",
            "",
        ),

        "razon_riesgo_protocolo": _texto(
            senal.get(
                "razon_riesgo_protocolo",
                "",
            )
        ),

        # ==================================================
        # CONFIRMACIÓN IA
        # ==================================================

        "indice_confirmacion_ia": senal.get(
            "indice_confirmacion_ia",
            0,
        ),

        "nivel_confirmacion_ia": senal.get(
            "nivel_confirmacion_ia",
            "",
        ),

        "accion_confirmacion_ia": senal.get(
            "accion_confirmacion_ia",
            "",
        ),

        "razon_confirmacion_ia": _texto(
            senal.get(
                "razon_confirmacion_ia",
                "",
            )
        ),

        # ==================================================
        # EJECUCIÓN
        # ==================================================

        "idx_senal": idx,
        "idx_entrada": idx_entrada,
        "motivo_ejecucion": motivo_ejecucion,
        "estado_operacion": estado_operacion,
        "espera_velas": idx_entrada - idx,

        # ==================================================
        # CEREBRO ÚNICO
        # ==================================================

        "cerebro_unico_decision": decision_oficial,

        "cerebro_unico_decision_legacy": senal.get(
            "cerebro_unico_decision_legacy",
            decision_oficial,
        ),

        "cerebro_unico_operar": bool(
            senal.get(
                "cerebro_unico_operar",
                False,
            )
        ),

        "cerebro_unico_confianza": senal.get(
            "cerebro_unico_confianza",
            0,
        ),

        "cerebro_unico_requiere_protocolo": bool(
            senal.get(
                "cerebro_unico_requiere_protocolo",
                False,
            )
        ),

        "cerebro_unico_modo_ejecucion": senal.get(
            "cerebro_unico_modo_ejecucion",
            "BLOQUEADA",
        ),

        "cerebro_unico_bloquear_por_riesgo": bool(
            senal.get(
                "cerebro_unico_bloquear_por_riesgo",
                False,
            )
        ),

        "cerebro_unico_riesgo": senal.get(
            "cerebro_unico_riesgo",
            "",
        ),

        "cerebro_unico_riesgo_puntos": senal.get(
            "cerebro_unico_riesgo_puntos",
            0,
        ),

        "cerebro_unico_motivos": _texto(
            senal.get(
                "cerebro_unico_motivos",
                "",
            )
        ),

        # ==================================================
        # MODO SOMBRA ESTADÍSTICO
        # ==================================================

        "modo_probabilidad": senal.get(
            "modo_probabilidad",
            "SOMBRA",
        ),

        "probabilidad_estimada": senal.get(
            "probabilidad_estimada",
            0,
        ),

        "intervalo_probabilidad_inferior": senal.get(
            "intervalo_probabilidad_inferior",
            0,
        ),

        "intervalo_probabilidad_superior": senal.get(
            "intervalo_probabilidad_superior",
            0,
        ),

        "muestra_probabilidad": senal.get(
            "muestra_probabilidad",
            0,
        ),

        "wins_probabilidad": senal.get(
            "wins_probabilidad",
            0,
        ),

        "losses_probabilidad": senal.get(
            "losses_probabilidad",
            0,
        ),

        "confiabilidad_probabilidad": senal.get(
            "confiabilidad_probabilidad",
            "SIN_DATOS",
        ),

        "fuente_probabilidad_principal": _texto(
            senal.get(
                "fuente_probabilidad_principal",
                "",
            )
        ),

        "fuente_probabilidad_respaldo": _texto(
            senal.get(
                "fuente_probabilidad_respaldo",
                "",
            )
        ),

        "nivel_probabilidad_principal": senal.get(
            "nivel_probabilidad_principal",
            "",
        ),

        "clave_probabilidad_principal": senal.get(
            "clave_probabilidad_principal",
            "",
        ),

        "decision_estadistica_sombra": senal.get(
            "decision_estadistica_sombra",
            "SIN_DATOS",
        ),

        "operar_estadistico_sombra": bool(
            senal.get(
                "operar_estadistico_sombra",
                False,
            )
        ),

        "requiere_protocolo_estadistico_sombra": bool(
            senal.get(
                "requiere_protocolo_estadistico_sombra",
                False,
            )
        ),

        "motivo_decision_estadistica_sombra": _texto(
            senal.get(
                "motivo_decision_estadistica_sombra",
                "",
            )
        ),

        # ==================================================
        # AUDITORÍA ENTRADA DIRECTA V3
        # ==================================================
        # Diagnóstico únicamente. No modifica decisiones.
        "directa_evidencia_solida": bool(
            senal.get("directa_evidencia_solida", False)
        ),
        "directa_muestra": senal.get("directa_muestra", 0),
        "directa_confiabilidad": senal.get(
            "directa_confiabilidad", "SIN_DATOS"
        ),
        "directa_nivel_probabilidad": senal.get(
            "directa_nivel_probabilidad",
            senal.get("nivel_probabilidad_principal", ""),
        ),
        "directa_clave_probabilidad": senal.get(
            "directa_clave_probabilidad",
            senal.get("clave_probabilidad_principal", ""),
        ),

        # ==================================================
        # LEGACY FASE 4
        # ==================================================

        "fase4_evaluada": senal.get(
            "fase4_evaluada",
            True,
        ),

        "fase4_permitir_operacion": bool(
            senal.get(
                "fase4_permitir_operacion",
                senal.get(
                    "cerebro_unico_operar",
                    False,
                ),
            )
        ),

        "fase4_modo": senal.get(
            "fase4_modo",
            senal.get(
                "cerebro_unico_modo_ejecucion",
                "BLOQUEADA",
            ),
        ),

        "fase4_confianza": senal.get(
            "fase4_confianza",
            senal.get(
                "cerebro_unico_confianza",
                0,
            ),
        ),

        "fase4_decision": senal.get(
            "fase4_decision",
            decision_oficial,
        ),

        "fase4_debe_bloquear": bool(
            senal.get(
                "fase4_debe_bloquear",
                not senal.get(
                    "cerebro_unico_operar",
                    False,
                ),
            )
        ),

        "fase4_motivo": _texto(
            senal.get(
                "fase4_motivo",
                senal.get(
                    "cerebro_unico_motivos",
                    "",
                ),
            )
        ),

        # ==================================================
        # AUDITORÍA MOTOR PROTOCOLOS
        # ==================================================

        "auditoria_protocolo_tipo": senal.get(
            "auditoria_protocolo_tipo",
            "",
        ),

        "auditoria_protocolo_subtipo": senal.get(
            "auditoria_protocolo_subtipo",
            "",
        ),

        "auditoria_protocolo_familia": senal.get(
            "auditoria_protocolo_familia",
            "",
        ),

        "auditoria_protocolo_operada": bool(
            senal.get(
                "auditoria_protocolo_operada",
                False,
            )
        ),

        "auditoria_protocolo_idx_senal": senal.get(
            "auditoria_protocolo_idx_senal",
            -1,
        ),

        "auditoria_protocolo_idx_entrada": senal.get(
            "auditoria_protocolo_idx_entrada",
            -1,
        ),

        "auditoria_protocolo_espera_velas": senal.get(
            "auditoria_protocolo_espera_velas",
            -1,
        ),

        "auditoria_protocolo_motivo": senal.get(
            "auditoria_protocolo_motivo",
            "",
        ),

        "auditoria_protocolo_riesgo": senal.get(
            "auditoria_protocolo_riesgo",
            0,
        ),

        "auditoria_protocolo_nivel_riesgo": senal.get(
            "auditoria_protocolo_nivel_riesgo",
            "",
        ),

        "auditoria_protocolo_indice_confirmacion": senal.get(
            "auditoria_protocolo_indice_confirmacion",
            0,
        ),

        "auditoria_protocolo_nivel_confirmacion": senal.get(
            "auditoria_protocolo_nivel_confirmacion",
            "",
        ),

        "auditoria_protocolo_accion_confirmacion": senal.get(
            "auditoria_protocolo_accion_confirmacion",
            "",
        ),

        "auditoria_protocolo_tipo_mercado": senal.get(
            "auditoria_protocolo_tipo_mercado",
            "",
        ),

        "auditoria_protocolo_tendencia": senal.get(
            "auditoria_protocolo_tendencia",
            "",
        ),

        "auditoria_protocolo_pa_tipo": senal.get(
            "auditoria_protocolo_pa_tipo",
            "",
        ),

        "auditoria_protocolo_probabilidad": senal.get(
            "auditoria_protocolo_probabilidad",
            0,
        ),
        # ==================================================
        # F4.3-D — SOMBRA RETEST POST-RUPTURA
        # ==================================================
        
        "sombra_retest_aplica": bool(
            senal.get(
                "sombra_retest_aplica",
                False,
            )
        ),
        
        "sombra_retest_encontro_ruptura": bool(
            senal.get(
                "sombra_retest_encontro_ruptura",
                False,
            )
        ),
        
        "sombra_retest_idx_ruptura": senal.get(
            "sombra_retest_idx_ruptura",
            -1,
        ),
        
        "sombra_retest_nivel_roto": senal.get(
            "sombra_retest_nivel_roto",
            "",
        ),
        
        "sombra_pullback_idx_entrada": senal.get(
            "sombra_pullback_idx_entrada",
            -1,
        ),
        
        "sombra_pullback_espera": senal.get(
            "sombra_pullback_espera",
            -1,
        ),
        
        "sombra_pullback_resultado": senal.get(
            "sombra_pullback_resultado",
            "",
        ),
        
        "sombra_retest_nivel_idx_entrada": senal.get(
            "sombra_retest_nivel_idx_entrada",
            -1,
        ),
        
        "sombra_retest_nivel_espera": senal.get(
            "sombra_retest_nivel_espera",
            -1,
        ),
        
        "sombra_retest_nivel_resultado": senal.get(
            "sombra_retest_nivel_resultado",
            "",
        ),
        # ==================================================
        # C-C2 — APRENDIZAJE POST-PROTOCOLO
        # ==================================================

        "decision_post_protocolo": senal.get(
            "decision_post_protocolo",
            "SIN_DATOS",
        ),

        "autoriza_post_protocolo": bool(
            senal.get(
                "autoriza_post_protocolo",
                True,
            )
        ),

        "probabilidad_post_protocolo": senal.get(
            "probabilidad_post_protocolo",
            0,
        ),

        "intervalo_post_protocolo_inferior": senal.get(
            "intervalo_post_protocolo_inferior",
            0,
        ),

        "intervalo_post_protocolo_superior": senal.get(
            "intervalo_post_protocolo_superior",
            0,
        ),

        "muestra_post_protocolo": senal.get(
            "muestra_post_protocolo",
            0,
        ),

        "confiabilidad_post_protocolo": senal.get(
            "confiabilidad_post_protocolo",
            "SIN_DATOS",
        ),

        "fuente_post_protocolo_principal": _texto(
            fuente_cc2_principal
        ),

        "fuente_post_protocolo_respaldo": _texto(
            fuente_cc2_respaldo
        ),

        # ==================================================
        # C-C2 — IDENTIDAD DIRECTA DE FUENTES
        # ==================================================

        "nivel_post_protocolo_principal": (
            fuente_cc2_principal.get(
                "nivel",
                "",
            )
        ),

        "clave_post_protocolo_principal": (
            fuente_cc2_principal.get(
                "clave",
                "",
            )
        ),

        "nivel_post_protocolo_respaldo": (
            fuente_cc2_respaldo.get(
                "nivel",
                "",
            )
        ),

        "clave_post_protocolo_respaldo": (
            fuente_cc2_respaldo.get(
                "clave",
                "",
            )
        ),

        # ==================================================
        # C-C2 — AUDITORÍA DE GENERALIZACIÓN
        # ==================================================
        #
        # Se usa primero el campo cc2_* si ya existe.
        # Si no existe, se extrae directamente de la fuente
        # real retornada por C-C2.
        # ==================================================

        "cc2_nivel_principal": (
            senal.get("cc2_nivel_principal")
            or fuente_cc2_principal.get(
                "nivel",
                "",
            )
        ),

        "cc2_clave_principal": (
            senal.get("cc2_clave_principal")
            or fuente_cc2_principal.get(
                "clave",
                "",
            )
        ),

        "cc2_train_total_principal": senal.get(
            "cc2_train_total_principal",
            fuente_cc2_principal.get(
                "total",
                0,
            ),
        ),

        "cc2_train_wins_principal": senal.get(
            "cc2_train_wins_principal",
            fuente_cc2_principal.get(
                "wins",
                0,
            ),
        ),

        "cc2_train_losses_principal": senal.get(
            "cc2_train_losses_principal",
            fuente_cc2_principal.get(
                "losses",
                0,
            ),
        ),

        "cc2_train_winrate_principal": senal.get(
            "cc2_train_winrate_principal",
            fuente_cc2_principal.get(
                "winrate",
                0,
            ),
        ),

        "cc2_probabilidad_ajustada_principal": senal.get(
            "cc2_probabilidad_ajustada_principal",
            fuente_cc2_principal.get(
                "probabilidad_ajustada",
                fuente_cc2_principal.get(
                    "probabilidad",
                    0,
                ),
            ),
        ),

        "cc2_ajuste_principal": senal.get(
            "cc2_ajuste_principal",
            fuente_cc2_principal.get(
                "ajuste",
                0,
            ),
        ),

        "cc2_confiabilidad_principal": (
            senal.get("cc2_confiabilidad_principal")
            or fuente_cc2_principal.get(
                "confiabilidad",
                "",
            )
        ),

        "cc2_factor_muestra_principal": senal.get(
            "cc2_factor_muestra_principal",
            fuente_cc2_principal.get(
                "factor_muestra",
                0,
            ),
        ),

        "cc2_nivel_respaldo": (
            senal.get("cc2_nivel_respaldo")
            or fuente_cc2_respaldo.get(
                "nivel",
                "",
            )
        ),

        "cc2_clave_respaldo": (
            senal.get("cc2_clave_respaldo")
            or fuente_cc2_respaldo.get(
                "clave",
                "",
            )
        ),

        "cc2_train_total_respaldo": senal.get(
            "cc2_train_total_respaldo",
            fuente_cc2_respaldo.get(
                "total",
                0,
            ),
        ),

        "cc2_train_winrate_respaldo": senal.get(
            "cc2_train_winrate_respaldo",
            fuente_cc2_respaldo.get(
                "winrate",
                0,
            ),
        ),

        "cc2_probabilidad_ajustada_respaldo": senal.get(
            "cc2_probabilidad_ajustada_respaldo",
            fuente_cc2_respaldo.get(
                "probabilidad_ajustada",
                fuente_cc2_respaldo.get(
                    "probabilidad",
                    0,
                ),
            ),
        ),

        "cc2_fuentes_usadas": _texto(
            senal.get(
                "cc2_fuentes_usadas",
                [],
            )
        ),

        "cc2_claves_consultadas": _texto(
            senal.get(
                "cc2_claves_consultadas",
                [],
            )
        ),

        "cc2_claves_descartadas": _texto(
            senal.get(
                "cc2_claves_descartadas",
                [],
            )
        ),

        # ==================================================
        # VALIDACIÓN RECUPERACIÓN VETO SETUP — SOMBRA
        # ==================================================

        "recuperacion_sombra_candidata": bool(
            senal.get(
                "recuperacion_sombra_candidata",
                False,
            )
        ),

        "recuperacion_sombra_sobrevive_protocolo": bool(
            senal.get(
                "recuperacion_sombra_sobrevive_protocolo",
                False,
            )
        ),

        "recuperacion_sombra_idx_entrada": senal.get(
            "recuperacion_sombra_idx_entrada",
            "",
        ),

        "recuperacion_sombra_motivo": senal.get(
            "recuperacion_sombra_motivo",
            "",
        ),

        "recuperacion_sombra_resultado": senal.get(
            "recuperacion_sombra_resultado",
            "",
        ),

        "recuperacion_sombra_espera_velas": senal.get(
            "recuperacion_sombra_espera_velas",
            0,
        ),

        # ==================================================
        # C3 — BYPASS SOMBRA DE VETOS
        # ==================================================

        "c3_sombra_aplicada": bool(
            senal.get(
                "c3_sombra_aplicada",
                False,
            )
        ),

        "c3_sombra_grupo_veto": senal.get(
            "c3_sombra_grupo_veto",
            "",
        ),

        "c3_sombra_protocolo": senal.get(
            "c3_sombra_protocolo",
            "",
        ),

        "c3_sombra_idx_entrada": senal.get(
            "c3_sombra_idx_entrada",
            -1,
        ),

        "c3_sombra_motivo": senal.get(
            "c3_sombra_motivo",
            "",
        ),

        "c3_sombra_encuentra_entrada": bool(
            senal.get(
                "c3_sombra_encuentra_entrada",
                False,
            )
        ),

        "c3_sombra_resultado": senal.get(
            "c3_sombra_resultado",
            "",
        ),

        "c3_sombra_espera_velas": senal.get(
            "c3_sombra_espera_velas",
            -1,
        ),

        "c3_sombra_riesgo": senal.get(
            "c3_sombra_riesgo",
            0,
        ),

        "c3_sombra_nivel_riesgo": senal.get(
            "c3_sombra_nivel_riesgo",
            "",
        ),

        "c3_sombra_confirmacion": senal.get(
            "c3_sombra_confirmacion",
            "",
        ),

        # ==================================================
        # RESULTADOS
        # ==================================================

        "resultado": info_resultado[
            "resultado"
        ],

        "resultado_hipotetico": info_hipotetico[
            "resultado"
        ],

        "fecha_senal": velas[idx]["from"],

        "precio_entrada_hipotetico": velas[idx][
            "close"
        ],

        "precio_cierre_hipotetico": velas[
            idx + 1
        ]["close"],

        "precio_entrada": velas[
            idx_entrada
        ]["close"],

        "precio_cierre": velas[
            idx_entrada + 1
        ]["close"],

        "movimiento": info_resultado[
            "movimiento"
        ],

        "distancia_resultado": info_resultado[
            "distancia_resultado"
        ],

        "excursion_favor": info_resultado[
            "excursion_favor"
        ],

        "excursion_contra": info_resultado[
            "excursion_contra"
        ],

        "fuerza_cierre_siguiente": info_resultado[
            "fuerza_cierre_siguiente"
        ],

        "open_siguiente": info_resultado[
            "open_siguiente"
        ],

        "close_siguiente": info_resultado[
            "close_siguiente"
        ],

        "high_siguiente": info_resultado[
            "high_siguiente"
        ],

        "low_siguiente": info_resultado[
            "low_siguiente"
        ],

        # ==================================================
        # DECISIÓN UNIFICADA
        # ==================================================

        "decision_unificada_accion": senal.get(
            "decision_unificada_accion",
            decision_oficial,
        ),

        "decision_unificada_score": senal.get(
            "decision_unificada_score",
            0,
        ),

        "decision_unificada_confianza": senal.get(
            "decision_unificada_confianza",
            0,
        ),

        "decision_unificada_razones": _texto(
            senal.get(
                "decision_unificada_razones",
                "",
            )
        ),

        "decision_unificada_advertencias": _texto(
            senal.get(
                "decision_unificada_advertencias",
                "",
            )
        ),

        "decision_unificada_bloqueos": _texto(
            senal.get(
                "decision_unificada_bloqueos",
                "",
            )
        ),

        "razon": _texto(
            senal.get(
                "razon",
                "",
            )
        ),

        "ajuste_ponderacion": senal.get(
            "ajuste_ponderacion",
            0,
        ),

        "motivos_ponderacion": _texto(
            senal.get(
                "motivos_ponderacion",
                "",
            )
        ),

        "pesos_aplicados": _texto(
            senal.get(
                "pesos_aplicados",
                "",
            )
        ),

        "confianza_final_cerebro": senal.get(
            "confianza_final_cerebro",
            senal.get(
                "cerebro_unico_confianza",
                0,
            ),
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
            senal.get(
                "cerebro_unico_confianza",
                0,
            ),
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

def es_candidata_recuperacion_veto_sombra(senal):
    """
    Regla congelada descubierta exclusivamente en TRAIN.

    Solo auditoría:
    - no modifica motor_decision;
    - no modifica motor_protocolos;
    - no cambia la ejecución oficial.
    """

    subtipo_setup = str(
        senal.get("subtipo_setup", "")
        or ""
    ).upper().strip()

    tipo_mercado = str(
        senal.get("tipo_mercado", "")
        or ""
    ).upper().strip()

    return (
        subtipo_setup == "SWEEP_SIMPLE"
        and tipo_mercado == "TENDENCIA_ALCISTA"
    )


def evaluar_recuperacion_veto_sombra(
    senal,
    velas,
    idx,
):
    """
    Simula qué habría ocurrido si únicamente se levantara
    el veto general de setup para la regla congelada.

    Después, la señal debe pasar normalmente por motor_protocolos.
    """

    salida = {
        "candidata": False,
        "sobrevive_protocolo": False,
        "idx_entrada": None,
        "motivo": "",
        "resultado": "",
        "espera_velas": 0,
    }

    if not es_candidata_recuperacion_veto_sombra(senal):
        return salida

    salida["candidata"] = True

    senal_sombra = copy.deepcopy(senal)

    # Única excepción simulada:
    # levantar el veto estructural general del setup.
    senal_sombra[
        "riesgo_estructural_critico_setup"
    ] = False

    idx_entrada, motivo = buscar_entrada_confirmada(
        velas,
        idx,
        senal_sombra,
    )

    salida["motivo"] = motivo

    if idx_entrada is None:
        return salida

    if idx_entrada + 1 >= len(velas):
        salida["motivo"] = (
            "RECUPERACION_SOMBRA_SIN_VELA_RESULTADO"
        )
        return salida

    info = resultado_binario(
        velas,
        idx_entrada,
        senal.get("direccion", ""),
    )

    salida["sobrevive_protocolo"] = True
    salida["idx_entrada"] = idx_entrada
    salida["resultado"] = info["resultado"]
    salida["espera_velas"] = idx_entrada - idx

    return salida



def _c3_bool(valor, default=False):
    if isinstance(valor, bool):
        return valor

    if valor is None:
        return default

    texto = str(valor).lower().strip()

    if texto in {"true", "1", "si", "sí", "yes"}:
        return True

    if texto in {"false", "0", "no", "none", "null", ""}:
        return False

    return default


def _c3_num(valor, default=0.0):
    try:
        return float(valor)
    except Exception:
        return float(default)


def _c3_grupo_veto(senal):
    """
    Clasifica la señal usando exactamente las dos evidencias
    estudiadas en C2.

    No modifica ninguna decisión.
    """

    modo_setup = str(
        senal.get("modo_entrada_setup", "")
        or ""
    ).lower().strip()

    setup_bloquea = _c3_bool(
        senal.get("riesgo_estructural_critico_setup"),
        default=(
            "no_operar" in modo_setup
            or "cancelar" in modo_setup
        ),
    )

    riesgo = _c3_num(
        senal.get("riesgo_protocolo", 0),
        0,
    )

    riesgo_bloquea = riesgo >= 85

    if setup_bloquea and riesgo_bloquea:
        return "SETUP_BLOQUEA + RIESGO_BLOQUEA"

    if setup_bloquea and not riesgo_bloquea:
        return "SETUP_BLOQUEA + RIESGO_PASA"

    if not setup_bloquea and riesgo_bloquea:
        return "SETUP_PASA + RIESGO_BLOQUEA"

    return "SETUP_PASA + RIESGO_PASA"


def _c3_ejecutar_protocolo_sin_vetos(
    velas,
    idx,
    senal,
):
    """
    Ejecuta la misma selección de protocolo de motor_protocolos,
    pero deliberadamente NO llama _riesgo_cancelacion().

    Es una ruta SOMBRA de diagnóstico.
    """

    # Primero se conservan los motores auxiliares reales.
    diagnostico_riesgo = (
        motor_protocolos_mod.evaluar_riesgo_protocolo(
            senal
        )
    )

    senal["riesgo_protocolo"] = diagnostico_riesgo.get(
        "riesgo",
        100,
    )
    senal["nivel_riesgo_protocolo"] = diagnostico_riesgo.get(
        "nivel",
        "ERROR",
    )
    senal["razon_riesgo_protocolo"] = diagnostico_riesgo.get(
        "razon",
        "",
    )

    confirmacion_ia = (
        motor_protocolos_mod.decidir_confirmacion(
            senal
        )
    )

    senal["indice_confirmacion_ia"] = confirmacion_ia.get(
        "indice",
        0,
    )
    senal["nivel_confirmacion_ia"] = confirmacion_ia.get(
        "nivel",
        "BAJO",
    )
    senal["accion_confirmacion_ia"] = confirmacion_ia.get(
        "accion",
        "CANCELAR",
    )
    senal["razon_confirmacion_ia"] = confirmacion_ia.get(
        "razon",
        "",
    )

    protocolo_sugerido = str(
        senal.get("protocolo_sugerido", "")
        or ""
    ).lower().strip()

    # Mantener la prioridad real de ruptura_resistencia.
    if (
        protocolo_sugerido
        == "protocolo_ruptura_resistencia"
    ):
        idx_entrada, motivo = (
            motor_protocolos_mod
            ._protocolo_ruptura_resistencia(
                velas,
                idx,
                senal,
            )
        )

        return (
            idx_entrada,
            motivo,
            "RUPTURA_RESISTENCIA",
        )

    protocolo = motor_protocolos_mod._tipo_protocolo(
        senal
    )

    if protocolo == "SWEEP":
        idx_entrada, motivo = (
            motor_protocolos_mod._protocolo_sweep(
                velas,
                idx,
                senal,
            )
        )

    elif protocolo == "CHOCH":
        idx_entrada, motivo = (
            motor_protocolos_mod._protocolo_choch(
                velas,
                idx,
                senal,
            )
        )

    elif protocolo == "PULLBACK":
        idx_entrada, motivo = (
            motor_protocolos_mod._protocolo_pullback(
                velas,
                idx,
                senal,
            )
        )

    elif protocolo == "REACCION_ZONA":
        idx_entrada, motivo = (
            motor_protocolos_mod._protocolo_reaccion_zona(
                velas,
                idx,
                senal,
            )
        )

    elif protocolo == "CONTINUACION":
        idx_entrada, motivo = (
            motor_protocolos_mod._protocolo_continuacion(
                velas,
                idx,
                senal,
            )
        )

    else:
        idx_entrada, motivo = (
            motor_protocolos_mod._protocolo_generico(
                velas,
                idx,
                senal,
            )
        )

    return idx_entrada, motivo, protocolo


def evaluar_c3_bypass_vetos_sombra(
    senal,
    velas,
    idx,
    motivo_oficial,
):
    """
    C3.

    Solo se aplica cuando la ruta OFICIAL fue cancelada por
    uno de los dos vetos generales estudiados.

    La operación oficial NO cambia.
    """

    salida = {
        "aplicada": False,
        "grupo_veto": "",
        "protocolo": "",
        "idx_entrada": None,
        "motivo": "",
        "encuentra_entrada": False,
        "resultado": "",
        "espera_velas": -1,
        "riesgo": 0,
        "nivel_riesgo": "",
        "confirmacion": "",
    }

    motivos_c3 = {
        "CANCELADA_SETUP_NO_OPERAR",
        "CANCELADA_RIESGO_PROTOCOLO_CRITICO",
    }

    if motivo_oficial not in motivos_c3:
        return salida

    salida["aplicada"] = True

    senal_sombra = copy.deepcopy(senal)

    # Recalcular primero los diagnósticos reales para clasificar
    # correctamente el cruce setup/riesgo.
    diag = motor_protocolos_mod.evaluar_riesgo_protocolo(
        senal_sombra
    )
    senal_sombra["riesgo_protocolo"] = diag.get(
        "riesgo",
        100,
    )
    senal_sombra["nivel_riesgo_protocolo"] = diag.get(
        "nivel",
        "ERROR",
    )

    salida["grupo_veto"] = _c3_grupo_veto(
        senal_sombra
    )

    idx_entrada, motivo, protocolo = (
        _c3_ejecutar_protocolo_sin_vetos(
            velas,
            idx,
            senal_sombra,
        )
    )

    salida["protocolo"] = protocolo
    salida["motivo"] = motivo
    salida["riesgo"] = senal_sombra.get(
        "riesgo_protocolo",
        0,
    )
    salida["nivel_riesgo"] = senal_sombra.get(
        "nivel_riesgo_protocolo",
        "",
    )
    salida["confirmacion"] = senal_sombra.get(
        "accion_confirmacion_ia",
        "",
    )

    if idx_entrada is None:
        return salida

    if idx_entrada + 1 >= len(velas):
        salida["motivo"] = (
            "C3_SOMBRA_SIN_VELA_RESULTADO"
        )
        return salida

    info = resultado_binario(
        velas,
        idx_entrada,
        senal.get("direccion", ""),
    )

    salida["encuentra_entrada"] = True
    salida["idx_entrada"] = idx_entrada
    salida["resultado"] = info["resultado"]
    salida["espera_velas"] = idx_entrada - idx

    return salida

def evaluar_sombra_retest_ruptura(
    senal,
    velas,
    idx,
):
    """
    F4.3-D — experimento SOMBRA.

    Solo estudia señales cuyo protocolo sugerido es
    PROTOCOLO_RUPTURA_RESISTENCIA.

    NO modifica:
    - la decisión del Cerebro;
    - el protocolo oficial;
    - idx_entrada oficial;
    - estado_operacion.

    Compara dos alternativas posteriores a la PRIMERA ruptura
    real encontrada dentro de la ventana autorizada:

    A) pullback_recuperado existente;
    B) retest exacto del nivel roto + recuperación.

    Ambas respetan la misma ventana ESPERAR_2 / ESPERAR_3.
    """

    salida = {
        "aplica": False,
        "encontro_ruptura": False,

        "idx_ruptura": -1,
        "nivel_roto": None,

        "pullback_idx_entrada": -1,
        "pullback_espera": -1,
        "pullback_resultado": "",

        "retest_idx_entrada": -1,
        "retest_espera": -1,
        "retest_resultado": "",
    }

    protocolo_sugerido = str(
        senal.get("protocolo_sugerido", "")
        or ""
    ).lower().strip()

    if (
        protocolo_sugerido
        != "protocolo_ruptura_resistencia"
    ):
        return salida

    salida["aplica"] = True

    direccion = str(
        senal.get("direccion", "")
        or ""
    ).lower().strip()

    if direccion not in ["call", "put"]:
        return salida

    inicio, _, fin = (
        motor_protocolos_mod._ventana_confirmacion(
            senal,
            idx,
            velas,
        )
    )

    # ========================================================
    # 1. ENCONTRAR PRIMERA RUPTURA REAL
    # ========================================================

    idx_ruptura = None
    nivel_roto = None

    for j in range(inicio, fin):
        if not motor_protocolos_mod._ruptura_micro(
            velas,
            j,
            direccion,
        ):
            continue

        idx_ruptura = j

        anteriores = velas[j - 2:j]

        if direccion == "call":
            nivel_roto = max(
                v["max"]
                for v in anteriores
            )
        else:
            nivel_roto = min(
                v["min"]
                for v in anteriores
            )

        break

    if idx_ruptura is None:
        return salida

    salida["encontro_ruptura"] = True
    salida["idx_ruptura"] = idx_ruptura
    salida["nivel_roto"] = nivel_roto

    # ========================================================
    # 2. SOMBRA A — PULLBACK_RECUPERADO EXISTENTE
    # ========================================================

    for k in range(idx_ruptura + 1, fin):
        if not motor_protocolos_mod._pullback_recuperado(
            velas,
            k,
            direccion,
        ):
            continue

        if k + 1 >= len(velas):
            continue

        info = resultado_binario(
            velas,
            k,
            direccion,
        )

        salida["pullback_idx_entrada"] = k
        salida["pullback_espera"] = k - idx
        salida["pullback_resultado"] = info[
            "resultado"
        ]

        break

    # ========================================================
    # 3. SOMBRA B — RETEST EXACTO DEL NIVEL ROTO
    # ========================================================

    for k in range(idx_ruptura + 1, fin):
        if k + 1 >= len(velas):
            continue

        vela = velas[k]

        if direccion == "call":
            toca_nivel = (
                vela["min"]
                <= nivel_roto
            )

            recupera_nivel = (
                vela["close"]
                > nivel_roto
                and vela["close"]
                > vela["open"]
            )

        else:
            toca_nivel = (
                vela["max"]
                >= nivel_roto
            )

            recupera_nivel = (
                vela["close"]
                < nivel_roto
                and vela["close"]
                < vela["open"]
            )

        if not (
            toca_nivel
            and recupera_nivel
        ):
            continue

        info = resultado_binario(
            velas,
            k,
            direccion,
        )

        salida["retest_idx_entrada"] = k
        salida["retest_espera"] = k - idx
        salida["retest_resultado"] = info[
            "resultado"
        ]

        break

    return salida

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
    
        # ========================================================
        # SELECCION CAUSAL DE MERCADOS POR RONDA
        # ========================================================
        # Cada instante histórico vuelve a evaluar los datasets
        # utilizando únicamente las 180 velas conocidas hasta i.
        #
        # No utiliza velas posteriores a la ronda simulada.
        datasets_ronda = seleccionar_top_datasets(
            datasets,
            limite=MAX_ACTIVOS_ANALIZAR,
            indice_actual=i,
            mostrar=False,
        )
    
        senales_ronda = []
    
        for data in datasets_ronda:
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

        # Ranking único BootIQ V3.
        # No recalcula aprendizaje ni decide:
        # solo ordena señales ya evaluadas por el Cerebro Único.
        senales_ronda = ordenar_candidatas_v3(
            senales_ronda
        )

        if ronda % 100 == 0:
            print(
                "Ronda:",
                ronda,
                "Señales:",
                len(senales_ronda),
            )

        for senal in senales_ronda[:MAX_SENALES_POR_RONDA]:
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

                # ========================================================
                # F4.3-D — SOMBRA RETEST POST-RUPTURA
                # ========================================================
                # No altera idx_entrada ni motivo_ejecucion oficiales.
                
                sombra_retest = evaluar_sombra_retest_ruptura(
                    senal,
                    velas,
                    idx,
                )
                
                senal["sombra_retest_aplica"] = (
                    sombra_retest["aplica"]
                )
                
                senal["sombra_retest_encontro_ruptura"] = (
                    sombra_retest["encontro_ruptura"]
                )
                
                senal["sombra_retest_idx_ruptura"] = (
                    sombra_retest["idx_ruptura"]
                )
                
                senal["sombra_retest_nivel_roto"] = (
                    sombra_retest["nivel_roto"]
                )
                
                senal["sombra_pullback_idx_entrada"] = (
                    sombra_retest["pullback_idx_entrada"]
                )
                
                senal["sombra_pullback_espera"] = (
                    sombra_retest["pullback_espera"]
                )
                
                senal["sombra_pullback_resultado"] = (
                    sombra_retest["pullback_resultado"]
                )
                
                senal["sombra_retest_nivel_idx_entrada"] = (
                    sombra_retest["retest_idx_entrada"]
                )
                
                senal["sombra_retest_nivel_espera"] = (
                    sombra_retest["retest_espera"]
                )
                
                senal["sombra_retest_nivel_resultado"] = (
                    sombra_retest["retest_resultado"]
                )
                
                if idx_entrada is None:

                    # ========================================
                    # C3 — BYPASS SOMBRA DE VETOS
                    # ========================================
                    c3_sombra = (
                        evaluar_c3_bypass_vetos_sombra(
                            senal,
                            velas,
                            idx,
                            motivo_ejecucion,
                        )
                    )

                    senal["c3_sombra_aplicada"] = (
                        c3_sombra["aplicada"]
                    )
                    senal["c3_sombra_grupo_veto"] = (
                        c3_sombra["grupo_veto"]
                    )
                    senal["c3_sombra_protocolo"] = (
                        c3_sombra["protocolo"]
                    )
                    senal["c3_sombra_idx_entrada"] = (
                        c3_sombra["idx_entrada"]
                        if c3_sombra["idx_entrada"] is not None
                        else -1
                    )
                    senal["c3_sombra_motivo"] = (
                        c3_sombra["motivo"]
                    )
                    senal["c3_sombra_encuentra_entrada"] = (
                        c3_sombra["encuentra_entrada"]
                    )
                    senal["c3_sombra_resultado"] = (
                        c3_sombra["resultado"]
                    )
                    senal["c3_sombra_espera_velas"] = (
                        c3_sombra["espera_velas"]
                    )
                    senal["c3_sombra_riesgo"] = (
                        c3_sombra["riesgo"]
                    )
                    senal["c3_sombra_nivel_riesgo"] = (
                        c3_sombra["nivel_riesgo"]
                    )
                    senal["c3_sombra_confirmacion"] = (
                        c3_sombra["confirmacion"]
                    )

                    recuperacion_sombra = {
                        "candidata": False,
                        "sobrevive_protocolo": False,
                        "idx_entrada": None,
                        "motivo": "",
                        "resultado": "",
                        "espera_velas": 0,
                    }

                    if (
                        MODO_EXPERIMENTO
                        == MODO_EXPERIMENTO_VALIDACION
                        and motivo_ejecucion
                        == "CANCELADA_SETUP_NO_OPERAR"
                    ):
                        recuperacion_sombra = (
                            evaluar_recuperacion_veto_sombra(
                                senal,
                                velas,
                                idx,
                            )
                        )

                    senal[
                        "recuperacion_sombra_candidata"
                    ] = recuperacion_sombra["candidata"]

                    senal[
                        "recuperacion_sombra_sobrevive_protocolo"
                    ] = recuperacion_sombra[
                        "sobrevive_protocolo"
                    ]

                    senal[
                        "recuperacion_sombra_idx_entrada"
                    ] = recuperacion_sombra["idx_entrada"]

                    senal[
                        "recuperacion_sombra_motivo"
                    ] = recuperacion_sombra["motivo"]

                    senal[
                        "recuperacion_sombra_resultado"
                    ] = recuperacion_sombra["resultado"]

                    senal[
                        "recuperacion_sombra_espera_velas"
                    ] = recuperacion_sombra["espera_velas"]

                    resultados.append(
                        crear_registro_resultado(
                            senal=senal,
                            velas=velas,
                            idx=idx,
                            idx_entrada=idx,
                            motivo_ejecucion=motivo_ejecucion,
                            estado_operacion="CANCELADA_PROTOCOLO",
                            decision_bootiq=decision_bootiq,
                        )
                    )
                    continue
                # ========================================================
                # C-C2 — EVALUACIÓN POST-PROTOCOLO EN SOMBRA
                # ========================================================
                
                decision_post = (
                    evaluar_decision_post_protocolo(
                        senal
                    )
                )
                
                senal["decision_post_protocolo"] = (
                    decision_post.get(
                        "decision_post_protocolo",
                        "SIN_DATOS",
                    )
                )
                
                senal["autoriza_post_protocolo"] = (
                    decision_post.get(
                        "autoriza_post_protocolo",
                        True,
                    )
                )
                
                senal["probabilidad_post_protocolo"] = (
                    decision_post.get(
                        "probabilidad_post_protocolo",
                        0,
                    )
                )
                
                senal[
                    "intervalo_post_protocolo_inferior"
                ] = decision_post.get(
                    "intervalo_post_protocolo_inferior",
                    0,
                )
                
                senal[
                    "intervalo_post_protocolo_superior"
                ] = decision_post.get(
                    "intervalo_post_protocolo_superior",
                    0,
                )
                
                senal["muestra_post_protocolo"] = (
                    decision_post.get(
                        "muestra_post_protocolo",
                        0,
                    )
                )
                
                senal[
                    "confiabilidad_post_protocolo"
                ] = decision_post.get(
                    "confiabilidad_post_protocolo",
                    "SIN_DATOS",
                )
                
                senal[
                    "fuente_post_protocolo_principal"
                ] = decision_post.get(
                    "fuente_post_protocolo_principal"
                )
                
                senal[
                    "fuente_post_protocolo_respaldo"
                ] = decision_post.get(
                    "fuente_post_protocolo_respaldo"
                )

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
        "bootiq_evidencias_price_action",
        "bootiq_evidencias_mercado",
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

        # Modo sombra estadístico BootIQ V3.
        "modo_probabilidad",
        "probabilidad_estimada",
        "intervalo_probabilidad_inferior",
        "intervalo_probabilidad_superior",
        "muestra_probabilidad",
        "wins_probabilidad",
        "losses_probabilidad",
        "confiabilidad_probabilidad",
        "fuente_probabilidad_principal",
        "fuente_probabilidad_respaldo",
        "nivel_probabilidad_principal",
        "clave_probabilidad_principal",
        "decision_estadistica_sombra",
        "operar_estadistico_sombra",
        "requiere_protocolo_estadistico_sombra",
        "motivo_decision_estadistica_sombra",

        # Auditoría de entrada directa V3.
        "directa_evidencia_solida",
        "directa_muestra",
        "directa_confiabilidad",
        "directa_nivel_probabilidad",
        "directa_clave_probabilidad",

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

        # Auditoría motor_protocolos.
        "auditoria_protocolo_tipo",
        "auditoria_protocolo_subtipo",
        "auditoria_protocolo_familia",
        "auditoria_protocolo_operada",
        "auditoria_protocolo_idx_senal",
        "auditoria_protocolo_idx_entrada",
        "auditoria_protocolo_espera_velas",
        "auditoria_protocolo_motivo",
        "auditoria_protocolo_riesgo",
        "auditoria_protocolo_nivel_riesgo",
        "auditoria_protocolo_indice_confirmacion",
        "auditoria_protocolo_nivel_confirmacion",
        "auditoria_protocolo_accion_confirmacion",
        "auditoria_protocolo_tipo_mercado",
        "auditoria_protocolo_tendencia",
        "auditoria_protocolo_pa_tipo",
        "auditoria_protocolo_probabilidad",
        
        # F4.3-D — sombra retest post-ruptura.
        "sombra_retest_aplica",
        "sombra_retest_encontro_ruptura",
        "sombra_retest_idx_ruptura",
        "sombra_retest_nivel_roto",
        
        "sombra_pullback_idx_entrada",
        "sombra_pullback_espera",
        "sombra_pullback_resultado",
        
        "sombra_retest_nivel_idx_entrada",
        "sombra_retest_nivel_espera",
        "sombra_retest_nivel_resultado",
        
        # C-C2 — aprendizaje post-protocolo.
        # ==================================================
        # C-C2 — APRENDIZAJE POST-PROTOCOLO
        # ==================================================
        "decision_post_protocolo",
        "autoriza_post_protocolo",
        "probabilidad_post_protocolo",
        "intervalo_post_protocolo_inferior",
        "intervalo_post_protocolo_superior",
        "muestra_post_protocolo",
        "confiabilidad_post_protocolo",
        "fuente_post_protocolo_principal",
        "fuente_post_protocolo_respaldo",
        
        # ==================================================
        # C-C2 — IDENTIDAD DIRECTA DE FUENTES
        # ==================================================
        "nivel_post_protocolo_principal",
        "clave_post_protocolo_principal",
        "nivel_post_protocolo_respaldo",
        "clave_post_protocolo_respaldo",
        
        # ==================================================
        # C-C2 — AUDITORÍA DE GENERALIZACIÓN
        # ==================================================
        "cc2_nivel_principal",
        "cc2_clave_principal",
        "cc2_train_total_principal",
        "cc2_train_wins_principal",
        "cc2_train_losses_principal",
        "cc2_train_winrate_principal",
        "cc2_probabilidad_ajustada_principal",
        "cc2_ajuste_principal",
        "cc2_confiabilidad_principal",
        "cc2_factor_muestra_principal",
        
        "cc2_nivel_respaldo",
        "cc2_clave_respaldo",
        "cc2_train_total_respaldo",
        "cc2_train_winrate_respaldo",
        "cc2_probabilidad_ajustada_respaldo",
        
        "cc2_fuentes_usadas",
        "cc2_claves_consultadas",
        "cc2_claves_descartadas",
        # ==================================================
        # F5.7-C2B — VETO TÉCNICO SOMBRA
        # ==================================================
        "bootiq_veto_tecnico_sombra_detectado",
        "bootiq_veto_tecnico_sombra_cantidad",
        "bootiq_veto_tecnico_sombra_tipos",
        "bootiq_veto_tecnico_sombra_modo",
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

def resumen_por_rangos(
    resultados,
    campo,
    campo_resultado="resultado_hipotetico",
):
    """
    Agrupa un valor numérico por rangos de confianza.
    """

    rangos = [
        ("0-39", 0, 39.999),
        ("40-44", 40, 44.999),
        ("45-49", 45, 49.999),
        ("50-54", 50, 54.999),
        ("55-59", 55, 59.999),
        ("60-64", 60, 64.999),
        ("65-69", 65, 69.999),
        ("70+", 70, 1000),
    ]

    grupos = {
        nombre: {
            "total": 0,
            "win": 0,
        }
        for nombre, _, _ in rangos
    }

    for r in resultados:

        try:
            valor = float(r.get(campo, 0))
        except Exception:
            continue

        for nombre, minimo, maximo in rangos:

            if minimo <= valor <= maximo:

                grupos[nombre]["total"] += 1

                if r.get(campo_resultado) == "WIN":
                    grupos[nombre]["win"] += 1

                break

    filas = []

    for nombre, _, _ in rangos:

        total = grupos[nombre]["total"]

        win = grupos[nombre]["win"]

        loss = total - win

        wr = round((win / total) * 100, 2) if total else 0

        filas.append(
            (
                nombre,
                total,
                win,
                loss,
                wr,
            )
        )

    return filas
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


def imprimir_comparacion_sombra(resultados):
    """
    Compara la decisión oficial contra la decisión estadística sombra.

    Siempre utiliza resultado_hipotetico para medir la señal original.
    La decisión sombra nunca modifica la ejecución.
    """

    if not resultados:
        return

    grupos = {
        "ACTUAL_SI_SOMBRA_SI": [],
        "ACTUAL_SI_SOMBRA_NO": [],
        "ACTUAL_NO_SOMBRA_SI": [],
        "ACTUAL_NO_SOMBRA_NO": [],
    }

    for registro in resultados:
        actual = bool(registro.get("cerebro_unico_operar", False))
        sombra = bool(registro.get("operar_estadistico_sombra", False))

        if actual and sombra:
            clave = "ACTUAL_SI_SOMBRA_SI"
        elif actual and not sombra:
            clave = "ACTUAL_SI_SOMBRA_NO"
        elif not actual and sombra:
            clave = "ACTUAL_NO_SOMBRA_SI"
        else:
            clave = "ACTUAL_NO_SOMBRA_NO"

        grupos[clave].append(registro)

    print("\n===== COMPARACIÓN DECISIÓN ACTUAL VS SOMBRA =====")

    for clave, filas in grupos.items():
        total = len(filas)
        wins = sum(
            1 for fila in filas
            if fila.get("resultado_hipotetico") == "WIN"
        )
        losses = total - wins
        winrate = round((wins / total) * 100, 2) if total else 0

        print(
            clave,
            "| total:", total,
            "| win:", wins,
            "| loss:", losses,
            "| winrate:", str(winrate) + "%",
        )

    sombra_autorizadas = [
        registro for registro in resultados
        if registro.get("operar_estadistico_sombra") is True
    ]

    total = len(sombra_autorizadas)
    wins = sum(
        1 for registro in sombra_autorizadas
        if registro.get("resultado_hipotetico") == "WIN"
    )
    losses = total - wins
    winrate = round((wins / total) * 100, 2) if total else 0

    print("----------------------------")
    print("Autorizadas por sombra:", total)
    print("WIN sombra:", wins)
    print("LOSS sombra:", losses)
    print("Winrate sombra:", str(winrate) + "%")
    print("=================================================\n")


def _resumen_combinacion(
    filas,
    campos,
    campo_resultado="resultado_hipotetico",
):
    grupos = {}

    for fila in filas:
        clave = tuple(
            str(fila.get(campo, "") or "").strip()
            for campo in campos
        )

        if not any(clave):
            continue

        if clave not in grupos:
            grupos[clave] = {
                "total": 0,
                "win": 0,
                "activos": set(),
            }

        grupos[clave]["total"] += 1

        if fila.get(campo_resultado) == "WIN":
            grupos[clave]["win"] += 1

        activo = str(fila.get("activo", "") or "").strip()

        if activo:
            grupos[clave]["activos"].add(activo)

    salida = []

    for clave, datos in grupos.items():
        total = datos["total"]
        win = datos["win"]
        loss = total - win
        wr = round((win / total) * 100, 2) if total else 0

        salida.append({
            "campos": tuple(campos),
            "clave": clave,
            "total": total,
            "win": win,
            "loss": loss,
            "winrate": wr,
            "activos": len(datos["activos"]),
        })

    return sorted(
        salida,
        key=lambda x: (
            -x["winrate"],
            -x["total"],
            -x["activos"],
        ),
    )


def imprimir_auditoria_veto_setup(resultados):
    """
    Audita exclusivamente CANCELADA_SETUP_NO_OPERAR.

    No modifica decisiones.
    Solo descubre hipótesis sobre TRAIN.
    """

    if MODO_EXPERIMENTO != MODO_EXPERIMENTO_AUDITORIA_TRAIN:
        return

    vetadas = [
        r for r in resultados
        if str(r.get("motivo_ejecucion", "")).upper().strip()
        == "CANCELADA_SETUP_NO_OPERAR"
    ]

    print("\n===== AUDITORIA VETO SETUP — TRAIN =====")

    if not vetadas:
        print("No se encontraron señales CANCELADA_SETUP_NO_OPERAR.")
        print("=========================================")
        return

    total = len(vetadas)

    wins = sum(
        1 for r in vetadas
        if r.get("resultado_hipotetico") == "WIN"
    )

    losses = total - wins

    wr = round((wins / total) * 100, 2) if total else 0

    activos = {
        str(r.get("activo", "") or "").strip()
        for r in vetadas
        if str(r.get("activo", "") or "").strip()
    }

    print("Total vetadas:", total)
    print("WIN hipotéticos:", wins)
    print("LOSS hipotéticos:", losses)
    print("Winrate hipotético:", str(wr) + "%")
    print("Activos presentes:", len(activos))

    campos_simples = [
        ("POR FAMILIA", ["familia_setup"]),
        ("POR TIPO SETUP", ["tipo_setup"]),
        ("POR SUBTIPO", ["subtipo_setup"]),
        ("POR CALIDAD", ["calidad_setup"]),
        ("POR PA", ["pa_tipo"]),
        ("POR DIRECCION PA", ["pa_direccion"]),
        ("POR MERCADO", ["tipo_mercado"]),
        ("POR TENDENCIA", ["estado_tendencia"]),
        ("POR ACCION PRECIO", ["accion_precio"]),
        ("POR PROTOCOLO", ["protocolo_sugerido"]),
        (
            "POR NIVEL PROBABILIDAD",
            ["nivel_probabilidad_principal"],
        ),
    ]

    for titulo, campos in campos_simples:
        print("\n---", titulo, "---")

        filas = _resumen_combinacion(
            vetadas,
            campos,
        )

        for fila in filas[:20]:
            print(
                " | ".join(fila["clave"]),
                "| total:", fila["total"],
                "| win:", fila["win"],
                "| loss:", fila["loss"],
                "| winrate:", str(fila["winrate"]) + "%",
                "| activos:", fila["activos"],
            )

    combinaciones = [
        ["familia_setup", "tipo_mercado"],
        ["familia_setup", "pa_tipo"],
        ["tipo_setup", "pa_tipo"],
        ["tipo_setup", "tipo_mercado"],
        ["calidad_setup", "pa_tipo"],
        ["calidad_setup", "tipo_mercado"],
        ["subtipo_setup", "tipo_mercado"],
        ["familia_setup", "estado_tendencia"],
        ["pa_tipo", "tipo_mercado"],
        [
            "familia_setup",
            "tipo_mercado",
            "estado_tendencia",
        ],
        [
            "tipo_setup",
            "pa_tipo",
            "tipo_mercado",
        ],
    ]

    print("\n--- CANDIDATOS RECUPERABLES TRAIN ---")
    print(
        "Criterio: muestra >= 8, winrate >= 60%, "
        "presencia en >= 2 activos."
    )

    candidatos = []

    for campos in combinaciones:
        filas = _resumen_combinacion(
            vetadas,
            campos,
        )

        for fila in filas:
            if (
                fila["total"] >= 8
                and fila["winrate"] >= 60
                and fila["activos"] >= 2
            ):
                candidatos.append(fila)

    candidatos = sorted(
        candidatos,
        key=lambda x: (
            -x["winrate"],
            -x["total"],
            -x["activos"],
        ),
    )

    if not candidatos:
        print("No hay candidatos que superen los criterios.")

    else:
        for fila in candidatos[:40]:
            print(
                " + ".join(fila["campos"]),
                "=>",
                " | ".join(fila["clave"]),
                "| total:", fila["total"],
                "| win:", fila["win"],
                "| loss:", fila["loss"],
                "| winrate:", str(fila["winrate"]) + "%",
                "| activos:", fila["activos"],
            )

    print("=========================================\n")


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
def imprimir_validacion_recuperacion_sombra(resultados):
    """
    Valida en los 4 datasets reservados la única regla
    descubierta previamente en TRAIN.

    No modifica el resultado oficial del backtest.
    """

    if (
        MODO_EXPERIMENTO
        != MODO_EXPERIMENTO_VALIDACION
    ):
        return

    candidatas = [
        r for r in resultados
        if r.get(
            "recuperacion_sombra_candidata"
        ) is True
    ]

    recuperadas = [
        r for r in candidatas
        if r.get(
            "recuperacion_sombra_sobrevive_protocolo"
        ) is True
    ]

    total_candidatas = len(candidatas)
    total_recuperadas = len(recuperadas)

    wins_recuperadas = sum(
        1
        for r in recuperadas
        if r.get(
            "recuperacion_sombra_resultado"
        ) == "WIN"
    )

    losses_recuperadas = (
        total_recuperadas
        - wins_recuperadas
    )

    wr_recuperadas = (
        round(
            (
                wins_recuperadas
                / total_recuperadas
            ) * 100,
            2,
        )
        if total_recuperadas
        else 0
    )

    operadas_actuales = [
        r for r in resultados
        if str(
            r.get("estado_operacion", "")
        ).startswith("OPERADA")
    ]

    total_actual = len(operadas_actuales)

    wins_actual = sum(
        1
        for r in operadas_actuales
        if r.get("resultado") == "WIN"
    )

    losses_actual = total_actual - wins_actual

    wr_actual = (
        round(
            (wins_actual / total_actual) * 100,
            2,
        )
        if total_actual
        else 0
    )

    total_sombra = (
        total_actual
        + total_recuperadas
    )

    wins_sombra = (
        wins_actual
        + wins_recuperadas
    )

    losses_sombra = (
        losses_actual
        + losses_recuperadas
    )

    wr_sombra = (
        round(
            (wins_sombra / total_sombra) * 100,
            2,
        )
        if total_sombra
        else 0
    )

    print(
        "\n===== VALIDACION RECUPERACION VETO SETUP ====="
    )

    print(
        "Regla congelada:",
        "SWEEP_SIMPLE + TENDENCIA_ALCISTA",
    )

    print("----------------------------------------")
    print("Candidatas encontradas:", total_candidatas)
    print("Sobreviven protocolo:", total_recuperadas)
    print("WIN recuperadas:", wins_recuperadas)
    print("LOSS recuperadas:", losses_recuperadas)
    print("Winrate recuperadas:", str(wr_recuperadas) + "%")

    print("----------------------------------------")

    print(
        "BASELINE VALIDACION:",
        total_actual,
        "operaciones |",
        wins_actual,
        "WIN |",
        losses_actual,
        "LOSS |",
        str(wr_actual) + "%",
    )

    print(
        "SOMBRA + RECUPERACION:",
        total_sombra,
        "operaciones |",
        wins_sombra,
        "WIN |",
        losses_sombra,
        "LOSS |",
        str(wr_sombra) + "%",
    )

    print(
        "============================================\n"
    )


def _resumen_protocolo_combinado(filas, campos, campo_resultado):
    grupos = {}

    for fila in filas:
        clave = tuple(str(fila.get(c, "") or "").strip() for c in campos)

        if not any(clave):
            continue

        datos = grupos.setdefault(
            clave,
            {"total": 0, "win": 0, "activos": set()},
        )

        datos["total"] += 1

        if fila.get(campo_resultado) == "WIN":
            datos["win"] += 1

        activo = str(fila.get("activo", "") or "").strip()
        if activo:
            datos["activos"].add(activo)

    salida = []

    for clave, datos in grupos.items():
        total = datos["total"]
        win = datos["win"]
        loss = total - win
        wr = round((win / total) * 100, 2) if total else 0

        salida.append({
            "clave": clave,
            "total": total,
            "win": win,
            "loss": loss,
            "winrate": wr,
            "activos": len(datos["activos"]),
        })

    return sorted(
        salida,
        key=lambda x: (-x["winrate"], -x["total"], -x["activos"]),
    )


def imprimir_auditoria_motor_protocolos(resultados):
    """
    Auditoría TRAIN de motor_protocolos.
    No modifica ninguna decisión.
    """

    if MODO_EXPERIMENTO != MODO_EXPERIMENTO_AUDITORIA_TRAIN:
        return

    filas = [
        r for r in resultados
        if str(r.get("cerebro_unico_decision", "")).upper().strip()
        == "OPERAR_CON_PROTOCOLO"
    ]

    print("\n===== AUDITORIA MOTOR PROTOCOLOS — TRAIN =====")

    if not filas:
        print("No hay señales OPERAR_CON_PROTOCOLO.")
        print("==============================================")
        return

    normalizadas = []

    for r in filas:
        copia = dict(r)

        if r.get("estado_operacion") == "OPERADA_PROTOCOLO":
            copia["_resultado_proto"] = r.get("resultado")
        else:
            copia["_resultado_proto"] = r.get("resultado_hipotetico")

        normalizadas.append(copia)

    bloques = [
        ("POR PROTOCOLO", ["auditoria_protocolo_tipo"]),
        ("POR PROTOCOLO + ESTADO", ["auditoria_protocolo_tipo", "estado_operacion"]),
        ("POR PROTOCOLO + ESPERA", ["auditoria_protocolo_tipo", "auditoria_protocolo_espera_velas"]),
        ("POR PROTOCOLO + MOTIVO", ["auditoria_protocolo_tipo", "auditoria_protocolo_motivo"]),
        ("POR PROTOCOLO + NIVEL CONFIRMACION", ["auditoria_protocolo_tipo", "auditoria_protocolo_nivel_confirmacion"]),
        ("POR PROTOCOLO + ACCION CONFIRMACION", ["auditoria_protocolo_tipo", "auditoria_protocolo_accion_confirmacion"]),
        ("POR PROTOCOLO + NIVEL RIESGO", ["auditoria_protocolo_tipo", "auditoria_protocolo_nivel_riesgo"]),
        ("POR PROTOCOLO + MERCADO", ["auditoria_protocolo_tipo", "auditoria_protocolo_tipo_mercado"]),
        ("POR PROTOCOLO + TENDENCIA", ["auditoria_protocolo_tipo", "auditoria_protocolo_tendencia"]),
        ("POR PROTOCOLO + PA", ["auditoria_protocolo_tipo", "auditoria_protocolo_pa_tipo"]),
        ("POR PROTOCOLO + SUBTIPO", ["auditoria_protocolo_tipo", "auditoria_protocolo_subtipo"]),
    ]

    for titulo, campos in bloques:
        print("\n---", titulo, "---")

        resumen = _resumen_protocolo_combinado(
            normalizadas,
            campos,
            "_resultado_proto",
        )

        for fila in resumen[:40]:
            print(
                " | ".join(fila["clave"]),
                "| total:", fila["total"],
                "| win:", fila["win"],
                "| loss:", fila["loss"],
                "| winrate:", str(fila["winrate"]) + "%",
                "| activos:", fila["activos"],
            )

    print("\n--- CANDIDATOS PROTOCOLO TRAIN ---")
    print("Criterio: >= 8 muestras, >= 60% WR, >= 2 activos.")

    operadas = [
        r for r in normalizadas
        if r.get("estado_operacion") == "OPERADA_PROTOCOLO"
    ]

    combinaciones = [
        ["auditoria_protocolo_tipo", "auditoria_protocolo_espera_velas"],
        ["auditoria_protocolo_tipo", "auditoria_protocolo_motivo"],
        ["auditoria_protocolo_tipo", "auditoria_protocolo_nivel_confirmacion"],
        ["auditoria_protocolo_tipo", "auditoria_protocolo_nivel_riesgo"],
        ["auditoria_protocolo_tipo", "auditoria_protocolo_tipo_mercado"],
        ["auditoria_protocolo_tipo", "auditoria_protocolo_subtipo", "auditoria_protocolo_espera_velas"],
    ]

    candidatos = []

    for campos in combinaciones:
        resumen = _resumen_protocolo_combinado(
            operadas,
            campos,
            "_resultado_proto",
        )

        for fila in resumen:
            if (
                fila["total"] >= 8
                and fila["winrate"] >= 60
                and fila["activos"] >= 2
            ):
                candidatos.append((campos, fila))

    candidatos.sort(
        key=lambda x: (
            -x[1]["winrate"],
            -x[1]["total"],
            -x[1]["activos"],
        )
    )

    if not candidatos:
        print("No hay candidatos que superen los criterios.")
    else:
        for campos, fila in candidatos[:40]:
            print(
                " + ".join(campos),
                "=>",
                " | ".join(fila["clave"]),
                "| total:", fila["total"],
                "| win:", fila["win"],
                "| loss:", fila["loss"],
                "| winrate:", str(fila["winrate"]) + "%",
                "| activos:", fila["activos"],
            )

    print("==============================================\n")


def _normalizar_valor_modelo(valor):
    texto = str(valor or "").strip().upper()

    if not texto:
        return "SIN_DATO"

    return texto


def _bin_probabilidad_v3(valor):
    try:
        x = float(valor)
    except Exception:
        return "SIN_DATO"

    if x < 45:
        return "<45"
    if x < 50:
        return "45_49"
    if x < 55:
        return "50_54"
    return "55+"


def _bin_espera_protocolo(valor):
    try:
        x = int(float(valor))
    except Exception:
        return "SIN_DATO"

    if x < 0:
        return "SIN_ENTRADA"

    if x >= 5:
        return "5+"

    return str(x)


def _extraer_features_probabilidad_protocolo(registro):
    """
    Features disponibles en el momento en que el protocolo
    ya encontró un punto técnico de entrada.
    """

    return {
        "protocolo": _normalizar_valor_modelo(
            registro.get("auditoria_protocolo_tipo")
        ),
        "subtipo": _normalizar_valor_modelo(
            registro.get("auditoria_protocolo_subtipo")
        ),
        "mercado": _normalizar_valor_modelo(
            registro.get("auditoria_protocolo_tipo_mercado")
        ),
        "tendencia": _normalizar_valor_modelo(
            registro.get("auditoria_protocolo_tendencia")
        ),
        "pa": _normalizar_valor_modelo(
            registro.get("auditoria_protocolo_pa_tipo")
        ),
        "riesgo": _normalizar_valor_modelo(
            registro.get("auditoria_protocolo_nivel_riesgo")
        ),
        "confirmacion": _normalizar_valor_modelo(
            registro.get("auditoria_protocolo_nivel_confirmacion")
        ),
        "espera": _bin_espera_protocolo(
            registro.get("auditoria_protocolo_espera_velas")
        ),
        "prob_v3": _bin_probabilidad_v3(
            registro.get("probabilidad_estimada")
        ),
    }


def _crear_tabla_estadistica(filas, campos):
    tabla = {}

    for r in filas:
        features = _extraer_features_probabilidad_protocolo(r)

        clave = tuple(
            features.get(campo, "SIN_DATO")
            for campo in campos
        )

        datos = tabla.setdefault(
            clave,
            {
                "total": 0,
                "win": 0,
                "activos": set(),
            },
        )

        datos["total"] += 1

        if r.get("resultado") == "WIN":
            datos["win"] += 1

        activo = str(
            r.get("activo", "")
            or ""
        ).strip()

        if activo:
            datos["activos"].add(activo)

    return tabla


def _probabilidad_suavizada(win, total, prior, fuerza_prior=8.0):
    """
    Suavizado bayesiano simple.

    Evita que grupos pequeños como 3/3 aparezcan como 100%.
    """

    if total <= 0:
        return prior

    return (
        win + (prior * fuerza_prior)
    ) / (
        total + fuerza_prior
    )


def construir_modelo_probabilidad_protocolo_train(resultados):
    """
    Construye un estimador estadístico sobre entradas de protocolo
    REALMENTE ejecutadas en TRAIN.

    No modifica decisiones.
    No utiliza VALIDACION.
    """

    operadas = [
        r for r in resultados
        if r.get("estado_operacion") == "OPERADA_PROTOCOLO"
    ]

    total = len(operadas)

    wins = sum(
        1 for r in operadas
        if r.get("resultado") == "WIN"
    )

    prior = (
        wins / total
        if total
        else 0.5
    )

    definiciones = [
        ("PROTOCOLO_SUBTIPO", ["protocolo", "subtipo"]),
        ("PROTOCOLO_MERCADO", ["protocolo", "mercado"]),
        ("PROTOCOLO_RIESGO", ["protocolo", "riesgo"]),
        (
            "PROTOCOLO_CONFIRMACION",
            ["protocolo", "confirmacion"],
        ),
        ("PROTOCOLO_ESPERA", ["protocolo", "espera"]),
        ("PROTOCOLO_PA", ["protocolo", "pa"]),
        (
            "PROTOCOLO_MERCADO_RIESGO",
            ["protocolo", "mercado", "riesgo"],
        ),
        (
            "PROTOCOLO_SUBTIPO_ESPERA",
            ["protocolo", "subtipo", "espera"],
        ),
        (
            "PROTOCOLO_CONFIRMACION_ESPERA",
            ["protocolo", "confirmacion", "espera"],
        ),
    ]

    modelo = {
        "prior": prior,
        "total_train": total,
        "wins_train": wins,
        "tablas": {},
    }

    for nombre, campos in definiciones:
        modelo["tablas"][nombre] = {
            "campos": campos,
            "datos": _crear_tabla_estadistica(
                operadas,
                campos,
            ),
        }

    return modelo


def estimar_probabilidad_protocolo(registro, modelo):
    """
    Combina evidencia estadística TRAIN con backoff.

    Reglas:
    - grupos con < 5 muestras no pesan;
    - grupos con >= 8 y >= 2 activos pesan más;
    - todas las tasas están suavizadas hacia el prior.
    """

    prior = modelo["prior"]
    features = _extraer_features_probabilidad_protocolo(registro)

    suma_pesos = 1.0
    suma = prior
    fuentes = []

    for nombre, info in modelo["tablas"].items():
        campos = info["campos"]

        clave = tuple(
            features.get(campo, "SIN_DATO")
            for campo in campos
        )

        datos = info["datos"].get(clave)

        if not datos:
            continue

        total = datos["total"]

        if total < 5:
            continue

        win = datos["win"]
        activos = len(datos["activos"])

        prob = _probabilidad_suavizada(
            win,
            total,
            prior,
            fuerza_prior=8.0,
        )

        if total >= 12 and activos >= 4:
            peso = 2.0
        elif total >= 8 and activos >= 2:
            peso = 1.5
        else:
            peso = 1.0

        suma += prob * peso
        suma_pesos += peso

        fuentes.append({
            "nombre": nombre,
            "total": total,
            "win": win,
            "activos": activos,
            "prob": prob,
            "peso": peso,
        })

    prob_final = suma / suma_pesos

    return {
        "probabilidad": round(prob_final * 100, 2),
        "fuentes": fuentes,
        "cantidad_fuentes": len(fuentes),
    }


def imprimir_probabilidad_protocolo_train(resultados):
    """
    Evalúa si la probabilidad de protocolo construida con TRAIN
    ordena las entradas ejecutadas de menor a mayor calidad.

    Esta etapa todavía es diagnóstico.
    """

    if (
        MODO_EXPERIMENTO
        != MODO_EXPERIMENTO_AUDITORIA_TRAIN
    ):
        return

    operadas = [
        r for r in resultados
        if r.get("estado_operacion") == "OPERADA_PROTOCOLO"
    ]

    print(
        "\n===== PROBABILIDAD PROTOCOLO — TRAIN ====="
    )

    if not operadas:
        print("No hay operaciones de protocolo.")
        print("==========================================")
        return

    modelo = construir_modelo_probabilidad_protocolo_train(
        resultados
    )

    print(
        "Muestra TRAIN:",
        modelo["total_train"],
        "| WIN:",
        modelo["wins_train"],
        "| prior:",
        str(round(modelo["prior"] * 100, 2)) + "%",
    )

    evaluadas = []

    for r in operadas:
        estimacion = estimar_probabilidad_protocolo(
            r,
            modelo,
        )

        evaluadas.append({
            "resultado": r.get("resultado"),
            "prob": estimacion["probabilidad"],
            "fuentes": estimacion["cantidad_fuentes"],
            "activo": r.get("activo", ""),
            "protocolo": r.get(
                "auditoria_protocolo_tipo",
                "",
            ),
        })

    rangos = [
        ("<50", None, 50),
        ("50-54", 50, 55),
        ("55-59", 55, 60),
        ("60-64", 60, 65),
        ("65+", 65, None),
    ]

    print("\n--- CALIBRACION PROBABILIDAD PROTOCOLO ---")

    for etiqueta, minimo, maximo in rangos:
        grupo = []

        for r in evaluadas:
            p = r["prob"]

            if minimo is not None and p < minimo:
                continue

            if maximo is not None and p >= maximo:
                continue

            grupo.append(r)

        total = len(grupo)

        wins = sum(
            1 for r in grupo
            if r["resultado"] == "WIN"
        )

        loss = total - wins

        wr = (
            round((wins / total) * 100, 2)
            if total
            else 0
        )

        activos = len({
            str(r["activo"])
            for r in grupo
            if str(r["activo"])
        })

        print(
            etiqueta,
            "| total:", total,
            "| win:", wins,
            "| loss:", loss,
            "| winrate:", str(wr) + "%",
            "| activos:", activos,
        )

    ordenadas = sorted(
        evaluadas,
        key=lambda x: x["prob"],
        reverse=True,
    )

    print("\n--- TOP CUANTILES PROTOCOLO ---")

    for porcentaje in [25, 40, 50, 60, 75, 100]:
        n = max(
            1,
            int(
                round(
                    len(ordenadas)
                    * porcentaje
                    / 100
                )
            ),
        )

        grupo = ordenadas[:n]

        wins = sum(
            1 for r in grupo
            if r["resultado"] == "WIN"
        )

        wr = round(
            (wins / len(grupo)) * 100,
            2,
        )

        corte = grupo[-1]["prob"]

        print(
            "TOP",
            str(porcentaje) + "%",
            "| total:", len(grupo),
            "| winrate:", str(wr) + "%",
            "| prob mínima:", str(corte) + "%",
        )

    print("\n--- COBERTURA DE EVIDENCIA ---")

    cobertura = {}

    for r in evaluadas:
        n = r["fuentes"]

        if n not in cobertura:
            cobertura[n] = {
                "total": 0,
                "win": 0,
            }

        cobertura[n]["total"] += 1

        if r["resultado"] == "WIN":
            cobertura[n]["win"] += 1

    for n in sorted(cobertura):
        datos = cobertura[n]
        total = datos["total"]
        win = datos["win"]
        wr = round((win / total) * 100, 2)

        print(
            n,
            "fuentes",
            "| total:", total,
            "| winrate:", str(wr) + "%",
        )

    print("==========================================\n")



def _bool_auditoria(valor, default=False):
    if isinstance(valor, bool):
        return valor

    if valor is None:
        return default

    texto = str(valor).lower().strip()

    if texto in {"true", "1", "si", "sí", "yes"}:
        return True

    if texto in {"false", "0", "no", "none", "null", ""}:
        return False

    return default


def _num_auditoria(valor, default=0.0):
    try:
        return float(valor)
    except Exception:
        return float(default)


def imprimir_matriz_setup_riesgo(resultados):
    """
    C2 — Auditoría cruzada SETUP × RIESGO.

    No cambia ninguna decisión.

    Universo:
    todas las señales que el Cerebro Único clasificó como
    OPERAR_CON_PROTOCOLO.

    SETUP_BLOQUEA reproduce la condición neutral utilizada por
    motor_protocolos:
        riesgo_estructural_critico_setup == True
    con fallback legacy a modo_entrada_setup NO_OPERAR/CANCELAR.

    RIESGO_BLOQUEA reproduce el veto técnico actual:
        riesgo_protocolo >= 85

    El resultado usado es resultado_hipotetico para que todas las
    señales se comparen desde el mismo punto temporal: la vela donde
    nació la señal.
    """

    filas = [
        r for r in resultados
        if str(
            r.get("cerebro_unico_decision", "")
            or ""
        ).upper().strip() == "OPERAR_CON_PROTOCOLO"
    ]

    titulo_modo = (
        "TRAIN"
        if MODO_EXPERIMENTO == MODO_EXPERIMENTO_AUDITORIA_TRAIN
        else "VALIDACION"
    )

    print(
        "\n===== MATRIZ SETUP × RIESGO — "
        + titulo_modo
        + " ====="
    )

    if not filas:
        print("No hay señales OPERAR_CON_PROTOCOLO.")
        print("==============================================")
        return

    grupos = {}

    for r in filas:
        modo_setup = str(
            r.get("modo_entrada_setup", "")
            or ""
        ).lower().strip()

        setup_bloquea = _bool_auditoria(
            r.get("riesgo_estructural_critico_setup"),
            default=(
                "no_operar" in modo_setup
                or "cancelar" in modo_setup
            ),
        )

        riesgo_valor = _num_auditoria(
            r.get("riesgo_protocolo", 0),
            0,
        )
        riesgo_bloquea = riesgo_valor >= 85

        if setup_bloquea and riesgo_bloquea:
            clave = "SETUP_BLOQUEA + RIESGO_BLOQUEA"
        elif setup_bloquea and not riesgo_bloquea:
            clave = "SETUP_BLOQUEA + RIESGO_PASA"
        elif not setup_bloquea and riesgo_bloquea:
            clave = "SETUP_PASA + RIESGO_BLOQUEA"
        else:
            clave = "SETUP_PASA + RIESGO_PASA"

        datos = grupos.setdefault(
            clave,
            {
                "total": 0,
                "win": 0,
                "activos": set(),
                "protocolos": {},
                "tipos_setup": {},
                "subtipos_setup": {},
                "mercados": {},
                "confirmaciones": {},
                "niveles_riesgo": {},
            },
        )

        datos["total"] += 1

        resultado = str(
            r.get("resultado_hipotetico", "")
            or ""
        ).upper().strip()

        if resultado == "WIN":
            datos["win"] += 1

        activo = str(r.get("activo", "") or "").strip()
        if activo:
            datos["activos"].add(activo)

        dimensiones = [
            (
                "protocolos",
                str(
                    r.get("protocolo_sugerido", "")
                    or "SIN_PROTOCOLO"
                ).upper().strip(),
            ),
            (
                "tipos_setup",
                str(
                    r.get("tipo_setup", "")
                    or "SIN_TIPO"
                ).upper().strip(),
            ),
            (
                "subtipos_setup",
                str(
                    r.get("subtipo_setup", "")
                    or "SIN_SUBTIPO"
                ).upper().strip(),
            ),
            (
                "mercados",
                str(
                    r.get("tipo_mercado", "")
                    or "SIN_MERCADO"
                ).upper().strip(),
            ),
            (
                "confirmaciones",
                str(
                    r.get("accion_confirmacion_ia", "")
                    or "SIN_CONFIRMACION"
                ).upper().strip(),
            ),
            (
                "niveles_riesgo",
                str(
                    r.get("nivel_riesgo_protocolo", "")
                    or "SIN_NIVEL"
                ).upper().strip(),
            ),
        ]

        for nombre, valor in dimensiones:
            datos[nombre][valor] = (
                datos[nombre].get(valor, 0) + 1
            )

    orden = [
        "SETUP_BLOQUEA + RIESGO_BLOQUEA",
        "SETUP_BLOQUEA + RIESGO_PASA",
        "SETUP_PASA + RIESGO_BLOQUEA",
        "SETUP_PASA + RIESGO_PASA",
    ]

    for clave in orden:
        datos = grupos.get(
            clave,
            {
                "total": 0,
                "win": 0,
                "activos": set(),
                "protocolos": {},
                "tipos_setup": {},
                "subtipos_setup": {},
                "mercados": {},
                "confirmaciones": {},
                "niveles_riesgo": {},
            },
        )

        total = datos["total"]
        win = datos["win"]
        loss = total - win
        wr = round((win / total) * 100, 2) if total else 0

        print("\n---", clave, "---")
        print(
            "total:", total,
            "| win:", win,
            "| loss:", loss,
            "| winrate:", str(wr) + "%",
            "| activos:", len(datos["activos"]),
        )

        for etiqueta, nombre in [
            ("protocolos", "PROTOCOLOS"),
            ("tipos_setup", "TIPO SETUP"),
            ("subtipos_setup", "SUBTIPO SETUP"),
            ("mercados", "MERCADO"),
            ("confirmaciones", "CONFIRMACION"),
            ("niveles_riesgo", "NIVEL RIESGO"),
        ]:
            valores = sorted(
                datos[etiqueta].items(),
                key=lambda x: (-x[1], x[0]),
            )

            if valores:
                resumen = " | ".join(
                    f"{k}:{v}"
                    for k, v in valores[:8]
                )
                print(nombre + ":", resumen)

    # --------------------------------------------------------
    # Solapamiento global: cuánto duplican setup y riesgo.
    # --------------------------------------------------------
    ambos = grupos.get(
        "SETUP_BLOQUEA + RIESGO_BLOQUEA",
        {},
    ).get("total", 0)

    solo_setup = grupos.get(
        "SETUP_BLOQUEA + RIESGO_PASA",
        {},
    ).get("total", 0)

    solo_riesgo = grupos.get(
        "SETUP_PASA + RIESGO_BLOQUEA",
        {},
    ).get("total", 0)

    ninguno = grupos.get(
        "SETUP_PASA + RIESGO_PASA",
        {},
    ).get("total", 0)

    setup_total = ambos + solo_setup
    riesgo_total = ambos + solo_riesgo

    print("\n--- SOLAPAMIENTO ---")
    print("Universo protocolo:", len(filas))
    print("Setup bloquearía:", setup_total)
    print("Riesgo bloquearía:", riesgo_total)
    print("Ambos bloquearían:", ambos)
    print("Solo setup:", solo_setup)
    print("Solo riesgo:", solo_riesgo)
    print("Ninguno:", ninguno)

    if setup_total:
        print(
            "% de veto setup también cubierto por riesgo:",
            str(
                round(
                    (ambos / setup_total) * 100,
                    2,
                )
            )
            + "%",
        )

    if riesgo_total:
        print(
            "% de veto riesgo también cubierto por setup:",
            str(
                round(
                    (ambos / riesgo_total) * 100,
                    2,
                )
            )
            + "%",
        )

    print("==============================================\n")



def imprimir_c3_bypass_vetos_sombra(resultados):
    """
    Reporte C3.

    Mide el timing REAL que habrían encontrado los protocolos
    específicos si los vetos setup/riesgo no hubieran cortado
    primero la señal.

    No cambia el baseline.
    """

    filas = [
        r for r in resultados
        if r.get("c3_sombra_aplicada")
    ]

    modo = (
        "TRAIN"
        if MODO_EXPERIMENTO
        == MODO_EXPERIMENTO_AUDITORIA_TRAIN
        else "VALIDACION"
    )

    print(
        "\n===== C3 BYPASS SOMBRA DE VETOS — "
        + modo
        + " ====="
    )

    if not filas:
        print("No hay señales alcanzadas por C3.")
        print("============================================")
        return

    total = len(filas)

    con_entrada = [
        r for r in filas
        if r.get("c3_sombra_encuentra_entrada")
    ]

    sin_entrada = total - len(con_entrada)

    wins = sum(
        1 for r in con_entrada
        if str(
            r.get("c3_sombra_resultado", "")
            or ""
        ).upper() == "WIN"
    )

    loss = len(con_entrada) - wins

    wr = (
        round(
            (wins / len(con_entrada)) * 100,
            2,
        )
        if con_entrada
        else 0
    )

    print("Señales vetadas evaluadas:", total)
    print("Protocolo encontró entrada:", len(con_entrada))
    print("Sin entrada técnica:", sin_entrada)
    print(
        "Cobertura timing:",
        str(
            round(
                (len(con_entrada) / total) * 100,
                2,
            )
        ) + "%",
    )
    print(
        "Resultado de entradas sombra:",
        "WIN:", wins,
        "| LOSS:", loss,
        "| WR:", str(wr) + "%",
    )

    # --------------------------------------------------------
    # Por cruce de veto
    # --------------------------------------------------------
    print("\n--- POR GRUPO VETO ---")

    grupos = {}

    for r in filas:
        clave = str(
            r.get("c3_sombra_grupo_veto", "")
            or "SIN_GRUPO"
        )

        d = grupos.setdefault(
            clave,
            {
                "total": 0,
                "entrada": 0,
                "win": 0,
            },
        )

        d["total"] += 1

        if r.get("c3_sombra_encuentra_entrada"):
            d["entrada"] += 1

            if str(
                r.get("c3_sombra_resultado", "")
                or ""
            ).upper() == "WIN":
                d["win"] += 1

    for clave, d in sorted(
        grupos.items(),
        key=lambda x: -x[1]["total"],
    ):
        wr_g = (
            round(
                (d["win"] / d["entrada"]) * 100,
                2,
            )
            if d["entrada"]
            else 0
        )

        print(
            clave,
            "| vetadas:", d["total"],
            "| entradas:", d["entrada"],
            "| win:", d["win"],
            "| loss:", d["entrada"] - d["win"],
            "| WR timing:", str(wr_g) + "%",
        )

    # --------------------------------------------------------
    # Por protocolo específico
    # --------------------------------------------------------
    print("\n--- POR PROTOCOLO SOMBRA ---")

    protocolos = {}

    for r in filas:
        protocolo = str(
            r.get("c3_sombra_protocolo", "")
            or "SIN_PROTOCOLO"
        )

        d = protocolos.setdefault(
            protocolo,
            {
                "total": 0,
                "entrada": 0,
                "win": 0,
                "esperas": [],
                "motivos": {},
            },
        )

        d["total"] += 1

        motivo = str(
            r.get("c3_sombra_motivo", "")
            or "SIN_MOTIVO"
        )

        d["motivos"][motivo] = (
            d["motivos"].get(motivo, 0) + 1
        )

        if r.get("c3_sombra_encuentra_entrada"):
            d["entrada"] += 1

            try:
                espera = int(
                    r.get("c3_sombra_espera_velas", -1)
                )
            except Exception:
                espera = -1

            if espera >= 0:
                d["esperas"].append(espera)

            if str(
                r.get("c3_sombra_resultado", "")
                or ""
            ).upper() == "WIN":
                d["win"] += 1

    for protocolo, d in sorted(
        protocolos.items(),
        key=lambda x: -x[1]["total"],
    ):
        wr_p = (
            round(
                (d["win"] / d["entrada"]) * 100,
                2,
            )
            if d["entrada"]
            else 0
        )

        cobertura = (
            round(
                (d["entrada"] / d["total"]) * 100,
                2,
            )
            if d["total"]
            else 0
        )

        espera_media = (
            round(
                sum(d["esperas"]) / len(d["esperas"]),
                2,
            )
            if d["esperas"]
            else -1
        )

        print(
            protocolo,
            "| vetadas:", d["total"],
            "| entradas:", d["entrada"],
            "| cobertura:", str(cobertura) + "%",
            "| win:", d["win"],
            "| loss:", d["entrada"] - d["win"],
            "| WR timing:", str(wr_p) + "%",
            "| espera media:", espera_media,
        )

        top_motivos = sorted(
            d["motivos"].items(),
            key=lambda x: -x[1],
        )[:5]

        if top_motivos:
            print(
                "  motivos:",
                " | ".join(
                    f"{m}:{n}"
                    for m, n in top_motivos
                ),
            )

    # --------------------------------------------------------
    # Por espera de entrada
    # --------------------------------------------------------
    print("\n--- POR ESPERA SOMBRA ---")

    esperas = {}

    for r in con_entrada:
        try:
            e = int(
                r.get("c3_sombra_espera_velas", -1)
            )
        except Exception:
            e = -1

        d = esperas.setdefault(
            e,
            {"total": 0, "win": 0},
        )

        d["total"] += 1

        if str(
            r.get("c3_sombra_resultado", "")
            or ""
        ).upper() == "WIN":
            d["win"] += 1

    for e in sorted(esperas):
        d = esperas[e]
        wr_e = round(
            (d["win"] / d["total"]) * 100,
            2,
        )

        print(
            e,
            "velas",
            "| total:", d["total"],
            "| win:", d["win"],
            "| loss:", d["total"] - d["win"],
            "| WR:", str(wr_e) + "%",
        )

    print("============================================\n")



def imprimir_c5_timing_ruptura_resistencia(resultados):
    """C5: auditoría de timing de RUPTURA_RESISTENCIA. No cambia decisiones."""
    modo = (
        "TRAIN"
        if MODO_EXPERIMENTO == MODO_EXPERIMENTO_AUDITORIA_TRAIN
        else "VALIDACION"
    )

    filas = [
        r for r in resultados
        if r.get("estado_operacion") == "OPERADA_PROTOCOLO"
        and str(r.get("auditoria_protocolo_tipo", "") or "").upper().strip()
        == "RUPTURA_RESISTENCIA"
    ]

    print("\n===== C5 RUPTURA RESISTENCIA — TIMING " + modo + " =====")

    if not filas:
        print("No hay operaciones RUPTURA_RESISTENCIA.")
        print("==============================================")
        return

    def resumen(grupo):
        total = len(grupo)
        win = sum(1 for r in grupo if str(r.get("resultado", "") or "").upper() == "WIN")
        loss = total - win
        wr = round((win / total) * 100, 2) if total else 0
        activos = len({str(r.get("activo", "") or "") for r in grupo if str(r.get("activo", "") or "")})
        return total, win, loss, wr, activos

    t,w,l,wr,a = resumen(filas)
    print("TOTAL RUPTURA_RESISTENCIA:", t, "| WIN:", w, "| LOSS:", l, "| WR:", str(wr)+"%", "| activos:", a)

    print("\n--- POR ESPERA ---")
    grupos = {}
    for r in filas:
        try:
            espera = int(r.get("auditoria_protocolo_espera_velas", -1))
        except Exception:
            espera = -1
        etiqueta = "5+" if espera >= 5 else str(espera)
        grupos.setdefault(etiqueta, []).append(r)

    for etiqueta in ["1","2","3","4","5+","0","-1"]:
        g = grupos.get(etiqueta, [])
        if not g:
            continue
        t,w,l,wr,a = resumen(g)
        print(etiqueta, "velas | total:", t, "| win:", w, "| loss:", l, "| WR:", str(wr)+"%", "| activos:", a)

    tempranas=[]
    tardias=[]
    for r in filas:
        try:
            espera=int(r.get("auditoria_protocolo_espera_velas",-1))
        except Exception:
            espera=-1
        if espera in (1,2):
            tempranas.append(r)
        elif espera >= 3:
            tardias.append(r)

    print("\n--- TIMING TEMPRANO VS TARDIO ---")
    for nombre,g in [("1-2_VELAS",tempranas),("3+_VELAS",tardias)]:
        t,w,l,wr,a=resumen(g)
        print(nombre, "| total:",t,"| win:",w,"| loss:",l,"| WR:",str(wr)+"%","| activos:",a)

    dimensiones=[
        ("SUBTIPO","subtipo_setup"),
        ("NIVEL_RIESGO","auditoria_protocolo_nivel_riesgo"),
        ("NIVEL_CONFIRMACION","auditoria_protocolo_nivel_confirmacion"),
        ("ACCION_CONFIRMACION","auditoria_protocolo_accion_confirmacion"),
        ("MERCADO","auditoria_protocolo_tipo_mercado"),
        ("TENDENCIA","estado_tendencia"),
        ("MOTIVO","motivo_ejecucion"),
    ]

    for titulo,campo in dimensiones:
        print("\n--- ESPERA × "+titulo+" ---")
        cruces={}
        for r in filas:
            try:
                espera=int(r.get("auditoria_protocolo_espera_velas",-1))
            except Exception:
                espera=-1
            espera_txt="5+" if espera>=5 else str(espera)
            valor=str(r.get(campo,"") or "SIN_DATO").upper().strip()
            cruces.setdefault((espera_txt,valor),[]).append(r)
        for (e,v),g in sorted(cruces.items(), key=lambda kv:(-len(kv[1]),kv[0][0],kv[0][1])):
            if len(g)<2:
                continue
            t,w,l,wr,a=resumen(g)
            print("espera:",e,"|",titulo+":",v,"| total:",t,"| win:",w,"| loss:",l,"| WR:",str(wr)+"%","| activos:",a)

    print("==============================================\n")


def imprimir_c6_auditoria_confirmacion(resultados):
    """
    C6 — Auditoría de motor_confirmacion.

    No cambia decisiones.
    Estudia únicamente señales OPERAR_CON_PROTOCOLO y separa:
    - protocolo real auditado
    - nivel confirmación
    - acción confirmación
    - estado operado/cancelado
    - resultado WIN/LOSS hipotético/real según registro

    Objetivo:
    comprobar si MEDIO/ALTO están calibrados de forma coherente
    en TRAIN y luego en VALIDACION.
    """

    modo = (
        "TRAIN"
        if MODO_EXPERIMENTO
        == MODO_EXPERIMENTO_AUDITORIA_TRAIN
        else "VALIDACION"
    )

    filas = [
        r for r in resultados
        if str(
            r.get("cerebro_unico_decision", "")
            or ""
        ).upper().strip() == "OPERAR_CON_PROTOCOLO"
    ]

    print(
        "\n===== C6 AUDITORIA MOTOR CONFIRMACION — "
        + modo
        + " ====="
    )

    if not filas:
        print("No hay señales OPERAR_CON_PROTOCOLO.")
        print("==============================================")
        return

    def resultado_fila(r):
        """
        C6 mide el resultado según lo que realmente ocurrió:
    
        - OPERADA_PROTOCOLO:
          usa el resultado REAL desde la entrada confirmada.
    
        - CANCELADA_PROTOCOLO:
          como nunca hubo entrada real, usa el resultado
          hipotético desde la señal original.
        """
    
        estado_operacion = str(
            r.get("estado_operacion", "")
            or ""
        ).upper().strip()
    
        if estado_operacion == "OPERADA_PROTOCOLO":
            return str(
                r.get("resultado", "")
                or ""
            ).upper().strip()
    
        return str(
            r.get("resultado_hipotetico", "")
            or ""
        ).upper().strip()
    
    def resumen(grupo):
        total = len(grupo)
        win = sum(
            1 for r in grupo
            if resultado_fila(r) == "WIN"
        )
        loss = total - win
        wr = round((win / total) * 100, 2) if total else 0
        activos = len({
            str(r.get("activo", "") or "")
            for r in grupo
            if str(r.get("activo", "") or "")
        })
        return total, win, loss, wr, activos

    total, win, loss, wr, activos = resumen(filas)

    print(
        "UNIVERSO PROTOCOLO:",
        total,
        "| WIN:", win,
        "| LOSS:", loss,
        "| WR:", str(wr) + "%",
        "| activos:", activos,
    )

    # --------------------------------------------------------
    # 1) Nivel confirmación global
    # --------------------------------------------------------
    print("\n--- NIVEL CONFIRMACION GLOBAL ---")

    niveles = {}
    for r in filas:
        nivel = str(
            r.get("auditoria_protocolo_nivel_confirmacion", "")
            or r.get("nivel_confirmacion_ia", "")
            or "SIN_DATO"
        ).upper().strip()

        niveles.setdefault(nivel, []).append(r)

    for nivel, grupo in sorted(
        niveles.items(),
        key=lambda kv: -len(kv[1]),
    ):
        t, w, l, wr_g, act = resumen(grupo)
        print(
            nivel,
            "| total:", t,
            "| win:", w,
            "| loss:", l,
            "| WR:", str(wr_g) + "%",
            "| activos:", act,
        )

    # --------------------------------------------------------
    # 2) Acción confirmación global
    # --------------------------------------------------------
    print("\n--- ACCION CONFIRMACION GLOBAL ---")

    acciones = {}
    for r in filas:
        accion = str(
            r.get("auditoria_protocolo_accion_confirmacion", "")
            or r.get("accion_confirmacion_ia", "")
            or "SIN_DATO"
        ).upper().strip()

        acciones.setdefault(accion, []).append(r)

    for accion, grupo in sorted(
        acciones.items(),
        key=lambda kv: -len(kv[1]),
    ):
        t, w, l, wr_g, act = resumen(grupo)
        print(
            accion,
            "| total:", t,
            "| win:", w,
            "| loss:", l,
            "| WR:", str(wr_g) + "%",
            "| activos:", act,
        )

    # --------------------------------------------------------
    # 3) Protocolo × nivel confirmación
    # --------------------------------------------------------
    print("\n--- PROTOCOLO × NIVEL CONFIRMACION ---")

    grupos = {}

    for r in filas:
        protocolo = str(
            r.get("auditoria_protocolo_tipo", "")
            or "SIN_PROTOCOLO"
        ).upper().strip()

        nivel = str(
            r.get("auditoria_protocolo_nivel_confirmacion", "")
            or r.get("nivel_confirmacion_ia", "")
            or "SIN_DATO"
        ).upper().strip()

        grupos.setdefault(
            (protocolo, nivel),
            [],
        ).append(r)

    for (protocolo, nivel), grupo in sorted(
        grupos.items(),
        key=lambda kv: (-len(kv[1]), kv[0][0], kv[0][1]),
    ):
        t, w, l, wr_g, act = resumen(grupo)
        print(
            protocolo,
            "|", nivel,
            "| total:", t,
            "| win:", w,
            "| loss:", l,
            "| WR:", str(wr_g) + "%",
            "| activos:", act,
        )

    # --------------------------------------------------------
    # 4) Protocolo × acción confirmación
    # --------------------------------------------------------
    print("\n--- PROTOCOLO × ACCION CONFIRMACION ---")

    grupos = {}

    for r in filas:
        protocolo = str(
            r.get("auditoria_protocolo_tipo", "")
            or "SIN_PROTOCOLO"
        ).upper().strip()

        accion = str(
            r.get("auditoria_protocolo_accion_confirmacion", "")
            or r.get("accion_confirmacion_ia", "")
            or "SIN_DATO"
        ).upper().strip()

        grupos.setdefault(
            (protocolo, accion),
            [],
        ).append(r)

    for (protocolo, accion), grupo in sorted(
        grupos.items(),
        key=lambda kv: (-len(kv[1]), kv[0][0], kv[0][1]),
    ):
        t, w, l, wr_g, act = resumen(grupo)
        print(
            protocolo,
            "|", accion,
            "| total:", t,
            "| win:", w,
            "| loss:", l,
            "| WR:", str(wr_g) + "%",
            "| activos:", act,
        )

    # --------------------------------------------------------
    # 5) Protocolo × nivel × estado
    # --------------------------------------------------------
    print("\n--- PROTOCOLO × NIVEL × ESTADO ---")

    grupos = {}

    for r in filas:
        protocolo = str(
            r.get("auditoria_protocolo_tipo", "")
            or "SIN_PROTOCOLO"
        ).upper().strip()

        nivel = str(
            r.get("auditoria_protocolo_nivel_confirmacion", "")
            or r.get("nivel_confirmacion_ia", "")
            or "SIN_DATO"
        ).upper().strip()

        estado = str(
            r.get("estado_operacion", "")
            or "SIN_ESTADO"
        ).upper().strip()

        grupos.setdefault(
            (protocolo, nivel, estado),
            [],
        ).append(r)

    for (protocolo, nivel, estado), grupo in sorted(
        grupos.items(),
        key=lambda kv: (-len(kv[1]), kv[0][0], kv[0][1], kv[0][2]),
    ):
        t, w, l, wr_g, act = resumen(grupo)
        print(
            protocolo,
            "|", nivel,
            "|", estado,
            "| total:", t,
            "| win:", w,
            "| loss:", l,
            "| WR:", str(wr_g) + "%",
            "| activos:", act,
        )

    # --------------------------------------------------------
    # 6) Índice confirmación por rangos
    # --------------------------------------------------------
    print("\n--- INDICE CONFIRMACION POR RANGO ---")

    rangos = {
        "0-44": [],
        "45-59": [],
        "60-74": [],
        "75+": [],
    }

    for r in filas:
        try:
            indice = float(
                r.get("indice_confirmacion_ia", 0)
                or 0
            )
        except Exception:
            indice = 0.0

        if indice < 45:
            clave = "0-44"
        elif indice < 60:
            clave = "45-59"
        elif indice < 75:
            clave = "60-74"
        else:
            clave = "75+"

        rangos[clave].append(r)

    for clave in ["0-44", "45-59", "60-74", "75+"]:
        grupo = rangos[clave]
        if not grupo:
            continue

        t, w, l, wr_g, act = resumen(grupo)
        print(
            clave,
            "| total:", t,
            "| win:", w,
            "| loss:", l,
            "| WR:", str(wr_g) + "%",
            "| activos:", act,
        )

    # --------------------------------------------------------
    # 7) Señal de posible inversión
    # --------------------------------------------------------
    medio = niveles.get("MEDIO", [])
    alto = niveles.get("ALTO", [])

    print("\n--- COMPARACION MEDIO VS ALTO ---")

    for nombre, grupo in [
        ("MEDIO", medio),
        ("ALTO", alto),
    ]:
        t, w, l, wr_g, act = resumen(grupo)
        print(
            nombre,
            "| total:", t,
            "| win:", w,
            "| loss:", l,
            "| WR:", str(wr_g) + "%",
            "| activos:", act,
        )

    if medio and alto:
        _, _, _, wr_medio, _ = resumen(medio)
        _, _, _, wr_alto, _ = resumen(alto)

        print(
            "DIFERENCIA MEDIO - ALTO:",
            str(round(wr_medio - wr_alto, 2)) + " puntos",
        )

    print("==============================================\n")



def imprimir_c7_confirmacion_vs_espera(resultados):
    """
    C7 — ACCION_CONFIRMACION × ESPERA REAL

    Auditoría pura. No cambia decisiones ni operaciones.

    Compara:
      motor_confirmacion -> ESPERAR_2 / ESPERAR_3
    contra:
      auditoria_protocolo_espera_velas real

    Universo:
      señales OPERAR_CON_PROTOCOLO que llegaron a una salida
      auditable de protocolo.

    Separa por:
      - acción confirmación
      - espera real
      - protocolo
      - estado operada/cancelada
    """

    modo = (
        "TRAIN"
        if MODO_EXPERIMENTO
        == MODO_EXPERIMENTO_AUDITORIA_TRAIN
        else "VALIDACION"
    )

    filas = [
        r for r in resultados
        if str(
            r.get("cerebro_unico_decision", "")
            or ""
        ).upper().strip() == "OPERAR_CON_PROTOCOLO"
    ]

    print(
        "\n===== C7 CONFIRMACION × ESPERA REAL — "
        + modo
        + " ====="
    )

    if not filas:
        print("No hay señales OPERAR_CON_PROTOCOLO.")
        print("==============================================")
        return

    def resultado_fila(r):
        """
        C7 distingue correctamente entre:
    
        - operación ejecutada:
          usa el resultado REAL desde la entrada del protocolo;
    
        - operación cancelada:
          como no existió entrada real, conserva únicamente
          el resultado hipotético de la señal original.
        """
    
        estado_operacion = str(
            r.get("estado_operacion", "")
            or ""
        ).upper().strip()
    
        if estado_operacion == "OPERADA_PROTOCOLO":
            return str(
                r.get("resultado", "")
                or ""
            ).upper().strip()
    
        return str(
            r.get("resultado_hipotetico", "")
            or ""
        ).upper().strip()
    def resumen(grupo):
        total = len(grupo)
        win = sum(
            1 for r in grupo
            if resultado_fila(r) == "WIN"
        )
        loss = total - win
        wr = round((win / total) * 100, 2) if total else 0
        activos = len({
            str(r.get("activo", "") or "")
            for r in grupo
            if str(r.get("activo", "") or "")
        })
        return total, win, loss, wr, activos

    def accion_confirmacion(r):
        return str(
            r.get("auditoria_protocolo_accion_confirmacion", "")
            or r.get("accion_confirmacion_ia", "")
            or "SIN_DATO"
        ).upper().strip()

    def espera_real(r):
        try:
            return int(
                r.get("auditoria_protocolo_espera_velas", -1)
            )
        except Exception:
            return -1

    def protocolo(r):
        return str(
            r.get("auditoria_protocolo_tipo", "")
            or "SIN_PROTOCOLO"
        ).upper().strip()

    def categoria_relacion(accion, espera):
        """
        Clasifica si el protocolo terminó entrando antes,
        exactamente o después de lo sugerido.
        """

        if espera < 0:
            return "SIN_ENTRADA"

        if accion == "ESPERAR_2":
            objetivo = 2
        elif accion == "ESPERAR_3":
            objetivo = 3
        else:
            return "SIN_OBJETIVO"

        if espera < objetivo:
            return "ANTES_DE_LO_SUGERIDO"

        if espera == objetivo:
            return "EXACTAMENTE_LO_SUGERIDO"

        return "DESPUES_DE_LO_SUGERIDO"

    # --------------------------------------------------------
    # GLOBAL
    # --------------------------------------------------------
    print("\n--- GLOBAL ACCION × ESPERA REAL ---")

    grupos = {}

    for r in filas:
        accion = accion_confirmacion(r)
        espera = espera_real(r)

        if espera >= 5:
            espera_txt = "5+"
        else:
            espera_txt = str(espera)

        grupos.setdefault(
            (accion, espera_txt),
            [],
        ).append(r)

    for (accion, espera_txt), grupo in sorted(
        grupos.items(),
        key=lambda kv: (-len(kv[1]), kv[0][0], kv[0][1]),
    ):
        t, w, l, wr, act = resumen(grupo)

        print(
            accion,
            "| espera_real:", espera_txt,
            "| total:", t,
            "| win:", w,
            "| loss:", l,
            "| WR:", str(wr) + "%",
            "| activos:", act,
        )

    # --------------------------------------------------------
    # RELACIÓN CON LA RECOMENDACIÓN
    # --------------------------------------------------------
    print("\n--- CUMPLIMIENTO DE LA RECOMENDACION ---")

    grupos = {}

    for r in filas:
        accion = accion_confirmacion(r)
        espera = espera_real(r)
        relacion = categoria_relacion(
            accion,
            espera,
        )

        grupos.setdefault(
            (accion, relacion),
            [],
        ).append(r)

    for (accion, relacion), grupo in sorted(
        grupos.items(),
        key=lambda kv: (-len(kv[1]), kv[0][0], kv[0][1]),
    ):
        t, w, l, wr, act = resumen(grupo)

        print(
            accion,
            "|", relacion,
            "| total:", t,
            "| win:", w,
            "| loss:", l,
            "| WR:", str(wr) + "%",
            "| activos:", act,
        )

    # --------------------------------------------------------
    # PROTOCOLO × ACCIÓN × RELACIÓN
    # --------------------------------------------------------
    print("\n--- PROTOCOLO × ACCION × RELACION ---")

    grupos = {}

    for r in filas:
        p = protocolo(r)
        accion = accion_confirmacion(r)
        espera = espera_real(r)
        relacion = categoria_relacion(
            accion,
            espera,
        )

        grupos.setdefault(
            (p, accion, relacion),
            [],
        ).append(r)

    for (p, accion, relacion), grupo in sorted(
        grupos.items(),
        key=lambda kv: (
            -len(kv[1]),
            kv[0][0],
            kv[0][1],
            kv[0][2],
        ),
    ):
        t, w, l, wr, act = resumen(grupo)

        print(
            p,
            "|", accion,
            "|", relacion,
            "| total:", t,
            "| win:", w,
            "| loss:", l,
            "| WR:", str(wr) + "%",
            "| activos:", act,
        )

    # --------------------------------------------------------
    # PROTOCOLO × ACCIÓN × ESPERA EXACTA
    # --------------------------------------------------------
    print("\n--- PROTOCOLO × ACCION × ESPERA EXACTA ---")

    grupos = {}

    for r in filas:
        p = protocolo(r)
        accion = accion_confirmacion(r)
        espera = espera_real(r)

        if espera >= 5:
            espera_txt = "5+"
        else:
            espera_txt = str(espera)

        grupos.setdefault(
            (p, accion, espera_txt),
            [],
        ).append(r)

    for (p, accion, espera_txt), grupo in sorted(
        grupos.items(),
        key=lambda kv: (
            -len(kv[1]),
            kv[0][0],
            kv[0][1],
            kv[0][2],
        ),
    ):
        t, w, l, wr, act = resumen(grupo)

        print(
            p,
            "|", accion,
            "| espera:", espera_txt,
            "| total:", t,
            "| win:", w,
            "| loss:", l,
            "| WR:", str(wr) + "%",
            "| activos:", act,
        )

    # --------------------------------------------------------
    # SOLO OPERADAS
    # --------------------------------------------------------
    print("\n--- SOLO OPERADAS: ACCION × RELACION ---")

    operadas = [
        r for r in filas
        if str(
            r.get("estado_operacion", "")
            or ""
        ).upper().strip() == "OPERADA_PROTOCOLO"
    ]

    grupos = {}

    for r in operadas:
        accion = accion_confirmacion(r)
        espera = espera_real(r)
        relacion = categoria_relacion(
            accion,
            espera,
        )

        grupos.setdefault(
            (accion, relacion),
            [],
        ).append(r)

    for (accion, relacion), grupo in sorted(
        grupos.items(),
        key=lambda kv: (-len(kv[1]), kv[0][0], kv[0][1]),
    ):
        t, w, l, wr, act = resumen(grupo)

        print(
            accion,
            "|", relacion,
            "| total:", t,
            "| win:", w,
            "| loss:", l,
            "| WR:", str(wr) + "%",
            "| activos:", act,
        )

    # --------------------------------------------------------
    # RESUMEN DE COHERENCIA
    # --------------------------------------------------------
    print("\n--- RESUMEN COHERENCIA ---")

    con_objetivo = [
        r for r in filas
        if accion_confirmacion(r)
        in {"ESPERAR_2", "ESPERAR_3"}
    ]

    exactas = []
    antes = []
    despues = []
    sin_entrada = []

    for r in con_objetivo:
        rel = categoria_relacion(
            accion_confirmacion(r),
            espera_real(r),
        )

        if rel == "EXACTAMENTE_LO_SUGERIDO":
            exactas.append(r)
        elif rel == "ANTES_DE_LO_SUGERIDO":
            antes.append(r)
        elif rel == "DESPUES_DE_LO_SUGERIDO":
            despues.append(r)
        elif rel == "SIN_ENTRADA":
            sin_entrada.append(r)

    total_obj = len(con_objetivo)

    print("Señales con objetivo de espera:", total_obj)
    print(
        "Exactamente:",
        len(exactas),
        "|",
        str(
            round(
                (len(exactas) / total_obj) * 100,
                2,
            )
            if total_obj else 0
        ) + "%",
    )
    print(
        "Antes:",
        len(antes),
        "|",
        str(
            round(
                (len(antes) / total_obj) * 100,
                2,
            )
            if total_obj else 0
        ) + "%",
    )
    print(
        "Después:",
        len(despues),
        "|",
        str(
            round(
                (len(despues) / total_obj) * 100,
                2,
            )
            if total_obj else 0
        ) + "%",
    )
    print(
        "Sin entrada:",
        len(sin_entrada),
        "|",
        str(
            round(
                (len(sin_entrada) / total_obj) * 100,
                2,
            )
            if total_obj else 0
        ) + "%",
    )

    print("==============================================\n")



def imprimir_c8_evento_tecnico(resultados):
    """
    C8 — EVENTO TECNICO QUE DISPARA LA ENTRADA

    Auditoría pura: NO modifica decisiones.

    Usa únicamente información ya emitida por motor_protocolos:
      - auditoria_protocolo_motivo / motivo_ejecucion
      - auditoria_protocolo_tipo
      - auditoria_protocolo_espera_velas
      - accion_confirmacion_ia
      - subtipo_setup
      - resultado

    Objetivo:
    identificar QUÉ evento técnico real acompaña las entradas
    tempranas, exactas y tardías, especialmente en
    RUPTURA_RESISTENCIA.
    """

    modo = (
        "TRAIN"
        if MODO_EXPERIMENTO
        == MODO_EXPERIMENTO_AUDITORIA_TRAIN
        else "VALIDACION"
    )

    filas = [
        r for r in resultados
        if str(
            r.get("estado_operacion", "")
            or ""
        ).upper().strip() == "OPERADA_PROTOCOLO"
    ]

    print(
        "\n===== C8 EVENTO TECNICO DE ENTRADA — "
        + modo
        + " ====="
    )

    if not filas:
        print("No hay operaciones de protocolo.")
        print("==============================================")
        return

    def resultado_fila(r):
        return str(
            r.get("resultado", "")
            or ""
        ).upper().strip()

    def resumen(grupo):
        total = len(grupo)
        win = sum(
            1 for r in grupo
            if resultado_fila(r) == "WIN"
        )
        loss = total - win
        wr = round((win / total) * 100, 2) if total else 0
        activos = len({
            str(r.get("activo", "") or "")
            for r in grupo
            if str(r.get("activo", "") or "")
        })
        return total, win, loss, wr, activos

    def protocolo(r):
        return str(
            r.get("auditoria_protocolo_tipo", "")
            or "SIN_PROTOCOLO"
        ).upper().strip()

    def motivo(r):
        return str(
            r.get("auditoria_protocolo_motivo", "")
            or r.get("motivo_ejecucion", "")
            or "SIN_MOTIVO"
        ).upper().strip()

    def accion(r):
        return str(
            r.get("auditoria_protocolo_accion_confirmacion", "")
            or r.get("accion_confirmacion_ia", "")
            or "SIN_DATO"
        ).upper().strip()

    def espera(r):
        try:
            return int(
                r.get("auditoria_protocolo_espera_velas", -1)
            )
        except Exception:
            return -1

    def relacion(r):
        e = espera(r)
        a = accion(r)

        if e < 0:
            return "SIN_ENTRADA"

        if a == "ESPERAR_2":
            objetivo = 2
        elif a == "ESPERAR_3":
            objetivo = 3
        else:
            return "SIN_OBJETIVO"

        if e < objetivo:
            return "ANTES"
        if e == objetivo:
            return "EXACTA"
        return "DESPUES"

    def familia_evento(texto):
        """
        Agrupa el motivo sin inventar nuevas señales.
        Solo resume palabras que ya aparecen en el motivo real.
        """
        t = str(texto or "").upper()

        if "CONTINUIDAD" in t:
            return "CONTINUIDAD"

        if "RECHAZO" in t:
            return "RECHAZO"

        if "IMPULSO" in t:
            return "IMPULSO"

        if "CONFIRMACION_MEDIA" in t or t.endswith("_MEDIA"):
            return "CONFIRMACION_MEDIA"

        if "RECUPERACION" in t:
            return "RECUPERACION"

        return "OTRO"

    total, win, loss, wr, activos = resumen(filas)

    print(
        "OPERADAS PROTOCOLO:",
        total,
        "| WIN:", win,
        "| LOSS:", loss,
        "| WR:", str(wr) + "%",
        "| activos:", activos,
    )

    # --------------------------------------------------------
    # EVENTO EXACTO GLOBAL
    # --------------------------------------------------------
    print("\n--- EVENTO EXACTO GLOBAL ---")

    grupos = {}

    for r in filas:
        m = motivo(r)
        grupos.setdefault(m, []).append(r)

    for m, grupo in sorted(
        grupos.items(),
        key=lambda kv: (-len(kv[1]), kv[0]),
    ):
        t, w, l, wr_g, act = resumen(grupo)

        print(
            m,
            "| total:", t,
            "| win:", w,
            "| loss:", l,
            "| WR:", str(wr_g) + "%",
            "| activos:", act,
        )

    # --------------------------------------------------------
    # FAMILIA EVENTO GLOBAL
    # --------------------------------------------------------
    print("\n--- FAMILIA EVENTO GLOBAL ---")

    grupos = {}

    for r in filas:
        f = familia_evento(motivo(r))
        grupos.setdefault(f, []).append(r)

    for f, grupo in sorted(
        grupos.items(),
        key=lambda kv: -len(kv[1]),
    ):
        t, w, l, wr_g, act = resumen(grupo)

        print(
            f,
            "| total:", t,
            "| win:", w,
            "| loss:", l,
            "| WR:", str(wr_g) + "%",
            "| activos:", act,
        )

    # --------------------------------------------------------
    # PROTOCOLO × EVENTO EXACTO
    # --------------------------------------------------------
    print("\n--- PROTOCOLO × EVENTO EXACTO ---")

    grupos = {}

    for r in filas:
        clave = (
            protocolo(r),
            motivo(r),
        )
        grupos.setdefault(clave, []).append(r)

    for (p, m), grupo in sorted(
        grupos.items(),
        key=lambda kv: (-len(kv[1]), kv[0][0], kv[0][1]),
    ):
        t, w, l, wr_g, act = resumen(grupo)

        print(
            p,
            "|", m,
            "| total:", t,
            "| win:", w,
            "| loss:", l,
            "| WR:", str(wr_g) + "%",
            "| activos:", act,
        )

    # --------------------------------------------------------
    # PROTOCOLO × EVENTO × RELACION TEMPORAL
    # --------------------------------------------------------
    print("\n--- PROTOCOLO × EVENTO × TIMING ---")

    grupos = {}

    for r in filas:
        clave = (
            protocolo(r),
            familia_evento(motivo(r)),
            relacion(r),
        )
        grupos.setdefault(clave, []).append(r)

    for (p, f, rel), grupo in sorted(
        grupos.items(),
        key=lambda kv: (
            -len(kv[1]),
            kv[0][0],
            kv[0][1],
            kv[0][2],
        ),
    ):
        t, w, l, wr_g, act = resumen(grupo)

        print(
            p,
            "| evento:", f,
            "| timing:", rel,
            "| total:", t,
            "| win:", w,
            "| loss:", l,
            "| WR:", str(wr_g) + "%",
            "| activos:", act,
        )

    # --------------------------------------------------------
    # RUPTURA_RESISTENCIA — FOCO C8
    # --------------------------------------------------------
    ruptura = [
        r for r in filas
        if protocolo(r) == "RUPTURA_RESISTENCIA"
    ]

    print("\n--- FOCO RUPTURA_RESISTENCIA ---")

    if ruptura:
        t, w, l, wr_g, act = resumen(ruptura)
        print(
            "TOTAL",
            "| total:", t,
            "| win:", w,
            "| loss:", l,
            "| WR:", str(wr_g) + "%",
            "| activos:", act,
        )

        grupos = {}

        for r in ruptura:
            clave = (
                accion(r),
                str(espera(r)),
                familia_evento(motivo(r)),
                str(
                    r.get("subtipo_setup", "")
                    or "SIN_SUBTIPO"
                ).upper().strip(),
            )

            grupos.setdefault(clave, []).append(r)

        for (
            accion_txt,
            espera_txt,
            evento_txt,
            subtipo_txt,
        ), grupo in sorted(
            grupos.items(),
            key=lambda kv: (
                -len(kv[1]),
                kv[0][0],
                kv[0][1],
                kv[0][2],
                kv[0][3],
            ),
        ):
            # Mostrar grupos de al menos 2 para evitar ruido extremo.
            if len(grupo) < 2:
                continue

            t, w, l, wr_g, act = resumen(grupo)

            print(
                accion_txt,
                "| espera:", espera_txt,
                "| evento:", evento_txt,
                "| subtipo:", subtipo_txt,
                "| total:", t,
                "| win:", w,
                "| loss:", l,
                "| WR:", str(wr_g) + "%",
                "| activos:", act,
            )

    # --------------------------------------------------------
    # ENTRADAS ANTES DE LO SUGERIDO
    # --------------------------------------------------------
    tempranas = [
        r for r in filas
        if relacion(r) == "ANTES"
    ]

    print("\n--- SOLO ENTRADAS ANTES DE LO SUGERIDO ---")

    grupos = {}

    for r in tempranas:
        clave = (
            protocolo(r),
            familia_evento(motivo(r)),
            accion(r),
            str(espera(r)),
        )

        grupos.setdefault(clave, []).append(r)

    for (p, f, a, e), grupo in sorted(
        grupos.items(),
        key=lambda kv: (
            -len(kv[1]),
            kv[0][0],
            kv[0][1],
        ),
    ):
        t, w, l, wr_g, act = resumen(grupo)

        print(
            p,
            "| evento:", f,
            "| accion:", a,
            "| espera_real:", e,
            "| total:", t,
            "| win:", w,
            "| loss:", l,
            "| WR:", str(wr_g) + "%",
            "| activos:", act,
        )

    print("==============================================\n")

def imprimir_cc2_probabilidad_post_protocolo(
    resultados,
):
    """
    C-C2 — calibración oficial POST-PROTOCOLO.

    IMPORTANTE:
    - NO construye ningún modelo;
    - NO aprende;
    - NO recalcula probabilidades;
    - NO modifica operaciones.

    Únicamente mide la probabilidad que ya produjo:

        motor_aprendizaje_historico.py
            ->
        evaluar_aprendizaje_post_protocolo()
            ->
        motor_decision.py
            ->
        evaluar_decision_post_protocolo()
    """

    modo = (
        "TRAIN"
        if MODO_EXPERIMENTO
        == MODO_EXPERIMENTO_AUDITORIA_TRAIN
        else "VALIDACION"
    )

    operadas = [
        r
        for r in resultados
        if r.get("estado_operacion")
        == "OPERADA_PROTOCOLO"
    ]

    print(
        "\n===== C-C2 PROBABILIDAD POST-PROTOCOLO — "
        + modo
        + " ====="
    )

    if not operadas:
        print(
            "No hay operaciones de protocolo "
            "para evaluar."
        )
        print(
            "============================================"
        )
        return

    con_datos = [
        r
        for r in operadas
        if str(
            r.get(
                "decision_post_protocolo",
                "",
            )
        ).upper().strip()
        == "EVALUAR"
    ]

    sin_datos = len(operadas) - len(con_datos)

    print(
        "Operaciones protocolo:",
        len(operadas),
    )

    print(
        "Con aprendizaje post-protocolo:",
        len(con_datos),
    )

    print(
        "Sin datos post-protocolo:",
        sin_datos,
    )

    if not con_datos:
        print(
            "ERROR DIAGNOSTICO: ninguna operación "
            "recibió aprendizaje post-protocolo."
        )
        print(
            "============================================"
        )
        return

    # ========================================================
    # CALIBRACIÓN
    # ========================================================

    rangos = [
        ("<45", None, 45),
        ("45-49", 45, 50),
        ("50-54", 50, 55),
        ("55-59", 55, 60),
        ("60-64", 60, 65),
        ("65+", 65, None),
    ]

    print(
        "\n--- CALIBRACION POST-PROTOCOLO ---"
    )

    for etiqueta, minimo, maximo in rangos:
        grupo = []

        for r in con_datos:
            try:
                prob = float(
                    r.get(
                        "probabilidad_post_protocolo",
                        0,
                    )
                    or 0
                )
            except (TypeError, ValueError):
                continue

            if (
                minimo is not None
                and prob < minimo
            ):
                continue

            if (
                maximo is not None
                and prob >= maximo
            ):
                continue

            grupo.append(r)

        total = len(grupo)

        wins = sum(
            1
            for r in grupo
            if r.get("resultado") == "WIN"
        )

        losses = total - wins

        wr = (
            round(
                (wins / total) * 100,
                2,
            )
            if total
            else 0
        )

        activos = len({
            str(
                r.get("activo", "")
                or ""
            )
            for r in grupo
            if str(
                r.get("activo", "")
                or ""
            )
        })

        print(
            etiqueta,
            "| total:",
            total,
            "| win:",
            wins,
            "| loss:",
            losses,
            "| WR:",
            str(wr) + "%",
            "| activos:",
            activos,
        )

    # ========================================================
    # POR CONFIABILIDAD
    # ========================================================

    print(
        "\n--- CONFIABILIDAD POST-PROTOCOLO ---"
    )

    grupos_confianza = {}

    for r in con_datos:
        clave = str(
            r.get(
                "confiabilidad_post_protocolo",
                "SIN_DATOS",
            )
            or "SIN_DATOS"
        ).upper().strip()

        grupos_confianza.setdefault(
            clave,
            [],
        ).append(r)

    for clave, grupo in sorted(
        grupos_confianza.items(),
        key=lambda x: -len(x[1]),
    ):
        total = len(grupo)

        wins = sum(
            1
            for r in grupo
            if r.get("resultado") == "WIN"
        )

        losses = total - wins

        wr = (
            round(
                (wins / total) * 100,
                2,
            )
            if total
            else 0
        )

        print(
            clave,
            "| total:",
            total,
            "| win:",
            wins,
            "| loss:",
            losses,
            "| WR:",
            str(wr) + "%",
        )

    # ========================================================
    # TOP CUANTILES
    # ========================================================

    ordenadas = sorted(
        con_datos,
        key=lambda r: float(
            r.get(
                "probabilidad_post_protocolo",
                0,
            )
            or 0
        ),
        reverse=True,
    )

    print(
        "\n--- TOP CUANTILES POST-PROTOCOLO ---"
    )

    for porcentaje in [
        25,
        40,
        50,
        60,
        75,
        100,
    ]:
        n = max(
            1,
            int(
                round(
                    len(ordenadas)
                    * porcentaje
                    / 100
                )
            ),
        )

        grupo = ordenadas[:n]

        wins = sum(
            1
            for r in grupo
            if r.get("resultado") == "WIN"
        )

        losses = len(grupo) - wins

        wr = round(
            (wins / len(grupo)) * 100,
            2,
        )

        corte = float(
            grupo[-1].get(
                "probabilidad_post_protocolo",
                0,
            )
            or 0
        )

        print(
            "TOP",
            str(porcentaje) + "%",
            "| total:",
            len(grupo),
            "| win:",
            wins,
            "| loss:",
            losses,
            "| WR:",
            str(wr) + "%",
            "| prob mínima:",
            str(round(corte, 2)) + "%",
        )

    print(
        "============================================\n"
    )


def imprimir_cc2_sombra_cuello_protocolo(resultados):
    """
    Auditoría sombra del cuello de botella post-protocolo.

    NO modifica decisiones ni operaciones.
    Usa exclusivamente operaciones que el protocolo ya ejecutó y
    compara varios cortes fijos de probabilidad C-C2.

    Objetivo: comprobar fuera de muestra si C-C2 separa mejor las
    entradas de protocolo antes de convertirlo en filtro real.
    """

    modo = (
        "TRAIN"
        if MODO_EXPERIMENTO
        == MODO_EXPERIMENTO_AUDITORIA_TRAIN
        else "VALIDACION"
    )

    operadas = [
        r for r in resultados
        if r.get("estado_operacion") == "OPERADA_PROTOCOLO"
    ]

    con_datos = [
        r for r in operadas
        if str(r.get("decision_post_protocolo", ""))
        .upper().strip() == "EVALUAR"
    ]

    print(
        "\n===== C-C2 SOMBRA CUELLO PROTOCOLO — "
        + modo
        + " ====="
    )

    if not operadas:
        print("No hay operaciones de protocolo.")
        print("===============================================\n")
        return

    total = len(operadas)
    wins = sum(1 for r in operadas if r.get("resultado") == "WIN")
    losses = total - wins
    wr = round((wins / total) * 100, 2) if total else 0

    print("PROTOCOLO ACTUAL")
    print(
        "Total:", total,
        "| WIN:", wins,
        "| LOSS:", losses,
        "| WR:", str(wr) + "%",
    )
    print(
        "Con datos C-C2:", len(con_datos),
        "| Sin datos:", total - len(con_datos),
    )

    if not con_datos:
        print("No existen datos C-C2 para auditar.")
        print("===============================================\n")
        return

    def probabilidad(r):
        try:
            return float(r.get("probabilidad_post_protocolo", 0) or 0)
        except (TypeError, ValueError):
            return 0.0

    def resumen(grupo):
        t = len(grupo)
        w = sum(1 for r in grupo if r.get("resultado") == "WIN")
        l = t - w
        wr_g = round((w / t) * 100, 2) if t else 0
        activos = len({
            str(r.get("activo", "") or "").strip()
            for r in grupo
            if str(r.get("activo", "") or "").strip()
        })
        return t, w, l, wr_g, activos

    print("\n--- CORTES FIJOS C-C2 (SOLO SOMBRA) ---")

    for corte in (45.0, 50.0, 52.5, 55.0):
        aprobadas = [r for r in con_datos if probabilidad(r) >= corte]
        rechazadas = [r for r in con_datos if probabilidad(r) < corte]

        at, aw, al, awr, aa = resumen(aprobadas)
        rt, rw, rl, rwr, ra = resumen(rechazadas)

        print("\nCorte probabilidad >=", corte)
        print(
            "APROBADAS SOMBRA",
            "| total:", at,
            "| win:", aw,
            "| loss:", al,
            "| WR:", str(awr) + "%",
            "| activos:", aa,
        )
        print(
            "RECHAZADAS SOMBRA",
            "| total:", rt,
            "| win:", rw,
            "| loss:", rl,
            "| WR hipotético:", str(rwr) + "%",
            "| activos:", ra,
        )

    print("\n--- CONFIABILIDAD C-C2 ---")
    grupos = {}
    for r in con_datos:
        clave = str(
            r.get("confiabilidad_post_protocolo", "SIN_DATOS")
            or "SIN_DATOS"
        ).upper().strip()
        grupos.setdefault(clave, []).append(r)

    for clave, grupo in sorted(grupos.items(), key=lambda kv: -len(kv[1])):
        t, w, l, wr_g, activos = resumen(grupo)
        print(
            clave,
            "| total:", t,
            "| win:", w,
            "| loss:", l,
            "| WR:", str(wr_g) + "%",
            "| activos:", activos,
        )

    print("===============================================\n")
def reevaluar_cc2_post_entrenamiento(resultados):
    """
    C-C2 — segunda pasada exclusivamente estadística.

    Se utiliza después de generar/actualizar la memoria
    PROTOCOLO_* en TRAIN.

    NO vuelve a ejecutar estrategia, protocolos ni operaciones.
    Solo vuelve a consultar C-C2 para operaciones ya ejecutadas.
    """

    total_operadas = 0
    con_datos = 0
    sin_datos = 0

    for registro in resultados:

        if (
            registro.get("estado_operacion")
            != "OPERADA_PROTOCOLO"
        ):
            continue

        total_operadas += 1

        decision_post = (
            evaluar_decision_post_protocolo(
                registro
            )
        )

        registro["decision_post_protocolo"] = (
            decision_post.get(
                "decision_post_protocolo",
                "SIN_DATOS",
            )
        )

        registro["autoriza_post_protocolo"] = (
            decision_post.get(
                "autoriza_post_protocolo",
                True,
            )
        )

        registro["probabilidad_post_protocolo"] = (
            decision_post.get(
                "probabilidad_post_protocolo",
                0,
            )
        )

        registro[
            "intervalo_post_protocolo_inferior"
        ] = decision_post.get(
            "intervalo_post_protocolo_inferior",
            0,
        )

        registro[
            "intervalo_post_protocolo_superior"
        ] = decision_post.get(
            "intervalo_post_protocolo_superior",
            0,
        )

        registro["muestra_post_protocolo"] = (
            decision_post.get(
                "muestra_post_protocolo",
                0,
            )
        )

        registro[
            "confiabilidad_post_protocolo"
        ] = decision_post.get(
            "confiabilidad_post_protocolo",
            "SIN_DATOS",
        )

        registro[
            "fuente_post_protocolo_principal"
        ] = decision_post.get(
            "fuente_post_protocolo_principal",
            "",
        )

        registro[
            "fuente_post_protocolo_respaldo"
        ] = decision_post.get(
            "fuente_post_protocolo_respaldo",
            "",
        )
        # ========================================================
        # AUDITORÍA DETALLADA C-C2
        # ========================================================
        
        fuente_principal = decision_post.get(
            "fuente_post_protocolo_principal"
        )
        
        if not isinstance(fuente_principal, dict):
            fuente_principal = {}
        
        fuente_respaldo = decision_post.get(
            "fuente_post_protocolo_respaldo"
        )
        
        if not isinstance(fuente_respaldo, dict):
            fuente_respaldo = {}
        
        registro["cc2_nivel_principal"] = (
            fuente_principal.get("nivel", "")
        )
        
        registro["cc2_clave_principal"] = (
            fuente_principal.get("clave", "")
        )
        
        registro["cc2_train_total_principal"] = (
            fuente_principal.get("total", 0)
        )
        
        registro["cc2_train_wins_principal"] = (
            fuente_principal.get("wins", 0)
        )
        
        registro["cc2_train_losses_principal"] = (
            fuente_principal.get("losses", 0)
        )
        
        registro["cc2_train_winrate_principal"] = (
            fuente_principal.get("winrate", 0)
        )
        
        registro["cc2_probabilidad_ajustada_principal"] = (
            fuente_principal.get(
                "probabilidad_ajustada",
                0,
            )
        )
        
        registro["cc2_ajuste_principal"] = (
            fuente_principal.get("ajuste", 0)
        )
        
        registro["cc2_confiabilidad_principal"] = (
            fuente_principal.get(
                "confiabilidad",
                "SIN_DATOS",
            )
        )
        
        registro["cc2_factor_muestra_principal"] = (
            fuente_principal.get(
                "factor_muestra",
                0,
            )
        )
        
        registro["cc2_nivel_respaldo"] = (
            fuente_respaldo.get("nivel", "")
        )
        
        registro["cc2_clave_respaldo"] = (
            fuente_respaldo.get("clave", "")
        )
        
        registro["cc2_train_total_respaldo"] = (
            fuente_respaldo.get("total", 0)
        )
        
        registro["cc2_train_winrate_respaldo"] = (
            fuente_respaldo.get("winrate", 0)
        )
        
        registro["cc2_probabilidad_ajustada_respaldo"] = (
            fuente_respaldo.get(
                "probabilidad_ajustada",
                0,
            )
        )
        
        registro["cc2_fuentes_usadas"] = (
            decision_post.get(
                "fuentes_post_protocolo",
                [],
            )
        )
        
        registro["cc2_claves_consultadas"] = (
            decision_post.get(
                "claves_consultadas_post_protocolo",
                [],
            )
        )
        
        registro["cc2_claves_descartadas"] = (
            decision_post.get(
                "claves_descartadas_post_protocolo",
                [],
            )
        )
        if (
            str(
                registro.get(
                    "decision_post_protocolo",
                    "",
                )
            ).upper().strip()
            == "EVALUAR"
        ):
            con_datos += 1
        else:
            sin_datos += 1

    print(
        "\n===== C-C2 REEVALUACION POST-TRAIN ====="
    )

    print(
        "Operaciones protocolo reevaluadas:",
        total_operadas,
    )

    print(
        "Con aprendizaje C-C2:",
        con_datos,
    )

    print(
        "Sin aprendizaje C-C2:",
        sin_datos,
    )

    print(
        "========================================\n"
    )

    return resultados

def imprimir_auditoria_generalizacion_cc2(resultados):
    """
    Diagnóstico TRAIN -> VALIDACIÓN de C-C2.

    No decide.
    No bloquea.
    No aprende.
    Solo muestra qué fuente histórica produjo
    las probabilidades post-protocolo.
    """

    operaciones = [
        r
        for r in resultados
        if r.get("estado_operacion")
        == "OPERADA_PROTOCOLO"
        and str(
            r.get(
                "decision_post_protocolo",
                "",
            )
        ).upper().strip()
        == "EVALUAR"
    ]

    print(
        "\n===== C-C2 AUDITORIA GENERALIZACION ====="
    )

    print(
        "Operaciones C-C2 evaluables:",
        len(operaciones),
    )

    if not operaciones:
        print(
            "No existen operaciones C-C2 evaluables."
        )
        print(
            "========================================\n"
        )
        return

    grupos = {}

    for r in operaciones:

        nivel = str(
            r.get(
                "cc2_nivel_principal",
                "SIN_NIVEL",
            )
            or "SIN_NIVEL"
        )

        clave = str(
            r.get(
                "cc2_clave_principal",
                "SIN_CLAVE",
            )
            or "SIN_CLAVE"
        )

        llave = (
            nivel,
            clave,
        )

        if llave not in grupos:
            grupos[llave] = {
                "total": 0,
                "win": 0,
                "loss": 0,
                "train_total": r.get(
                    "cc2_train_total_principal",
                    0,
                ),
                "train_wr": r.get(
                    "cc2_train_winrate_principal",
                    0,
                ),
                "prob_train": r.get(
                    "cc2_probabilidad_ajustada_principal",
                    0,
                ),
                "activos": set(),
            }

        grupo = grupos[llave]

        grupo["total"] += 1

        if r.get("resultado") == "WIN":
            grupo["win"] += 1
        else:
            grupo["loss"] += 1

        activo = str(
            r.get("activo", "")
            or ""
        )

        if activo:
            grupo["activos"].add(activo)

    ordenados = sorted(
        grupos.items(),
        key=lambda item: (
            item[1]["total"],
            item[1]["train_total"],
        ),
        reverse=True,
    )

    print(
        "\n--- FUENTE PRINCIPAL TRAIN VS RESULTADO ACTUAL ---"
    )

    for (nivel, clave), g in ordenados:

        wr_actual = round(
            (
                g["win"]
                / g["total"]
            ) * 100,
            2,
        )

        print(
            nivel,
            "|",
            clave,
            "| train total:",
            g["train_total"],
            "| train WR:",
            str(g["train_wr"]) + "%",
            "| prob train:",
            str(g["prob_train"]) + "%",
            "| valid total:",
            g["total"],
            "| valid WIN:",
            g["win"],
            "| valid LOSS:",
            g["loss"],
            "| valid WR:",
            str(wr_actual) + "%",
            "| activos:",
            len(g["activos"]),
        )

    print(
        "========================================\n"
    )


def imprimir_auditoria_operaciones_directas(resultados):
    """
    Auditoría específica de OPERADA_DIRECTA.

    No modifica decisiones, operaciones ni aprendizaje.
    Usa el resultado real para estudiar qué separa WIN de LOSS
    antes de tocar nuevos umbrales en motor_decision.py.
    """

    directas = [
        r for r in resultados
        if str(r.get("estado_operacion", "") or "").upper().strip()
        == "OPERADA_DIRECTA"
    ]

    modo = (
        "TRAIN"
        if MODO_EXPERIMENTO == MODO_EXPERIMENTO_AUDITORIA_TRAIN
        else "VALIDACION"
    )

    print("\n===== AUDITORIA OPERACIONES DIRECTAS — " + modo + " =====")

    if not directas:
        print("No hay operaciones directas.")
        print("==============================================\n")
        return

    def resumen(grupo):
        total = len(grupo)
        wins = sum(
            1 for r in grupo
            if str(r.get("resultado", "") or "").upper().strip() == "WIN"
        )
        losses = total - wins
        wr = round((wins / total) * 100, 2) if total else 0
        activos = len({
            str(r.get("activo", "") or "").strip()
            for r in grupo
            if str(r.get("activo", "") or "").strip()
        })
        return total, wins, losses, wr, activos

    def normalizar(valor, defecto="SIN_DATO"):
        texto = str(valor or "").strip()
        return texto if texto else defecto

    def bin_muestra(valor):
        try:
            muestra = int(float(valor or 0))
        except (TypeError, ValueError):
            return "SIN_DATO"
        if muestra < 20:
            return "<20"
        if muestra < 30:
            return "20-29"
        if muestra < 50:
            return "30-49"
        if muestra < 100:
            return "50-99"
        return "100+"

    def bin_probabilidad(valor):
        try:
            prob = float(valor or 0)
        except (TypeError, ValueError):
            return "SIN_DATO"
        if prob < 55:
            return "<55"
        if prob < 57.5:
            return "55-57.49"
        if prob < 60:
            return "57.5-59.99"
        if prob < 65:
            return "60-64.99"
        return "65+"

    def imprimir_grupos(titulo, selector):
        grupos = {}
        for r in directas:
            clave = selector(r)
            grupos.setdefault(clave, []).append(r)

        print("\n---", titulo, "---")
        filas = []
        for clave, grupo in grupos.items():
            total, wins, losses, wr, activos = resumen(grupo)
            filas.append((clave, total, wins, losses, wr, activos))

        filas.sort(key=lambda x: (-x[1], -x[4], str(x[0])))
        for clave, total, wins, losses, wr, activos in filas[:40]:
            print(
                clave,
                "| total:", total,
                "| win:", wins,
                "| loss:", losses,
                "| WR:", str(wr) + "%",
                "| activos:", activos,
            )

    total, wins, losses, wr, activos = resumen(directas)
    print(
        "TOTAL DIRECTAS:", total,
        "| WIN:", wins,
        "| LOSS:", losses,
        "| WR:", str(wr) + "%",
        "| activos:", activos,
    )

    con_muestra = []
    for r in directas:
        try:
            muestra = float(r.get("directa_muestra", 0) or 0)
        except (TypeError, ValueError):
            muestra = 0
        if muestra > 0:
            con_muestra.append(r)

    print("Con auditoría de muestra:", len(con_muestra), "/", total)
    if not con_muestra:
        print(
            "ADVERTENCIA: directa_muestra no llegó a las operaciones directas. "
            "Revisar propagación desde motor_decision.py."
        )

    imprimir_grupos(
        "POR EVIDENCIA SOLIDA",
        lambda r: str(bool(r.get("directa_evidencia_solida", False))).upper(),
    )
    imprimir_grupos(
        "POR CONFIABILIDAD",
        lambda r: normalizar(r.get("directa_confiabilidad", "SIN_DATOS"), "SIN_DATOS").upper(),
    )
    imprimir_grupos(
        "POR RANGO DE MUESTRA",
        lambda r: bin_muestra(r.get("directa_muestra", 0)),
    )
    imprimir_grupos(
        "POR NIVEL PROBABILIDAD",
        lambda r: normalizar(
            r.get("directa_nivel_probabilidad", "")
            or r.get("nivel_probabilidad_principal", ""),
            "SIN_NIVEL",
        ).upper(),
    )
    imprimir_grupos(
        "POR RANGO PROBABILIDAD",
        lambda r: bin_probabilidad(r.get("probabilidad_estimada", 0)),
    )
    imprimir_grupos(
        "POR TIPO SETUP",
        lambda r: normalizar(r.get("tipo_setup", ""), "SIN_TIPO").upper(),
    )
    imprimir_grupos(
        "POR SUBTIPO SETUP",
        lambda r: normalizar(r.get("subtipo_setup", ""), "SIN_SUBTIPO").upper(),
    )
    imprimir_grupos(
        "POR MERCADO",
        lambda r: normalizar(r.get("tipo_mercado", ""), "SIN_MERCADO").upper(),
    )
    imprimir_grupos(
        "POR TENDENCIA",
        lambda r: normalizar(r.get("estado_tendencia", ""), "SIN_TENDENCIA").upper(),
    )
    imprimir_grupos(
        "POR PA",
        lambda r: normalizar(r.get("pa_tipo", ""), "SIN_PA").upper(),
    )
    imprimir_grupos(
        "NIVEL PROBABILIDAD × CONFIABILIDAD",
        lambda r: (
            normalizar(
                r.get("directa_nivel_probabilidad", "")
                or r.get("nivel_probabilidad_principal", ""),
                "SIN_NIVEL",
            ).upper()
            + " | "
            + normalizar(r.get("directa_confiabilidad", "SIN_DATOS"), "SIN_DATOS").upper()
        ),
    )
    imprimir_grupos(
        "RANGO MUESTRA × RANGO PROBABILIDAD",
        lambda r: (
            bin_muestra(r.get("directa_muestra", 0))
            + " | "
            + bin_probabilidad(r.get("probabilidad_estimada", 0))
        ),
    )
    imprimir_grupos(
        "SUBTIPO SETUP × MERCADO",
        lambda r: (
            normalizar(r.get("subtipo_setup", ""), "SIN_SUBTIPO").upper()
            + " | "
            + normalizar(r.get("tipo_mercado", ""), "SIN_MERCADO").upper()
        ),
    )

    print("\n--- CLAVES PRINCIPALES DIRECTAS ---")
    claves = {}
    for r in directas:
        clave = normalizar(
            r.get("directa_clave_probabilidad", "")
            or r.get("clave_probabilidad_principal", ""),
            "SIN_CLAVE",
        )
        claves.setdefault(clave, []).append(r)

    for clave, grupo in sorted(claves.items(), key=lambda kv: -len(kv[1]))[:30]:
        total, wins, losses, wr, activos = resumen(grupo)
        print(
            clave,
            "| total:", total,
            "| win:", wins,
            "| loss:", losses,
            "| WR:", str(wr) + "%",
            "| activos:", activos,
        )

    print("==============================================\n")


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
    # ========================================================
    # CURVAS DE CALIBRACION DE LA CONFIANZA
    # ========================================================
    # Utilizan resultado_hipotetico porque deben medir
    # la calidad de la señal original, no el efecto posterior
    # del protocolo.
    # ========================================================

    imprimir_tabla_resumen(
        "CALIBRACION CONFIANZA BASE",
        resumen_por_rangos(
            resultados,
            "auditoria_confianza_base",
            campo_resultado="resultado_hipotetico",
        ),
        limite=20,
    )

    imprimir_tabla_resumen(
        "CALIBRACION ANTES PONDERACION",
        resumen_por_rangos(
            resultados,
            "auditoria_confianza_antes_ponderacion",
            campo_resultado="resultado_hipotetico",
        ),
        limite=20,
    )

    imprimir_tabla_resumen(
        "CALIBRACION CONFIANZA FINAL",
        resumen_por_rangos(
            resultados,
            "auditoria_confianza_final",
            campo_resultado="resultado_hipotetico",
        ),
        limite=20,
    )

    # ========================================================
    # AUDITORÍA DEL MODO SOMBRA ESTADÍSTICO
    # ========================================================
    imprimir_tabla_resumen(
        "CALIBRACION PROBABILIDAD ESTIMADA",
        resumen_por_rangos(
            resultados,
            "probabilidad_estimada",
            campo_resultado="resultado_hipotetico",
        ),
        limite=20,
    )

    imprimir_tabla_resumen(
        "POR DECISION ESTADISTICA SOMBRA",
        resumen_por_campo(
            resultados,
            "decision_estadistica_sombra",
            campo_resultado="resultado_hipotetico",
        ),
        limite=20,
    )

    imprimir_tabla_resumen(
        "POR CONFIABILIDAD PROBABILIDAD",
        resumen_por_campo(
            resultados,
            "confiabilidad_probabilidad",
            campo_resultado="resultado_hipotetico",
        ),
        limite=20,
    )

    imprimir_tabla_resumen(
        "POR NIVEL PROBABILIDAD PRINCIPAL",
        resumen_por_campo(
            resultados,
            "nivel_probabilidad_principal",
            campo_resultado="resultado_hipotetico",
        ),
        limite=30,
    )

    imprimir_comparacion_sombra(resultados)

    # Auditoría específica del cuello actual: entradas directas.
    imprimir_auditoria_operaciones_directas(
        resultados
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

    imprimir_auditoria_veto_setup(resultados)

    imprimir_auditoria_motor_protocolos(resultados)

    imprimir_matriz_setup_riesgo(resultados)

    imprimir_c3_bypass_vetos_sombra(resultados)

    imprimir_c5_timing_ruptura_resistencia(resultados)

    imprimir_c6_auditoria_confirmacion(resultados)

    imprimir_c7_confirmacion_vs_espera(resultados)

    imprimir_c8_evento_tecnico(resultados)

    # C-C2 oficial.
    imprimir_cc2_probabilidad_post_protocolo(
        resultados
    )

    # Auditoría sombra del cuello principal: protocolo.
    imprimir_cc2_sombra_cuello_protocolo(
        resultados
    )
    imprimir_auditoria_generalizacion_cc2(
        resultados
    )
    # Modelo paralelo antiguo:
    # se deja temporalmente apagado.
    # imprimir_probabilidad_protocolo_train(
    #     resultados
    # )

    imprimir_validacion_recuperacion_sombra(
        resultados
    )


def main():
    print("BUILD:", BUILD_ID)
    reset_estado()

    datasets_cargados = cargar_datasets()

    # ========================================================
    # SELECCION INICIAL DEL UNIVERSO
    # ========================================================
    #
    # OUT_OF_SAMPLE no puede seleccionar activos mirando
    # el final completo de cada dataset.
    #
    # Se entregan todos los datasets disponibles y
    # ejecutar_backtest() decidirá causalmente qué activos
    # cumplen el filtro en cada instante histórico.
    #
    # TRAIN / VALIDACION conservan su universo experimental
    # fijo 12 + 4.
    # ========================================================
    
    if (
        MODO_EXPERIMENTO
        == MODO_EXPERIMENTO_OUT_OF_SAMPLE
    ):
        datasets_seleccionados = list(
            datasets_cargados
        )
    
    else:
        datasets_seleccionados = (
            seleccionar_top_datasets(
                datasets_cargados,
                limite=MAX_ACTIVOS_ANALIZAR,
            )
    )

    # Auditoría general del filtro de datasets.
    imprimir_auditoria_datasets()

    # División experimental blindada:
    # 11 TRAIN + 5 VALIDACIÓN.
    datasets = seleccionar_datasets_experimento(
        datasets_seleccionados
    )

    global DATASETS_USADOS_BACKTEST
    DATASETS_USADOS_BACKTEST = len(datasets)

    print(
        "\nDatasets cargados para esta ejecución:",
        len(datasets),
    )

    print(
        "Política ranking:",
        "MOTOR_CANDIDATOS_V3",
        "| TOP señales por ronda:",
        MAX_SENALES_POR_RONDA,
    )

    print(
        "Ejecutando backtest usando analizar_activo() real..."
    )

    resultados = ejecutar_backtest(datasets)

    # guardar_resultados(resultados)
    if (
        ACTUALIZAR_APRENDIZAJE
        and ACTUALIZAR_APRENDIZAJE_PROTOCOLO
    ):
        raise RuntimeError(
            "No se puede actualizar memoria general "
            "y memoria post-protocolo simultáneamente."
        )
    # ========================================================
    # APRENDIZAJE
    # ========================================================
    # ========================================================
    # FASE 2.6 — SEGURIDAD TRAIN / VALIDACION
    # ========================================================
    # La memoria histórica general solo puede regenerarse
    # utilizando el conjunto TRAIN.
    #
    # VALIDACION y OUT_OF_SAMPLE nunca pueden modificar
    # el aprendizaje general.
    # ========================================================
    
    if (
        ACTUALIZAR_APRENDIZAJE
        and MODO_EXPERIMENTO
        != MODO_EXPERIMENTO_AUDITORIA_TRAIN
    ):
        raise RuntimeError(
            "SEGURIDAD BOOTIQ: ACTUALIZAR_APRENDIZAJE=True "
            "solo está permitido en AUDITORIA_TRAIN. "
            "VALIDACION y OUT_OF_SAMPLE deben permanecer congelados."
        )
    if (
        ACTUALIZAR_APRENDIZAJE_PROTOCOLO
        and MODO_EXPERIMENTO
        != MODO_EXPERIMENTO_AUDITORIA_TRAIN
    ):
        raise RuntimeError(
            "SEGURIDAD BOOTIQ: "
            "ACTUALIZAR_APRENDIZAJE_PROTOCOLO=True "
            "solo está permitido en AUDITORIA_TRAIN. "
            "VALIDACION y OUT_OF_SAMPLE no pueden "
            "modificar memoria C-C2."
        )
    if ACTUALIZAR_APRENDIZAJE:
        generar_aprendizaje_desde_resultados(
            resultados,
            incluir_hipoteticos=True,
        )

        print(
            "Memoria general regenerada."
        )

    elif ACTUALIZAR_APRENDIZAJE_PROTOCOLO:
        filas_cc2 = actualizar_aprendizaje_post_protocolo(
            resultados
        )
    
        print(
            "C-C2: memoria general congelada; "
            "solo PROTOCOLO_* fue actualizado."
        )
    
        print(
            "Filas C-C2 generadas:",
            len(filas_cc2),
        )
    
        resultados = reevaluar_cc2_post_entrenamiento(
            resultados
        )
    else:
        print(
            "Aprendizaje histórico congelado: "
            "no se sobrescribió durante esta prueba."
        )
    guardar_resultados(resultados)
    imprimir_resumen(resultados)

    print("Archivo generado:", SALIDA)
if __name__ == "__main__":
    main()