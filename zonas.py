# Zonas, soportes, resistencias y rupturas

def zonas_reales(highs, lows, minimo_toques=3, tolerancia_base=None):
    precios = [float(x) for x in list(highs) + list(lows)]

    if not precios:
        return []

    precios = sorted(precios)

    if tolerancia_base is None:
        rango_promedio = sum(
            abs(highs[i] - lows[i])
            for i in range(-min(30, len(highs)), 0)
        ) / min(30, len(highs))

        tolerancia_base = rango_promedio * 0.35

    zonas = []

    for precio in precios:
        agregado = False

        for zona in zonas:
            distancia = abs(precio - zona["precio"])

            if distancia <= zona["tolerancia"]:
                zona["precios"].append(precio)
                zona["toques"] += 1
                zona["precio"] = sum(zona["precios"]) / len(zona["precios"])
                agregado = True
                break

        if not agregado:
            zonas.append({
                "precio": precio,
                "toques": 1,
                "precios": [precio],
                "tolerancia": tolerancia_base
            })

    zonas_filtradas = []

    for zona in zonas:
        if zona["toques"] < minimo_toques:
            continue

        precios_zona = zona["precios"]
        amplitud_zona = max(precios_zona) - min(precios_zona)

        # Evita zonas demasiado anchas.
        if amplitud_zona > tolerancia_base * 3:
            continue

        zonas_filtradas.append({
            "precio": zona["precio"],
            "toques": zona["toques"],
            "tolerancia": tolerancia_base,
            "fuerza": zona["toques"],
            "amplitud": amplitud_zona
        })

    zonas_filtradas = sorted(
        zonas_filtradas,
        key=lambda z: z["fuerza"],
        reverse=True
    )

    return zonas_filtradas


def soporte_resistencia_zonas(price, highs, lows, vol):
    if vol <= 0:
        vol = abs(price) * 0.0001

    tolerancia = vol * 0.45

    zonas = zonas_reales(
        highs[-100:],
        lows[-100:],
        minimo_toques=3,
        tolerancia_base=tolerancia
    )

    soportes = []
    resistencias = []

    for zona in zonas:
        distancia = abs(price - zona["precio"])

        # Soporte solo si está claramente debajo del precio.
        if zona["precio"] < price - (tolerancia * 0.35):
            zona["distancia"] = distancia
            soportes.append(zona)

        # Resistencia solo si está claramente encima del precio.
        elif zona["precio"] > price + (tolerancia * 0.35):
            zona["distancia"] = distancia
            resistencias.append(zona)

    if soportes:
        soporte = sorted(
            soportes,
            key=lambda z: (z["distancia"], -z["fuerza"])
        )[0]
    else:
        soporte = {
            "precio": min(lows[-80:]),
            "toques": 1,
            "tolerancia": tolerancia,
            "fuerza": 1,
            "distancia": abs(price - min(lows[-80:])),
            "amplitud": 0
        }

    if resistencias:
        resistencia = sorted(
            resistencias,
            key=lambda z: (z["distancia"], -z["fuerza"])
        )[0]
    else:
        resistencia = {
            "precio": max(highs[-80:]),
            "toques": 1,
            "tolerancia": tolerancia,
            "fuerza": 1,
            "distancia": abs(max(highs[-80:]) - price),
            "amplitud": 0
        }

    # Si soporte y resistencia quedan demasiado cerca,
    # reducimos la tolerancia para evitar señales dobles.
    distancia_sr = abs(resistencia["precio"] - soporte["precio"])

    if distancia_sr <= tolerancia * 2.2:
        if soporte.get("fuerza", 1) > resistencia.get("fuerza", 1):
            resistencia["tolerancia"] = tolerancia * 0.45
        elif resistencia.get("fuerza", 1) > soporte.get("fuerza", 1):
            soporte["tolerancia"] = tolerancia * 0.45
        else:
            soporte["tolerancia"] = tolerancia * 0.40
            resistencia["tolerancia"] = tolerancia * 0.40

    return soporte, resistencia


def triple_rechazo(highs, lows, zona, tipo="soporte", cantidad=25):
    if zona is None:
        return False

    precio_zona = zona["precio"]
    tolerancia = zona["tolerancia"]

    toques = []

    inicio = max(-cantidad, -len(highs))

    for i in range(inicio, 0):
        if tipo == "soporte":
            if abs(lows[i] - precio_zona) <= tolerancia:
                toques.append(i)

        elif tipo == "resistencia":
            if abs(highs[i] - precio_zona) <= tolerancia:
                toques.append(i)

    if len(toques) < 3:
        return False

    # Evita contar tres velas consecutivas como triple rechazo.
    separados = []

    for toque in toques:
        if not separados:
            separados.append(toque)
        else:
            if abs(toque - separados[-1]) >= 3:
                separados.append(toque)

    if len(separados) < 3:
        return False

    return True


def falsa_ruptura(opens, closes, highs, lows, zona, tipo="soporte"):
    if zona is None:
        return 0, "sin falsa ruptura"
    precio_zona = zona["precio"]
    tolerancia = zona["tolerancia"]
    o, c, h, l = opens[-1], closes[-1], highs[-1], lows[-1]
    cuerpo = abs(c - o)
    rango = h - l
    if rango == 0:
        return 0, "sin falsa ruptura"
    fuerza = cuerpo / rango
    mecha_sup = h - max(o, c)
    mecha_inf = min(o, c) - l
    if tipo == "soporte":
        if l < precio_zona - tolerancia and c > precio_zona and mecha_inf >= cuerpo * 2 and c > o and fuerza >= 0.45:
            return 1, "falsa ruptura alcista confirmada"
    if tipo == "resistencia":
        if h > precio_zona + tolerancia and c < precio_zona and mecha_sup >= cuerpo * 2 and c < o and fuerza >= 0.45:
            return -1, "falsa ruptura bajista confirmada"
    return 0, "sin falsa ruptura"


def breakout_retest(opens, closes, highs, lows, zona, tipo="resistencia"):
    if zona is None:
        return 0, "sin breakout retest"
    precio_zona = zona["precio"]
    tolerancia = zona["tolerancia"]
    cierre_actual = closes[-1]
    cierre_anterior = closes[-2]
    low_actual = lows[-1]
    high_actual = highs[-1]
    if tipo == "resistencia":
        if cierre_anterior > precio_zona + tolerancia and abs(low_actual - precio_zona) <= tolerancia and cierre_actual > precio_zona:
            return 1, "breakout retest alcista"
    if tipo == "soporte":
        if cierre_anterior < precio_zona - tolerancia and abs(high_actual - precio_zona) <= tolerancia and cierre_actual < precio_zona:
            return -1, "breakout retest bajista"
    return 0, "sin breakout retest"
def _precio_zona(zona):
    if isinstance(zona, dict):
        return zona.get("precio", 0)
    return zona


def _tolerancia_zona(zona, vol):
    if isinstance(zona, dict):
        return zona.get("tolerancia", vol)
    return vol

def confirmar_ruptura_zona(
    direccion,
    opens,
    closes,
    highs,
    lows,
    soporte,
    resistencia,
    vol
):
    try:
        if len(closes) < 5:
            return {
                "confirmada": False,
                "tipo": "SIN_DATOS",
                "razon": "ruptura: velas insuficientes"
            }

        price = closes[-1]

        if vol <= 0:
            vol = abs(price) * 0.0001

        soporte_precio = _precio_zona(soporte)
        resistencia_precio = _precio_zona(resistencia)

        o = opens[-1]
        c = closes[-1]
        h = highs[-1]
        l = lows[-1]

        rango = h - l
        cuerpo = abs(c - o)

        if rango <= 0:
            return {
                "confirmada": False,
                "tipo": "RANGO_INVALIDO",
                "razon": "ruptura: rango inválido"
            }

        mecha_sup = h - max(o, c)
        mecha_inf = min(o, c) - l

        cuerpo_fuerte = cuerpo >= rango * 0.38

        if direccion == "call":
            rompio = h > resistencia_precio + vol * 0.25
            cerro_encima = c > resistencia_precio + vol * 0.18
            vela_alcista = c > o
            mecha_aceptable = mecha_sup <= max(cuerpo * 1.6, vol * 0.20)

            if rompio and cerro_encima and vela_alcista and cuerpo_fuerte and mecha_aceptable:
                return {
                    "confirmada": True,
                    "tipo": "RUPTURA_RESISTENCIA_CONFIRMADA",
                    "razon": "ruptura real: resistencia rota con cierre fuerte encima"
                }

            if rompio and not cerro_encima:
                return {
                    "confirmada": False,
                    "tipo": "FALSA_RUPTURA_RESISTENCIA",
                    "razon": "falsa ruptura: perforó resistencia pero no confirmó cierre"
                }

            return {
                "confirmada": False,
                "tipo": "SIN_RUPTURA_RESISTENCIA",
                "razon": "sin ruptura confirmada de resistencia"
            }

        if direccion == "put":
            rompio = l < soporte_precio - vol * 0.25
            cerro_debajo = c < soporte_precio - vol * 0.18
            vela_bajista = c < o
            mecha_aceptable = mecha_inf <= max(cuerpo * 1.6, vol * 0.20)

            if rompio and cerro_debajo and vela_bajista and cuerpo_fuerte and mecha_aceptable:
                return {
                    "confirmada": True,
                    "tipo": "RUPTURA_SOPORTE_CONFIRMADA",
                    "razon": "ruptura real: soporte roto con cierre fuerte debajo"
                }

            if rompio and not cerro_debajo:
                return {
                    "confirmada": False,
                    "tipo": "FALSA_RUPTURA_SOPORTE",
                    "razon": "falsa ruptura: perforó soporte pero no confirmó cierre"
                }

            return {
                "confirmada": False,
                "tipo": "SIN_RUPTURA_SOPORTE",
                "razon": "sin ruptura confirmada de soporte"
            }

        return {
            "confirmada": False,
            "tipo": "DIRECCION_INVALIDA",
            "razon": "ruptura: dirección inválida"
        }

    except Exception as e:
        return {
            "confirmada": False,
            "tipo": "ERROR",
            "razon": "error confirmando ruptura: " + str(e)
        }
def entrada_pullback(direccion, price, ema21, soporte, resistencia, vol, patron, rechazo):
    cerca_ema = abs(price - ema21) <= vol * 1.2
    if direccion == "call":
        cerca_soporte = abs(price - soporte) <= vol * 1.5
        if (cerca_ema or cerca_soporte) and (patron == 1 or rechazo == 1):
            return True
    if direccion == "put":
        cerca_resistencia = abs(resistencia - price) <= vol * 1.5
        if (cerca_ema or cerca_resistencia) and (patron == -1 or rechazo == -1):
            return True
    return False


def validar_interaccion_soporte_resistencia(
    direccion,
    opens,
    closes,
    highs,
    lows,
    soporte,
    resistencia,
    vol,
    puntaje,
    patron,
    tipo_mercado,
    calidad_mercado,
    ruptura_confirmada=False,
    tipo_ruptura="SIN_DATOS"
):
    try:
        precio = closes[-1]

        if vol <= 0:
            vol = abs(precio) * 0.0001

        soporte_precio = _precio_zona(soporte)
        resistencia_precio = _precio_zona(resistencia)

        distancia_soporte = abs(precio - soporte_precio)
        distancia_resistencia = abs(resistencia_precio - precio)

        patron_txt = str(patron).lower()
        tipo_ruptura_txt = str(tipo_ruptura).lower()

        es_rango = tipo_mercado in ["RANGO", "COMPRESION", "INDEFINIDO"]
        es_tendencia_alcista = tipo_mercado == "TENDENCIA_ALCISTA"
        es_tendencia_bajista = tipo_mercado == "TENDENCIA_BAJISTA"

        multiplicador_zona = 1.30 if es_rango else 1.10

        cerca_soporte = distancia_soporte <= vol * multiplicador_zona
        cerca_resistencia = distancia_resistencia <= vol * multiplicador_zona

        ruptura_real_resistencia = (
            ruptura_confirmada is True
            and tipo_ruptura_txt == "ruptura_resistencia_confirmada"
        )

        ruptura_real_soporte = (
            ruptura_confirmada is True
            and tipo_ruptura_txt == "ruptura_soporte_confirmada"
        )

        es_retest_alcista = (
            "breakout" in patron_txt
            or "retest" in patron_txt
            or tipo_ruptura_txt == "breakout_retest_alcista"
        )

        es_retest_bajista = (
            "breakout" in patron_txt
            or "retest" in patron_txt
            or tipo_ruptura_txt == "breakout_retest_bajista"
        )

        # =========================
        # CALL cerca de resistencia
        # =========================
        if direccion == "call" and cerca_resistencia:
            if ruptura_real_resistencia or es_retest_alcista:
                return True, "CALL permitido: resistencia rota/retest real confirmado"

            # Permiso flexible: tendencia alcista presionando resistencia.
            if (
                es_tendencia_alcista
                and calidad_mercado in ["LIMPIO", "NORMAL"]
                and puntaje >= 20
            ):
                return True, "CALL permitido con cautela: tendencia alcista presiona resistencia"

            return False, "CALL bloqueado: resistencia cerca sin ruptura confirmada"

        # =========================
        # PUT cerca de soporte
        # =========================
        if direccion == "put" and cerca_soporte:
            if ruptura_real_soporte or es_retest_bajista:
                return True, "PUT permitido: soporte roto/retest real confirmado"

            # Permiso flexible: tendencia bajista presionando soporte.
            if (
                es_tendencia_bajista
                and calidad_mercado in ["LIMPIO", "NORMAL"]
                and puntaje >= 18
            ):
                return True, "PUT permitido con cautela: tendencia bajista presiona soporte"

            return False, "PUT bloqueado: soporte cerca sin ruptura confirmada"

        if direccion == "call" and cerca_soporte:
            return True, "CALL permitido: reacción/zona favorable cerca de soporte"

        if direccion == "put" and cerca_resistencia:
            return True, "PUT permitido: reacción/zona favorable cerca de resistencia"

        if (
            tipo_mercado in ["COMPRESION", "INDEFINIDO"]
            or calidad_mercado in ["SUCIO", "CAOTICO"]
        ):
            if puntaje < 16:
                return False, "zona bloqueada: mercado delicado con puntaje bajo"

        return True, "zona válida"

    except Exception as e:
        return False, "error validando soporte/resistencia: " + str(e)