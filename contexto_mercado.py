
from indicadores import pendiente_ema, estructura_reciente, fuerza_impulso
def promedio(lista):
    if not lista:
        return 0
    return sum(lista) / len(lista)


def calcular_rangos(candles):
    rangos = []

    for c in candles:
        h = float(c["max"])
        l = float(c["min"])
        rangos.append(h - l)

    return rangos


def detectar_tipo_mercado(candles):
    try:
        if not candles or len(candles) < 20:
            return "INDEFINIDO", "velas insuficientes"

        candles = sorted(candles, key=lambda x: x["from"])

        opens = [float(c["open"]) for c in candles]
        closes = [float(c["close"]) for c in candles]
        highs = [float(c["max"]) for c in candles]
        lows = [float(c["min"]) for c in candles]

        ultimas = candles[-20:]
        closes_ult = closes[-20:]
        highs_ult = highs[-20:]
        lows_ult = lows[-20:]

        max_20 = max(highs_ult)
        min_20 = min(lows_ult)
        rango_total = max_20 - min_20

        if rango_total <= 0:
            return "INDEFINIDO", "rango inválido"

        avance = closes_ult[-1] - closes_ult[0]
        fuerza = abs(avance) / rango_total

        mitad_1 = closes_ult[:10]
        mitad_2 = closes_ult[10:]

        promedio_1 = sum(mitad_1) / len(mitad_1)
        promedio_2 = sum(mitad_2) / len(mitad_2)

        velas_verdes = sum(
            1 for c in ultimas
            if float(c["close"]) > float(c["open"])
        )

        velas_rojas = sum(
            1 for c in ultimas
            if float(c["close"]) < float(c["open"])
        )

        rangos = []
        for c in ultimas:
            rangos.append(float(c["max"]) - float(c["min"]))

        rango_promedio = sum(rangos) / len(rangos)
        rango_reciente = sum(rangos[-5:]) / len(rangos[-5:])

        ema_dir = pendiente_ema(closes, 21, 8)
        estructura_dir = estructura_reciente(highs, lows, 12)
        impulso = fuerza_impulso(opens, closes, highs, lows, 8)

        # =========================
        # COMPRESIÓN
        # =========================
        if rango_reciente < rango_promedio * 0.60 and fuerza < 0.25:
            return "COMPRESION", "rango reciente comprimido y sin avance"

        # =========================
        # EXPANSIÓN
        # =========================
        if rango_reciente > rango_promedio * 1.60:
            return "EXPANSION", "rango reciente expandido con volatilidad alta"

        # =========================
        # TENDENCIA ALCISTA CONFIRMADA
        # =========================
        if (
            promedio_2 > promedio_1
            and closes_ult[-1] > closes_ult[5]
            and velas_verdes >= 10
            and fuerza >= 0.32
            and ema_dir == 1
            and estructura_dir == 1
            and impulso >= 0.42
        ):
            return "TENDENCIA_ALCISTA", "tendencia alcista confirmada por estructura, EMA e impulso"

        # =========================
        # TENDENCIA BAJISTA CONFIRMADA
        # =========================
        if (
            promedio_2 < promedio_1
            and closes_ult[-1] < closes_ult[5]
            and velas_rojas >= 11
            and fuerza >= 0.35
            and ema_dir == -1
            and estructura_dir == -1
            and impulso >= 0.42
        ):
            return "TENDENCIA_BAJISTA", "tendencia bajista confirmada por estructura, EMA e impulso"

        # =========================
        # TENDENCIA MODERADA MÁS EXIGENTE
        # =========================
        if fuerza >= 0.28:
            if avance > 0:
                return "TENDENCIA_ALCISTA", "tendencia alcista moderada por avance predominante"

            if avance < 0:
                return "TENDENCIA_BAJISTA", "tendencia bajista moderada por avance predominante"

        # =========================
        # RANGO
        # =========================
        if fuerza < 0.35:
            return "RANGO", "precio lateral o sin avance direccional fuerte"

        return "RANGO", "mercado mixto tratado como rango preventivo"

    except Exception as e:
        return "INDEFINIDO", "error detectando mercado: " + str(e)
def mercado_permite_direccion(tipo_mercado, direccion):
    """
    Esta función NO bloquea todavía fuerte.
    Solo clasifica si la dirección va a favor o contra contexto.
    """

    if tipo_mercado == "TENDENCIA_ALCISTA":
        if direccion == "call":
            return True, "operación a favor de tendencia alcista"
        return True, "operación contra tendencia alcista"

    if tipo_mercado == "TENDENCIA_BAJISTA":
        if direccion == "put":
            return True, "operación a favor de tendencia bajista"
        return True, "operación contra tendencia bajista"

    if tipo_mercado == "RANGO":
        return True, "mercado en rango: requiere ubicación"

    if tipo_mercado == "COMPRESION":
        return True, "mercado en compresión: operar con cuidado"

    if tipo_mercado == "EXPANSION":
        return True, "mercado en expansión: evitar perseguir precio"

    return True, "mercado indefinido"
def diagnostico_maestro_mercado(candles):
    """
    Diagnóstico maestro:
    No reemplaza detectar_tipo_mercado().
    Complementa la lectura para saber si el mercado es limpio, sucio,
    agotado, peligroso o apto para continuación.
    """
    try:
        if not candles or len(candles) < 30:
            return {
                "regimen": "SIN_DATOS",
                "operable": False,
                "riesgo": "ALTO",
                "modo": "ESPERAR",
                "razon": "velas insuficientes",
            }

        candles = sorted(candles, key=lambda x: x["from"])

        tipo_mercado, razon_tipo = detectar_tipo_mercado(candles)
        calidad = diagnostico_calidad_mercado(candles)
        tendencia = diagnostico_tendencia_avanzada(candles)

        calidad_mercado = calidad.get("calidad", "SIN_DATOS")
        score_mercado = calidad.get("score", 0)

        estado_tendencia = tendencia.get("estado_tendencia", "INDEFINIDA")
        fuerza_tendencia = tendencia.get("fuerza_tendencia", 0)
        direccion_tendencia = tendencia.get("direccion_tendencia", "INDEFINIDA")
        mechas_agotamiento = tendencia.get("mechas_agotamiento", 0)
        velas_debilitadas = tendencia.get("velas_debilitadas", 0)

        ultimas = candles[-20:]

        rangos = []
        cuerpos = []
        mechas_totales = 0
        cambios_color = 0
        color_anterior = None

        for c in ultimas:
            o = float(c["open"])
            close = float(c["close"])
            h = float(c["max"])
            l = float(c["min"])

            rango = h - l
            cuerpo = abs(close - o)

            if rango <= 0:
                continue

            rangos.append(rango)
            cuerpos.append(cuerpo)

            mecha_sup = h - max(o, close)
            mecha_inf = min(o, close) - l
            mechas_totales += mecha_sup + mecha_inf

            color = "verde" if close > o else "roja" if close < o else "doji"

            if color_anterior and color != "doji" and color_anterior != "doji":
                if color != color_anterior:
                    cambios_color += 1

            if color != "doji":
                color_anterior = color

        if not rangos:
            return {
                "regimen": "SIN_DATOS",
                "operable": False,
                "riesgo": "ALTO",
                "modo": "ESPERAR",
                "razon": "rangos inválidos",
            }

        rango_promedio = promedio(rangos)
        cuerpo_promedio = promedio(cuerpos)
        ratio_cuerpo = cuerpo_promedio / rango_promedio if rango_promedio > 0 else 0

        rango_reciente = promedio(rangos[-5:])
        expansion = rango_reciente > rango_promedio * 1.55
        compresion = rango_reciente < rango_promedio * 0.65

        ruido_alto = (
            calidad_mercado in ["SUCIO", "CAOTICO"]
            or cambios_color >= 9
            or ratio_cuerpo < 0.24
        )

        agotamiento = (
            "AGOTADA" in estado_tendencia
            or mechas_agotamiento >= 3
            or velas_debilitadas >= 4
        )

        tendencia_limpia = (
            tipo_mercado in ["TENDENCIA_ALCISTA", "TENDENCIA_BAJISTA"]
            and calidad_mercado in ["LIMPIO", "NORMAL"]
            and estado_tendencia.endswith(("NORMAL", "FUERTE"))
            and fuerza_tendencia >= 58
            and not ruido_alto
            and not expansion
        )

        tendencia_sucia = (
            tipo_mercado in ["TENDENCIA_ALCISTA", "TENDENCIA_BAJISTA"]
            and (
                ruido_alto
                or fuerza_tendencia < 58
                or "DEBIL" in estado_tendencia
            )
        )

        rango_limpio = (
            tipo_mercado == "RANGO"
            and calidad_mercado in ["LIMPIO", "NORMAL"]
            and score_mercado >= 60
            and not expansion
        )

        rango_sucio = (
            tipo_mercado == "RANGO"
            and (
                calidad_mercado in ["SUCIO", "CAOTICO"]
                or score_mercado < 60
                or expansion
            )
        )

        if expansion:
            return {
                "regimen": "EXPANSION_PELIGROSA",
                "operable": False,
                "riesgo": "ALTO",
                "modo": "NO_PERSEGUIR",
                "direccion_tendencia": direccion_tendencia,
                "fuerza_tendencia": fuerza_tendencia,
                "calidad_mercado": calidad_mercado,
                "score_mercado": score_mercado,
                "razon": "mercado expandido: evitar perseguir vela corrida",
            }

        if compresion and tipo_mercado in ["RANGO", "COMPRESION"]:
            return {
                "regimen": "COMPRESION_PRE_RUPTURA",
                "operable": False,
                "riesgo": "MEDIO",
                "modo": "ESPERAR_RUPTURA",
                "direccion_tendencia": direccion_tendencia,
                "fuerza_tendencia": fuerza_tendencia,
                "calidad_mercado": calidad_mercado,
                "score_mercado": score_mercado,
                "razon": "mercado comprimido: esperar ruptura confirmada",
            }

        if agotamiento and tipo_mercado in ["TENDENCIA_ALCISTA", "TENDENCIA_BAJISTA"]:
            return {
                "regimen": "AGOTAMIENTO_" + direccion_tendencia,
                "operable": True,
                "riesgo": "MEDIO",
                "modo": "SWEEP_REVERSION",
                "direccion_tendencia": direccion_tendencia,
                "fuerza_tendencia": fuerza_tendencia,
                "calidad_mercado": calidad_mercado,
                "score_mercado": score_mercado,
                "razon": "tendencia con agotamiento: preferir sweep/rechazo, no continuación",
            }

        if tendencia_limpia:
            return {
                "regimen": "TENDENCIA_LIMPIA",
                "operable": True,
                "riesgo": "BAJO",
                "modo": "PULLBACK_CONTINUACION",
                "direccion_tendencia": direccion_tendencia,
                "fuerza_tendencia": fuerza_tendencia,
                "calidad_mercado": calidad_mercado,
                "score_mercado": score_mercado,
                "razon": "tendencia limpia: pullback/continuación a favor",
            }

        if tendencia_sucia:
            return {
                "regimen": "TENDENCIA_SUCIA",
                "operable": True,
                "riesgo": "MEDIO",
                "modo": "SOLO_SWEEP_O_RECHAZO",
                "direccion_tendencia": direccion_tendencia,
                "fuerza_tendencia": fuerza_tendencia,
                "calidad_mercado": calidad_mercado,
                "score_mercado": score_mercado,
                "razon": "tendencia con ruido o fuerza débil: evitar CHOCH/pullback flojo",
            }

        if rango_limpio:
            return {
                "regimen": "RANGO_LIMPIO",
                "operable": True,
                "riesgo": "MEDIO",
                "modo": "EXTREMOS_SWEEP",
                "direccion_tendencia": direccion_tendencia,
                "fuerza_tendencia": fuerza_tendencia,
                "calidad_mercado": calidad_mercado,
                "score_mercado": score_mercado,
                "razon": "rango limpio: operar extremos, sweep y rechazo",
            }

        if rango_sucio:
            return {
                "regimen": "RANGO_SUCIO",
                "operable": False,
                "riesgo": "ALTO",
                "modo": "ESPERAR",
                "direccion_tendencia": direccion_tendencia,
                "fuerza_tendencia": fuerza_tendencia,
                "calidad_mercado": calidad_mercado,
                "score_mercado": score_mercado,
                "razon": "rango sucio: demasiado ruido",
            }

        return {
            "regimen": "MERCADO_MIXTO",
            "operable": True,
            "riesgo": "MEDIO",
            "modo": "SOLO_SEÑALES_FUERTES",
            "direccion_tendencia": direccion_tendencia,
            "fuerza_tendencia": fuerza_tendencia,
            "calidad_mercado": calidad_mercado,
            "score_mercado": score_mercado,
            "razon": "mercado mixto: operar solo señales fuertes",
        }

    except Exception as e:
        return {
            "regimen": "ERROR",
            "operable": False,
            "riesgo": "ALTO",
            "modo": "ESPERAR",
            "razon": "error diagnóstico maestro: " + str(e),
        }
def clasificar_setup_estrategico(senal, ctx):
    """
    Clasifica la oportunidad sin bloquearla.
    Sirve para que BootIQ aprenda qué tipo de setup está viendo:
    reversión, continuación, ruptura, rechazo, sweep, CHOCH o riesgo de zona.
    """

    patron = str(senal.get("patron", "")).lower()
    direccion = str(senal.get("direccion", "")).lower()

    tipo_mercado = ctx.get("tipo_mercado", "INDEFINIDO")
    calidad_mercado = ctx.get("calidad_mercado", "NORMAL")
    estado_tendencia = ctx.get("estado_tendencia", "INDEFINIDA")
    direccion_tendencia = ctx.get("direccion_tendencia", "INDEFINIDA")
    fuerza_tendencia = ctx.get("fuerza_tendencia", 0)

    cerca_soporte = ctx.get("cerca_soporte", False)
    cerca_resistencia = ctx.get("cerca_resistencia", False)

    rechazo = ctx.get("rechazo", 0)
    liquidity_sweep = ctx.get("liquidity_sweep", 0)
    ruptura_confirmada = ctx.get("ruptura_confirmada", False)

    pa_tipo = ctx.get("pa_tipo", "SIN_CONTEXTO_CLARO")
    pa_direccion = ctx.get("pa_direccion", "NEUTRA")
    pa_fuerza = ctx.get("pa_fuerza", 0)

    puntaje = senal.get("puntaje", 0)

    direccion_setup = "ALCISTA" if direccion == "call" else "BAJISTA"
    a_favor_tendencia = direccion_setup == direccion_tendencia

    tipo_setup = "INDEFINIDO"
    calidad_setup = "MEDIA"
    modo_entrada = "DIRECTA"
    puntaje_extra = 0
    riesgo_extra = 0
    razones = []

    # =========================
    # UBICACIÓN EN ZONA
    # =========================
    if direccion == "call" and cerca_soporte:
        razones.append("CALL ubicado cerca de soporte")
        puntaje_extra += 2

    if direccion == "put" and cerca_resistencia:
        razones.append("PUT ubicado cerca de resistencia")
        puntaje_extra += 2

    if direccion == "call" and cerca_resistencia:
        razones.append("CALL cerca de resistencia: requiere ruptura o impulso")
        riesgo_extra += 2
        modo_entrada = "ESPERAR_RUPTURA"

    if direccion == "put" and cerca_soporte:
        razones.append("PUT cerca de soporte: requiere ruptura o impulso")
        riesgo_extra += 2
        modo_entrada = "ESPERAR_RUPTURA"

    # =========================
    # RECHAZO
    # =========================
    if direccion == "call" and rechazo == 1:
        tipo_setup = "RECHAZO_ALCISTA"
        puntaje_extra += 3
        razones.append("rechazo comprador detectado")

    if direccion == "put" and rechazo == -1:
        tipo_setup = "RECHAZO_BAJISTA"
        puntaje_extra += 3
        razones.append("rechazo vendedor detectado")

    # =========================
    # LIQUIDITY SWEEP
    # =========================
    if "liquidity sweep" in patron:
        if direccion == "call":
            tipo_setup = "SWEEP_ALCISTA"
        else:
            tipo_setup = "SWEEP_BAJISTA"

        puntaje_extra += 2
        razones.append("setup basado en barrida de liquidez")

        if (
            direccion == "call"
            and cerca_soporte
            and (rechazo == 1 or pa_direccion == "CALL")
        ):
            tipo_setup = "REVERSION_ALCISTA"
            calidad_setup = "BUENA"
            modo_entrada = "DIRECTA"
            puntaje_extra += 4
            razones.append("sweep alcista con soporte/rechazo: reversión válida")

        elif (
            direccion == "put"
            and cerca_resistencia
            and (rechazo == -1 or pa_direccion == "PUT")
        ):
            tipo_setup = "REVERSION_BAJISTA"
            calidad_setup = "BUENA"
            puntaje_extra += 4
            razones.append("sweep bajista con resistencia/rechazo: reversión válida")

        elif not a_favor_tendencia:
            riesgo_extra += 2
            razones.append("sweep contra tendencia sin confirmación completa")

    # =========================
    # CHOCH
    # =========================
    if "choch" in patron:
        if direccion == "call":
            tipo_setup = "CHOCH_ALCISTA"
        else:
            tipo_setup = "CHOCH_BAJISTA"

        razones.append("setup de cambio de estructura")

        if pa_direccion in ["CALL", "PUT"] and pa_direccion == direccion.upper():
            puntaje_extra += 3
            calidad_setup = "BUENA"
            razones.append("CHOCH con price action profesional a favor")

        if ruptura_confirmada:
            puntaje_extra += 3
            calidad_setup = "BUENA"
            modo_entrada = "DIRECTA"
            razones.append("CHOCH con ruptura confirmada")

        if not a_favor_tendencia and fuerza_tendencia >= 60:
            riesgo_extra += 3
            razones.append("CHOCH contra tendencia fuerte")

    # =========================
    # PULLBACK / CONTINUACIÓN
    # =========================
    if "pullback" in patron or "continuacion" in patron or "continuación" in patron:
        tipo_setup = "CONTINUACION"

        if a_favor_tendencia:
            puntaje_extra += 3
            razones.append("continuación a favor de tendencia")

        if fuerza_tendencia >= 60:
            puntaje_extra += 3
            calidad_setup = "BUENA"
            razones.append("tendencia con fuerza suficiente")

        if not a_favor_tendencia:
            riesgo_extra += 4
            calidad_setup = "DEBIL"
            razones.append("pullback/continuación contra tendencia")

    # =========================
    # BREAKOUT / RETEST
    # =========================
    if "breakout" in patron or "retest" in patron:
        tipo_setup = "RUPTURA_RETEST"

        if ruptura_confirmada:
            puntaje_extra += 4
            calidad_setup = "BUENA"
            modo_entrada = "DIRECTA"
            razones.append("ruptura/retest confirmado")

        else:
            modo_entrada = "ESPERAR_CONFIRMACION"
            riesgo_extra += 2
            razones.append("ruptura/retest sin confirmación completa")

    # =========================
    # PRICE ACTION PROFESIONAL
    # =========================
    if pa_tipo in [
        "RECHAZO_COMPRADOR_CONFIRMADO",
        "RECHAZO_VENDEDOR_CONFIRMADO",
        "AGOTAMIENTO_BAJISTA_CONFIRMADO",
        "AGOTAMIENTO_ALCISTA_CONFIRMADO"
    ]:
        puntaje_extra += 4
        calidad_setup = "BUENA"
        razones.append("price action profesional confirma rechazo/agottamiento")

    if pa_tipo in [
        "IMPULSO_ALCISTA_FUERTE",
        "IMPULSO_BAJISTA_FUERTE"
    ]:
        puntaje_extra += 2
        razones.append("price action muestra impulso fuerte")

    if pa_tipo == "SIN_CONTEXTO_CLARO":
        riesgo_extra += 2
        razones.append("price action sin contexto claro")

    # =========================
    # CALIDAD DEL MERCADO
    # =========================
    if calidad_mercado == "LIMPIO":
        puntaje_extra += 2
        razones.append("mercado limpio")

    if calidad_mercado == "NORMAL":
        razones.append("mercado normal operable")

    if calidad_mercado in ["SUCIO", "CAOTICO"]:
        riesgo_extra += 4
        calidad_setup = "DEBIL"
        razones.append("mercado sucio/caótico")

    # =========================
    # CLASIFICACIÓN FINAL
    # =========================
    balance = puntaje + puntaje_extra - riesgo_extra

    if balance >= 26 and riesgo_extra <= 2:
        calidad_setup = "PREMIUM"
    elif balance >= 21 and riesgo_extra <= 4:
        calidad_setup = "BUENA"
    elif balance >= 16:
        calidad_setup = "MEDIA"
    else:
        calidad_setup = "DEBIL"

    if riesgo_extra >= 6 and calidad_setup != "PREMIUM":
        modo_entrada = "NO_OPERAR"

    return {
        "tipo_setup": tipo_setup,
        "calidad_setup": calidad_setup,
        "modo_entrada": modo_entrada,
        "puntaje_extra_setup": puntaje_extra,
        "riesgo_extra_setup": riesgo_extra,
        "balance_setup": balance,
        "a_favor_tendencia": a_favor_tendencia,
        "razones_setup": razones,
    }    
def validar_estrategia_por_mercado(senal, ctx):
    if not senal:
        return False, "señal vacía"

    tipo_mercado = ctx.get("tipo_mercado", "INDEFINIDO")
    calidad_mercado = ctx.get("calidad_mercado", "NORMAL")
    patron = str(senal.get("patron", "")).lower()
    direccion = senal.get("direccion", "")
    puntaje = senal.get("puntaje", 0)

    estado_tendencia = ctx.get("estado_tendencia", "INDEFINIDA")
    direccion_tendencia = ctx.get("direccion_tendencia", "INDEFINIDA")

    cerca_soporte = ctx.get("cerca_soporte", False)
    cerca_resistencia = ctx.get("cerca_resistencia", False)

    rechazo = ctx.get("rechazo", 0)
    liquidity_sweep = ctx.get("liquidity_sweep", 0)
    patron_vela = ctx.get("patron", 0)
    regimen_mercado = ctx.get("regimen_mercado", "SIN_DATOS")
    modo_mercado = ctx.get("modo_mercado", "SIN_DATOS")
    riesgo_mercado = ctx.get("riesgo_mercado", "MEDIO")
    direccion_senal = "ALCISTA" if direccion == "call" else "BAJISTA"
    a_favor = direccion_senal == direccion_tendencia

    tendencia_debil = "DEBIL" in estado_tendencia
    tendencia_indefinida = estado_tendencia == "INDEFINIDA"
    tendencia_agotada = "AGOTADA" in estado_tendencia

    mercado_delicado = (
        tipo_mercado == "RANGO"
        or calidad_mercado == "SUCIO"
        or tendencia_debil
        or tendencia_indefinida
    )
    ruptura_confirmada = ctx.get("ruptura_confirmada", False)
    confirmacion_fuerte = (
        rechazo != 0
        or patron_vela != 0
        or liquidity_sweep != 0
        or ruptura_confirmada
        or puntaje >= 18
    )

    agotamiento_real_call = (
        direccion == "call"
        and cerca_soporte
        and (
            rechazo == 1
            or patron_vela == 1
            or liquidity_sweep == 1
            or tendencia_agotada
        )
    )

    agotamiento_real_put = (
        direccion == "put"
        and cerca_resistencia
        and (
            rechazo == -1
            or patron_vela == -1
            or liquidity_sweep == -1
            or tendencia_agotada
        )
    )

    agotamiento_real = agotamiento_real_call or agotamiento_real_put
    
    # =========================
    # FILTRO MAESTRO DE MERCADO
    # =========================
    if regimen_mercado == "EXPANSION_PELIGROSA":
        if "liquidity sweep" in patron and puntaje >= 25 and agotamiento_real:
            return True, "mercado peligroso: solo sweep premium con agotamiento real"

        return False, "mercado peligroso: señal bloqueada por régimen maestro"
    if regimen_mercado == "RANGO_SUCIO":
        if "liquidity sweep" in patron and puntaje >= 24:
            return True, "rango sucio: sweep premium permitido"

        return False, "rango sucio: señal bloqueada"
    if regimen_mercado == "COMPRESION_PRE_RUPTURA":
        if ruptura_confirmada and puntaje >= 22:
            return True, "compresión resuelta: ruptura confirmada"

        return False, "compresión: esperar ruptura confirmada"

    if regimen_mercado == "TENDENCIA_SUCIA":
        if "liquidity sweep" in patron and puntaje >= 23 and agotamiento_real:
            return True, "tendencia sucia: sweep permitido solo con agotamiento"
    
        if "pullback alcista" in patron and direccion == "call" and puntaje >= 19 and a_favor:
            return True, "tendencia sucia: pullback alcista permitido con puntaje alto"
    
        if "pullback bajista" in patron and direccion == "put" and puntaje >= 20 and a_favor:
            return True, "tendencia sucia: pullback bajista permitido con puntaje alto"
    
        if "choch" in patron and puntaje < 22:
            return False, "tendencia sucia: CHOCH débil bloqueado"
        
    if regimen_mercado == "TENDENCIA_LIMPIA":
        if "pullback" in patron and not a_favor:
            return False, "tendencia limpia: pullback contra tendencia bloqueado"

        if "continuacion" in patron or "continuación" in patron:
            if puntaje >= 16 and a_favor:
                return True, "tendencia limpia: continuación permitida a favor"

    if regimen_mercado == "RANGO_LIMPIO":
        if "pullback" in patron:
            return False, "rango limpio: pullback EMA bloqueado, preferir extremos"

        if "liquidity sweep" in patron and puntaje >= 22:
            return True, "rango limpio: sweep permitido"

        if ("reaccion" in patron or "reacción" in patron) and agotamiento_real:
            return True, "rango limpio: reacción en extremo permitida"

    # =========================
    # MERCADO CAÓTICO
    # =========================
    if calidad_mercado == "CAOTICO":
        if puntaje >= 25 and agotamiento_real:
            return True, "mercado caótico: solo señal premium con agotamiento real"

        return False, "mercado caótico: señal bloqueada"

    # =========================
    # CHOCH
    # =========================
    if "choch" in patron:

        if "choch alcista" in patron and direccion == "call":
            if cerca_resistencia and puntaje < 19:
                return False, "CHOCH CALL bloqueado: resistencia cerca requiere ruptura/retest o puntaje >= 22"

        if "choch bajista" in patron and direccion == "put":
            if cerca_soporte and puntaje < 19:
                return False, "CHOCH PUT bloqueado: soporte cerca requiere ruptura/retest o puntaje >= 22"

        if a_favor:
            if mercado_delicado and puntaje < 18:
                return False, "CHOCH bloqueado: mercado delicado requiere mínimo puntaje 18"

            if puntaje >= 18 and confirmacion_fuerte:
                return True, "CHOCH permitido a favor de tendencia con confirmación"
            
            if (
                puntaje >= 20
                and calidad_mercado in ["LIMPIO", "NORMAL"]
                and tipo_mercado in ["TENDENCIA_ALCISTA", "TENDENCIA_BAJISTA"]
                and a_favor
            ):
                return True, "CHOCH permitido por contexto fuerte aunque confirmación no sea perfecta"
            
            return False, "CHOCH bloqueado: sin confirmación fuerte"

        # CHOCH contra tendencia
        if not a_favor:
            if puntaje >= 23 and agotamiento_real:
                return True, "CHOCH contra tendencia permitido por agotamiento real"

            return False, "CHOCH contra tendencia bloqueado"

    # =========================
    # PULLBACK
    # =========================
    if "pullback" in patron:
        if calidad_mercado == "CAOTICO":
            return False, "pullback bloqueado en mercado caótico"
    
        if not a_favor:
            return False, "pullback fuera de contexto"
    
        if "pullback alcista" in patron:
            if tipo_mercado != "TENDENCIA_ALCISTA":
                return False, "pullback alcista requiere tendencia alcista"
    
            if calidad_mercado not in ["LIMPIO", "NORMAL"]:
                return False, "pullback alcista requiere mercado operable"
            
            if estado_tendencia not in ["ALCISTA_NORMAL", "ALCISTA_FUERTE"]:
                return False, "pullback alcista requiere tendencia alcista válida"
            if puntaje < 16:
                return False, "pullback alcista requiere mínimo 16 puntos"
    
            if rechazo != 1 and patron_vela != 1:
                return False, "pullback alcista requiere rechazo o patrón alcista"
    
            return True, "pullback alcista permitido con filtro reforzado"
    
        if "pullback bajista" in patron:
            if tipo_mercado != "TENDENCIA_BAJISTA":
                return False, "pullback bajista requiere tendencia bajista"

            if calidad_mercado not in ["LIMPIO", "NORMAL"]:
                return False, "pullback bajista requiere mercado operable"

            if estado_tendencia not in ["BAJISTA_NORMAL", "BAJISTA_FUERTE"]:
                return False, "pullback bajista requiere tendencia bajista válida"

            if puntaje < 18:
                return False, "pullback bajista requiere mínimo 18 puntos"

            if rechazo != -1 and patron_vela != -1:
                return False, "pullback bajista requiere rechazo o patrón bajista"
            if cerca_soporte and puntaje < 21:
                return False, "pullback bajista bloqueado: demasiado cerca de soporte"
            
            if estado_tendencia != "BAJISTA_FUERTE" and puntaje < 20:
                return False, "pullback bajista requiere tendencia bajista fuerte o puntaje alto"
            return True, "pullback bajista permitido con filtro reforzado"
    
        return False, "pullback no reconocido"
    # =========================
    # BREAKOUT + RETEST
    # =========================
    if "breakout" in patron or "retest" in patron:
        if puntaje >= 20:
            return True, "breakout/retest permitido"

        return False, "breakout/retest bloqueado: puntaje bajo"

    # =========================
    # LIQUIDITY SWEEP
    # =========================
    if "liquidity sweep" in patron:
        if a_favor:
            if mercado_delicado and puntaje < 21:
                return False, "sweep bloqueado: mercado delicado requiere mínimo 21"

            if puntaje >= 20 and confirmacion_fuerte:
                return True, "sweep permitido a favor de tendencia"

            return False, "sweep bloqueado: sin confirmación fuerte"

        # Sweep contra tendencia:
        # Solo permitir si hay agotamiento real.
        if not a_favor:
            if puntaje >= 24 and (
                agotamiento_real
                or rechazo != 0
                or liquidity_sweep != 0
            ):
                return True, "sweep contra tendencia permitido por barrida/rechazo fuerte"
        
            return False, "sweep contra tendencia bloqueado: sin agotamiento suficiente"
    # =========================
    # TENDENCIA ALCISTA
    # =========================
    if tipo_mercado == "TENDENCIA_ALCISTA":
        if direccion == "call":
            return True, "CALL permitido a favor de tendencia alcista"

        if direccion == "put":
            if puntaje >= 24 and agotamiento_real_put:
                return True, "PUT contra tendencia permitido por agotamiento alcista"

            return False, "PUT bloqueado contra tendencia alcista"

    # =========================
    # TENDENCIA BAJISTA
    # =========================
    if tipo_mercado == "TENDENCIA_BAJISTA":
        if direccion == "put":
            return True, "PUT permitido a favor de tendencia bajista"

        if direccion == "call":
            if puntaje >= 24 and agotamiento_real_call:
                return True, "CALL contra tendencia permitido por agotamiento bajista"

            return False, "CALL bloqueado contra tendencia bajista"

    # =========================
    # COMPRESIÓN
    # =========================
    if tipo_mercado == "COMPRESION":
        return False, "mercado en compresión: esperar ruptura"

    # =========================
    # EXPANSIÓN
    # =========================
    if tipo_mercado == "EXPANSION":
        if puntaje >= 24 and confirmacion_fuerte:
            return True, "señal premium permitida en expansión"

        return False, "mercado en expansión: evitar perseguir precio"

    # =========================
    # INDEFINIDO
    # =========================
    if tipo_mercado == "INDEFINIDO":
        if calidad_mercado in ["LIMPIO", "NORMAL"] and puntaje >= 20 and confirmacion_fuerte:
            return True, "señal fuerte permitida en mercado indefinido operable"
    
        if "choch" in patron and puntaje >= 20 and calidad_mercado in ["LIMPIO", "NORMAL"]:
            return True, "CHOCH permitido en indefinido operable"
    
        return False, "mercado indefinido: señal bloqueada"

    return True, "mercado permitido"

def diagnostico_calidad_mercado(candles):
    
    try:
        if not candles or len(candles) < 20:
            return {
                "calidad": "SIN_DATOS",
                "score": 0,
                "razon": "velas insuficientes"
            }

        candles = sorted(candles, key=lambda x: x["from"])

        ultimas = candles[-20:]

        cuerpos = []
        rangos = []
        mechas_grandes = 0
        velas_indecisas = 0
        cambios_color = 0

        color_anterior = None

        for c in ultimas:
            o = float(c["open"])
            close = float(c["close"])
            h = float(c["max"])
            l = float(c["min"])

            rango = h - l
            cuerpo = abs(close - o)

            if rango <= 0:
                continue

            mecha_sup = h - max(o, close)
            mecha_inf = min(o, close) - l
            mecha_total = mecha_sup + mecha_inf

            cuerpos.append(cuerpo)
            rangos.append(rango)

            if cuerpo <= rango * 0.25:
                velas_indecisas += 1

            if mecha_total >= cuerpo * 2.5:
                mechas_grandes += 1

            color = "verde" if close > o else "roja" if close < o else "doji"

            if color_anterior and color != "doji" and color_anterior != "doji":
                if color != color_anterior:
                    cambios_color += 1

            if color != "doji":
                color_anterior = color

        if not rangos:
            return {
                "calidad": "SIN_DATOS",
                "score": 0,
                "razon": "rangos inválidos"
            }

        promedio_rango = sum(rangos) / len(rangos)
        promedio_cuerpo = sum(cuerpos) / len(cuerpos) if cuerpos else 0

        ratio_cuerpo = promedio_cuerpo / promedio_rango if promedio_rango > 0 else 0

        ruido = 0

        ruido += mechas_grandes * 4
        ruido += velas_indecisas * 3
        ruido += cambios_color * 2

        if ratio_cuerpo < 0.28:
            ruido += 15

        score = max(0, 100 - ruido)

        if score >= 75:
            calidad = "LIMPIO"
            razon = "mercado limpio, velas con cuerpo y poco ruido"

        elif score >= 55:
            calidad = "NORMAL"
            razon = "mercado aceptable, algo de ruido pero operable"

        elif score >= 35:
            calidad = "SUCIO"
            razon = "mercado con muchas mechas o indecisión"

        else:
            calidad = "CAOTICO"
            razon = "mercado muy sucio, muchas mechas/cambios bruscos"

        return {
            "calidad": calidad,
            "score": round(score, 2),
            "razon": razon,
            "mechas_grandes": mechas_grandes,
            "velas_indecisas": velas_indecisas,
            "cambios_color": cambios_color,
            "ratio_cuerpo": round(ratio_cuerpo, 2)
        }

    except Exception as e:
        return {
            "calidad": "ERROR",
            "score": 0,
            "razon": str(e)
        }
    
def diagnostico_tendencia_avanzada(candles):
    try:
        if not candles or len(candles) < 20:
            return {
                "estado_tendencia": "SIN_DATOS",
                "fuerza_tendencia": 0,
                "direccion_tendencia": "INDEFINIDA",
                "razon_tendencia": "velas insuficientes"
            }

        candles = sorted(candles, key=lambda x: x["from"])
        ultimas = candles[-20:]

        closes = [float(c["close"]) for c in ultimas]
        highs = [float(c["max"]) for c in ultimas]
        lows = [float(c["min"]) for c in ultimas]
        opens = [float(c["open"]) for c in ultimas]

        maximo = max(highs)
        minimo = min(lows)
        rango_total = maximo - minimo

        if rango_total <= 0:
            return {
                "estado_tendencia": "INDEFINIDA",
                "fuerza_tendencia": 0,
                "direccion_tendencia": "INDEFINIDA",
                "razon_tendencia": "rango inválido"
            }

        avance = closes[-1] - closes[0]
        fuerza_base = abs(avance) / rango_total

        cierres_alcistas = 0
        cierres_bajistas = 0

        for i in range(1, len(closes)):
            if closes[i] > closes[i - 1]:
                cierres_alcistas += 1
            elif closes[i] < closes[i - 1]:
                cierres_bajistas += 1

        maximos_crecientes = 0
        minimos_crecientes = 0
        maximos_decrecientes = 0
        minimos_decrecientes = 0

        for i in range(1, len(highs)):
            if highs[i] > highs[i - 1]:
                maximos_crecientes += 1
            elif highs[i] < highs[i - 1]:
                maximos_decrecientes += 1

            if lows[i] > lows[i - 1]:
                minimos_crecientes += 1
            elif lows[i] < lows[i - 1]:
                minimos_decrecientes += 1

        cuerpos = []
        mechas_contra = 0

        for i in range(len(ultimas)):
            o = opens[i]
            c = closes[i]
            h = highs[i]
            l = lows[i]

            rango = h - l
            cuerpo = abs(c - o)

            if rango <= 0:
                continue

            cuerpos.append(cuerpo / rango)

            if avance > 0:
                mecha_sup = h - max(o, c)
                if mecha_sup >= cuerpo * 1.8:
                    mechas_contra += 1

            if avance < 0:
                mecha_inf = min(o, c) - l
                if mecha_inf >= cuerpo * 1.8:
                    mechas_contra += 1

        cuerpo_promedio = sum(cuerpos) / len(cuerpos) if cuerpos else 0

        # =========================
        # Dirección principal
        # =========================
        if avance > 0:
            direccion = "ALCISTA"
            puntos_direccion = cierres_alcistas + maximos_crecientes + minimos_crecientes
        elif avance < 0:
            direccion = "BAJISTA"
            puntos_direccion = cierres_bajistas + maximos_decrecientes + minimos_decrecientes
        else:
            direccion = "INDEFINIDA"
            puntos_direccion = 0

        fuerza = 0
        fuerza += fuerza_base * 45
        fuerza += min(puntos_direccion, 38)
        fuerza += cuerpo_promedio * 17

        # Penalización por mechas contrarias.
        fuerza -= mechas_contra * 4

        if fuerza < 0:
            fuerza = 0

        if fuerza > 100:
            fuerza = 100

        fuerza = round(fuerza, 2)

        # =========================
        # Agotamiento
        # =========================
        ultimas_5 = ultimas[-5:]
        mechas_agotamiento = 0
        velas_debilitadas = 0

        for cdl in ultimas_5:
            o = float(cdl["open"])
            c = float(cdl["close"])
            h = float(cdl["max"])
            l = float(cdl["min"])

            rango = h - l
            cuerpo = abs(c - o)

            if rango <= 0:
                continue

            if cuerpo <= rango * 0.28:
                velas_debilitadas += 1

            if direccion == "ALCISTA":
                mecha_sup = h - max(o, c)
                if mecha_sup >= cuerpo * 1.8:
                    mechas_agotamiento += 1

            if direccion == "BAJISTA":
                mecha_inf = min(o, c) - l
                if mecha_inf >= cuerpo * 1.8:
                    mechas_agotamiento += 1

        agotada = mechas_agotamiento >= 3 or velas_debilitadas >= 4

        if direccion == "INDEFINIDA":
            estado = "INDEFINIDA"
            razon = "sin avance direccional claro"
        elif agotada and fuerza >= 45:
            estado = direccion + "_AGOTADA"
            razon = "tendencia con señales de agotamiento"
        elif fuerza >= 70:
            estado = direccion + "_FUERTE"
            razon = "tendencia fuerte con avance claro"
        elif fuerza >= 50:
            estado = direccion + "_NORMAL"
            razon = "tendencia operable"
        elif fuerza >= 35:
            estado = direccion + "_DEBIL"
            razon = "tendencia débil o con poco avance"
        else:
            estado = "INDEFINIDA"
            razon = "tendencia demasiado débil"

        return {
            "estado_tendencia": estado,
            "fuerza_tendencia": fuerza,
            "direccion_tendencia": direccion,
            "razon_tendencia": razon,
            "mechas_agotamiento": mechas_agotamiento,
            "velas_debilitadas": velas_debilitadas,
            "fuerza_base": round(fuerza_base, 2),
            "cuerpo_promedio": round(cuerpo_promedio, 2)
        }

    except Exception as e:
        return {
            "estado_tendencia": "ERROR",
            "fuerza_tendencia": 0,
            "direccion_tendencia": "INDEFINIDA",
            "razon_tendencia": "error tendencia avanzada: " + str(e)
        }
def construir_evidencias_mercado(ctx):
    evidencias = []

    tipo_mercado = ctx.get("tipo_mercado", "INDEFINIDO")
    calidad = ctx.get("calidad_mercado", "SIN_DATOS")
    score = ctx.get("score_mercado", 0)
    estado = ctx.get("estado_tendencia", "INDEFINIDA")
    fuerza = ctx.get("fuerza_tendencia", 0)
    direccion_tendencia = ctx.get("direccion_tendencia", "INDEFINIDA")
    regimen = ctx.get("regimen_mercado", "SIN_DATOS")
    riesgo = ctx.get("riesgo_mercado", "MEDIO")

    if direccion_tendencia == "ALCISTA":
        direccion_ev = "CALL"
    elif direccion_tendencia == "BAJISTA":
        direccion_ev = "PUT"
    else:
        direccion_ev = "NEUTRA"

    if tipo_mercado in ["TENDENCIA_ALCISTA", "TENDENCIA_BAJISTA"]:
        evidencias.append({
            "fuente": "mercado",
            "tipo": tipo_mercado,
            "direccion": direccion_ev,
            "peso": 14 if fuerza >= 58 else 8,
            "fuerza": fuerza,
            "confirmada": fuerza >= 50,
            "razon": "mercado en tendencia: " + estado
        })

    if calidad == "LIMPIO":
        evidencias.append({
            "fuente": "mercado",
            "tipo": "MERCADO_LIMPIO",
            "direccion": "NEUTRA",
            "peso": 10,
            "fuerza": score,
            "confirmada": True,
            "razon": "mercado limpio"
        })

    elif calidad == "NORMAL":
        evidencias.append({
            "fuente": "mercado",
            "tipo": "MERCADO_NORMAL",
            "direccion": "NEUTRA",
            "peso": 5,
            "fuerza": score,
            "confirmada": True,
            "razon": "mercado normal operable"
        })

    elif calidad in ["SUCIO", "CAOTICO"]:
        evidencias.append({
            "fuente": "mercado",
            "tipo": "MERCADO_SUCIO",
            "direccion": "NEUTRA",
            "peso": -14,
            "fuerza": score,
            "confirmada": True,
            "razon": "mercado sucio o caótico"
        })

    if "DEBIL" in estado:
        evidencias.append({
            "fuente": "mercado",
            "tipo": "TENDENCIA_DEBIL",
            "direccion": direccion_ev,
            "peso": -8,
            "fuerza": fuerza,
            "confirmada": True,
            "razon": "tendencia débil"
        })

    if "FUERTE" in estado:
        evidencias.append({
            "fuente": "mercado",
            "tipo": "TENDENCIA_FUERTE",
            "direccion": direccion_ev,
            "peso": 10,
            "fuerza": fuerza,
            "confirmada": True,
            "razon": "tendencia fuerte"
        })

    if "AGOTADA" in estado:
        evidencias.append({
            "fuente": "mercado",
            "tipo": "TENDENCIA_AGOTADA",
            "direccion": "NEUTRA",
            "peso": -10,
            "fuerza": fuerza,
            "confirmada": True,
            "razon": "tendencia agotada"
        })

    if regimen in ["EXPANSION_PELIGROSA", "RANGO_SUCIO"]:
        evidencias.append({
            "fuente": "mercado",
            "tipo": regimen,
            "direccion": "NEUTRA",
            "peso": -18,
            "fuerza": 0,
            "confirmada": True,
            "razon": "régimen de mercado riesgoso"
        })

    if regimen == "TENDENCIA_LIMPIA":
        evidencias.append({
            "fuente": "mercado",
            "tipo": "TENDENCIA_LIMPIA",
            "direccion": direccion_ev,
            "peso": 12,
            "fuerza": fuerza,
            "confirmada": True,
            "razon": "tendencia limpia favorable"
        })

    if riesgo == "ALTO":
        evidencias.append({
            "fuente": "mercado",
            "tipo": "RIESGO_MERCADO_ALTO",
            "direccion": "NEUTRA",
            "peso": -12,
            "fuerza": 0,
            "confirmada": True,
            "razon": "riesgo de mercado alto"
        })

    return evidencias