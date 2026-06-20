
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
        # TENDENCIA ALCISTA FLEXIBLE
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
        # TENDENCIA BAJISTA FLEXIBLE
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
        or puntaje >= 23
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
            if cerca_resistencia and puntaje < 21:
                return False, "CHOCH CALL bloqueado: resistencia cerca requiere ruptura/retest o puntaje >= 22"

        if "choch bajista" in patron and direccion == "put":
            if cerca_soporte and puntaje < 21:
                return False, "CHOCH PUT bloqueado: soporte cerca requiere ruptura/retest o puntaje >= 22"

        if a_favor:
            if mercado_delicado and puntaje < 20:
                return False, "CHOCH bloqueado: mercado delicado requiere mínimo 20"

            if puntaje >= 22 and confirmacion_fuerte:
                return True, "CHOCH permitido a favor de tendencia con confirmación"
            
            if (
                puntaje >= 22
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
            if puntaje < 18:
                return False, "pullback alcista requiere mínimo 18 puntos"
    
            if rechazo != 1 and patron_vela != 1:
                return False, "pullback alcista requiere rechazo o patrón alcista"
    
            return True, "pullback alcista permitido con filtro reforzado"
    
        if "pullback bajista" in patron:
            if tipo_mercado not in ["TENDENCIA_BAJISTA", "RANGO", "INDEFINIDO"]:
                return False, "pullback bajista requiere tendencia bajista, rango o indefinido operable"
            
            if tipo_mercado == "INDEFINIDO":
                if not (
                    direccion_tendencia == "BAJISTA"
                    and estado_tendencia in ["BAJISTA_NORMAL", "BAJISTA_FUERTE"]
                    and calidad_mercado in ["LIMPIO", "NORMAL"]
                ):
                    return False, "pullback bajista bloqueado: indefinido sin tendencia bajista real"
            if calidad_mercado not in ["LIMPIO", "NORMAL"]:
                return False, "pullback bajista requiere mercado operable"
    
            if puntaje < 18:
                return False, "pullback bajista requiere mínimo 16 puntos"
    
            return True, "pullback bajista permitido"
    
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
    
        if "choch" in patron and puntaje >= 22 and calidad_mercado in ["LIMPIO", "NORMAL"]:
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