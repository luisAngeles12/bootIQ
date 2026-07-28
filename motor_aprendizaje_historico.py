import csv
import os
import re
from collections import defaultdict

RUTA_APRENDIZAJE = "aprendizaje_historico_bootiq.csv"

# ============================================================
# CONFIGURACIÓN OFICIAL DEL APRENDIZAJE JERÁRQUICO
# ============================================================

# Se permite empezar a aportar con muestras pequeñas,
# pero el peso crece de forma progresiva.
MIN_MUESTRA_APORTE = 5
MIN_MUESTRA_CONFIABLE = 12

UMBRAL_BUENO = 58.0
UMBRAL_MALO = 48.0

AJUSTE_MAXIMO = 5.0
AJUSTE_MINIMO = -5.0

RESULTADOS_VALIDOS = {"WIN", "LOSS"}

# Pesos relativos por nivel histórico.
# No necesitan sumar 1 porque luego se normalizan.
PESOS_NIVELES = {
    # Memoria estructural anterior: se conserva por compatibilidad.
    "FAMILIA": 0.85,
    "FAMILIA_DIRECCION": 0.95,
    "FAMILIA_MERCADO": 0.85,
    "FAMILIA_TENDENCIA": 0.85,
    "ACTIVO_FAMILIA": 0.60,
    "ACTIVO_DIRECCION": 0.50,
    "CLAVE_ESPECIFICA": 1.00,

    # Memoria del Cerebro Único basada en evidencias observadas.
    "PA": 0.90,
    "PA_DIRECCION": 1.00,
    "MERCADO_EVIDENCIAS": 0.85,
    "SETUP_EVIDENCIAS": 0.95,
    "PA_MERCADO": 1.10,
    "PA_SETUP": 1.15,
    "SETUP_MERCADO": 1.05,
    "PA_SETUP_MERCADO": 1.30,
    "FIRMA_EVIDENCIAS_EXACTA": 1.40,
}

# Evita firmas gigantes, demasiado específicas o inestables.
MAX_EVIDENCIAS_POR_ORIGEN = 6
MAX_COMPONENTES_FIRMA_EXACTA = 14


def _txt(valor):
    return str(valor or "").upper().strip()


def _entero(valor, default=0):
    try:
        return int(float(valor if valor is not None else default))
    except (TypeError, ValueError):
        return int(default)


def _numero(valor, default=0.0):
    try:
        return float(valor if valor is not None else default)
    except (TypeError, ValueError):
        return float(default)


def _limitar_ajuste(valor):
    valor = _numero(valor, 0.0)
    return round(max(AJUSTE_MINIMO, min(AJUSTE_MAXIMO, valor)), 2)


def _normalizar_token(valor):
    """Convierte cualquier evidencia en un token estable para el CSV."""

    token = _txt(valor)
    if not token:
        return ""

    # Unifica separadores para que la misma evidencia no genere claves distintas.
    for separador in ("|", ";", ",", "/", "\\", "\n", "\t"):
        token = token.replace(separador, "_")

    token = "_".join(token.split())
    while "__" in token:
        token = token.replace("__", "_")

    return token.strip("_")


def _extraer_tokens(valor):
    """
    Extrae evidencias desde listas, diccionarios o textos serializados.

    Acepta tanto las estructuras originales de Price Action como las firmas
    ya construidas por motor_decision.py.
    """

    tokens = []

    def agregar(item):
        if item is None:
            return

        if isinstance(item, dict):
            candidato = (
                item.get("tipo")
                or item.get("evidencia")
                or item.get("nombre")
                or item.get("codigo")
                or item.get("familia")
            )
            token = _normalizar_token(candidato)
            if token:
                tokens.append(token)
            return

        if isinstance(item, (list, tuple, set)):
            for subitem in item:
                agregar(subitem)
            return

        texto = str(item or "").strip()
        if not texto:
            return

        # Las auditorías suelen serializar listas con " | ".
        partes = re.split(r"\s*[|;,]\s*", texto)
        for parte in partes:
            token = _normalizar_token(parte)
            if token:
                tokens.append(token)

    agregar(valor)

    vistos = set()
    salida = []
    for token in tokens:
        if token in vistos:
            continue
        vistos.add(token)
        salida.append(token)

    return sorted(salida)


def _primer_valor(senal, nombres):
    for nombre in nombres:
        valor = senal.get(nombre)
        if valor not in (None, "", [], {}):
            return valor
    return None


def _evidencias_por_origen(senal):
    """Recupera las evidencias del Cerebro Único con compatibilidad amplia."""

    pa = _extraer_tokens(_primer_valor(senal, [
        "price_action_evidencias",
        "evidencias_price_action",
        "evidencias_pa",
        "evidencia_pa",
        "pa_evidencias",
        "pa_profesional_evidencias",
    ]))

    mercado = _extraer_tokens(_primer_valor(senal, [
        "mercado_evidencias",
        "evidencias_mercado",
        "evidencia_mercado",
        "contexto_mercado_evidencias",
    ]))

    estrategia = _extraer_tokens(_primer_valor(senal, [
        "estrategia_evidencias",
        "evidencias_estrategia",
        "evidencia_estrategia",
        "setup_evidencias",
    ]))

    unificadas = _extraer_tokens(_primer_valor(senal, [
        "evidencias_unificadas",
        "evidencias_cerebro",
        "firma_evidencias_exacta",
        "firma_exacta",
    ]))

    # Si solo existe la lista unificada, no inventamos el origen.
    # Aun así se conserva para la firma exacta.
    pa = pa[:MAX_EVIDENCIAS_POR_ORIGEN]
    mercado = mercado[:MAX_EVIDENCIAS_POR_ORIGEN]
    estrategia = estrategia[:MAX_EVIDENCIAS_POR_ORIGEN]
    unificadas = unificadas[:MAX_COMPONENTES_FIRMA_EXACTA]

    return {
        "pa": pa,
        "mercado": mercado,
        "estrategia": estrategia,
        "unificadas": unificadas,
    }


def _firma_tokens(tokens):
    tokens = [token for token in tokens if token]
    return "+".join(sorted(dict.fromkeys(tokens)))


def _agregar_clave(claves, vistos, nivel, componentes):
    componentes = [
        _normalizar_token(componente)
        for componente in componentes
        if _normalizar_token(componente)
    ]
    if not componentes:
        return

    clave = "|".join([nivel] + componentes)
    if clave in vistos:
        return

    vistos.add(clave)
    claves.append({"nivel": nivel, "clave": clave})


def _familia_setup(senal):
    """
    Obtiene una familia estable para el aprendizaje.
    """

    familia = _txt(senal.get("familia_setup"))
    if familia:
        return familia

    texto = " ".join([
        _txt(senal.get("patron")),
        _txt(senal.get("tipo_setup")),
        _txt(senal.get("subtipo_setup")),
    ])

    if "CHOCH" in texto:
        return "CHOCH"

    if "PULLBACK" in texto:
        return "PULLBACK"

    if "SWEEP" in texto or "LIQUIDITY" in texto:
        return "SWEEP"

    if "RUPTURA" in texto or "BREAKOUT" in texto:
        return "RUPTURA"

    if "RECHAZO" in texto:
        return "RECHAZO"

    if "CONTINUACION" in texto or "CONTINUACIÓN" in texto:
        return "CONTINUACION"

    if "REVERS" in texto:
        return "REVERSION"

    tipo_setup = _txt(senal.get("tipo_setup"))
    return tipo_setup or "OTRA"


def _normalizar_mercado(senal):
    valor = _txt(
        senal.get("tipo_mercado")
        or senal.get("mercado")
        or senal.get("regimen_mercado")
    )

    if not valor:
        return "SIN_MERCADO"

    if "TENDENCIA" in valor:
        return "TENDENCIA"

    if "RANGO" in valor:
        return "RANGO"

    if "COMPRESION" in valor or "COMPRESIÓN" in valor:
        return "COMPRESION"

    return valor


def _normalizar_tendencia(senal):
    valor = _txt(
        senal.get("estado_tendencia")
        or senal.get("tendencia")
        or senal.get("tipo_tendencia")
    )

    if not valor:
        return "SIN_TENDENCIA"

    if "ALCISTA" in valor:
        direccion = "ALCISTA"
    elif "BAJISTA" in valor:
        direccion = "BAJISTA"
    else:
        direccion = "INDEFINIDA"

    if "FUERTE" in valor:
        fuerza = "FUERTE"
    elif "DEBIL" in valor or "DÉBIL" in valor:
        fuerza = "DEBIL"
    elif "AGOTADA" in valor or "AGOTADO" in valor:
        fuerza = "AGOTADA"
    elif "NORMAL" in valor:
        fuerza = "NORMAL"
    else:
        fuerza = ""

    return "_".join(parte for parte in [direccion, fuerza] if parte)


def _clave_legacy(senal):
    """
    Conserva la clave anterior para compatibilidad con CSV existentes.
    """

    return "|".join([
        _txt(senal.get("activo")),
        _txt(senal.get("direccion")),
        _familia_setup(senal),
        _txt(senal.get("tipo_mercado")),
        _txt(senal.get("estado_tendencia")),
    ])


def _claves_jerarquicas(senal):
    """
    Genera memoria estructural y memoria de combinaciones del Cerebro Único.

    Las claves antiguas se conservan. Las nuevas se crean únicamente cuando
    existen evidencias reales en el registro, evitando fabricar contexto.
    """

    activo = _txt(senal.get("activo")) or "SIN_ACTIVO"
    direccion = _txt(senal.get("direccion")) or "SIN_DIRECCION"
    familia = _familia_setup(senal)
    mercado = _normalizar_mercado(senal)
    tendencia = _normalizar_tendencia(senal)
    tipo_setup = _normalizar_token(senal.get("tipo_setup"))
    subtipo_setup = _normalizar_token(senal.get("subtipo_setup"))

    evidencias = _evidencias_por_origen(senal)
    firma_pa = _firma_tokens(evidencias["pa"])
    firma_mercado = _firma_tokens(evidencias["mercado"])
    firma_estrategia = _firma_tokens(evidencias["estrategia"])

    componentes_setup = [familia, tipo_setup, subtipo_setup]
    firma_setup_contextual = _firma_tokens(
        componentes_setup + evidencias["estrategia"]
    )

    claves = []
    vistos = set()

    # --------------------------------------------------------
    # Niveles anteriores: compatibilidad con memoria existente.
    # --------------------------------------------------------
    _agregar_clave(claves, vistos, "FAMILIA", [familia])
    _agregar_clave(
        claves, vistos, "FAMILIA_DIRECCION", [familia, direccion]
    )
    _agregar_clave(
        claves, vistos, "FAMILIA_MERCADO", [familia, mercado]
    )
    _agregar_clave(
        claves, vistos, "FAMILIA_TENDENCIA", [familia, tendencia]
    )
    _agregar_clave(
        claves, vistos, "ACTIVO_FAMILIA", [activo, familia]
    )
    _agregar_clave(
        claves, vistos, "ACTIVO_DIRECCION", [activo, direccion]
    )
    _agregar_clave(
        claves,
        vistos,
        "CLAVE_ESPECIFICA",
        [activo, direccion, familia, mercado, tendencia],
    )

    # --------------------------------------------------------
    # Niveles nuevos: evidencias individuales por origen.
    # Cada evidencia también aprende por separado para asegurar muestra.
    # --------------------------------------------------------
    for token in evidencias["pa"]:
        _agregar_clave(claves, vistos, "PA", [token])
        _agregar_clave(
            claves, vistos, "PA_DIRECCION", [token, direccion]
        )

    for token in evidencias["mercado"]:
        _agregar_clave(claves, vistos, "MERCADO_EVIDENCIAS", [token])

    for token in evidencias["estrategia"]:
        _agregar_clave(claves, vistos, "SETUP_EVIDENCIAS", [token])

    # Firmas completas por origen.
    if firma_pa:
        _agregar_clave(claves, vistos, "PA", [firma_pa])
    if firma_mercado:
        _agregar_clave(
            claves, vistos, "MERCADO_EVIDENCIAS", [firma_mercado]
        )
    if firma_setup_contextual:
        _agregar_clave(
            claves, vistos, "SETUP_EVIDENCIAS", [firma_setup_contextual]
        )

    # --------------------------------------------------------
    # Combinaciones cruzadas. Estas son las claves que permiten
    # aprender cuándo PA, setup y mercado funcionan juntos.
    # --------------------------------------------------------
    if firma_pa and firma_mercado:
        _agregar_clave(
            claves, vistos, "PA_MERCADO", [firma_pa, firma_mercado]
        )

    if firma_pa and firma_setup_contextual:
        _agregar_clave(
            claves, vistos, "PA_SETUP", [firma_pa, firma_setup_contextual]
        )

    if firma_setup_contextual and firma_mercado:
        _agregar_clave(
            claves,
            vistos,
            "SETUP_MERCADO",
            [firma_setup_contextual, firma_mercado],
        )

    if firma_pa and firma_setup_contextual and firma_mercado:
        _agregar_clave(
            claves,
            vistos,
            "PA_SETUP_MERCADO",
            [firma_pa, firma_setup_contextual, firma_mercado],
        )

    # Firma exacta: prioriza la generada por motor_decision.py. Si no existe,
    # la construye con las evidencias disponibles y contexto esencial.
    firma_exacta_recibida = _normalizar_token(
        senal.get("firma_evidencias_exacta")
        or senal.get("firma_exacta")
    )

    if firma_exacta_recibida:
        firma_exacta = firma_exacta_recibida
    else:
        componentes_exactos = (
            [direccion, familia, mercado, tendencia]
            + evidencias["pa"]
            + evidencias["mercado"]
            + evidencias["estrategia"]
            + evidencias["unificadas"]
        )
        firma_exacta = _firma_tokens(
            componentes_exactos[:MAX_COMPONENTES_FIRMA_EXACTA]
        )

    if firma_exacta:
        _agregar_clave(
            claves,
            vistos,
            "FIRMA_EVIDENCIAS_EXACTA",
            [firma_exacta],
        )

    return claves


def _clave(senal):
    """
    Mantiene compatibilidad con código externo que espere una sola clave.
    Devuelve la clave específica jerárquica.
    """

    for item in _claves_jerarquicas(senal):
        if item["nivel"] == "CLAVE_ESPECIFICA":
            return item["clave"]

    return _clave_legacy(senal)


def _confiabilidad_muestra(total):
    total = _entero(total, 0)

    if total < MIN_MUESTRA_APORTE:
        return "INSUFICIENTE"

    if total < MIN_MUESTRA_CONFIABLE:
        return "MUY_BAJA"

    if total < 20:
        return "BAJA"

    if total < 50:
        return "MEDIA"

    return "ALTA"


def _factor_muestra(total):
    """
    Factor progresivo.
    Evita el salto brusco de 0 a ajuste completo.
    """

    total = _entero(total, 0)

    if total < MIN_MUESTRA_APORTE:
        return 0.0

    if total < MIN_MUESTRA_CONFIABLE:
        return 0.25

    if total < 20:
        return 0.45

    if total < 30:
        return 0.65

    if total < 50:
        return 0.85

    return 1.00


def _calcular_ajuste(total, winrate):
    """
    Convierte el rendimiento histórico en ajuste moderado
    usando confiabilidad progresiva.
    """

    total = _entero(total, 0)
    winrate = _numero(winrate, 0.0)
    factor_muestra = _factor_muestra(total)

    if factor_muestra <= 0:
        return 0.0, "MUESTRA_INSUFICIENTE"

    if winrate >= UMBRAL_BUENO:
        diferencia = winrate - UMBRAL_BUENO
        ajuste_base = 2.0 + min(3.0, diferencia / 6.0)
        return (
            _limitar_ajuste(ajuste_base * factor_muestra),
            "FAVORABLE",
        )

    if winrate <= UMBRAL_MALO:
        diferencia = UMBRAL_MALO - winrate
        ajuste_base = -(2.0 + min(3.0, diferencia / 6.0))
        return (
            _limitar_ajuste(ajuste_base * factor_muestra),
            "DEBIL",
        )

    return 0.0, "NEUTRO"


def _crear_data_memoria(row):
    total = _entero(row.get("total"), 0)
    wins = _entero(row.get("wins"), 0)
    losses = _entero(row.get("losses"), 0)

    if total <= 0:
        total = wins + losses

    if total > 0 and wins + losses != total:
        total = wins + losses

    winrate = _numero(row.get("winrate"), 0.0)
    if total > 0 and winrate <= 0 and wins > 0:
        winrate = (wins / total) * 100

    ajuste, decision = _calcular_ajuste(
        total=total,
        winrate=winrate,
    )

    return {
        "total": total,
        "wins": wins,
        "losses": losses,
        "winrate": round(winrate, 2),
        "ajuste_confianza": ajuste,
        "decision_aprendizaje": decision,
        "confiabilidad_muestra": _confiabilidad_muestra(total),
        "nivel": _txt(row.get("nivel")),
    }


def cargar_aprendizaje(ruta=RUTA_APRENDIZAJE):
    """
    Carga memoria jerárquica.

    También acepta CSV del diseño anterior.
    """

    if not os.path.exists(ruta):
        return {}

    memoria = {}

    try:
        with open(ruta, "r", encoding="utf-8-sig", newline="") as archivo:
            reader = csv.DictReader(archivo)

            for row in reader:
                clave = str(row.get("clave", "") or "").strip()
                if not clave:
                    continue

                data = _crear_data_memoria(row)
                memoria[clave] = data

    except (OSError, csv.Error):
        return {}

    return memoria


def _buscar_fuentes_aprendizaje(senal, memoria):
    fuentes = []
    descartadas = []

    for item in _claves_jerarquicas(senal):
        nivel = item["nivel"]
        clave = item["clave"]
        data = memoria.get(clave)

        if not data:
            descartadas.append({
                "nivel": nivel,
                "clave": clave,
                "motivo": "SIN_DATOS",
            })
            continue

        total = _entero(data.get("total"), 0)
        wins = _entero(data.get("wins"), 0)
        losses = _entero(data.get("losses"), 0)
        winrate = _numero(data.get("winrate"), 0.0)

        ajuste, decision = _calcular_ajuste(
            total=total,
            winrate=winrate,
        )

        if total < MIN_MUESTRA_APORTE:
            descartadas.append({
                "nivel": nivel,
                "clave": clave,
                "motivo": "MUESTRA_INSUFICIENTE",
                "total": total,
            })
            continue

        peso_nivel = _numero(PESOS_NIVELES.get(nivel), 1.0)
        factor = _factor_muestra(total)
        peso_efectivo = peso_nivel * factor

        fuentes.append({
            "nivel": nivel,
            "clave": clave,
            "total": total,
            "wins": wins,
            "losses": losses,
            "winrate": round(winrate, 2),
            "ajuste": ajuste,
            "decision": decision,
            "confiabilidad": _confiabilidad_muestra(total),
            "peso_nivel": round(peso_nivel, 3),
            "factor_muestra": round(factor, 3),
            "peso_efectivo": round(peso_efectivo, 3),
        })

    # Compatibilidad con la memoria antigua.
    if not fuentes:
        clave_legacy = _clave_legacy(senal)
        data_legacy = memoria.get(clave_legacy)

        if data_legacy:
            total = _entero(data_legacy.get("total"), 0)
            wins = _entero(data_legacy.get("wins"), 0)
            losses = _entero(data_legacy.get("losses"), 0)
            winrate = _numero(data_legacy.get("winrate"), 0.0)
            ajuste, decision = _calcular_ajuste(total, winrate)

            if total >= MIN_MUESTRA_APORTE:
                factor = _factor_muestra(total)
                fuentes.append({
                    "nivel": "LEGACY",
                    "clave": clave_legacy,
                    "total": total,
                    "wins": wins,
                    "losses": losses,
                    "winrate": round(winrate, 2),
                    "ajuste": ajuste,
                    "decision": decision,
                    "confiabilidad": _confiabilidad_muestra(total),
                    "peso_nivel": 1.0,
                    "factor_muestra": round(factor, 3),
                    "peso_efectivo": round(factor, 3),
                })

    return fuentes, descartadas


def _combinar_fuentes(fuentes):
    """
    Combina las fuentes sin duplicar autoridad.

    El ajuste final es un promedio ponderado, no una suma.
    """

    if not fuentes:
        return {
            "ajuste": 0.0,
            "winrate": 0.0,
            "muestra": 0,
            "wins": 0,
            "losses": 0,
            "peso_total": 0.0,
        }

    suma_ajustes = 0.0
    suma_winrate = 0.0
    peso_total = 0.0

    muestras = []
    wins_total = 0
    losses_total = 0

    for fuente in fuentes:
        peso = _numero(fuente.get("peso_efectivo"), 0.0)
        if peso <= 0:
            continue

        ajuste = _numero(fuente.get("ajuste"), 0.0)
        winrate = _numero(fuente.get("winrate"), 0.0)

        suma_ajustes += ajuste * peso
        suma_winrate += winrate * peso
        peso_total += peso

        muestras.append(_entero(fuente.get("total"), 0))
        wins_total += _entero(fuente.get("wins"), 0)
        losses_total += _entero(fuente.get("losses"), 0)

    if peso_total <= 0:
        return {
            "ajuste": 0.0,
            "winrate": 0.0,
            "muestra": 0,
            "wins": 0,
            "losses": 0,
            "peso_total": 0.0,
        }

    ajuste_final = _limitar_ajuste(suma_ajustes / peso_total)
    winrate_final = round(suma_winrate / peso_total, 2)

    # La muestra representativa no se suma porque las fuentes
    # contienen operaciones superpuestas.
    muestra_representativa = max(muestras) if muestras else 0

    return {
        "ajuste": ajuste_final,
        "winrate": winrate_final,
        "muestra": muestra_representativa,
        "wins": wins_total,
        "losses": losses_total,
        "peso_total": round(peso_total, 3),
    }


def evaluar_aprendizaje_historico(senal, memoria=None):
    """
    Consulta memoria histórica jerárquica.

    Mantiene el contrato anterior y agrega diagnóstico completo.
    """

    if not isinstance(senal, dict):
        senal = {}

    if memoria is None:
        memoria = cargar_aprendizaje()

    if not isinstance(memoria, dict):
        memoria = {}

    fuentes, descartadas = _buscar_fuentes_aprendizaje(
        senal=senal,
        memoria=memoria,
    )

    combinado = _combinar_fuentes(fuentes)
    ajuste = combinado["ajuste"]
    winrate = combinado["winrate"]
    muestra = combinado["muestra"]

    if not fuentes:
        return {
            "aprendizaje_encontrado": False,
            "clave_aprendizaje": _clave(senal),
            "claves_consultadas": [
                item["clave"] for item in _claves_jerarquicas(senal)
            ],
            "fuentes_utilizadas": [],
            "claves_descartadas": descartadas,
            "ajuste_confianza_aprendizaje": 0.0,
            "decision_aprendizaje": "SIN_DATOS",
            "motivo_aprendizaje": (
                "Sin fuentes históricas utilizables para esta señal."
            ),
            "muestra_historica": 0,
            "wins": 0,
            "losses": 0,
            "winrate": 0.0,
            "confiabilidad_muestra": "SIN_DATOS",
            "confianza_historica": 0.0,
            "peso_historico_total": 0.0,
        }

    if ajuste > 0:
        decision = "FAVORABLE"
    elif ajuste < 0:
        decision = "DEBIL"
    else:
        decision = "NEUTRO"

    confiabilidad = _confiabilidad_muestra(muestra)

    motivo = (
        f"Aprendizaje jerárquico: {len(fuentes)} fuentes utilizadas; "
        f"winrate ponderado {winrate:.2f}%; "
        f"muestra representativa {muestra}; "
        f"ajuste {ajuste:+.2f}; "
        f"confiabilidad {confiabilidad.lower()}."
    )

    return {
        "aprendizaje_encontrado": True,
        "clave_aprendizaje": _clave(senal),
        "claves_consultadas": [
            item["clave"] for item in _claves_jerarquicas(senal)
        ],
        "fuentes_utilizadas": fuentes,
        "claves_descartadas": descartadas,
        "ajuste_confianza_aprendizaje": ajuste,
        "decision_aprendizaje": decision,
        "motivo_aprendizaje": motivo,
        "muestra_historica": muestra,
        "wins": combinado["wins"],
        "losses": combinado["losses"],
        "winrate": winrate,
        "confiabilidad_muestra": confiabilidad,
        "confianza_historica": winrate,
        "peso_historico_total": combinado["peso_total"],
    }


def _resultado_real(registro):
    """
    Devuelve WIN o LOSS únicamente cuando el resultado es real y válido.
    """

    if not isinstance(registro, dict):
        return ""

    if bool(registro.get("es_hipotetico", False)):
        return ""

    estado = _txt(registro.get("estado_operacion"))

    if estado in {
        "HIPOTETICA",
        "HIPOTETICO",
        "ABIERTA",
        "PENDIENTE",
        "CANCELADA",
        "CANCELADO",
        "CANCELADA_CEREBRO",
        "CANCELADA_PROTOCOLO",
    }:
        return ""

    resultado = _txt(registro.get("resultado"))

    if resultado in RESULTADOS_VALIDOS:
        return resultado

    return ""


def generar_aprendizaje_desde_resultados(
    resultados,
    ruta=RUTA_APRENDIZAJE,
):
    """
    Genera memoria jerárquica usando exclusivamente operaciones reales.

    Una operación válida alimenta todos los niveles históricos.
    """

    grupos = defaultdict(
        lambda: {
            "total": 0,
            "wins": 0,
            "losses": 0,
            "nivel": "",
            "ejemplo": {},
        }
    )

    registros_validos = 0
    registros_ignorados = 0

    for registro in resultados or []:
        if not isinstance(registro, dict):
            registros_ignorados += 1
            continue

        resultado = _resultado_real(registro)

        if resultado not in RESULTADOS_VALIDOS:
            registros_ignorados += 1
            continue

        registros_validos += 1

        for item in _claves_jerarquicas(registro):
            nivel = item["nivel"]
            clave = item["clave"]
            grupo = grupos[clave]

            if not grupo["ejemplo"]:
                grupo["ejemplo"] = registro

            grupo["nivel"] = nivel
            grupo["total"] += 1

            if resultado == "WIN":
                grupo["wins"] += 1
            elif resultado == "LOSS":
                grupo["losses"] += 1

    filas = []

    for clave, datos in grupos.items():
        total = datos["total"]
        wins = datos["wins"]
        losses = datos["losses"]

        winrate = round(
            (wins / total) * 100,
            2,
        ) if total else 0.0

        ajuste, decision = _calcular_ajuste(
            total=total,
            winrate=winrate,
        )

        ejemplo = datos["ejemplo"]

        filas.append({
            "nivel": datos["nivel"],
            "clave": clave,
            "total": total,
            "wins": wins,
            "losses": losses,
            "winrate": winrate,
            "ajuste_confianza": ajuste,
            "decision_aprendizaje": decision,
            "confiabilidad_muestra": _confiabilidad_muestra(total),
            "activo": ejemplo.get("activo", ""),
            "direccion": ejemplo.get("direccion", ""),
            "familia_setup": _familia_setup(ejemplo),
            "tipo_mercado": _normalizar_mercado(ejemplo),
            "estado_tendencia": _normalizar_tendencia(ejemplo),
            "firma_pa": _firma_tokens(
                _evidencias_por_origen(ejemplo)["pa"]
            ),
            "firma_mercado": _firma_tokens(
                _evidencias_por_origen(ejemplo)["mercado"]
            ),
            "firma_estrategia": _firma_tokens(
                _evidencias_por_origen(ejemplo)["estrategia"]
            ),
            "firma_evidencias_exacta": ejemplo.get(
                "firma_evidencias_exacta",
                ejemplo.get("firma_exacta", ""),
            ),
        })

    filas.sort(
        key=lambda fila: (
            fila["total"],
            fila["winrate"],
        ),
        reverse=True,
    )

    campos = [
        "nivel",
        "clave",
        "total",
        "wins",
        "losses",
        "winrate",
        "ajuste_confianza",
        "decision_aprendizaje",
        "confiabilidad_muestra",
        "activo",
        "direccion",
        "familia_setup",
        "tipo_mercado",
        "estado_tendencia",
        "firma_pa",
        "firma_mercado",
        "firma_estrategia",
        "firma_evidencias_exacta",
    ]

    directorio = os.path.dirname(os.path.abspath(ruta))
    if directorio:
        os.makedirs(directorio, exist_ok=True)

    with open(
        ruta,
        "w",
        newline="",
        encoding="utf-8",
    ) as archivo:
        writer = csv.DictWriter(
            archivo,
            fieldnames=campos,
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(filas)

    print("Archivo de aprendizaje generado:", ruta)
    print("Combinaciones jerárquicas aprendidas:", len(filas))
    print("Resultados reales utilizados:", registros_validos)
    print("Registros ignorados:", registros_ignorados)

    return filas


def probar_motor_aprendizaje():
    """Prueba memoria anterior y nuevas combinaciones de evidencias."""

    senal = {
        "activo": "EURUSD",
        "direccion": "CALL",
        "familia_setup": "PULLBACK",
        "tipo_setup": "CONTINUACION",
        "subtipo_setup": "PULLBACK_GENERICO",
        "tipo_mercado": "TENDENCIA",
        "estado_tendencia": "ALCISTA_FUERTE",
        "evidencias_pa": [
            {"tipo": "RECHAZO_COMPRADOR_OBSERVADO"},
            {"tipo": "IMPULSO_ALCISTA_MEDIO"},
        ],
        "evidencias_mercado": [
            "MERCADO_NORMAL",
            "TENDENCIA_FUERTE",
        ],
        "estrategia_evidencias": [
            "PULLBACK_CON_PA_A_FAVOR",
        ],
    }

    claves = _claves_jerarquicas(senal)
    niveles = {item["nivel"] for item in claves}

    assert "FAMILIA" in niveles
    assert "PA" in niveles
    assert "PA_MERCADO" in niveles
    assert "PA_SETUP" in niveles
    assert "SETUP_MERCADO" in niveles
    assert "PA_SETUP_MERCADO" in niveles
    assert "FIRMA_EVIDENCIAS_EXACTA" in niveles

    memoria = {}
    for item in claves:
        memoria[item["clave"]] = {
            "total": 20,
            "wins": 13,
            "losses": 7,
            "winrate": 65.0,
            "nivel": item["nivel"],
        }

    resultado = evaluar_aprendizaje_historico(
        senal=senal,
        memoria=memoria,
    )

    assert resultado["aprendizaje_encontrado"] is True
    assert resultado["fuentes_utilizadas"]
    assert resultado["muestra_historica"] == 20
    assert 0 < resultado["ajuste_confianza_aprendizaje"] <= AJUSTE_MAXIMO

    return resultado


if __name__ == "__main__":
    resultado_prueba = probar_motor_aprendizaje()
    print("Prueba motor aprendizaje:", resultado_prueba)