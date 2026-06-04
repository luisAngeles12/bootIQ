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
