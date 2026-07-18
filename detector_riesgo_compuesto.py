from normalizador import normalizar_texto, normalizar_direccion


def _contiene(valor, clave):
    """
    Comprueba si una clave normalizada existe dentro de un campo
    que puede contener varias etiquetas separadas por '|'.
    """

    valor = normalizar_texto(valor)
    clave = normalizar_texto(clave)

    if not valor or not clave:
        return False

    elementos = {
        normalizar_texto(item)
        for item in valor.split("|")
        if normalizar_texto(item)
    }

    return clave in elementos


def _registrar_riesgo(
    categoria,
    puntos,
    motivo,
    categorias_detectadas,
    motivos,
):
    """
    Registra una categoría de riesgo una sola vez.

    Evita sumar varias veces una misma contradicción cuando aparece
    representada por diferentes campos de la evidencia.
    """

    categoria = normalizar_texto(categoria)

    if not categoria:
        return 0

    if categoria in categorias_detectadas:
        return 0

    categorias_detectadas.add(categoria)
    motivos.append(motivo)

    return puntos


def evaluar_riesgo_compuesto(evidencia):
    """
    Evalúa el riesgo estructural de una señal.

    Responsabilidad:
    - identificar contradicciones del contexto actual;
    - clasificar el nivel de riesgo;
    - indicar cuándo el riesgo estructural exige bloqueo;
    - no calcular confianza histórica;
    - no decidir por sí solo toda la operación;
    - no ejecutar ni aplicar protocolos.

    La decisión operativa final pertenece a motor_decision.py.
    """

    evidencia = evidencia or {}

    direccion = normalizar_direccion(
        evidencia.get("direccion")
    )
    patron = normalizar_texto(
        evidencia.get("patron")
    )
    tipo_mercado = normalizar_texto(
        evidencia.get("tipo_mercado")
    )
    estado_tendencia = normalizar_texto(
        evidencia.get("estado_tendencia")
    )
    pa_tipo = normalizar_texto(
        evidencia.get("pa_tipo")
    )
    pa_direccion = normalizar_direccion(
        evidencia.get("pa_direccion")
    )
    accion_precio = normalizar_texto(
        evidencia.get("accion_precio")
    )
    nivel_consenso = normalizar_texto(
        evidencia.get("nivel_consenso")
    )
    base_estrategia = normalizar_texto(
        evidencia.get("base_estrategia")
    )
    riesgos_base = normalizar_texto(
        evidencia.get("riesgos_base")
    )

    riesgo = 0
    motivos = []
    categorias_detectadas = set()

    # ==========================
    # CONTEXTO INSUFICIENTE
    # ==========================
    sin_contexto_claro = (
        pa_tipo == "sin_contexto_claro"
        or _contiene(
            riesgos_base,
            "sin_contexto_claro",
        )
    )

    if sin_contexto_claro:
        riesgo += _registrar_riesgo(
            categoria="contexto_insuficiente",
            puntos=1,
            motivo="Price Action sin contexto claro.",
            categorias_detectadas=categorias_detectadas,
            motivos=motivos,
        )

    # ==========================
    # CONSENSO Y BASE
    # ==========================
    if nivel_consenso in {"bajo", "muy_bajo"}:
        riesgo += _registrar_riesgo(
            categoria="consenso_insuficiente",
            puntos=1,
            motivo="Consenso bajo o muy bajo.",
            categorias_detectadas=categorias_detectadas,
            motivos=motivos,
        )

    if base_estrategia in {"media", "debil"}:
        riesgo += _registrar_riesgo(
            categoria="base_estrategia_insuficiente",
            puntos=1,
            motivo="Base de estrategia débil o media.",
            categorias_detectadas=categorias_detectadas,
            motivos=motivos,
        )

    # ==========================
    # CONTRADICCIÓN DIRECCIONAL
    # ==========================
    tendencia_alcista = (
        tipo_mercado == "tendencia_alcista"
        or estado_tendencia
        in {"alcista_normal", "alcista_fuerte"}
    )

    tendencia_bajista = (
        tipo_mercado == "tendencia_bajista"
        or estado_tendencia
        in {"bajista_normal", "bajista_fuerte"}
    )

    contra_tendencia_declarada = _contiene(
        riesgos_base,
        "contra_tendencia",
    )

    contradiccion_tendencia = (
        direccion == "call"
        and tendencia_bajista
    ) or (
        direccion == "put"
        and tendencia_alcista
    )

    if (
        contra_tendencia_declarada
        or contradiccion_tendencia
    ):
        riesgo += _registrar_riesgo(
            categoria="contradiccion_tendencia",
            puntos=2,
            motivo=(
                "La dirección de la operación contradice "
                "la tendencia principal."
            ),
            categorias_detectadas=categorias_detectadas,
            motivos=motivos,
        )

    # ==========================
    # PRICE ACTION CONTRARIO
    # ==========================
    pa_contrario = (
        direccion in {"call", "put"}
        and pa_direccion in {"call", "put"}
        and pa_direccion != direccion
    )

    if pa_contrario:
        riesgo += _registrar_riesgo(
            categoria="price_action_contrario",
            puntos=2,
            motivo=(
                "Price Action contradice la dirección "
                "de la operación."
            ),
            categorias_detectadas=categorias_detectadas,
            motivos=motivos,
        )

    # ==========================
    # OPERACIÓN CONTRA NIVEL
    # ==========================
    call_resistencia = (
        direccion == "call"
        and (
            "call_resistencia" in accion_precio
            or _contiene(
                riesgos_base,
                "call_resistencia_sin_ruptura",
            )
        )
    )

    put_soporte = (
        direccion == "put"
        and (
            "put_soporte" in accion_precio
            or _contiene(
                riesgos_base,
                "put_soporte_sin_ruptura",
            )
        )
    )

    if call_resistencia:
        riesgo += _registrar_riesgo(
            categoria="entrada_contra_nivel",
            puntos=2,
            motivo=(
                "CALL cerca de resistencia sin ruptura "
                "confirmada."
            ),
            categorias_detectadas=categorias_detectadas,
            motivos=motivos,
        )

    if put_soporte:
        riesgo += _registrar_riesgo(
            categoria="entrada_contra_nivel",
            puntos=2,
            motivo=(
                "PUT cerca de soporte sin ruptura "
                "confirmada."
            ),
            categorias_detectadas=categorias_detectadas,
            motivos=motivos,
        )

    # ==========================
    # SWEEP SIN CONFIRMACIÓN
    # ==========================
    sweep_sin_confirmacion = _contiene(
        riesgos_base,
        "sweep_sin_confirmacion_pa",
    )

    if sweep_sin_confirmacion:
        riesgo += _registrar_riesgo(
            categoria="sweep_sin_confirmacion",
            puntos=2,
            motivo=(
                "Liquidity sweep sin confirmación "
                "de Price Action."
            ),
            categorias_detectadas=categorias_detectadas,
            motivos=motivos,
        )

    # ==========================
    # REACCIÓN SIN CONFIRMACIÓN
    # ==========================
    reaccion_sin_confirmacion = (
        _contiene(
            riesgos_base,
            "reaccion_sin_confirmacion_fuerte",
        )
        or _contiene(
            riesgos_base,
            "accion_precio_no_validada",
        )
    )

    if reaccion_sin_confirmacion:
        riesgo += _registrar_riesgo(
            categoria="reaccion_no_confirmada",
            puntos=2,
            motivo=(
                "La reacción del precio no tiene "
                "confirmación suficiente."
            ),
            categorias_detectadas=categorias_detectadas,
            motivos=motivos,
        )

    # ==========================
    # MERCADO NO VALIDADO
    # ==========================
    if _contiene(
        riesgos_base,
        "mercado_no_validado",
    ):
        riesgo += _registrar_riesgo(
            categoria="mercado_no_validado",
            puntos=1,
            motivo="El contexto de mercado no está validado.",
            categorias_detectadas=categorias_detectadas,
            motivos=motivos,
        )

    # ==========================
    # PATRÓN CONTRA CONTEXTO
    # ==========================
    sweep_bajista_contra_alcista = (
        direccion == "put"
        and "liquidity_sweep_bajista" in patron
        and tendencia_alcista
    )

    sweep_alcista_contra_bajista = (
        direccion == "call"
        and "liquidity_sweep_alcista" in patron
        and tendencia_bajista
    )

    if (
        sweep_bajista_contra_alcista
        or sweep_alcista_contra_bajista
    ):
        # No suma nuevamente contradicción de tendencia.
        # Solo se registra como diagnóstico adicional.
        if "contradiccion_tendencia" not in categorias_detectadas:
            riesgo += _registrar_riesgo(
                categoria="contradiccion_tendencia",
                puntos=2,
                motivo=(
                    "Liquidity sweep contrario a la "
                    "tendencia principal."
                ),
                categorias_detectadas=categorias_detectadas,
                motivos=motivos,
            )

    # ==========================
    # CLASIFICACIÓN
    # ==========================
    if riesgo >= 7:
        nivel = "EXTREMO"
        bloquear = True

    elif riesgo >= 5:
        nivel = "ALTO"
        bloquear = True

    elif riesgo >= 3:
        nivel = "MEDIO"
        bloquear = False

    else:
        nivel = "BAJO"
        bloquear = False

    return {
        "riesgo_puntos": riesgo,
        "riesgo_nivel": nivel,
        "bloquear_por_riesgo": bloquear,
        "motivos_riesgo": motivos,
        "categorias_riesgo": sorted(
            categorias_detectadas
        ),
    }


def probar_detector_riesgo():
    """
    Pruebas mínimas para comprobar:

    - simetría entre CALL y PUT;
    - deduplicación de contradicciones;
    - bloqueo de riesgo alto o extremo;
    - ausencia de reglas históricas por dirección.
    """

    ejemplos = [
        {
            "nombre": "PUT contra tendencia y PA alcistas",
            "evidencia": {
                "direccion": "put",
                "patron": "liquidity sweep bajista",
                "tipo_mercado": "TENDENCIA_ALCISTA",
                "estado_tendencia": "ALCISTA_FUERTE",
                "pa_tipo": "SIN_CONTEXTO_CLARO",
                "pa_direccion": "CALL",
                "nivel_consenso": "MUY_BAJO",
                "base_estrategia": "DEBIL",
                "riesgos_base": (
                    "SIN_CONTEXTO_CLARO|"
                    "CONTRA_TENDENCIA|"
                    "SWEEP_SIN_CONFIRMACION_PA"
                ),
            },
        },
        {
            "nombre": "CALL contra tendencia y PA bajistas",
            "evidencia": {
                "direccion": "call",
                "patron": "liquidity sweep alcista",
                "tipo_mercado": "TENDENCIA_BAJISTA",
                "estado_tendencia": "BAJISTA_FUERTE",
                "pa_tipo": "SIN_CONTEXTO_CLARO",
                "pa_direccion": "PUT",
                "nivel_consenso": "MUY_BAJO",
                "base_estrategia": "DEBIL",
                "riesgos_base": (
                    "SIN_CONTEXTO_CLARO|"
                    "CONTRA_TENDENCIA|"
                    "SWEEP_SIN_CONFIRMACION_PA"
                ),
            },
        },
        {
            "nombre": "CALL alineado sin riesgo estructural",
            "evidencia": {
                "direccion": "call",
                "patron": "choch alcista",
                "tipo_mercado": "TENDENCIA_ALCISTA",
                "estado_tendencia": "ALCISTA_NORMAL",
                "pa_tipo": "IMPULSO_ALCISTA_FUERTE",
                "pa_direccion": "CALL",
                "nivel_consenso": "ALTO",
                "base_estrategia": "FUERTE",
                "riesgos_base": "",
            },
        },
    ]

    print(
        "\n===== PRUEBA DETECTOR RIESGO COMPUESTO BOOTIQ ====="
    )

    for ejemplo in ejemplos:
        resultado = evaluar_riesgo_compuesto(
            ejemplo["evidencia"]
        )

        print(f"\n--- {ejemplo['nombre']} ---")
        print(
            "Puntos:",
            resultado["riesgo_puntos"],
        )
        print(
            "Nivel:",
            resultado["riesgo_nivel"],
        )
        print(
            "Bloquear:",
            resultado["bloquear_por_riesgo"],
        )
        print(
            "Categorías:",
            resultado["categorias_riesgo"],
        )

        for motivo in resultado["motivos_riesgo"]:
            print("-", motivo)


if __name__ == "__main__":
    probar_detector_riesgo()