def _txt(v):
    return str(v or "").lower().strip()


def _num(v, defecto=0):
    try:
        return float(v)
    except Exception:
        return defecto


PESOS_EVIDENCIA = {
    # Fortalezas históricamente buenas
    "pa_a_favor_call_alta": 8,
    "rechazo_vendedor_confirmado_debil_historico": 5,
    "pa_contra_call": 5,
    "pa_contra_put": 4,
    "choch_con_tendencia_debil": 3,
    "impulso_alcista_fuerte_debil_historico": 1,
    "reaccion_confirmada": 3,

    # Riesgos que NO deben castigar fuerte
    "call_resistencia_sin_ruptura": 0,
    "accion_precio_no_validada": 0,
    "ubicacion_fatiga_no_validada": 0,
    "vela_contraria_reciente": 0,

    # Riesgos moderados
    "mercado_no_validado": -4,
    "sin_contexto_claro": -3,
    "put_soporte_sin_ruptura": -3,
    "sweep_sin_confirmacion_pa": -3,
    "sweep_con_confirmacion_pa_debil": -2,

    # Riesgos malos reales
    "reaccion_sin_confirmacion_fuerte": -5,
    "reaccion_sin_confirmacion_fuerte": -8,
    "pa_a_favor_put_debil": -6,
    "pa_a_favor_call_debil": -6,
}


PESOS_ACTIVOS = {
    "cocoa-otc": 4,
    "suiusd-otc": 4,
    "injusd-otc": 4,
    "ondousd-otc": 3,
    "usdvnd-otc": 3,
    "eurgbp-otc": 2,

    "fb-otc": -5,
    "eurthb-otc": -6,
    "fartcoinusd-otc": -6,
    "cardano-otc": -3,
}


def _aplicar_peso(nombre, pesos, motivos, origen):
    clave = _txt(nombre)

    if not clave:
        return 0

    peso = PESOS_EVIDENCIA.get(clave)

    if peso is None:
        return 0

    pesos.append(peso)
    motivos.append(f"Ponderación {origen}: {nombre} ({peso:+})")
    return peso


def calcular_ponderacion_estadistica(evidencia):
    """
    Calcula ajuste probabilístico basado en evidencias históricas.

    No decide.
    No bloquea.
    Solo devuelve ajuste de confianza y motivos.
    """

    pesos = []
    motivos = []

    activo = _txt(evidencia.get("activo"))
    nivel_consenso = _txt(evidencia.get("nivel_consenso"))
    accion_precio = _txt(evidencia.get("accion_precio"))
    pa_tipo = _txt(evidencia.get("pa_tipo"))
    pa_direccion = _txt(evidencia.get("pa_direccion"))
    direccion = _txt(evidencia.get("direccion"))
    tipo_setup = _txt(evidencia.get("tipo_setup"))
    subtipo_setup = _txt(evidencia.get("subtipo_setup"))
    protocolo = _txt(evidencia.get("protocolo_sugerido"))
    riesgos_base = _txt(evidencia.get("riesgos_base"))
    fortalezas_base = _txt(evidencia.get("fortalezas_base"))
    nivel_confirmacion_ia = _txt(evidencia.get("nivel_confirmacion_ia"))
    accion_confirmacion_ia = _txt(evidencia.get("accion_confirmacion_ia"))
    score_final = _num(evidencia.get("score_final", 0))
    indice_confirmacion = _num(evidencia.get("indice_confirmacion_ia", 0))

    # =========================
    # ACTIVO
    # =========================
    if activo in PESOS_ACTIVOS:
        peso = PESOS_ACTIVOS[activo]
        pesos.append(peso)
        motivos.append(f"Ponderación activo: {activo} ({peso:+})")

    # =========================
    # CONSENSO
    # =========================
    if nivel_consenso == "alto":
        pesos.append(4)
        motivos.append("Ponderación consenso: ALTO (+4)")

    elif nivel_consenso == "premium":
        pesos.append(3)
        motivos.append("Ponderación consenso: PREMIUM (+3)")

    elif nivel_consenso == "bueno":
        pesos.append(-3)
        motivos.append("Ponderación consenso: BUENO débil histórico (-3)")

    elif nivel_consenso == "medio":
        pesos.append(-1)
        motivos.append("Ponderación consenso: MEDIO (-1)")

    # =========================
    # SCORE FINAL
    # =========================
    if score_final >= 190:
        pesos.append(1)
        motivos.append("Ponderación score_final alto (+1)")
    elif score_final < 120:
        pesos.append(-2)
        motivos.append("Ponderación score_final bajo (-2)")

    # =========================
    # CONFIRMACIÓN IA
    # =========================
    if accion_confirmacion_ia == "entrar":
        pesos.append(2)
        motivos.append("Ponderación confirmación IA: ENTRAR (+2)")

    elif accion_confirmacion_ia == "cancelar":
        pesos.append(-2)
        motivos.append("Ponderación confirmación IA: CANCELAR (-2)")

    if nivel_confirmacion_ia == "medio":
        pesos.append(2)
        motivos.append("Ponderación nivel IA MEDIO (+2)")

    elif nivel_confirmacion_ia == "alto":
        pesos.append(-2)
        motivos.append("Ponderación nivel IA ALTO débil histórico (-2)")

    if 45 <= indice_confirmacion <= 59:
        pesos.append(2)
        motivos.append("Ponderación índice IA 45-59 (+2)")

    # =========================
    # PRICE ACTION
    # =========================
    _aplicar_peso(accion_precio, pesos, motivos, "acción precio")
    _aplicar_peso(pa_tipo, pesos, motivos, "PA profesional")

    if pa_direccion in ["call", "put"] and direccion in ["call", "put"]:
        if pa_direccion == direccion:
            pesos.append(2)
            motivos.append("Ponderación PA alineado con dirección (+2)")
        else:
            clave = "pa_contra_" + direccion
            _aplicar_peso(clave, pesos, motivos, "PA contra dirección")

    # =========================
    # SETUP / PROTOCOLO
    # =========================
    if "reversion_alcista" in tipo_setup:
        pesos.append(5)
        motivos.append("Ponderación setup: reversión alcista fuerte histórica (+5)")

    if "rechazo_alcista" in tipo_setup:
        pesos.append(4)
        motivos.append("Ponderación setup: rechazo alcista (+4)")

    if "sweep_ruptura_confirmable" in subtipo_setup:
        pesos.append(2)
        motivos.append("Ponderación subtipo: sweep ruptura confirmable (+2)")

    if "choch_con_pa_a_favor" in subtipo_setup:
        pesos.append(-2)
        motivos.append("Ponderación subtipo: CHOCH con PA a favor débil histórico (-2)")

    if "protocolo_ruptura_resistencia" in protocolo:
        pesos.append(2)
        motivos.append("Ponderación protocolo ruptura resistencia (+2)")

    if "protocolo_sweep" in protocolo:
        pesos.append(-1)
        motivos.append("Ponderación protocolo sweep (-1)")

    # =========================
    # RIESGOS Y FORTALEZAS
    # =========================
    for item in riesgos_base.split("|"):
        _aplicar_peso(item, pesos, motivos, "riesgo")

    for item in fortalezas_base.split("|"):
        _aplicar_peso(item, pesos, motivos, "fortaleza")

    ajuste_total = sum(pesos)

    # límite para evitar explosiones
    if ajuste_total > 15:
        ajuste_total = 15
    elif ajuste_total < -15:
        ajuste_total = -15

    return {
        "ajuste_ponderacion": round(ajuste_total, 2),
        "motivos_ponderacion": motivos,
        "pesos_aplicados": pesos,
    }