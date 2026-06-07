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
        # TENDENCIA ALCISTA FLEXIBLE
        # =========================
        if (
            promedio_2 > promedio_1
            and closes_ult[-1] > closes_ult[5]
            and velas_verdes >= 9
            and fuerza >= 0.25
        ):
            return "TENDENCIA_ALCISTA", "precio con avance alcista predominante"

        # =========================
        # TENDENCIA BAJISTA FLEXIBLE
        # =========================
        if (
            promedio_2 < promedio_1
            and closes_ult[-1] < closes_ult[5]
            and velas_rojas >= 9
            and fuerza >= 0.25
        ):
            return "TENDENCIA_BAJISTA", "precio con avance bajista predominante"

        # =========================
        # RANGO
        # =========================
        if fuerza < 0.35:
            return "RANGO", "precio lateral o sin avance direccional fuerte"

        # Si no cae en nada, lo tratamos como rango dudoso, no indefinido
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

    direccion_senal = "ALCISTA" if direccion == "call" else "BAJISTA"
    a_favor = direccion_senal == direccion_tendencia

    tendencia_debil = "DEBIL" in estado_tendencia
    tendencia_normal = "NORMAL" in estado_tendencia
    tendencia_fuerte = "FUERTE" in estado_tendencia
    tendencia_indefinida = estado_tendencia == "INDEFINIDA"
    tendencia_agotada = "AGOTADA" in estado_tendencia

    mercado_delicado = (
        tipo_mercado == "RANGO"
        or calidad_mercado == "SUCIO"
        or calidad_mercado == "CAOTICO"
        or tendencia_debil
        or tendencia_indefinida
    )

    # =========================
    # MERCADO CAÓTICO
    # =========================
    if calidad_mercado == "CAOTICO":
        if puntaje >= 24 and (
            "liquidity sweep" in patron
            or "rechazo" in patron
            or rechazo != 0
            or liquidity_sweep != 0
        ):
            return True, "caótico: solo señal premium permitida"

        return False, "mercado caótico: señal no premium bloqueada"

    # =========================
    # CHOCH
    # =========================
    if "choch" in patron:
        if mercado_delicado:
            if puntaje < 20:
                return False, "CHOCH bloqueado: mercado delicado requiere mínimo 22"

            if calidad_mercado == "SUCIO" and puntaje < 21:
                return False, "CHOCH bloqueado: mercado sucio requiere más confirmación"

            if direccion == "call" and cerca_resistencia and rechazo != 1 and liquidity_sweep != 1:
                return False, "CHOCH CALL bloqueado: resistencia cerca sin reacción compradora"

            if direccion == "put" and cerca_soporte and rechazo != -1 and liquidity_sweep != -1:
                return False, "CHOCH PUT bloqueado: soporte cerca sin reacción vendedora"

            return True, "CHOCH permitido en mercado delicado con confirmación"

        if a_favor and puntaje >= 18:
            return True, "CHOCH permitido a favor de tendencia"

        if not a_favor and puntaje >= 23 and (rechazo != 0 or liquidity_sweep != 0):
            return True, "CHOCH contra tendencia permitido por confirmación fuerte"

        return False, "CHOCH bloqueado: sin contexto suficiente"

    # =========================
    # PULLBACK
    # =========================
    if "pullback" in patron:

        if calidad_mercado == "CAOTICO":
            return False, "pullback bloqueado en mercado caótico"
    
        if a_favor and puntaje >= 18:
            return True, "pullback permitido"
    
        return False, "pullback fuera de contexto"
    # =========================
    # LIQUIDITY SWEEP
    # =========================
    if "liquidity sweep" in patron:
        if mercado_delicado:
            if puntaje < 22:
                return False, "sweep bloqueado: mercado delicado requiere mínimo 22"

            if calidad_mercado == "SUCIO" and puntaje < 23:
                return False, "sweep bloqueado: mercado sucio requiere más fuerza"

            if tendencia_debil and not tendencia_agotada and not a_favor:
                return False, "sweep contra tendencia bloqueado: tendencia débil no agotada"

            return True, "sweep permitido con confirmación suficiente"

        if a_favor or tendencia_indefinida:
            if puntaje >= 20:
                return True, "sweep permitido"

        if not a_favor and puntaje >= 23 and (rechazo != 0 or liquidity_sweep != 0):
            return True, "sweep contra tendencia permitido por agotamiento"

        return False, "sweep bloqueado: sin ventaja suficiente"

    # =========================
    # TENDENCIA ALCISTA
    # =========================
    if tipo_mercado == "TENDENCIA_ALCISTA":
        if direccion == "call":
            return True, "CALL permitido a favor de tendencia alcista"

        if direccion == "put":
            if cerca_resistencia and rechazo == -1 and (
                patron_vela == -1 or liquidity_sweep == -1 or puntaje >= 23
            ):
                return True, "PUT contra tendencia permitido por agotamiento alcista"

            return False, "PUT bloqueado contra tendencia alcista sin agotamiento"

    # =========================
    # TENDENCIA BAJISTA
    # =========================
    if tipo_mercado == "TENDENCIA_BAJISTA":
        if direccion == "put":
            return True, "PUT permitido a favor de tendencia bajista"

        if direccion == "call":
            if cerca_soporte and rechazo == 1 and (
                patron_vela == 1 or liquidity_sweep == 1 or puntaje >= 23
            ):
                return True, "CALL contra tendencia permitido por agotamiento bajista"

            return False, "CALL bloqueado contra tendencia bajista sin agotamiento"

    if tipo_mercado == "COMPRESION":
        return False, "mercado en compresión: esperar ruptura"

    if tipo_mercado == "EXPANSION":
        if puntaje >= 23 and ("liquidity sweep" in patron or "rechazo" in patron or rechazo != 0):
            return True, "señal premium permitida en expansión"

        return False, "mercado en expansión: evitar perseguir precio"

    if tipo_mercado == "INDEFINIDO":
        if puntaje >= 22 and ("liquidity sweep" in patron or "rechazo" in patron or rechazo != 0):
            return True, "señal fuerte permitida en indefinido"

        return False, "mercado indefinido: señal débil bloqueada"

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