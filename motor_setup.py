# motor_setup.py

def _txt(v):
    return str(v or "").upper().strip()


def _num(v, default=0):
    try:
        return float(v or default)
    except Exception:
        return default


def _contiene(texto, *palabras):
    texto = _txt(texto)
    return any(p.upper() in texto for p in palabras)


def _leer_lista(valor):
    if not valor:
        return []
    if isinstance(valor, list):
        return [str(x).upper().strip() for x in valor if str(x).strip()]
    return [x.strip().upper() for x in str(valor).split("|") if x.strip()]


def clasificar_setup(senal):
    """
    Fase 5.4
    Clasifica el setup sin bloquear ni ejecutar.
    Corrige degradación contextual para CALL cerca de resistencia sin ruptura.
    """

    tipo_setup = _txt(senal.get("tipo_setup", "INDEFINIDO"))
    patron = _txt(senal.get("patron", ""))
    direccion = _txt(senal.get("direccion", ""))
    accion_precio = _txt(senal.get("accion_precio", ""))
    pa_tipo = _txt(senal.get("pa_tipo", ""))
    pa_direccion = _txt(senal.get("pa_direccion", ""))
    mercado = _txt(senal.get("tipo_mercado", ""))
    calidad_mercado = _txt(senal.get("calidad_mercado", ""))
    tendencia = _txt(senal.get("estado_tendencia", ""))
    base_estrategia = _txt(senal.get("base_estrategia", ""))
    calidad_setup = _txt(senal.get("calidad_setup", ""))
    nivel_consenso = _txt(senal.get("nivel_consenso", ""))

    score_final = _num(senal.get("score_final"))
    balance_setup = _num(senal.get("balance_setup"))

    fortalezas = _leer_lista(senal.get("fortalezas_base", ""))
    riesgos = _leer_lista(senal.get("riesgos_base", ""))

    es_call_resistencia_sin_ruptura = (
        direccion == "CALL"
        and "CALL_RESISTENCIA_CERCA_SIN_RUPTURA" in accion_precio
    )

    es_put_soporte_sin_ruptura = (
        direccion == "PUT"
        and "PUT_SOPORTE_CERCA_SIN_RUPTURA" in accion_precio
    )

    texto_total = " ".join([
        tipo_setup,
        patron,
        accion_precio,
        pa_tipo,
        mercado,
        tendencia,
        " ".join(fortalezas),
        " ".join(riesgos),
    ])

    familia_setup = "INDEFINIDA"
    subtipo_setup = "INDEFINIDO"
    protocolo_sugerido = "PROTOCOLO_GENERICO"
    nivel_setup = "MEDIO"
    estado_setup = "INMADURO"
    confianza_setup = 50
    razones = []

    # ==========================
    # SWEEP
    # ==========================

    if _contiene(texto_total, "SWEEP", "LIQUIDITY", "LIQUIDEZ"):
        familia_setup = "REVERSIÓN"
        protocolo_sugerido = "PROTOCOLO_SWEEP"

        if _contiene(pa_tipo, "AGOTAMIENTO", "RECHAZO") or _contiene(
            " ".join(fortalezas),
            "SWEEP_CON_RECHAZO_AGOTAMIENTO"
        ):
            subtipo_setup = "SWEEP_CON_RECHAZO_AGOTAMIENTO"
            nivel_setup = "ALTO"
            estado_setup = "MADURO"
            confianza_setup = 78
            razones.append("Sweep con rechazo/agotamiento confirmado.")

        elif _contiene(texto_total, "RUPTURA"):
            subtipo_setup = "SWEEP_RUPTURA_CONFIRMABLE"
            nivel_setup = "MEDIO_ALTO"
            estado_setup = "CONFIRMABLE"
            confianza_setup = 68
            razones.append("Sweep necesita confirmación por ruptura.")

        else:
            subtipo_setup = "SWEEP_SIMPLE"
            nivel_setup = "MEDIO"
            estado_setup = "PENDIENTE_CONFIRMACION"
            confianza_setup = 58
            razones.append("Sweep sin confirmación fuerte.")

    # ==========================
    # CHOCH
    # ==========================

    elif _contiene(texto_total, "CHOCH", "CAMBIO_ESTRUCTURA"):
        familia_setup = "REVERSIÓN_ESTRUCTURAL"
        protocolo_sugerido = "PROTOCOLO_CHOCH"

        if _contiene(" ".join(fortalezas), "CHOCH_CON_PA_A_FAVOR") or pa_direccion == direccion:
            subtipo_setup = "CHOCH_CON_PA_A_FAVOR"
            nivel_setup = "ALTO"
            estado_setup = "MADURO"
            confianza_setup = 82
            razones.append("CHOCH con Price Action alineado.")

        elif _contiene(tendencia, "DEBIL", "DÉBIL"):
            subtipo_setup = "CHOCH_TENDENCIA_DEBIL"
            nivel_setup = "MEDIO_ALTO"
            estado_setup = "CONFIRMABLE"
            confianza_setup = 70
            razones.append("CHOCH en tendencia débil; requiere ruptura/impulso.")

        else:
            subtipo_setup = "CHOCH_SIMPLE"
            nivel_setup = "MEDIO_ALTO"
            estado_setup = "CONFIRMABLE"
            confianza_setup = 72
            razones.append("CHOCH válido con confirmación pendiente.")

    # ==========================
    # PULLBACK
    # ==========================

    elif _contiene(texto_total, "PULLBACK", "EMA", "RETROCESO"):
        familia_setup = "CONTINUACIÓN"
        protocolo_sugerido = "PROTOCOLO_PULLBACK"

        if _contiene(" ".join(riesgos), "PULLBACK_TENDENCIA_INSUFICIENTE"):
            subtipo_setup = "PULLBACK_TENDENCIA_INSUFICIENTE"
            nivel_setup = "BAJO"
            estado_setup = "PELIGROSO"
            confianza_setup = 38
            razones.append("Pullback con tendencia insuficiente.")

        elif _contiene(tendencia, "AGOTADA"):
            subtipo_setup = "PULLBACK_TENDENCIA_AGOTADA"
            nivel_setup = "BAJO"
            estado_setup = "PELIGROSO"
            confianza_setup = 35
            razones.append("Pullback en tendencia agotada.")

        elif calidad_mercado == "LIMPIO" and _contiene(" ".join(fortalezas), "TENDENCIA_A_FAVOR"):
            subtipo_setup = "PULLBACK_CONTINUACION_LIMPIA"
            nivel_setup = "ALTO"
            estado_setup = "MADURO"
            confianza_setup = 76
            razones.append("Pullback con mercado limpio y tendencia a favor.")

        elif balance_setup >= 2 and nivel_consenso in ["PREMIUM", "ALTO", "MEDIO"]:
            subtipo_setup = "PULLBACK_BALANCE_POSITIVO"
            nivel_setup = "MEDIO_ALTO"
            estado_setup = "CONFIRMABLE"
            confianza_setup = 66
            razones.append("Pullback con balance positivo, requiere confirmación.")

        else:
            subtipo_setup = "PULLBACK_GENERICO"
            nivel_setup = "MEDIO_BAJO"
            estado_setup = "INMADURO"
            confianza_setup = 48
            razones.append("Pullback genérico; no debe entrar directo.")

    # ==========================
    # REACCIÓN EN ZONA
    # ==========================

    elif _contiene(texto_total, "SOPORTE", "RESISTENCIA", "ZONA", "RECHAZO"):
        familia_setup = "REACCIÓN_ZONA"
        protocolo_sugerido = "PROTOCOLO_REACCION_ZONA"

        if _contiene(pa_tipo, "RECHAZO") and pa_direccion == direccion:
            subtipo_setup = "ZONA_RECHAZO_CONFIRMADO"
            nivel_setup = "ALTO"
            estado_setup = "MADURO"
            confianza_setup = 74
            razones.append("Reacción en zona con rechazo confirmado.")

        elif _contiene(accion_precio, "SIN_RUPTURA"):
            subtipo_setup = "ZONA_SIN_RUPTURA"
            nivel_setup = "MEDIO"
            estado_setup = "PENDIENTE_CONFIRMACION"
            confianza_setup = 58
            razones.append("Zona cercana sin ruptura; esperar rechazo o ruptura.")

        else:
            subtipo_setup = "ZONA_GENERICA"
            nivel_setup = "MEDIO"
            estado_setup = "CONFIRMABLE"
            confianza_setup = 55
            razones.append("Reacción en zona genérica.")

    # ==========================
    # CONTINUACIÓN
    # ==========================

    elif _contiene(texto_total, "CONTINUACION", "CONTINUACIÓN", "TENDENCIA"):
        familia_setup = "CONTINUACIÓN"
        protocolo_sugerido = "PROTOCOLO_CONTINUACION"

        if _contiene(tendencia, "FUERTE") and _contiene(
            " ".join(fortalezas),
            "CONTINUACION_CON_TENDENCIA_FUERTE"
        ):
            subtipo_setup = "CONTINUACION_TENDENCIA_FUERTE"
            nivel_setup = "MEDIO_ALTO"
            estado_setup = "CONFIRMABLE"
            confianza_setup = 68
            razones.append("Continuación con tendencia fuerte.")

        else:
            subtipo_setup = "CONTINUACION_SIMPLE"
            nivel_setup = "MEDIO"
            estado_setup = "CONFIRMABLE"
            confianza_setup = 56
            razones.append("Continuación simple, requiere impulso.")

    # ==========================
    # INDEFINIDO
    # ==========================

    else:
        familia_setup = "INDEFINIDA"
        subtipo_setup = "INDEFINIDO"
        protocolo_sugerido = "PROTOCOLO_GENERICO"
        nivel_setup = "BAJO"
        estado_setup = "INMADURO"
        confianza_setup = 40
        razones.append("Setup no clasificado con precisión.")

    # ==========================
    # AJUSTES GENERALES
    # ==========================

    if calidad_setup == "PREMIUM":
        confianza_setup += 6
    elif calidad_setup == "BUENA":
        confianza_setup += 3
    elif calidad_setup == "MEDIA":
        confianza_setup -= 2

    if base_estrategia == "FUERTE":
        confianza_setup += 4
    elif base_estrategia == "DEBIL":
        confianza_setup -= 3

    if score_final >= 200:
        confianza_setup += 5
    elif score_final < 120:
        confianza_setup -= 5

    # ==========================
    # AJUSTE CONTEXTUAL FASE 5.4
    # ==========================
    # El log mostró que CALL cerca de resistencia sin ruptura
    # está perdiendo fuerte. No se bloquea aquí: se degrada.
    # El protocolo deberá exigir ruptura real.

    if es_call_resistencia_sin_ruptura:
        confianza_setup -= 18
        nivel_setup = "MEDIO_BAJO"
        estado_setup = "PENDIENTE_CONFIRMACION"
        protocolo_sugerido = "PROTOCOLO_RUPTURA_RESISTENCIA"
        razones.append(
            "CALL cerca de resistencia sin ruptura: degradado a pendiente de confirmación."
        )

    # PUT cerca de soporte sin ruptura no se castiga igual.
    # En el log reciente está funcionando mejor que CALL en resistencia.

    if es_put_soporte_sin_ruptura:
        confianza_setup += 4
        razones.append(
            "PUT cerca de soporte sin ruptura mantiene buen rendimiento reciente."
        )

    confianza_setup = max(0, min(100, round(confianza_setup, 2)))

    return {
        "familia_setup": familia_setup,
        "subtipo_setup": subtipo_setup,
        "protocolo_sugerido": protocolo_sugerido,
        "nivel_setup": nivel_setup,
        "estado_setup": estado_setup,
        "confianza_setup": confianza_setup,
        "razones_clasificador_setup": " | ".join(razones),
    }


def enriquecer_senal_con_setup(senal):
    """
    Devuelve la misma señal enriquecida.
    No elimina campos anteriores.
    """
    datos_setup = clasificar_setup(senal)
    senal.update(datos_setup)
    return senal