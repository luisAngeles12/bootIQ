def _lista_desde_pipe(valor):
    if not valor:
        return []

    if isinstance(valor, list):
        return valor

    return [
        x.strip().upper()
        for x in str(valor).split("|")
        if x.strip()
    ]


def _misma_direccion(direccion, pa_direccion):
    direccion = str(direccion).lower()
    pa_direccion = str(pa_direccion).upper()

    return (
        (direccion == "call" and pa_direccion == "CALL") or
        (direccion == "put" and pa_direccion == "PUT")
    )


def _pa_contra(direccion, pa_direccion):
    direccion = str(direccion).lower()
    pa_direccion = str(pa_direccion).upper()

    return (
        (direccion == "call" and pa_direccion == "PUT") or
        (direccion == "put" and pa_direccion == "CALL")
    )


def calcular_consenso_senal(senal, ctx):
    """
    Motor de consenso BootIQ recalibrado.

    MODO OBSERVADOR:
    - No bloquea.
    - No elimina estrategias.
    - No modifica score_final.
    - Solo calcula consenso, nivel y razones.
    """

    try:
        direccion = str(senal.get("direccion", "")).lower()
        patron = str(senal.get("patron", "")).lower()

        pa_tipo = str(senal.get("pa_tipo", ctx.get("pa_tipo", "SIN_DATOS"))).upper()
        pa_direccion = str(senal.get("pa_direccion", ctx.get("pa_direccion", "NEUTRA"))).upper()
        pa_fuerza = float(senal.get("pa_fuerza", ctx.get("pa_fuerza", 0)) or 0)

        accion_precio = str(
            senal.get("accion_precio", ctx.get("accion_precio", "SIN_DATOS"))
        ).upper()

        calidad_mercado = str(ctx.get("calidad_mercado", "SIN_DATOS")).upper()
        regimen_mercado = str(ctx.get("regimen_mercado", "SIN_DATOS")).upper()
        riesgo_mercado = str(ctx.get("riesgo_mercado", "MEDIO")).upper()

        direccion_tendencia = str(ctx.get("direccion_tendencia", "NEUTRA")).upper()
        estado_tendencia = str(ctx.get("estado_tendencia", "INDEFINIDA")).upper()
        fuerza_tendencia = float(ctx.get("fuerza_tendencia", 0) or 0)
        score_mercado = float(ctx.get("score_mercado", 0) or 0)

        base_estrategia = str(senal.get("base_estrategia", "MEDIA")).upper()
        riesgos = _lista_desde_pipe(senal.get("riesgos_base", ""))
        fortalezas = _lista_desde_pipe(senal.get("fortalezas_base", ""))

        consenso = 70
        razones = []

        direccion_senal = "ALCISTA" if direccion == "call" else "BAJISTA"

        # =========================
        # BASE DE ESTRATEGIA
        # =========================
        if base_estrategia == "FUERTE":
            consenso += 6
            razones.append("base fuerte")
        elif base_estrategia == "MEDIA":
            consenso += 0
            razones.append("base media")
        elif base_estrategia == "DEBIL":
            consenso -= 12
            razones.append("base débil")

        # =========================
        # PRICE ACTION PRINCIPAL
        # =========================
        if _misma_direccion(direccion, pa_direccion):
            consenso += 8
            razones.append("price action a favor")

        if _pa_contra(direccion, pa_direccion):
            consenso -= 24
            razones.append("price action en contra")

        if pa_tipo in [
            "RECHAZO_COMPRADOR_CONFIRMADO",
            "RECHAZO_VENDEDOR_CONFIRMADO",
            "AGOTAMIENTO_BAJISTA_CONFIRMADO",
            "AGOTAMIENTO_ALCISTA_CONFIRMADO",
        ]:
            consenso += 8
            razones.append("PA confirmado")

        elif pa_tipo in [
            "IMPULSO_ALCISTA_FUERTE",
            "IMPULSO_BAJISTA_FUERTE",
        ]:
            consenso += 3
            razones.append("impulso fuerte")

        elif pa_tipo == "SIN_CONTEXTO_CLARO":
            consenso -= 18
            razones.append("PA sin contexto claro")

        if pa_fuerza >= 0.70:
            consenso += 4
            razones.append("PA fuerza alta")
        elif 0 < pa_fuerza < 0.35:
            consenso -= 6
            razones.append("PA fuerza baja")

        # =========================
        # TENDENCIA
        # =========================
        if direccion_senal == direccion_tendencia:
            consenso += 6
            razones.append("tendencia a favor")
        elif direccion_tendencia not in ["NEUTRA", "INDEFINIDA", "SIN_DATOS"]:
            consenso -= 18
            razones.append("contra tendencia")

        if fuerza_tendencia >= 72:
            consenso += 4
            razones.append("tendencia fuerte")
        elif fuerza_tendencia < 45:
            consenso -= 8
            razones.append("tendencia débil")

        if "AGOTADA" in estado_tendencia:
            if "sweep" in patron or "reacción" in patron or "reaccion" in patron:
                consenso += 4
                razones.append("agotamiento favorece reversión")
            else:
                consenso -= 6
                razones.append("tendencia agotada perjudica continuación")

        # =========================
        # MERCADO
        # =========================
        if calidad_mercado == "LIMPIO":
            consenso += 5
            razones.append("mercado limpio")
        elif calidad_mercado == "NORMAL":
            consenso += 0
            razones.append("mercado normal")
        elif calidad_mercado in ["SUCIO", "CAOTICO"]:
            consenso -= 16
            razones.append("mercado sucio/caótico")

        if score_mercado >= 75:
            consenso += 3
            razones.append("score mercado alto")
        elif score_mercado < 58:
            consenso -= 6
            razones.append("score mercado bajo")

        if regimen_mercado in ["RANGO_SUCIO", "EXPANSION_PELIGROSA"]:
            consenso -= 16
            razones.append("régimen peligroso")

        if riesgo_mercado == "BAJO":
            consenso += 2
            razones.append("riesgo mercado bajo")
        elif riesgo_mercado == "ALTO":
            consenso -= 10
            razones.append("riesgo mercado alto")

        # =========================
        # ZONAS / ACCIÓN DE PRECIO
        # =========================
        if direccion == "call" and accion_precio == "RECHAZO_COMPRADOR_SOPORTE":
            consenso += 7
            razones.append("CALL con rechazo en soporte")

        if direccion == "put" and accion_precio == "RECHAZO_VENDEDOR_RESISTENCIA":
            consenso += 7
            razones.append("PUT con rechazo en resistencia")

        if direccion == "call" and accion_precio == "CALL_RESISTENCIA_CERCA_SIN_RUPTURA":
            consenso -= 16
            razones.append("CALL cerca de resistencia sin ruptura")

        if direccion == "put" and accion_precio == "PUT_SOPORTE_CERCA_SIN_RUPTURA":
            consenso -= 16
            razones.append("PUT cerca de soporte sin ruptura")

        if accion_precio in ["CALL_ZONA_NEUTRA", "PUT_ZONA_NEUTRA"]:
            consenso += 1
            razones.append("zona neutra")

        # =========================
        # RIESGOS BASE
        # =========================
        penalizaciones = {
            "SIN_CONTEXTO_CLARO": -18,
            "SWEEP_SIN_CONFIRMACION_PA": -20,
            "PA_CONTRA_CALL": -24,
            "PA_CONTRA_PUT": -24,
            "CONTINUACION_TENDENCIA_INSUFICIENTE": -16,
            "PULLBACK_TENDENCIA_INSUFICIENTE": -14,
            "REACCION_SIN_CONFIRMACION_FUERTE": -14,
            "CALL_RESISTENCIA_SIN_RUPTURA": -16,
            "PUT_SOPORTE_SIN_RUPTURA": -16,
            "CONTRA_TENDENCIA": -18,
            "FUERZA_TENDENCIA_BAJA": -10,
            "CHOCH_CON_TENDENCIA_DEBIL": -12,
        }

        for riesgo in riesgos:
            ajuste = penalizaciones.get(riesgo, -4)
            consenso += ajuste
            razones.append("riesgo: " + riesgo)

        # =========================
        # FORTALEZAS BASE
        # Evitamos duplicar demasiado PA.
        # =========================
        bonificaciones = {
            "PA_A_FAVOR_CALL": 3,
            "PA_A_FAVOR_PUT": 3,
            "RECHAZO_COMPRADOR_CONFIRMADO": 3,
            "RECHAZO_VENDEDOR_CONFIRMADO": 3,
            "AGOTAMIENTO_BAJISTA_CONFIRMADO": 4,
            "AGOTAMIENTO_ALCISTA_CONFIRMADO": 4,
            "IMPULSO_ALCISTA_FUERTE": 2,
            "IMPULSO_BAJISTA_FUERTE": 2,
            "TENDENCIA_A_FAVOR": 4,
            "FUERZA_TENDENCIA_ALTA": 3,
            "CHOCH_CON_PA_A_FAVOR": 4,
            "SWEEP_CON_RECHAZO_AGOTAMIENTO": 5,
            "PULLBACK_CON_TENDENCIA_VALIDA": 4,
            "REACCION_CONFIRMADA": 5,
            "CONTINUACION_CON_TENDENCIA_FUERTE": 4,
        }

        for fortaleza in fortalezas:
            ajuste = bonificaciones.get(fortaleza, 1)
            consenso += ajuste
            razones.append("fortaleza: " + fortaleza)

        # =========================
        # AJUSTE POR ESTRATEGIA
        # =========================
        if "liquidity sweep" in patron:
            consenso += 2
            razones.append("sweep observado")

        if "continuación" in patron or "continuacion" in patron:
            consenso -= 8
            razones.append("continuación en observación")

        if "pullback alcista" in patron:
            consenso -= 3
            razones.append("pullback alcista en revisión")

        if "pullback bajista" in patron:
            consenso -= 3
            razones.append("pullback bajista en revisión")

        # =========================
        # VETOS SUAVES
        # No bloquean. Solo limitan consenso máximo.
        # =========================
        if "SIN_CONTEXTO_CLARO" in riesgos and "CONTRA_TENDENCIA" in riesgos:
            consenso = min(consenso, 38)
            razones.append("veto suave: sin contexto + contra tendencia")

        if "SWEEP_SIN_CONFIRMACION_PA" in riesgos and "CONTRA_TENDENCIA" in riesgos:
            consenso = min(consenso, 35)
            razones.append("veto suave: sweep sin PA + contra tendencia")

        if "PA_CONTRA_CALL" in riesgos or "PA_CONTRA_PUT" in riesgos:
            consenso = min(consenso, 45)
            razones.append("veto suave: PA contrario")

        if (
            "CALL_RESISTENCIA_SIN_RUPTURA" in riesgos
            and "SIN_CONTEXTO_CLARO" in riesgos
        ):
            consenso = min(consenso, 42)
            razones.append("veto suave: CALL resistencia + sin contexto")

        if (
            "PUT_SOPORTE_SIN_RUPTURA" in riesgos
            and "SIN_CONTEXTO_CLARO" in riesgos
        ):
            consenso = min(consenso, 42)
            razones.append("veto suave: PUT soporte + sin contexto")

        if (
            ("CALL_RESISTENCIA_SIN_RUPTURA" in riesgos or "PUT_SOPORTE_SIN_RUPTURA" in riesgos)
            and ("PA_CONTRA_CALL" in riesgos or "PA_CONTRA_PUT" in riesgos)
        ):
            consenso = min(consenso, 35)
            razones.append("veto suave: zona peligrosa + PA contrario")

        # =========================
        # NORMALIZAR
        # =========================
        consenso = max(0, min(100, consenso))

        if consenso >= 90:
            nivel = "PREMIUM"
            ajuste_score = 20
        elif consenso >= 82:
            nivel = "ALTO"
            ajuste_score = 12
        elif consenso >= 72:
            nivel = "BUENO"
            ajuste_score = 6
        elif consenso >= 60:
            nivel = "MEDIO"
            ajuste_score = 0
        elif consenso >= 45:
            nivel = "BAJO"
            ajuste_score = -8
        else:
            nivel = "MUY_BAJO"
            ajuste_score = -15

        return {
            "consenso": round(consenso, 2),
            "nivel_consenso": nivel,
            "ajuste_consenso": ajuste_score,
            "razones_consenso": " | ".join(razones),
        }

    except Exception as e:
        return {
            "consenso": 50,
            "nivel_consenso": "ERROR",
            "ajuste_consenso": 0,
            "razones_consenso": "error motor consenso: " + str(e),
        }


def aplicar_consenso_senal(senal, ctx):
    resultado = calcular_consenso_senal(senal, ctx)

    senal["consenso"] = resultado.get("consenso", 50)
    senal["nivel_consenso"] = resultado.get("nivel_consenso", "MEDIO")
    senal["ajuste_consenso"] = resultado.get("ajuste_consenso", 0)
    senal["razones_consenso"] = resultado.get("razones_consenso", "")

    return senal