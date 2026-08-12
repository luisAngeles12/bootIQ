# motor_candidatos.py


def _num(valor, default=0.0):
    try:
        return float(
            valor if valor is not None else default
        )
    except (TypeError, ValueError):
        return float(default)


def _decision_oficial(senal):
    """
    Obtiene únicamente la decisión ya tomada por el Cerebro Único.

    Este módulo NO decide.
    Solo usa la decisión como parte del ordenamiento.
    """

    return str(
        senal.get(
            "cerebro_unico_decision",
            senal.get(
                "decision_unificada_accion",
                "NO_OPERAR",
            ),
        )
        or "NO_OPERAR"
    ).upper().strip()


def clave_ranking_v3(senal):
    """
    Ranking oficial de candidatas BootIQ V3.

    IMPORTANTE:
    - no aprende;
    - no recalcula probabilidad;
    - no cambia la decisión del Cerebro;
    - no bloquea;
    - no ejecuta operaciones.

    Solo ordena señales YA evaluadas por el Cerebro Único.

    Prioridad:
    1. señal autorizada por el Cerebro;
    2. probabilidad histórica V3;
    3. tamaño de muestra histórica;
    4. score/puntaje solo como desempate legacy.
    """

    if not isinstance(senal, dict):
        return (
            0,
            0.0,
            0,
            0.0,
            0.0,
            0.0,
        )

    decision = _decision_oficial(senal)

    prioridad_decision = {
        "OPERAR": 2,
        "OPERAR_CON_PROTOCOLO": 1,
        "NO_OPERAR": 0,
        "ERROR": 0,
    }.get(
        decision,
        0,
    )

    probabilidad = _num(
        senal.get(
            "probabilidad_v3",
            senal.get(
                "probabilidad_estimada",
                0,
            ),
        ),
        0,
    )

    try:
        muestra = int(
            float(
                senal.get(
                    "muestra_probabilidad",
                    0,
                )
                or 0
            )
        )
    except (TypeError, ValueError):
        muestra = 0

    score_final = _num(
        senal.get("score_final", 0),
        0,
    )

    puntaje = _num(
        senal.get("puntaje", 0),
        0,
    )

    prioridad_original = _num(
        senal.get("prioridad", 0),
        0,
    )

    return (
        prioridad_decision,
        probabilidad,
        muestra,
        score_final,
        puntaje,
        prioridad_original,
    )


def ordenar_candidatas_v3(candidatas):
    """
    Devuelve las candidatas ordenadas de mejor a peor.

    No modifica las señales originales.
    """

    if not isinstance(candidatas, list):
        return []

    validas = [
        senal
        for senal in candidatas
        if isinstance(senal, dict)
    ]

    return sorted(
        validas,
        key=clave_ranking_v3,
        reverse=True,
    )


def seleccionar_mejor_candidata_v3(candidatas):
    """
    Selecciona la mejor candidata ya evaluada.

    Si ninguna es válida devuelve None.
    """

    ordenadas = ordenar_candidatas_v3(
        candidatas
    )

    if not ordenadas:
        return None

    return ordenadas[0]


def crear_candidato(
    activo,
    direccion,
    estrategia,
    rsi,
    evidencias=None,
    ctx=None,
):
    """
    Candidato BootIQ.

    No es una señal.
    No decide operación.
    Solo describe una oportunidad detectada.
    """

    if evidencias is None:
        evidencias = []

    return {
        "activo": activo,
        "direccion": direccion,
        "estrategia": estrategia,
        "patron": estrategia,
        "rsi": round(rsi, 2),
        "evidencias": evidencias,
        "ctx_ref": {
            "accion_precio": (
                ctx.get(
                    "accion_precio",
                    "SIN_DATOS",
                )
                if ctx
                else "SIN_DATOS"
            ),
            "pa_tipo": (
                ctx.get(
                    "pa_tipo",
                    "SIN_CONTEXTO_CLARO",
                )
                if ctx
                else "SIN_CONTEXTO_CLARO"
            ),
            "pa_direccion": (
                ctx.get(
                    "pa_direccion",
                    "NEUTRA",
                )
                if ctx
                else "NEUTRA"
            ),
            "pa_fuerza": (
                ctx.get("pa_fuerza", 0)
                if ctx
                else 0
            ),
            "tipo_mercado": (
                ctx.get(
                    "tipo_mercado",
                    "INDEFINIDO",
                )
                if ctx
                else "INDEFINIDO"
            ),
            "calidad_mercado": (
                ctx.get(
                    "calidad_mercado",
                    "SIN_DATOS",
                )
                if ctx
                else "SIN_DATOS"
            ),
            "estado_tendencia": (
                ctx.get(
                    "estado_tendencia",
                    "INDEFINIDA",
                )
                if ctx
                else "INDEFINIDA"
            ),
            "fuerza_tendencia": (
                ctx.get(
                    "fuerza_tendencia",
                    0,
                )
                if ctx
                else 0
            ),
            "direccion_tendencia": (
                ctx.get(
                    "direccion_tendencia",
                    "INDEFINIDA",
                )
                if ctx
                else "INDEFINIDA"
            ),
            "posicion_rango": (
                ctx.get(
                    "posicion_rango",
                    0.5,
                )
                if ctx
                else 0.5
            ),
        },
    }


def candidato_a_senal(
    candidato,
    puntaje_base=14,
    prioridad_base=2,
):
    """
    Conversión de candidato a señal.

    Compatibilidad con el flujo existente.
    """

    evidencias = candidato.get(
        "evidencias",
        [],
    )

    return {
        "activo": candidato.get(
            "activo",
            "",
        ),
        "direccion": candidato.get(
            "direccion",
            "",
        ),
        "puntaje": puntaje_base,
        "patron": candidato.get(
            "patron",
            "",
        ),
        "rsi": candidato.get(
            "rsi",
            0,
        ),
        "razon": ", ".join(
            str(x)
            for x in evidencias
        ),
        "calidad": "B",
        "prioridad": prioridad_base,
    }