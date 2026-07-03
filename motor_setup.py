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


def _ajustar(confianza, valor, razones, motivo):
    confianza += valor
    signo = "+" if valor >= 0 else ""
    razones.append(f"{signo}{valor}: {motivo}")
    return confianza


def _nivel_estado_desde_confianza(confianza):
    if confianza >= 78:
        return "ALTO", "MADURO"
    if confianza >= 65:
        return "MEDIO_ALTO", "CONFIRMABLE"
    if confianza >= 52:
        return "MEDIO", "PENDIENTE_CONFIRMACION"
    if confianza >= 42:
        return "MEDIO_BAJO", "INMADURO"
    return "BAJO", "PELIGROSO"


def clasificar_setup(senal):
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
    nivel_consenso = _txt(senal.get("nivel_consenso", ""))

    score_final = _num(senal.get("score_final"))
    balance_setup = _num(senal.get("balance_setup"))

    fortalezas = _leer_lista(senal.get("fortalezas_base", ""))
    riesgos = _leer_lista(senal.get("riesgos_base", ""))

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
    confianza_setup = 50
    razones = ["Base neutral: 50"]

    # ==========================
    # CLASIFICACIÓN BASE
    # ==========================

    if _contiene(texto_total, "SWEEP", "LIQUIDITY", "LIQUIDEZ"):
        familia_setup = "REVERSIÓN"
        protocolo_sugerido = "PROTOCOLO_SWEEP"

        if _contiene(pa_tipo, "AGOTAMIENTO", "RECHAZO") or _contiene(
            " ".join(fortalezas),
            "SWEEP_CON_RECHAZO_AGOTAMIENTO"
        ):
            subtipo_setup = "SWEEP_CON_RECHAZO_AGOTAMIENTO"
            confianza_setup = _ajustar(confianza_setup, 10, razones, "Sweep con rechazo/agotamiento")
        elif _contiene(texto_total, "RUPTURA"):
            subtipo_setup = "SWEEP_RUPTURA_CONFIRMABLE"
            confianza_setup = _ajustar(confianza_setup, 5, razones, "Sweep con ruptura confirmable")
        else:
            subtipo_setup = "SWEEP_SIMPLE"
            confianza_setup = _ajustar(confianza_setup, 0, razones, "Sweep simple")

    elif _contiene(texto_total, "CHOCH", "CAMBIO_ESTRUCTURA"):
        familia_setup = "REVERSIÓN_ESTRUCTURAL"
        protocolo_sugerido = "PROTOCOLO_CHOCH"

        if _contiene(" ".join(fortalezas), "CHOCH_CON_PA_A_FAVOR") or pa_direccion == direccion:
            subtipo_setup = "CHOCH_CON_PA_A_FAVOR"
            confianza_setup = _ajustar(confianza_setup, 4, razones, "CHOCH con PA alineado")
        elif _contiene(tendencia, "DEBIL", "DÉBIL"):
            subtipo_setup = "CHOCH_TENDENCIA_DEBIL"
            confianza_setup = _ajustar(confianza_setup, -8, razones, "CHOCH en tendencia débil")
        else:
            subtipo_setup = "CHOCH_SIMPLE"
            confianza_setup = _ajustar(confianza_setup, 2, razones, "CHOCH simple")

    elif _contiene(texto_total, "PULLBACK", "EMA", "RETROCESO"):
        familia_setup = "CONTINUACIÓN"
        protocolo_sugerido = "PROTOCOLO_PULLBACK"

        if _contiene(" ".join(riesgos), "PULLBACK_TENDENCIA_INSUFICIENTE"):
            subtipo_setup = "PULLBACK_TENDENCIA_INSUFICIENTE"
            confianza_setup = _ajustar(confianza_setup, -6, razones, "Pullback con tendencia insuficiente")
        elif _contiene(tendencia, "AGOTADA"):
            subtipo_setup = "PULLBACK_TENDENCIA_AGOTADA"
            confianza_setup = _ajustar(confianza_setup, -12, razones, "Pullback con tendencia agotada")
        elif calidad_mercado == "LIMPIO" and _contiene(" ".join(fortalezas), "TENDENCIA_A_FAVOR"):
            subtipo_setup = "PULLBACK_CONTINUACION_LIMPIA"
            confianza_setup = _ajustar(confianza_setup, 4, razones, "Pullback limpio con tendencia")
        elif balance_setup >= 2 and nivel_consenso in ["PREMIUM", "ALTO", "MEDIO"]:
            subtipo_setup = "PULLBACK_BALANCE_POSITIVO"
            confianza_setup = _ajustar(confianza_setup, 3, razones, "Pullback con balance positivo")
        else:
            subtipo_setup = "PULLBACK_GENERICO"
            confianza_setup = _ajustar(confianza_setup, -2, razones, "Pullback genérico")

    elif _contiene(texto_total, "SOPORTE", "RESISTENCIA", "ZONA", "RECHAZO"):
        familia_setup = "REACCIÓN_ZONA"
        protocolo_sugerido = "PROTOCOLO_REACCION_ZONA"

        if _contiene(pa_tipo, "RECHAZO") and pa_direccion == direccion:
            subtipo_setup = "ZONA_RECHAZO_CONFIRMADO"
            confianza_setup = _ajustar(confianza_setup, 6, razones, "Zona con rechazo confirmado")
        elif _contiene(accion_precio, "SIN_RUPTURA"):
            subtipo_setup = "ZONA_SIN_RUPTURA"
            confianza_setup = _ajustar(confianza_setup, -4, razones, "Zona sin ruptura")
        else:
            subtipo_setup = "ZONA_GENERICA"
            confianza_setup = _ajustar(confianza_setup, 0, razones, "Zona genérica")

    elif _contiene(texto_total, "CONTINUACION", "CONTINUACIÓN", "TENDENCIA"):
        familia_setup = "CONTINUACIÓN"
        protocolo_sugerido = "PROTOCOLO_CONTINUACION"

        if _contiene(tendencia, "FUERTE") and _contiene(
            " ".join(fortalezas),
            "CONTINUACION_CON_TENDENCIA_FUERTE"
        ):
            subtipo_setup = "CONTINUACION_TENDENCIA_FUERTE"
            confianza_setup = _ajustar(confianza_setup, 4, razones, "Continuación con tendencia fuerte")
        else:
            subtipo_setup = "CONTINUACION_SIMPLE"
            confianza_setup = _ajustar(confianza_setup, -2, razones, "Continuación simple")

    else:
        confianza_setup = _ajustar(confianza_setup, -10, razones, "Setup indefinido")

    # ==========================
    # AJUSTES POR EVIDENCIA
    # ==========================

    if pa_direccion == direccion:
        confianza_setup = _ajustar(confianza_setup, 6, razones, "PA alineado")
    elif pa_direccion and pa_direccion not in ["NEUTRA", "SIN_DATO"] and pa_direccion != direccion:
        confianza_setup = _ajustar(confianza_setup, -12, razones, "PA en contra")

    if _contiene(pa_tipo, "IMPULSO", "RECHAZO") and pa_direccion == direccion:
        confianza_setup = _ajustar(confianza_setup, 5, razones, "Impulso/rechazo a favor")

    if nivel_consenso == "PREMIUM":
        confianza_setup = _ajustar(confianza_setup, 4, razones, "Consenso premium")
    elif nivel_consenso == "ALTO":
        confianza_setup = _ajustar(confianza_setup, 3, razones, "Consenso alto")
    elif nivel_consenso in ["BAJO", "MUY_BAJO"]:
        confianza_setup = _ajustar(confianza_setup, -3, razones, "Consenso bajo")

    if base_estrategia == "FUERTE":
        confianza_setup = _ajustar(confianza_setup, 3, razones, "Base estrategia fuerte")
    elif base_estrategia == "DEBIL":
        confianza_setup = _ajustar(confianza_setup, -4, razones, "Base estrategia débil")

    if score_final >= 200:
        confianza_setup = _ajustar(confianza_setup, 3, razones, "Score final alto")
    elif score_final and score_final < 120:
        confianza_setup = _ajustar(confianza_setup, -4, razones, "Score final bajo")

    if calidad_mercado == "SUCIO":
        confianza_setup = _ajustar(confianza_setup, -10, razones, "Mercado sucio")

    if "CALL_RESISTENCIA_CERCA_SIN_RUPTURA" in accion_precio and direccion == "CALL":
        protocolo_sugerido = "PROTOCOLO_RUPTURA_RESISTENCIA"
        confianza_setup = _ajustar(confianza_setup, -14, razones, "CALL contra resistencia sin ruptura")

    if "PUT_SOPORTE_CERCA_SIN_RUPTURA" in accion_precio and direccion == "PUT":
        confianza_setup = _ajustar(confianza_setup, 2, razones, "PUT soporte cercano aceptable")

    if "PA_A_FAVOR_CALL_DEBIL" in riesgos:
        confianza_setup = _ajustar(confianza_setup, -12, razones, "PA CALL débil histórico")

    if "CHOCH_CON_TENDENCIA_DEBIL" in riesgos:
        confianza_setup = _ajustar(confianza_setup, -10, razones, "CHOCH con tendencia débil")

    if "CONTINUACION_TENDENCIA_INSUFICIENTE" in riesgos:
        confianza_setup = _ajustar(confianza_setup, -8, razones, "Continuación con tendencia insuficiente")

    if "REACCION_SIN_CONFIRMACION_FUERTE" in riesgos:
        confianza_setup = _ajustar(confianza_setup, -6, razones, "Reacción sin confirmación fuerte")

    # ==========================
    # HISTÓRICO COMO AJUSTE SUAVE
    # ==========================

    decision_aprendizaje = _txt(senal.get("decision_aprendizaje", ""))
    ajuste_aprendizaje = _num(
        senal.get(
            "ajuste_confianza_aprendizaje",
            senal.get("ajuste_confianza", 0)
        )
    )

    if decision_aprendizaje == "FAVORABLE":
        confianza_setup = _ajustar(
            confianza_setup,
            min(6, max(3, ajuste_aprendizaje)),
            razones,
            "Aprendizaje histórico favorable"
        )
    elif decision_aprendizaje == "DEBIL":
        confianza_setup = _ajustar(
            confianza_setup,
            max(-8, min(-3, ajuste_aprendizaje)),
            razones,
            "Aprendizaje histórico débil"
        )

    confianza_setup = max(0, min(100, round(confianza_setup, 2)))
    nivel_setup, estado_setup = _nivel_estado_desde_confianza(confianza_setup)

    if confianza_setup < 42:
        protocolo_sugerido = protocolo_sugerido

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
    datos_setup = clasificar_setup(senal)
    senal.update(datos_setup)
    return senal