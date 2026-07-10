
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
