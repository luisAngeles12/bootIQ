import csv
import os
import re
import math
from collections import defaultdict

RUTA_APRENDIZAJE = "aprendizaje_historico_bootiq_C9_original.csv"

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

# Prior conservador del universo observado. Se usa solo para suavizar
# muestras pequeñas; no autoriza ni bloquea operaciones.
PRIOR_WINRATE = 49.25
PRIOR_FUERZA = 20.0
Z_INTERVALO = 1.96

# Pesos relativos por nivel histórico.
# No necesitan sumar 1 porque luego se normalizan.
PESOS_NIVELES = {
    # ========================================================
    # C-D1 — MEMORIA TRANSFERIBLE ENTRE ACTIVOS
    # ========================================================
    # Estas claves NO contienen el activo. Son la columna vertebral
    # del aprendizaje porque pueden reutilizarse en símbolos nunca vistos.
    "CONTEXTO_TECNICO": 1.20,
    "CONTEXTO_SETUP": 1.25,
    "CONTEXTO_PA": 1.30,

    # Memoria estructural general.
    "FAMILIA": 0.85,
    "FAMILIA_DIRECCION": 0.95,
    "FAMILIA_MERCADO": 0.85,
    "FAMILIA_TENDENCIA": 0.85,

    # Especialización por activo: se conserva, pero deja de ser la
    # autoridad principal del aprendizaje transferible.
    "ACTIVO_FAMILIA": 0.35,
    "ACTIVO_DIRECCION": 0.30,
    "CLAVE_ESPECIFICA": 0.40,

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


def _probabilidad_suavizada(wins, losses):
    """
    Estimación beta-binomial conservadora.

    Evita interpretar 1/1 como 100% o 0/1 como 0%. El prior se centra
    en el winrate general observado y pierde autoridad a medida que
    crece la muestra real.
    """

    wins = max(0, _entero(wins, 0))
    losses = max(0, _entero(losses, 0))

    prior_p = max(0.0, min(1.0, PRIOR_WINRATE / 100.0))
    alpha = wins + (prior_p * PRIOR_FUERZA)
    beta = losses + ((1.0 - prior_p) * PRIOR_FUERZA)
    total = alpha + beta

    if total <= 0:
        return round(PRIOR_WINRATE, 2)

    return round((alpha / total) * 100.0, 2)


def _intervalo_probabilidad(wins, losses):
    """Intervalo aproximado del posterior beta, en porcentaje."""

    wins = max(0, _entero(wins, 0))
    losses = max(0, _entero(losses, 0))
    prior_p = max(0.0, min(1.0, PRIOR_WINRATE / 100.0))

    alpha = wins + (prior_p * PRIOR_FUERZA)
    beta = losses + ((1.0 - prior_p) * PRIOR_FUERZA)
    total = alpha + beta

    if total <= 0:
        return round(PRIOR_WINRATE, 2), round(PRIOR_WINRATE, 2)

    media = alpha / total
    varianza = (alpha * beta) / ((total ** 2) * (total + 1.0))
    desviacion = math.sqrt(max(0.0, varianza))

    inferior = max(0.0, media - (Z_INTERVALO * desviacion))
    superior = min(1.0, media + (Z_INTERVALO * desviacion))

    return round(inferior * 100.0, 2), round(superior * 100.0, 2)


def _prioridad_nivel(nivel):
    """Orden para elegir la fuente principal del aprendizaje general."""

    prioridades = {
        # Evidencia transferible de mayor precisión.
        "FIRMA_EVIDENCIAS_EXACTA": 18,
        "PA_SETUP_MERCADO": 17,
        "CONTEXTO_PA": 16,
        "CONTEXTO_SETUP": 15,
        "CONTEXTO_TECNICO": 14,
        "PA_SETUP": 13,
        "PA_MERCADO": 12,
        "SETUP_MERCADO": 11,

        # Memoria intermedia/general transferible.
        "PA_DIRECCION": 10,
        "FAMILIA_TENDENCIA": 9,
        "FAMILIA_MERCADO": 8,
        "FAMILIA_DIRECCION": 7,
        "SETUP_EVIDENCIAS": 6,
        "PA": 5,
        "MERCADO_EVIDENCIAS": 4,
        "FAMILIA": 3,

        # C-D1: memoria ligada al símbolo, solo especialización.
        "CLAVE_ESPECIFICA": 2,
        "ACTIVO_FAMILIA": 1,
        "ACTIVO_DIRECCION": 1,
        "LEGACY": 0,
    }
    return prioridades.get(_txt(nivel), 0)


NIVELES_ESPECIFICOS = {
    "FIRMA_EVIDENCIAS_EXACTA",
    "PA_SETUP_MERCADO",
    "CONTEXTO_PA",
    "CONTEXTO_SETUP",
    "CONTEXTO_TECNICO",
    "PA_SETUP",
    "PA_MERCADO",
    "SETUP_MERCADO",
}

NIVELES_INTERMEDIOS = {
    "PA_DIRECCION",
    "FAMILIA_TENDENCIA",
    "FAMILIA_DIRECCION",
    "SETUP_EVIDENCIAS",
    "PA",
}

NIVELES_GENERALES = {
    "FAMILIA_MERCADO",
    "FAMILIA",
    "MERCADO_EVIDENCIAS",
    "LEGACY",
}

NIVELES_ESPECIALIZACION_ACTIVO = {
    "CLAVE_ESPECIFICA",
    "ACTIVO_FAMILIA",
    "ACTIVO_DIRECCION",
}


def _grupo_nivel(nivel):
    nivel = _txt(nivel)

    if nivel in NIVELES_ESPECIFICOS:
        return "ESPECIFICO"

    if nivel in NIVELES_INTERMEDIOS:
        return "INTERMEDIO"

    if nivel in NIVELES_ESPECIALIZACION_ACTIVO:
        return "ESPECIALIZACION_ACTIVO"

    return "GENERAL"


def _seleccionar_fuente_principal(fuentes):
    """
    C-D1 — selecciona primero conocimiento transferible.

    La memoria dependiente del activo se conserva, pero solo puede ser
    principal cuando no existe ninguna fuente transferible utilizable.
    De este modo el bot aprende comportamiento técnico, no nombres de activos.
    """

    candidatas_por_grupo = {
        "ESPECIFICO": [],
        "INTERMEDIO": [],
        "GENERAL": [],
        "ESPECIALIZACION_ACTIVO": [],
    }

    for fuente in fuentes or []:
        total = _entero(fuente.get("total"), 0)

        if total < MIN_MUESTRA_APORTE:
            continue

        nivel = _txt(fuente.get("nivel"))
        grupo = _grupo_nivel(nivel)
        prioridad = _prioridad_nivel(nivel)
        factor = _factor_muestra(total)
        confiabilidad = _confiabilidad_muestra(total)

        # Las fuentes específicas transferibles y las ligadas al activo
        # necesitan muestra confiable. Las intermedias/generales pueden
        # empezar a aportar desde MIN_MUESTRA_APORTE.
        if grupo == "ESPECIFICO":
            muestra_minima_grupo = max(
                MIN_MUESTRA_CONFIABLE,
                20,
            )
        elif grupo == "ESPECIALIZACION_ACTIVO":
            muestra_minima_grupo = max(
                MIN_MUESTRA_CONFIABLE,
                20,
            )
        else:
            muestra_minima_grupo = MIN_MUESTRA_APORTE

        if total < muestra_minima_grupo:
            continue

        score_especificidad = prioridad * factor
        score_muestra = math.log1p(total) * 1.5

        bono_confiabilidad = {
            "ALTA": 3.0,
            "MEDIA": 2.0,
            "BAJA": 1.0,
            "MUY_BAJA": 0.0,
            "INSUFICIENTE": -5.0,
        }.get(confiabilidad, 0.0)

        bono_grupo = {
            "ESPECIFICO": 6.0,
            "INTERMEDIO": 3.0,
            "GENERAL": 0.0,
            "ESPECIALIZACION_ACTIVO": -4.0,
        }[grupo]

        score = (
            score_especificidad
            + score_muestra
            + bono_confiabilidad
            + bono_grupo
        )

        candidatas_por_grupo[grupo].append(
            (score, total, prioridad, fuente)
        )

    # La especialización por activo queda deliberadamente al final.
    for grupo in (
        "ESPECIFICO",
        "INTERMEDIO",
        "GENERAL",
        "ESPECIALIZACION_ACTIVO",
    ):
        candidatas = candidatas_por_grupo[grupo]

        if not candidatas:
            continue

        candidatas.sort(
            key=lambda item: (item[0], item[1], item[2]),
            reverse=True,
        )

        return candidatas[0][3]

    return None
def _seleccionar_fuente_respaldo(fuentes, principal):
    """
    Selecciona un respaldo transferible y más general que la principal.

    C-D1: las fuentes ACTIVO_* y CLAVE_ESPECIFICA nunca estabilizan una
    probabilidad general; solo sirven como especialización diagnóstica.
    """

    principal = principal if isinstance(principal, dict) else {}
    clave_principal = principal.get("clave")
    grupo_principal = _grupo_nivel(principal.get("nivel"))

    candidatas_generales = []
    candidatas_intermedias = []

    for fuente in fuentes or []:
        if fuente.get("clave") == clave_principal:
            continue

        total = _entero(fuente.get("total"), 0)

        if total < MIN_MUESTRA_CONFIABLE:
            continue

        grupo = _grupo_nivel(fuente.get("nivel"))

        # Nunca usamos especialización de activo como respaldo general.
        if grupo == "ESPECIALIZACION_ACTIVO":
            continue

        if grupo_principal == "ESPECIFICO":
            if grupo == "GENERAL":
                candidatas_generales.append((total, fuente))
            elif grupo == "INTERMEDIO":
                candidatas_intermedias.append((total, fuente))

        elif grupo_principal == "INTERMEDIO":
            if grupo == "GENERAL":
                candidatas_generales.append((total, fuente))

        elif grupo_principal == "ESPECIALIZACION_ACTIVO":
            # Si solo quedó memoria del activo, buscamos primero cualquier
            # contexto transferible confiable como respaldo.
            if grupo == "GENERAL":
                candidatas_generales.append((total, fuente))
            elif grupo == "INTERMEDIO":
                candidatas_intermedias.append((total, fuente))

        else:
            continue

    if candidatas_generales:
        candidatas_generales.sort(
            key=lambda item: item[0],
            reverse=True,
        )
        return candidatas_generales[0][1]

    if candidatas_intermedias:
        candidatas_intermedias.sort(
            key=lambda item: item[0],
            reverse=True,
        )
        return candidatas_intermedias[0][1]

    return None


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
def _banda_fuerza_evidencia(valor):
    """
    Convierte una fuerza numérica continua en una banda estable.

    No aprende el número exacto para evitar crear una clave
    distinta por cada pequeño cambio de fuerza.
    """

    if valor in (None, ""):
        return ""

    fuerza = _numero(
        valor,
        -1.0,
    )

    if fuerza < 0:
        return ""

    if fuerza < 40:
        return "FZA_0_39"

    if fuerza < 60:
        return "FZA_40_59"

    if fuerza < 75:
        return "FZA_60_74"

    return "FZA_75_MAS"


def _token_evidencia_enriquecida(item):
    """
    Construye una representación contextual estable
    de una evidencia estructurada.

    Ejemplo:

    IMPULSO_BAJISTA_MEDIO
        +
    direccion PUT
        +
    fuerza 67
        +
    confirmada True
        ↓
    IMPULSO_BAJISTA_MEDIO__DIR_PUT__FZA_60_74__CONF_SI

    No decide si la evidencia es buena o mala.
    Solo conserva información que anteriormente se perdía.
    """

    if not isinstance(item, dict):
        return ""

    tipo = _normalizar_token(
        item.get("tipo")
        or item.get("evidencia")
        or item.get("nombre")
        or item.get("codigo")
        or item.get("familia")
    )

    if not tipo:
        return ""

    componentes = [
        tipo,
    ]

    # ========================================================
    # DIRECCION
    # ========================================================

    direccion = _normalizar_token(
        item.get("direccion")
    )

    if direccion:
        componentes.append(
            f"DIR_{direccion}"
        )

    # ========================================================
    # FUERZA
    # ========================================================
    
    fuerza_evidencia = item.get("fuerza")
    
    modulo_evidencia = _txt(
        item.get("modulo")
        or item.get("fuente")
    )
    
    categoria_evidencia = _txt(
        item.get("categoria")
    )
    
    # Price Action trabaja internamente con fuerza 0.0–1.0,
    # mientras las bandas históricas trabajan en porcentaje 0–100.
    # La conversión se hace solo para PA para no alterar las escalas
    # utilizadas por mercado o estrategia.
    if (
        modulo_evidencia == "PRICE_ACTION"
        or categoria_evidencia == "PRICE_ACTION"
    ):
        fuerza_pa = _numero(
            fuerza_evidencia,
            -1.0,
        )
    
        if 0.0 <= fuerza_pa <= 1.0:
            fuerza_evidencia = fuerza_pa * 100.0
    
    banda_fuerza = (
        _banda_fuerza_evidencia(
            fuerza_evidencia
        )
    )

    if banda_fuerza:
        componentes.append(
            banda_fuerza
        )

    # ========================================================
    # CONFIRMACION
    # ========================================================

    if "confirmada" in item:
        confirmada = item.get(
            "confirmada"
        )

        if isinstance(confirmada, str):
            confirmada_txt = (
                confirmada
                .strip()
                .lower()
            )

            confirmada = (
                confirmada_txt
                in {
                    "true",
                    "1",
                    "si",
                    "sí",
                    "yes",
                }
            )

        componentes.append(
            "CONF_SI"
            if bool(confirmada)
            else "CONF_NO"
        )

    # ========================================================
    # CATEGORIA
    # ========================================================

    categoria = _normalizar_token(
        item.get("categoria")
    )

    if categoria:
        componentes.append(
            f"CAT_{categoria}"
        )

    # Si únicamente existe el tipo, no creamos
    # una copia redundante.
    if len(componentes) <= 1:
        return ""

    return "__".join(
        componentes
    )

def _extraer_tokens(valor):
    """
    Extrae evidencias desde listas, diccionarios o textos serializados.

    FASE INTELIGENCIA:
    cuando recibe una evidencia estructurada conserva dos niveles:

    1. token BASE
       Ej:
       IMPULSO_BAJISTA_MEDIO

    2. token CONTEXTUAL
       Ej:
       IMPULSO_BAJISTA_MEDIO__DIR_PUT__
       FZA_60_74__CONF_SI__CAT_PRICE_ACTION

    El token base mantiene compatibilidad con la memoria anterior.
    El contextual permite que BootIQ aprenda diferencias que antes
    estaban siendo descartadas.

    Esta función NO asigna si una evidencia es buena o mala.
    """

    tokens = []

    def agregar_token(token):
        token = _normalizar_token(
            token
        )

        if token:
            tokens.append(
                token
            )

    def agregar(item):
        if item is None:
            return

        # ====================================================
        # EVIDENCIA ESTRUCTURADA
        # ====================================================

        if isinstance(item, dict):
            candidato = (
                item.get("tipo")
                or item.get("evidencia")
                or item.get("nombre")
                or item.get("codigo")
                or item.get("familia")
            )

            # -----------------------------------------------
            # 1. TOKEN BASE
            #
            # Se conserva para compatibilidad.
            # -----------------------------------------------

            agregar_token(
                candidato
            )

            # -----------------------------------------------
            # 2. TOKEN CONTEXTUAL
            #
            # Conserva información que antes se perdía.
            # -----------------------------------------------

            enriquecido = (
                _token_evidencia_enriquecida(
                    item
                )
            )

            if enriquecido:
                agregar_token(
                    enriquecido
                )

            return

        # ====================================================
        # LISTAS / TUPLAS / SETS
        # ====================================================

        if isinstance(
            item,
            (
                list,
                tuple,
                set,
            ),
        ):
            for subitem in item:
                agregar(
                    subitem
                )

            return

        # ====================================================
        # TEXTO SERIALIZADO
        # ====================================================

        texto = str(
            item or ""
        ).strip()

        if not texto:
            return

        partes = re.split(
            r"\s*[|;,]\s*",
            texto,
        )

        for parte in partes:
            agregar_token(
                parte
            )

    agregar(
        valor
    )

    # ========================================================
    # ELIMINAR DUPLICADOS SIN PERDER ORDEN
    # ========================================================

    vistos = set()
    salida = []

    for token in tokens:
        if token in vistos:
            continue

        vistos.add(
            token
        )

        salida.append(
            token
        )

    return salida
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
def _normalizar_protocolo(senal):
    """
    Obtiene el protocolo técnico realmente evaluado.

    No decide.
    No crea información si el protocolo todavía no ocurrió.
    """

    protocolo = _normalizar_token(
        senal.get("auditoria_protocolo_tipo")
    )

    if not protocolo:
        return ""

    if protocolo in {
        "SIN_PROTOCOLO",
        "VETO_PREVIO",
    }:
        return ""

    return protocolo


def _normalizar_evento_protocolo(senal):
    """
    Evento técnico exacto que produjo o canceló la entrada.
    """

    motivo = _normalizar_token(
        senal.get("auditoria_protocolo_motivo")
    )

    if not motivo:
        return ""

    return motivo


def _normalizar_espera_protocolo(senal):
    """
    Agrupa la espera real sin fabricar timing.

    -1 significa que no hubo entrada y no participa
    como evidencia de una operación ejecutada.
    """

    try:
        espera = int(
            float(
                senal.get(
                    "auditoria_protocolo_espera_velas",
                    -1,
                )
            )
        )
    except (TypeError, ValueError):
        return ""

    if espera < 0:
        return ""

    if espera >= 5:
        return "5_MAS"

    return str(espera)


def _claves_protocolo(senal):
    """
    Construye únicamente memoria POST-PROTOCOLO.

    Estas claves existen solamente después de que
    motor_protocolos haya encontrado una entrada técnica.

    No sustituyen las claves históricas generales.
    Son una segunda capa de evidencia.
    """

    protocolo = _normalizar_protocolo(senal)

    operada = bool(
        senal.get(
            "auditoria_protocolo_operada",
            False,
        )
    )

    # No aprender como entrada válida algo que nunca se ejecutó.
    if not protocolo or not operada:
        return []

    subtipo = _normalizar_token(
        senal.get("auditoria_protocolo_subtipo")
        or senal.get("subtipo_setup")
    )

    evento = _normalizar_evento_protocolo(
        senal
    )

    espera = _normalizar_espera_protocolo(
        senal
    )

    nivel_riesgo = _normalizar_token(
        senal.get(
            "auditoria_protocolo_nivel_riesgo"
        )
    )

    nivel_confirmacion = _normalizar_token(
        senal.get(
            "auditoria_protocolo_nivel_confirmacion"
        )
    )

    accion_confirmacion = _normalizar_token(
        senal.get(
            "auditoria_protocolo_accion_confirmacion"
        )
    )

    mercado = _normalizar_mercado(senal)
    tendencia = _normalizar_tendencia(senal)

    direccion = (
        _txt(senal.get("direccion"))
        or "SIN_DIRECCION"
    )

    claves = []
    vistos = set()

    # ========================================================
    # NIVELES CON BUENA CAPACIDAD DE GENERALIZACIÓN
    # ========================================================

    _agregar_clave(
        claves,
        vistos,
        "PROTOCOLO",
        [protocolo],
    )

    _agregar_clave(
        claves,
        vistos,
        "PROTOCOLO_DIRECCION",
        [protocolo, direccion],
    )

    if subtipo:
        _agregar_clave(
            claves,
            vistos,
            "PROTOCOLO_SUBTIPO",
            [protocolo, subtipo],
        )

    if evento:
        _agregar_clave(
            claves,
            vistos,
            "PROTOCOLO_EVENTO",
            [protocolo, evento],
        )

    if espera:
        _agregar_clave(
            claves,
            vistos,
            "PROTOCOLO_ESPERA",
            [protocolo, espera],
        )

    if nivel_riesgo:
        _agregar_clave(
            claves,
            vistos,
            "PROTOCOLO_RIESGO",
            [protocolo, nivel_riesgo],
        )

    if nivel_confirmacion:
        _agregar_clave(
            claves,
            vistos,
            "PROTOCOLO_CONFIRMACION",
            [
                protocolo,
                nivel_confirmacion,
            ],
        )

    if accion_confirmacion:
        _agregar_clave(
            claves,
            vistos,
            "PROTOCOLO_ACCION_CONFIRMACION",
            [
                protocolo,
                accion_confirmacion,
            ],
        )

    # ========================================================
    # CONTEXTO
    # ========================================================

    if mercado and mercado != "SIN_MERCADO":
        _agregar_clave(
            claves,
            vistos,
            "PROTOCOLO_MERCADO",
            [protocolo, mercado],
        )

    if tendencia and tendencia != "SIN_TENDENCIA":
        _agregar_clave(
            claves,
            vistos,
            "PROTOCOLO_TENDENCIA",
            [protocolo, tendencia],
        )

    # ========================================================
    # COMBINACIONES TÉCNICAS CONTROLADAS
    # ========================================================
    #
    # No creamos combinaciones de 6-8 variables porque
    # destruiríamos la muestra.
    # ========================================================

    if subtipo and espera:
        _agregar_clave(
            claves,
            vistos,
            "PROTOCOLO_SUBTIPO_ESPERA",
            [
                protocolo,
                subtipo,
                espera,
            ],
        )

    if evento and espera:
        _agregar_clave(
            claves,
            vistos,
            "PROTOCOLO_EVENTO_ESPERA",
            [
                protocolo,
                evento,
                espera,
            ],
        )

    if evento and nivel_riesgo:
        _agregar_clave(
            claves,
            vistos,
            "PROTOCOLO_EVENTO_RIESGO",
            [
                protocolo,
                evento,
                nivel_riesgo,
            ],
        )

    if evento and nivel_confirmacion:
        _agregar_clave(
            claves,
            vistos,
            "PROTOCOLO_EVENTO_CONFIRMACION",
            [
                protocolo,
                evento,
                nivel_confirmacion,
            ],
        )

    return claves

def _claves_jerarquicas(senal):
    """
    Genera memoria estructural y memoria de combinaciones del Cerebro Único.

    Las claves antiguas se conservan. Las nuevas se crean únicamente cuando
    existen evidencias reales en el registro, evitando fabricar contexto.

    C-C1:
    - las claves post-protocolo se agregan de forma independiente;
    - la firma exacta no depende de PA + SETUP + MERCADO simultáneamente;
    - la función siempre devuelve una lista de claves.
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

    componentes_setup = [
        familia,
        tipo_setup,
        subtipo_setup,
    ]

    firma_setup_contextual = _firma_tokens(
        componentes_setup + evidencias["estrategia"]
    )

    claves = []
    vistos = set()

    # ========================================================
    # C-D1 — MEMORIA TRANSFERIBLE ENTRE ACTIVOS
    # ========================================================
    # Ninguna de estas claves contiene `activo`. El mismo patrón
    # aprendido en un símbolo puede reutilizarse en otro distinto.
    _agregar_clave(
        claves,
        vistos,
        "CONTEXTO_TECNICO",
        [direccion, familia, mercado, tendencia],
    )

    if tipo_setup or subtipo_setup:
        _agregar_clave(
            claves,
            vistos,
            "CONTEXTO_SETUP",
            [
                direccion,
                familia,
                tipo_setup,
                subtipo_setup,
                mercado,
            ],
        )

    if firma_pa:
        _agregar_clave(
            claves,
            vistos,
            "CONTEXTO_PA",
            [direccion, familia, firma_pa, mercado],
        )

    # ========================================================
    # MEMORIA ESTRUCTURAL GENERAL + ESPECIALIZACION POR ACTIVO
    # ========================================================
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

    for token in evidencias["pa"]:
        _agregar_clave(claves, vistos, "PA", [token])
        _agregar_clave(
            claves, vistos, "PA_DIRECCION", [token, direccion]
        )

    for token in evidencias["mercado"]:
        _agregar_clave(
            claves, vistos, "MERCADO_EVIDENCIAS", [token]
        )

    for token in evidencias["estrategia"]:
        _agregar_clave(
            claves, vistos, "SETUP_EVIDENCIAS", [token]
        )

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

    # FIRMA EXACTA: independiente de PA+SETUP+MERCADO simultáneos.
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

    # C-C1: memoria post-protocolo independiente.
    for item in _claves_protocolo(senal):
        clave = item.get("clave")

        if not clave or clave in vistos:
            continue

        vistos.add(clave)
        claves.append(item)

    return claves

def _clave(senal):
    """
    Mantiene compatibilidad con código externo que espere una sola clave.

    C-D1: devuelve primero la clave técnica transferible. La antigua
    CLAVE_ESPECIFICA por activo sigue existiendo dentro de la memoria,
    pero deja de representar la identidad principal de una señal.
    """

    claves = _claves_jerarquicas(senal)

    for nivel_objetivo in (
        "CONTEXTO_TECNICO",
        "FAMILIA_DIRECCION",
        "CLAVE_ESPECIFICA",
    ):
        for item in claves:
            if item["nivel"] == nivel_objetivo:
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
    Curva continua de autoridad estadística.

    Conserva MIN_MUESTRA_APORTE como mínimo absoluto, pero elimina
    los saltos bruscos entre 5, 12, 20, 30 y 50 observaciones.

    La autoridad crece suavemente:
    - cerca de 0.25 con 5 muestras;
    - alrededor de 0.45 con 12;
    - alrededor de 0.65 con 20;
    - alrededor de 0.85 con 35;
    - se aproxima progresivamente a 1.0.
    """

    total = _entero(total, 0)

    if total < MIN_MUESTRA_APORTE:
        return 0.0

    # Curva exponencial calibrada para crecer sin discontinuidades.
    factor = 1.0 - math.exp(-total / 19.0)

    # Mantiene una contribución mínima controlada desde 5 muestras.
    return round(max(0.20, min(1.0, factor)), 4)


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
    probabilidad = _probabilidad_suavizada(wins, losses)
    intervalo_inferior, intervalo_superior = _intervalo_probabilidad(
        wins, losses
    )

    return {
        "total": total,
        "wins": wins,
        "losses": losses,
        "winrate": round(winrate, 2),
        "ajuste_confianza": ajuste,
        "decision_aprendizaje": decision,
        "confiabilidad_muestra": _confiabilidad_muestra(total),
        "probabilidad_ajustada": probabilidad,
        "intervalo_inferior": intervalo_inferior,
        "intervalo_superior": intervalo_superior,
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
        probabilidad = _probabilidad_suavizada(wins, losses)
        intervalo_inferior, intervalo_superior = _intervalo_probabilidad(
            wins, losses
        )

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
            "probabilidad_ajustada": probabilidad,
            "intervalo_inferior": intervalo_inferior,
            "intervalo_superior": intervalo_superior,
        })


    return fuentes, descartadas


def _combinar_fuentes(fuentes):
    """
    Combina fuentes sin promediar indiscriminadamente claves correlacionadas.

    La fuente principal conserva su señal estadística. La fuente general de
    respaldo actúa como estabilizador, pero su influencia disminuye cuando
    la principal tiene suficiente muestra.

    Si no existe una fuente de respaldo válida, la fuente principal se
    estabiliza contra PRIOR_WINRATE para evitar que una muestra relativamente
    pequeña tenga 100% de autoridad.

    La incertidumbre se expresa mediante confiabilidad e intervalo; no se
    aplasta automáticamente una señal específica hasta el promedio general.
    """

    if not fuentes:
        return {
            "ajuste": 0.0,
            "winrate": 0.0,
            "muestra": 0,
            "wins": 0,
            "losses": 0,
            "peso_total": 0.0,
            "probabilidad_estimada": PRIOR_WINRATE,
            "intervalo_inferior": PRIOR_WINRATE,
            "intervalo_superior": PRIOR_WINRATE,
            "fuente_principal": None,
            "fuente_respaldo": None,
            "peso_fuente_principal": 0.0,
            "peso_fuente_respaldo": 0.0,
        }

    # Compatibilidad con el ajuste histórico anterior.
    suma_ajustes = 0.0
    suma_winrate = 0.0
    peso_total = 0.0
    muestras = []

    for fuente in fuentes:
        peso = _numero(
            fuente.get("peso_efectivo"),
            0.0,
        )

        if peso <= 0:
            continue

        suma_ajustes += (
            _numero(
                fuente.get("ajuste"),
                0.0,
            )
            * peso
        )

        suma_winrate += (
            _numero(
                fuente.get("winrate"),
                0.0,
            )
            * peso
        )

        peso_total += peso

        muestras.append(
            _entero(
                fuente.get("total"),
                0,
            )
        )

    if peso_total > 0:
        ajuste_final = _limitar_ajuste(
            suma_ajustes / peso_total
        )

        winrate_final = round(
            suma_winrate / peso_total,
            2,
        )
    else:
        ajuste_final = 0.0
        winrate_final = 0.0

    principal = _seleccionar_fuente_principal(
        fuentes
    )

    respaldo = _seleccionar_fuente_respaldo(
        fuentes,
        principal,
    )

    peso_principal = 0.0
    peso_respaldo = 0.0

    if principal:
        prob_principal = _numero(
            principal.get(
                "probabilidad_ajustada"
            ),
            PRIOR_WINRATE,
        )

        total_principal = _entero(
            principal.get("total"),
            0,
        )

        factor_principal = _factor_muestra(
            total_principal
        )

        # La principal gana autoridad progresivamente.
        #
        # Con poca muestra:
        # aproximadamente 50% de autoridad.
        #
        # Con muestra sólida:
        # puede llegar hasta 85%.
        #
        # Esto evita que una fuente específica con poca
        # evidencia domine excesivamente la probabilidad.
        peso_principal = min(
            0.85,
            max(
                0.50,
                0.45
                + (
                    0.40
                    * factor_principal
                ),
            ),
        )

        peso_respaldo = (
            1.0 - peso_principal
        )

        if respaldo:
            prob_respaldo = _numero(
                respaldo.get(
                    "probabilidad_ajustada"
                ),
                PRIOR_WINRATE,
            )

            probabilidad = (
                prob_principal
                * peso_principal
                +
                prob_respaldo
                * peso_respaldo
            )

        else:
            # Si no existe una fuente histórica
            # independiente de respaldo, usamos el prior
            # general como estabilizador.
            #
            # De esta forma la principal nunca obtiene
            # automáticamente 100% de autoridad.
            probabilidad = (
                prob_principal
                * peso_principal
                +
                PRIOR_WINRATE
                * peso_respaldo
            )

        intervalo_inferior = _numero(
            principal.get(
                "intervalo_inferior"
            ),
            probabilidad,
        )

        intervalo_superior = _numero(
            principal.get(
                "intervalo_superior"
            ),
            probabilidad,
        )

        muestra_representativa = (
            total_principal
        )

        wins_representativos = _entero(
            principal.get("wins"),
            0,
        )

        losses_representativos = _entero(
            principal.get("losses"),
            0,
        )

    else:
        probabilidad = PRIOR_WINRATE

        intervalo_inferior = (
            PRIOR_WINRATE
        )

        intervalo_superior = (
            PRIOR_WINRATE
        )

        muestra_representativa = (
            max(muestras)
            if muestras
            else 0
        )

        wins_representativos = 0
        losses_representativos = 0

    return {
        "ajuste": ajuste_final,
        "winrate": winrate_final,
        "muestra": muestra_representativa,
        "wins": wins_representativos,
        "losses": losses_representativos,
        "peso_total": round(
            peso_total,
            3,
        ),
        "probabilidad_estimada": round(
            probabilidad,
            2,
        ),
        "intervalo_inferior": round(
            intervalo_inferior,
            2,
        ),
        "intervalo_superior": round(
            intervalo_superior,
            2,
        ),
        "fuente_principal": principal,
        "fuente_respaldo": respaldo,
        "peso_fuente_principal": round(
            peso_principal,
            3,
        ),
        "peso_fuente_respaldo": round(
            peso_respaldo,
            3,
        ),
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
            "probabilidad_estimada": PRIOR_WINRATE,
            "intervalo_probabilidad_inferior": PRIOR_WINRATE,
            "intervalo_probabilidad_superior": PRIOR_WINRATE,
            "fuente_probabilidad_principal": None,
            "fuente_probabilidad_respaldo": None,
            "grupo_fuente_probabilidad_principal": "SIN_DATOS",
            "grupo_fuente_probabilidad_respaldo": "SIN_DATOS",
            "modo_probabilidad": "SOMBRA",
            "peso_historico_total": 0.0,
            "peso_fuente_probabilidad_principal": 0.0,
            "peso_fuente_probabilidad_respaldo": 0.0,
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
        f"probabilidad sombra {combinado['probabilidad_estimada']:.2f}%; "
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
        "probabilidad_estimada": combinado["probabilidad_estimada"],
        "intervalo_probabilidad_inferior": combinado["intervalo_inferior"],
        "intervalo_probabilidad_superior": combinado["intervalo_superior"],
        "fuente_probabilidad_principal": combinado["fuente_principal"],
        "fuente_probabilidad_respaldo": combinado["fuente_respaldo"],
        "grupo_fuente_probabilidad_principal": _grupo_nivel(
            (combinado["fuente_principal"] or {}).get("nivel")
        ),
        "grupo_fuente_probabilidad_respaldo": _grupo_nivel(
            (combinado["fuente_respaldo"] or {}).get("nivel")
        ) if combinado["fuente_respaldo"] else "SIN_RESPALDO",
        "modo_probabilidad": "SOMBRA",
        "peso_historico_total": combinado["peso_total"],
        "peso_fuente_probabilidad_principal": combinado.get(
            "peso_fuente_principal",
            0.0,
        ),
        "peso_fuente_probabilidad_respaldo": combinado.get(
            "peso_fuente_respaldo",
            0.0,
        ),
    }

def _prioridad_nivel_post_protocolo(nivel):
    """
    Prioridad específica de las fuentes C-C2.

    La entrada técnica real debe pesar más que
    el contexto general del protocolo.
    """

    prioridades = {
        "PROTOCOLO_EVENTO_ESPERA": 100,
        "PROTOCOLO_SUBTIPO_ESPERA": 95,
        "PROTOCOLO_EVENTO_CONFIRMACION": 90,
        "PROTOCOLO_EVENTO_RIESGO": 85,
        "PROTOCOLO_EVENTO": 80,
        "PROTOCOLO_ESPERA": 75,
        "PROTOCOLO_SUBTIPO": 70,
        "PROTOCOLO_CONFIRMACION": 65,
        "PROTOCOLO_ACCION_CONFIRMACION": 62,
        "PROTOCOLO_RIESGO": 60,
        "PROTOCOLO_MERCADO": 45,
        "PROTOCOLO_TENDENCIA": 40,
        "PROTOCOLO_DIRECCION": 35,
        "PROTOCOLO": 30,
    }

    return prioridades.get(_txt(nivel), 0)


def _combinar_fuentes_post_protocolo(fuentes):
    """
    Combinación exclusiva C-C2.

    Prioriza evento + espera real + subtipo.
    El contexto general solo funciona como respaldo.
    No decide si operar; solo estima probabilidad post-protocolo.
    """

    if not fuentes:
        return {
            "probabilidad_estimada": PRIOR_WINRATE,
            "intervalo_inferior": PRIOR_WINRATE,
            "intervalo_superior": PRIOR_WINRATE,
            "muestra": 0,
            "wins": 0,
            "losses": 0,
            "fuente_principal": None,
            "fuente_respaldo": None,
            "peso_fuente_principal": 0.0,
            "peso_fuente_respaldo": 0.0,
        }

    candidatas = []

    for fuente in fuentes:
        total = _entero(fuente.get("total"), 0)
        if total < MIN_MUESTRA_APORTE:
            continue

        nivel = _txt(fuente.get("nivel"))
        prioridad = _prioridad_nivel_post_protocolo(nivel)
        if prioridad <= 0:
            continue

        factor = _factor_muestra(total)
        score = prioridad * (0.70 + 0.30 * factor)
        candidatas.append((score, prioridad, total, fuente))

    if not candidatas:
        return {
            "probabilidad_estimada": PRIOR_WINRATE,
            "intervalo_inferior": PRIOR_WINRATE,
            "intervalo_superior": PRIOR_WINRATE,
            "muestra": 0,
            "wins": 0,
            "losses": 0,
            "fuente_principal": None,
            "fuente_respaldo": None,
            "peso_fuente_principal": 0.0,
            "peso_fuente_respaldo": 0.0,
        }

    candidatas.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
    principal = candidatas[0][3]
    prioridad_principal = _prioridad_nivel_post_protocolo(principal.get("nivel"))

    respaldo = None
    candidatas_respaldo = []

    for _, prioridad, total, fuente in candidatas[1:]:
        if fuente.get("clave") == principal.get("clave"):
            continue
        if prioridad >= prioridad_principal:
            continue
        if total < MIN_MUESTRA_CONFIABLE:
            continue
        candidatas_respaldo.append((prioridad, total, fuente))

    if candidatas_respaldo:
        candidatas_respaldo.sort(key=lambda item: (item[0], item[1]), reverse=True)
        respaldo = candidatas_respaldo[0][2]

    prob_principal = _numero(principal.get("probabilidad_ajustada"), PRIOR_WINRATE)
    total_principal = _entero(principal.get("total"), 0)
    factor_principal = _factor_muestra(total_principal)

    peso_principal = min(0.92, max(0.70, 0.65 + (0.27 * factor_principal)))
    peso_respaldo = 0.0

    if respaldo:
        prob_respaldo = _numero(respaldo.get("probabilidad_ajustada"), PRIOR_WINRATE)
        peso_respaldo = 1.0 - peso_principal
        probabilidad = (prob_principal * peso_principal) + (prob_respaldo * peso_respaldo)
    else:
        probabilidad = prob_principal
        peso_principal = 1.0

    intervalo_inferior = _numero(principal.get("intervalo_inferior"), probabilidad)
    intervalo_superior = _numero(principal.get("intervalo_superior"), probabilidad)

    return {
        "probabilidad_estimada": round(probabilidad, 2),
        "intervalo_inferior": round(intervalo_inferior, 2),
        "intervalo_superior": round(intervalo_superior, 2),
        "muestra": total_principal,
        "wins": _entero(principal.get("wins"), 0),
        "losses": _entero(principal.get("losses"), 0),
        "fuente_principal": principal,
        "fuente_respaldo": respaldo,
        "peso_fuente_principal": round(peso_principal, 3),
        "peso_fuente_respaldo": round(peso_respaldo, 3),
    }


def evaluar_aprendizaje_post_protocolo(
    senal,
    memoria=None,
):
    """
    Evalúa EXCLUSIVAMENTE la evidencia generada
    después de que motor_protocolos encontró
    una entrada técnica.

    No mezcla:
    - familia general;
    - PA general;
    - mercado general;
    - setup general.

    Solo consulta memoria PROTOCOLO_*.

    No decide la operación.
    Devuelve probabilidad y diagnóstico.
    """

    if not isinstance(senal, dict):
        senal = {}

    if memoria is None:
        memoria = cargar_aprendizaje()

    if not isinstance(memoria, dict):
        memoria = {}

    claves = _claves_protocolo(senal)

    fuentes = []
    descartadas = []

    for item in claves:
        nivel = item.get("nivel", "")
        clave = item.get("clave", "")

        if not clave:
            continue

        data = memoria.get(clave)

        if not data:
            descartadas.append({
                "nivel": nivel,
                "clave": clave,
                "motivo": "SIN_DATOS",
            })
            continue

        total = _entero(
            data.get("total"),
            0,
        )

        wins = _entero(
            data.get("wins"),
            0,
        )

        losses = _entero(
            data.get("losses"),
            0,
        )

        winrate = _numero(
            data.get("winrate"),
            0.0,
        )

        if total < MIN_MUESTRA_APORTE:
            descartadas.append({
                "nivel": nivel,
                "clave": clave,
                "motivo": "MUESTRA_INSUFICIENTE",
                "total": total,
            })
            continue

        ajuste, decision = _calcular_ajuste(
            total=total,
            winrate=winrate,
        )

        factor = _factor_muestra(total)

        probabilidad = _probabilidad_suavizada(
            wins,
            losses,
        )

        inferior, superior = (
            _intervalo_probabilidad(
                wins,
                losses,
            )
        )

        fuentes.append({
            "nivel": nivel,
            "clave": clave,
            "total": total,
            "wins": wins,
            "losses": losses,
            "winrate": round(
                winrate,
                2,
            ),
            "ajuste": ajuste,
            "decision": decision,
            "confiabilidad": (
                _confiabilidad_muestra(total)
            ),
            "peso_nivel": 1.0,
            "factor_muestra": round(
                factor,
                3,
            ),
            "peso_efectivo": round(
                factor,
                3,
            ),
            "probabilidad_ajustada": (
                probabilidad
            ),
            "intervalo_inferior": inferior,
            "intervalo_superior": superior,
        })

    combinado = (
        _combinar_fuentes_post_protocolo(
            fuentes
        )
    )

    if not fuentes:
        return {
            "aprendizaje_post_protocolo_encontrado": False,
            "claves_consultadas_post_protocolo": [
                item.get("clave")
                for item in claves
            ],
            "fuentes_post_protocolo": [],
            "claves_descartadas_post_protocolo": descartadas,
            "probabilidad_post_protocolo": PRIOR_WINRATE,
            "intervalo_post_protocolo_inferior": PRIOR_WINRATE,
            "intervalo_post_protocolo_superior": PRIOR_WINRATE,
            "muestra_post_protocolo": 0,
            "wins_post_protocolo": 0,
            "losses_post_protocolo": 0,
            "confiabilidad_post_protocolo": "SIN_DATOS",
            "fuente_post_protocolo_principal": None,
            "fuente_post_protocolo_respaldo": None,
        }

    muestra = combinado.get(
        "muestra",
        0,
    )

    return {
        "aprendizaje_post_protocolo_encontrado": True,

        "claves_consultadas_post_protocolo": [
            item.get("clave")
            for item in claves
        ],

        "fuentes_post_protocolo": fuentes,

        "claves_descartadas_post_protocolo": (
            descartadas
        ),

        "probabilidad_post_protocolo": (
            combinado.get(
                "probabilidad_estimada",
                PRIOR_WINRATE,
            )
        ),

        "intervalo_post_protocolo_inferior": (
            combinado.get(
                "intervalo_inferior",
                PRIOR_WINRATE,
            )
        ),

        "intervalo_post_protocolo_superior": (
            combinado.get(
                "intervalo_superior",
                PRIOR_WINRATE,
            )
        ),

        "muestra_post_protocolo": muestra,

        "wins_post_protocolo": combinado.get(
            "wins",
            0,
        ),

        "losses_post_protocolo": combinado.get(
            "losses",
            0,
        ),

        "confiabilidad_post_protocolo": (
            _confiabilidad_muestra(
                muestra
            )
        ),

        "fuente_post_protocolo_principal": (
            combinado.get(
                "fuente_principal"
            )
        ),

        "fuente_post_protocolo_respaldo": (
            combinado.get(
                "fuente_respaldo"
            )
        ),
    }
def _resultado_real(registro):
    """Devuelve WIN o LOSS únicamente para operaciones ejecutadas."""

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
    return resultado if resultado in RESULTADOS_VALIDOS else ""


def _resultado_aprendizaje(registro, incluir_hipoteticos=False):
    """
    Selecciona la etiqueta de entrenamiento.

    En producción conserva resultados ejecutados. En backtest diagnóstico
    puede usar resultado_hipotetico para aprender del universo completo y
    evitar el sesgo de entrenar solo con señales ya autorizadas.
    """

    if not isinstance(registro, dict):
        return ""

    if incluir_hipoteticos:
        resultado_hipotetico = _txt(registro.get("resultado_hipotetico"))
        if resultado_hipotetico in RESULTADOS_VALIDOS:
            return resultado_hipotetico

    return _resultado_real(registro)

def _medir_estabilidad_temporal(observaciones):
    """
    Mide si el comportamiento histórico de una misma clave
    se mantiene a través del tiempo.

    observaciones:
        lista de pares:
        [
            (timestamp, "WIN"),
            (timestamp, "LOSS"),
            ...
        ]

    No decide si una evidencia es buena o mala.
    Solo entrega métricas objetivas de estabilidad.
    """

    validas = []

    for observacion in observaciones or []:
        if (
            not isinstance(observacion, (list, tuple))
            or len(observacion) != 2
        ):
            continue

        fecha, resultado = observacion

        try:
            fecha = float(fecha)
        except (TypeError, ValueError):
            continue

        resultado = _txt(resultado)

        if (
            fecha <= 0
            or resultado not in RESULTADOS_VALIDOS
        ):
            continue

        validas.append(
            (
                fecha,
                resultado,
            )
        )

    # ========================================================
    # NECESITAMOS AL MENOS 3 BLOQUES DE MIN_MUESTRA_APORTE
    # ========================================================

    minimo_estabilidad = (
        MIN_MUESTRA_APORTE * 3
    )

    total = len(validas)

    if total < minimo_estabilidad:
        return {
            "estabilidad_disponible": False,
            "muestra_estabilidad": total,
            "wr_inicio": None,
            "wr_medio": None,
            "wr_reciente": None,
            "dispersion_temporal": None,
            "cambio_inicio_reciente": None,
            "bloques_mismo_lado_prior": 0,
            "persistencia_direccion": None,
        }

    # ========================================================
    # ORDEN CRONOLOGICO
    # ========================================================

    validas.sort(
        key=lambda item: item[0]
    )

    # ========================================================
    # DIVIDIR EN 3 PERIODOS CON TAMAÑOS LO MAS PAREJOS POSIBLE
    # ========================================================

    base = total // 3
    resto = total % 3

    tamanos = [
        base + (1 if i < resto else 0)
        for i in range(3)
    ]

    bloques = []
    inicio = 0

    for tamano in tamanos:
        fin = inicio + tamano

        bloques.append(
            validas[inicio:fin]
        )

        inicio = fin

    # ========================================================
    # WINRATE DE CADA BLOQUE
    # ========================================================

    winrates = []

    for bloque in bloques:
        total_bloque = len(bloque)

        wins_bloque = sum(
            1
            for _, resultado in bloque
            if resultado == "WIN"
        )

        if total_bloque > 0:
            wr = (
                wins_bloque
                / total_bloque
            ) * 100.0
        else:
            wr = 0.0

        winrates.append(
            round(wr, 2)
        )

    wr_inicio = winrates[0]
    wr_medio = winrates[1]
    wr_reciente = winrates[2]

    # ========================================================
    # DISPERSION
    # ========================================================

    dispersion = (
        max(winrates)
        - min(winrates)
    )

    # ========================================================
    # CAMBIO ENTRE PRINCIPIO Y FINAL
    # ========================================================

    cambio_inicio_reciente = (
        wr_reciente
        - wr_inicio
    )

    # ========================================================
    # PERSISTENCIA RESPECTO AL PRIOR
    # ========================================================

    wins_total = sum(
        1
        for _, resultado in validas
        if resultado == "WIN"
    )

    wr_total = (
        wins_total
        / total
    ) * 100.0

    global_favorable = (
        wr_total >= PRIOR_WINRATE
    )

    bloques_mismo_lado = 0

    for wr in winrates:
        bloque_favorable = (
            wr >= PRIOR_WINRATE
        )

        if bloque_favorable == global_favorable:
            bloques_mismo_lado += 1

    persistencia = (
        bloques_mismo_lado / 3.0
    )

    return {
        "estabilidad_disponible": True,
        "muestra_estabilidad": total,
        "wr_inicio": wr_inicio,
        "wr_medio": wr_medio,
        "wr_reciente": wr_reciente,
        "dispersion_temporal": round(
            dispersion,
            2,
        ),
        "cambio_inicio_reciente": round(
            cambio_inicio_reciente,
            2,
        ),
        "bloques_mismo_lado_prior": (
            bloques_mismo_lado
        ),
        "persistencia_direccion": round(
            persistencia,
            3,
        ),
    }
def generar_aprendizaje_desde_resultados(
    resultados,
    ruta=RUTA_APRENDIZAJE,
    incluir_hipoteticos=False,
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
            "observaciones": [],
        }
    )

    registros_validos = 0
    registros_ignorados = 0

    for registro in resultados or []:
        if not isinstance(registro, dict):
            registros_ignorados += 1
            continue

        resultado = _resultado_aprendizaje(
            registro,
            incluir_hipoteticos=incluir_hipoteticos,
        )

        if resultado not in RESULTADOS_VALIDOS:
            registros_ignorados += 1
            continue

        registros_validos += 1

        for item in _claves_jerarquicas(registro):
            nivel = item["nivel"]
            clave = item["clave"]
        
            # ========================================================
            # SEPARACION ESTRICTA C9 / C-C2
            # ========================================================
            #
            # La memoria general aprende de resultado_hipotetico.
            #
            # Las claves PROTOCOLO_* pertenecen exclusivamente a C-C2,
            # que aprende solamente de OPERADA_PROTOCOLO y resultado REAL.
            #
            # Por tanto, la generación de memoria general nunca debe
            # crear ni sobrescribir conocimiento post-protocolo.
            # ========================================================
        
            nivel_normalizado = _txt(nivel)
            clave_normalizada = _txt(clave)
        
            if (
                nivel_normalizado.startswith("PROTOCOLO")
                or clave_normalizada.startswith("PROTOCOLO")
            ):
                continue
        
            grupo = grupos[clave]
        
            if not grupo["ejemplo"]: 
                grupo["ejemplo"] = registro
        
            grupo["nivel"] = nivel
            grupo["total"] += 1
        
            if resultado == "WIN":
                grupo["wins"] += 1
            elif resultado == "LOSS":
                grupo["losses"] += 1

            fecha = registro.get("fecha")
            
            try:
                fecha = float(fecha)
            except (TypeError, ValueError):
                fecha = 0.0
            
            if fecha > 0:
                grupo["observaciones"].append(
                    (
                        fecha,
                        resultado,
                    )
                )

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
        probabilidad = _probabilidad_suavizada(wins, losses)
        intervalo_inferior, intervalo_superior = _intervalo_probabilidad(
            wins, losses
        )

        ejemplo = datos["ejemplo"]
        estabilidad = _medir_estabilidad_temporal(
            datos.get(
                "observaciones",
                [],
            )
        )
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
            "probabilidad_ajustada": probabilidad,
            "intervalo_inferior": intervalo_inferior,
            "intervalo_superior": intervalo_superior,
            "estabilidad_disponible": (
                estabilidad.get(
                    "estabilidad_disponible",
                    False,
                )
            ),
            "muestra_estabilidad": (
                estabilidad.get(
                    "muestra_estabilidad",
                    0,
                )
            ),
            "wr_inicio": estabilidad.get(
                "wr_inicio"
            ),
            "wr_medio": estabilidad.get(
                "wr_medio"
            ),
            "wr_reciente": estabilidad.get(
                "wr_reciente"
            ),
            "dispersion_temporal": (
                estabilidad.get(
                    "dispersion_temporal"
                )
            ),
            "cambio_inicio_reciente": (
                estabilidad.get(
                    "cambio_inicio_reciente"
                )
            ),
            "bloques_mismo_lado_prior": (
                estabilidad.get(
                    "bloques_mismo_lado_prior",
                    0,
                )
            ),
            "persistencia_direccion": (
                estabilidad.get(
                    "persistencia_direccion"
                )
            ),
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
        "probabilidad_ajustada",
        "intervalo_inferior",
        "intervalo_superior",
        "estabilidad_disponible",
        "muestra_estabilidad",
        "wr_inicio",
        "wr_medio",
        "wr_reciente",
        "dispersion_temporal",
        "cambio_inicio_reciente",
        "bloques_mismo_lado_prior",
        "persistencia_direccion",
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
    print(
        "Resultados utilizados:",
        registros_validos,
        "(universo hipotético)" if incluir_hipoteticos else "(ejecutados)",
    )
    print("Registros ignorados:", registros_ignorados)

    return filas

def actualizar_aprendizaje_post_protocolo(
    resultados,
    ruta=RUTA_APRENDIZAJE,
):
    """
    C-C2 — Actualiza EXCLUSIVAMENTE memoria PROTOCOLO_*.

    REGLAS:
    - conserva intacta toda la memoria general existente;
    - elimina/reemplaza únicamente filas PROTOCOLO_*;
    - aprende solo de OPERADA_PROTOCOLO;
    - utiliza resultado REAL de la operación;
    - NO utiliza resultado_hipotetico;
    - NO modifica FAMILIA_*, PA_*, MERCADO_*, SETUP_*, etc.

    Esto permite congelar el Cerebro inicial y entrenar
    independientemente la segunda evaluación post-protocolo.
    """

    # ========================================================
    # 1. LEER Y CONGELAR MEMORIA GENERAL EXISTENTE
    # ========================================================

    filas_generales = []

    if os.path.exists(ruta):
        try:
            with open(
                ruta,
                "r",
                encoding="utf-8-sig",
                newline="",
            ) as archivo:
                reader = csv.DictReader(archivo)

                for row in reader:
                    nivel = _txt(
                        row.get("nivel")
                    )

                    clave = str(
                        row.get("clave", "")
                        or ""
                    ).strip()

                    # Las filas post-protocolo se regeneran.
                    if (
                        nivel.startswith("PROTOCOLO")
                        or clave.startswith("PROTOCOLO")
                    ):
                        continue

                    filas_generales.append(
                        dict(row)
                    )

        except (OSError, csv.Error) as error:
            raise RuntimeError(
                "No se pudo leer la memoria histórica "
                "existente antes de actualizar C-C2: "
                + str(error)
            )

    # ========================================================
    # 2. APRENDER ÚNICAMENTE OPERACIONES POST-PROTOCOLO
    # ========================================================

    grupos = defaultdict(
        lambda: {
            "total": 0,
            "wins": 0,
            "losses": 0,
            "nivel": "",
            "ejemplo": {},
        }
    )

    operaciones_protocolo = 0
    ignoradas = 0

    for registro in resultados or []:
        if not isinstance(registro, dict):
            ignoradas += 1
            continue

        # ----------------------------------------------------
        # Solo una entrada realmente ejecutada por protocolo.
        # ----------------------------------------------------

        estado_operacion = _txt(
            registro.get(
                "estado_operacion"
            )
        )

        if estado_operacion != "OPERADA_PROTOCOLO":
            continue

        # ----------------------------------------------------
        # IMPORTANTE:
        # aquí usamos resultado REAL.
        #
        # NO resultado_hipotetico.
        # ----------------------------------------------------

        resultado = _resultado_real(
            registro
        )

        if resultado not in RESULTADOS_VALIDOS:
            ignoradas += 1
            continue

        claves = _claves_protocolo(
            registro
        )

        if not claves:
            ignoradas += 1
            continue

        operaciones_protocolo += 1

        for item in claves:
            nivel = item.get(
                "nivel",
                "",
            )

            clave = item.get(
                "clave",
                "",
            )

            if not clave:
                continue

            grupo = grupos[clave]

            grupo["nivel"] = nivel

            if not grupo["ejemplo"]:
                grupo["ejemplo"] = registro

            grupo["total"] += 1

            if resultado == "WIN":
                grupo["wins"] += 1

            elif resultado == "LOSS":
                grupo["losses"] += 1

    # ========================================================
    # 3. CONSTRUIR FILAS PROTOCOLO_*
    # ========================================================

    filas_protocolo = []

    for clave, datos in grupos.items():
        total = datos["total"]
        wins = datos["wins"]
        losses = datos["losses"]

        if total <= 0:
            continue

        winrate = round(
            (wins / total) * 100,
            2,
        )

        ajuste, decision = (
            _calcular_ajuste(
                total=total,
                winrate=winrate,
            )
        )

        probabilidad = (
            _probabilidad_suavizada(
                wins,
                losses,
            )
        )

        (
            intervalo_inferior,
            intervalo_superior,
        ) = _intervalo_probabilidad(
            wins,
            losses,
        )

        ejemplo = datos["ejemplo"]

        evidencias = (
            _evidencias_por_origen(
                ejemplo
            )
        )

        filas_protocolo.append({
            "nivel": datos["nivel"],
            "clave": clave,
            "total": total,
            "wins": wins,
            "losses": losses,
            "winrate": winrate,

            "ajuste_confianza": ajuste,

            "decision_aprendizaje": (
                decision
            ),

            "confiabilidad_muestra": (
                _confiabilidad_muestra(
                    total
                )
            ),

            "probabilidad_ajustada": (
                probabilidad
            ),

            "intervalo_inferior": (
                intervalo_inferior
            ),

            "intervalo_superior": (
                intervalo_superior
            ),

            "activo": ejemplo.get(
                "activo",
                "",
            ),

            "direccion": ejemplo.get(
                "direccion",
                "",
            ),

            "familia_setup": (
                _familia_setup(
                    ejemplo
                )
            ),

            "tipo_mercado": (
                _normalizar_mercado(
                    ejemplo
                )
            ),

            "estado_tendencia": (
                _normalizar_tendencia(
                    ejemplo
                )
            ),

            "firma_pa": _firma_tokens(
                evidencias["pa"]
            ),

            "firma_mercado": (
                _firma_tokens(
                    evidencias["mercado"]
                )
            ),

            "firma_estrategia": (
                _firma_tokens(
                    evidencias["estrategia"]
                )
            ),

            "firma_evidencias_exacta": (
                ejemplo.get(
                    "firma_evidencias_exacta",
                    ejemplo.get(
                        "firma_exacta",
                        "",
                    ),
                )
            ),
        })

    filas_protocolo.sort(
        key=lambda fila: (
            _entero(
                fila.get("total"),
                0,
            ),
            _numero(
                fila.get("winrate"),
                0.0,
            ),
        ),
        reverse=True,
    )

    # ========================================================
    # 4. UNIR:
    #
    # MEMORIA GENERAL CONGELADA
    # +
    # MEMORIA PROTOCOLO NUEVA
    # ========================================================

    filas_finales = (
        filas_generales
        + filas_protocolo
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
        "probabilidad_ajustada",
        "intervalo_inferior",
        "intervalo_superior",
        "estabilidad_disponible",
        "muestra_estabilidad",
        "wr_inicio",
        "wr_medio",
        "wr_reciente",
        "dispersion_temporal",
        "cambio_inicio_reciente",
        "bloques_mismo_lado_prior",
        "persistencia_direccion",
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

    directorio = os.path.dirname(
        os.path.abspath(ruta)
    )

    if directorio:
        os.makedirs(
            directorio,
            exist_ok=True,
        )

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
        writer.writerows(
            filas_finales
        )

    print(
        "C-C2 memoria post-protocolo actualizada."
    )

    print(
        "Memoria general preservada:",
        len(filas_generales),
        "filas.",
    )

    print(
        "Memoria PROTOCOLO_* generada:",
        len(filas_protocolo),
        "filas.",
    )

    print(
        "Operaciones reales protocolo utilizadas:",
        operaciones_protocolo,
    )

    print(
        "Registros protocolo ignorados:",
        ignoradas,
    )

    return filas_protocolo
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

    assert "CONTEXTO_TECNICO" in niveles
    assert "CONTEXTO_SETUP" in niveles
    assert "CONTEXTO_PA" in niveles
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