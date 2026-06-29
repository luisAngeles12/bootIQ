from normalizador import normalizar_texto, normalizar_direccion


def evaluar_riesgo_compuesto(evidencia):
    """
    Evalúa riesgo compuesto de una señal.
    No decide por sí solo toda la operación.
    Solo clasifica el riesgo contextual.
    """

    direccion = normalizar_direccion(evidencia.get("direccion"))
    patron = normalizar_texto(evidencia.get("patron"))
    tipo_mercado = normalizar_texto(evidencia.get("tipo_mercado"))
    estado_tendencia = normalizar_texto(evidencia.get("estado_tendencia"))
    pa_tipo = normalizar_texto(evidencia.get("pa_tipo"))
    pa_direccion = normalizar_texto(evidencia.get("pa_direccion"))
    accion_precio = normalizar_texto(evidencia.get("accion_precio"))
    nivel_consenso = normalizar_texto(evidencia.get("nivel_consenso"))
    base_estrategia = normalizar_texto(evidencia.get("base_estrategia"))
    riesgos_base = normalizar_texto(evidencia.get("riesgos_base"))

    riesgo = 0
    motivos = []

    # ==========================
    # RIESGOS GENERALES
    # ==========================
    if nivel_consenso in ["bajo", "muy_bajo"]:
        riesgo += 1
        motivos.append("Consenso bajo o muy bajo.")

    if base_estrategia in ["media", "debil"]:
        riesgo += 1
        motivos.append("Base de estrategia débil o media.")

    if "sin_contexto_claro" in riesgos_base or pa_tipo == "sin_contexto_claro":
        riesgo += 1
        motivos.append("Price Action sin contexto claro.")

    if "contra_tendencia" in riesgos_base:
        riesgo += 1
        motivos.append("Operación contra tendencia.")

    # ==========================
    # RIESGOS CALL
    # ==========================
    if direccion == "call":
        if "pullback_alcista" in patron:
            riesgo += 2
            motivos.append("Pullback alcista históricamente débil.")

        if "choch_alcista" in patron:
            riesgo += 1
            motivos.append("CHOCH alcista con bajo rendimiento.")

        if tipo_mercado == "tendencia_alcista" and estado_tendencia == "alcista_normal":
            riesgo += 1
            motivos.append("CALL en ALCISTA_NORMAL con bajo rendimiento.")

        if pa_direccion == "call":
            riesgo += 1
            motivos.append("PA CALL ha sido débil estadísticamente.")

        if "impulso_alcista_fuerte" in pa_tipo:
            riesgo += 1
            motivos.append("Impulso alcista fuerte ha fallado en validación.")

        if "call_resistencia" in accion_precio or "call_resistencia_sin_ruptura" in riesgos_base:
            riesgo += 1
            motivos.append("CALL cerca de resistencia sin ruptura.")

    # ==========================
    # RIESGOS PUT
    # ==========================
    if direccion == "put":
        if "liquidity_sweep_bajista" in patron and tipo_mercado == "tendencia_alcista":
            riesgo += 2
            motivos.append("Liquidity sweep bajista contra tendencia alcista.")

        if estado_tendencia in ["alcista_normal", "alcista_fuerte"]:
            riesgo += 1
            motivos.append("PUT contra estado de tendencia alcista.")

        if pa_direccion == "call":
            riesgo += 2
            motivos.append("PA contradice operación PUT.")

        if "sweep_sin_confirmacion_pa" in riesgos_base:
            riesgo += 1
            motivos.append("Sweep sin confirmación de Price Action.")

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
    }



if __name__ == "__main__":
    ejemplo = {
        "direccion": "put",
        "patron": "liquidity sweep bajista",
        "tipo_mercado": "TENDENCIA_ALCISTA",
        "estado_tendencia": "ALCISTA_FUERTE",
        "pa_tipo": "SIN_CONTEXTO_CLARO",
        "pa_direccion": "NEUTRA",
        "nivel_consenso": "MUY_BAJO",
        "base_estrategia": "DEBIL",
        "riesgos_base": "SIN_CONTEXTO_CLARO|CONTRA_TENDENCIA|SWEEP_SIN_CONFIRMACION_PA",
    }

    print(evaluar_riesgo_compuesto(ejemplo))