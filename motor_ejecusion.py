
def _bool(v, default=False):
    if isinstance(v, bool):
        return v

    if v is None:
        return default

    texto = str(v).lower().strip()

    if texto in ["true", "1", "si", "sí", "yes"]:
        return True

    if texto in ["false", "0", "no", "none", "null", ""]:
        return False

    return default
def calcular_info_vela(vela):
    apertura = vela["open"]
    cierre = vela["close"]
    high = vela["max"]
    low = vela["min"]

    rango = max(high - low, 0.0000001)
    cuerpo = abs(cierre - apertura)

    mecha_superior = high - max(apertura, cierre)
    mecha_inferior = min(apertura, cierre) - low

    return {
        "apertura": apertura,
        "cierre": cierre,
        "high": high,
        "low": low,
        "rango": rango,
        "cuerpo": cuerpo,
        "cuerpo_pct": cuerpo / rango,
        "mecha_superior_pct": mecha_superior / rango,
        "mecha_inferior_pct": mecha_inferior / rango,
        "verde": cierre > apertura,
        "roja": cierre < apertura,
        "cierre_alto": cierre >= high - (rango * 0.35),
        "cierre_bajo": cierre <= low + (rango * 0.35),
    }


def confirma_rechazo_alcista(vela):
    info = calcular_info_vela(vela)

    return (
        info["verde"]
        and info["mecha_inferior_pct"] >= 0.30
        and info["cierre_alto"]
        and info["cuerpo_pct"] >= 0.18
    )


def confirma_rechazo_bajista(vela):
    info = calcular_info_vela(vela)

    return (
        info["roja"]
        and info["mecha_superior_pct"] >= 0.30
        and info["cierre_bajo"]
        and info["cuerpo_pct"] >= 0.18
    )


def confirma_impulso_alcista(vela):
    info = calcular_info_vela(vela)

    return (
        info["verde"]
        and info["cuerpo_pct"] >= 0.45
        and info["cierre_alto"]
    )


def confirma_impulso_bajista(vela):
    info = calcular_info_vela(vela)

    return (
        info["roja"]
        and info["cuerpo_pct"] >= 0.45
        and info["cierre_bajo"]
    )


def debe_entrar_directo(senal):
    tipo_setup = str(senal.get("tipo_setup", "")).upper()
    calidad_setup = str(senal.get("calidad_setup", "")).upper()
    pa_tipo = str(senal.get("pa_tipo", "")).upper()
    pa_direccion = str(senal.get("pa_direccion", "")).upper()
    direccion = str(senal.get("direccion", "")).lower()

    if tipo_setup in ["RECHAZO_BAJISTA", "RECHAZO_ALCISTA"] and calidad_setup == "PREMIUM":
        return True, "setup de rechazo premium entra directo"

    if direccion == "put" and pa_direccion == "PUT" and pa_tipo in [
        "RECHAZO_VENDEDOR_CONFIRMADO",
        "AGOTAMIENTO_ALCISTA_CONFIRMADO",
        "IMPULSO_BAJISTA_FUERTE",
    ]:
        return True, "PA profesional bajista confirma entrada directa"

    if direccion == "call" and pa_direccion == "CALL" and pa_tipo in [
        "RECHAZO_COMPRADOR_CONFIRMADO",
        "AGOTAMIENTO_BAJISTA_CONFIRMADO",
        "IMPULSO_ALCISTA_FUERTE",
    ]:
        return True, "PA profesional alcista confirma entrada directa"

    return False, "requiere confirmación de ejecución"


def buscar_entrada_confirmada(velas, idx_senal, senal, max_espera=3):
    """
    Decide el índice real de entrada.

    Retorna:
        idx_entrada, motivo

    Si idx_entrada es None:
        la operación se cancela en backtest.

    No decide la calidad general de la señal.
    Solo ejecuta o espera según el contrato del setup
    y la confirmación técnica de las velas.
    """

    # Compatibilidad temporal con señales antiguas.
    modo_legacy = str(
        senal.get("modo_entrada_setup", "DIRECTA")
    ).upper()

    # Evidencias neutrales oficiales del setup.
    riesgo_critico_setup = _bool(
        senal.get("riesgo_estructural_critico_setup"),
        default=(
            modo_legacy == "NO_OPERAR"
            or "CANCELAR" in modo_legacy
        )
    )

    requiere_ruptura_setup = _bool(
        senal.get("requiere_ruptura_setup"),
        default=(modo_legacy == "ESPERAR_RUPTURA")
    )

    requiere_confirmacion_setup = _bool(
        senal.get("requiere_confirmacion_setup"),
        default=(modo_legacy == "ESPERAR_CONFIRMACION")
    )

    tipo_setup = str(
        senal.get("tipo_setup", "")
    ).upper()

    calidad_setup = str(
        senal.get("calidad_setup", "")
    ).upper()

    direccion = str(
        senal.get("direccion", "")
    ).lower()

    # =========================
    # RIESGO ESTRUCTURAL
    # =========================
    if riesgo_critico_setup:
        return None, "setup con riesgo estructural crítico"

    # =========================
    # ENTRADA DIRECTA VALIDADA
    # =========================
    directo, razon_directo = debe_entrar_directo(senal)

    setup_sin_espera_obligatoria = (
        not requiere_ruptura_setup
        and not requiere_confirmacion_setup
    )

    if setup_sin_espera_obligatoria and directo:
        return idx_senal, razon_directo

    # No castigamos todos los setups directos.
    # Solo obligamos a confirmar los setups débiles,
    # dudosos o que expresamente necesitan espera.
    requiere_confirmacion = (
        requiere_ruptura_setup
        or requiere_confirmacion_setup
        or calidad_setup == "MEDIA"
        or tipo_setup in [
            "SWEEP_ALCISTA",
            "SWEEP_BAJISTA",
            "REVERSION_ALCISTA",
            "REVERSION_BAJISTA",
            "INDEFINIDO",
        ]
    )

    if not requiere_confirmacion:
        return idx_senal, "entrada directa permitida por setup"

    # =========================
    # BUSCAR CONFIRMACIÓN
    # =========================
    limite = min(
        idx_senal + max_espera,
        len(velas) - 2
    )

    for idx in range(idx_senal + 1, limite + 1):
        vela = velas[idx]

        if direccion == "call":
            if confirma_rechazo_alcista(vela):
                return idx, "entrada confirmada por rechazo alcista"

            if confirma_impulso_alcista(vela):
                return idx, "entrada confirmada por impulso alcista"

        if direccion == "put":
            if confirma_rechazo_bajista(vela):
                return idx, "entrada confirmada por rechazo bajista"

            if confirma_impulso_bajista(vela):
                return idx, "entrada confirmada por impulso bajista"

    return None, "cancelada: no confirmó rechazo/impulso"