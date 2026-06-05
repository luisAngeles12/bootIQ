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

    patron = senal.get("patron", "")
    patron_texto = str(patron).lower()
    direccion = senal.get("direccion", "")
    puntaje = senal.get("puntaje", 0)

    cerca_soporte = ctx.get("cerca_soporte", False)
    cerca_resistencia = ctx.get("cerca_resistencia", False)
    rechazo = ctx.get("rechazo", 0)
    patron_vela = ctx.get("patron", 0)
    liquidity_sweep = ctx.get("liquidity_sweep", 0)

    # =========================
    # MERCADO CAÓTICO
    # =========================
    if calidad_mercado == "CAOTICO":

        # Los pullbacks fueron los que más fallaron en mercado caótico.
        if "pullback" in patron_texto:
            return False, "mercado caótico: pullback bloqueado"

        # En caótico no permitimos operaciones contra tendencia.
        if tipo_mercado == "TENDENCIA_ALCISTA" and direccion == "put":
            return False, "mercado caótico: PUT contra tendencia bloqueado"

        if tipo_mercado == "TENDENCIA_BAJISTA" and direccion == "call":
            return False, "mercado caótico: CALL contra tendencia bloqueado"

        # Solo señales premium en mercado caótico.
        if puntaje >= 24 and (
            "liquidity sweep" in patron_texto
            or "rechazo" in patron_texto
            or "choch" in patron_texto
        ):
            return True, "mercado caótico: señal premium permitida"

        return False, "mercado caótico: señal no premium bloqueada"

    # =========================
    # MERCADO EN RANGO
    # =========================
    if tipo_mercado == "RANGO":

        # En rango el pullback se permite solo si viene apoyado por zona/rechazo.
        if "pullback" in patron_texto:
            if puntaje >= 21 and (
                cerca_soporte
                or cerca_resistencia
                or rechazo != 0
                or liquidity_sweep != 0
            ):
                return True, "pullback permitido en rango con zona/rechazo"

            return False, "pullback bloqueado en mercado en rango"

        # CHOCH en rango solo si tiene confirmación fuerte.
        if "choch" in patron_texto:
            if puntaje >= 20 and (
                cerca_soporte
                or cerca_resistencia
                or rechazo != 0
                or liquidity_sweep != 0
            ):
                return True, "CHOCH permitido en rango por zona/rechazo fuerte"

            return False, "CHOCH bloqueado en mercado en rango"

        # CALL en rango: solo abajo del rango o con rechazo/liquidez.
        if direccion == "call":
            if cerca_soporte or rechazo == 1 or liquidity_sweep == 1:
                return True, "CALL permitido en rango por soporte/rechazo/liquidez"

            return False, "CALL bloqueado en rango: no está abajo del rango"

        # PUT en rango: solo arriba del rango o con rechazo/liquidez.
        if direccion == "put":
            if cerca_resistencia or rechazo == -1 or liquidity_sweep == -1:
                return True, "PUT permitido en rango por resistencia/rechazo/liquidez"

            return False, "PUT bloqueado en rango: no está arriba del rango"

    # =========================
    # TENDENCIA ALCISTA
    # =========================
    if tipo_mercado == "TENDENCIA_ALCISTA":

        if direccion == "call":
            return True, "CALL permitido a favor de tendencia alcista"

        if direccion == "put":
            if (
                cerca_resistencia
                and rechazo == -1
                and (
                    patron_vela == -1
                    or liquidity_sweep == -1
                    or puntaje >= 21
                )
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
            if (
                cerca_soporte
                and rechazo == 1
                and (
                    patron_vela == 1
                    or liquidity_sweep == 1
                    or puntaje >= 21
                )
            ):
                return True, "CALL contra tendencia permitido por agotamiento bajista"

            return False, "CALL bloqueado contra tendencia bajista sin agotamiento"

    # =========================
    # COMPRESIÓN
    # =========================
    if tipo_mercado == "COMPRESION":
        return False, "mercado en compresión: esperar ruptura"

    # =========================
    # EXPANSIÓN
    # =========================
    if tipo_mercado == "EXPANSION":
        if puntaje >= 23 and (
            "liquidity sweep" in patron_texto
            or "rechazo" in patron_texto
            or rechazo != 0
        ):
            return True, "señal premium permitida en expansión"

        return False, "mercado en expansión: evitar perseguir precio"

    # =========================
    # INDEFINIDO
    # =========================
    if tipo_mercado == "INDEFINIDO":
        if puntaje >= 21 and (
            "liquidity sweep" in patron_texto
            or "rechazo" in patron_texto
            or rechazo != 0
            or cerca_soporte
            or cerca_resistencia
        ):
            return True, "señal fuerte permitida en mercado indefinido"

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