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
        cuerpo_fuerte = cuerpo >= rango * 0.42

        if direccion == "call":
            rompio = h > resistencia + vol * 0.25
            cerro_encima = c > resistencia + vol * 0.20
            vela_alcista = c > o
            mecha_aceptable = mecha_sup <= cuerpo * 1.4

            ruptura_excesiva = (c - resistencia) > (vol * 1.60)

            if (
                rompio
                and cerro_encima
                and vela_alcista
                and cuerpo_fuerte
                and mecha_aceptable
                and not ruptura_excesiva
            ):
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
            rompio = l < soporte - vol * 0.25
            cerro_debajo = c < soporte - vol * 0.20
            vela_bajista = c < o
            mecha_aceptable = mecha_inf <= cuerpo * 1.4

            ruptura_excesiva = (soporte - c) > (vol * 1.60)

            if (
                rompio
                and cerro_debajo
                and vela_bajista
                and cuerpo_fuerte
                and mecha_aceptable
                and not ruptura_excesiva
            ):
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
def resolver_zona_pendiente(
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
        ruptura = confirmar_ruptura_zona(
            direccion,
            opens,
            closes,
            highs,
            lows,
            soporte,
            resistencia,
            vol
        )

        if ruptura.get("confirmada", False):
            return {
                "estado": "OPERAR",
                "tipo": ruptura.get("tipo", "RUPTURA_CONFIRMADA"),
                "razon": ruptura.get("razon", "ruptura confirmada")
            }

        if len(closes) < 5:
            return {
                "estado": "ESPERAR",
                "tipo": "SIN_DATOS",
                "razon": "zona pendiente: velas insuficientes"
            }

        price = closes[-1]

        if vol <= 0:
            vol = abs(price) * 0.0001

        o = opens[-1]
        c = closes[-1]
        h = highs[-1]
        l = lows[-1]

        o_prev = opens[-2]
        c_prev = closes[-2]
        h_prev = highs[-2]
        l_prev = lows[-2]

        rango = h - l
        cuerpo = abs(c - o)

        if rango <= 0:
            return {
                "estado": "ESPERAR",
                "tipo": "RANGO_INVALIDO",
                "razon": "zona pendiente: rango inválido"
            }

        mecha_sup = h - max(o, c)
        mecha_inf = min(o, c) - l

        fuerza = cuerpo / rango

        cerca_resistencia = abs(resistencia - c) <= vol * 1.25
        cerca_soporte = abs(c - soporte) <= vol * 1.25

        vela_roja = c < o
        vela_verde = c > o

        # =========================
        # RECHAZOS CONTRARIOS
        # =========================
        rechazo_vendedor = (
            cerca_resistencia
            and vela_roja
            and mecha_sup >= cuerpo * 1.3
            and fuerza >= 0.16
        )

        rechazo_comprador = (
            cerca_soporte
            and vela_verde
            and mecha_inf >= cuerpo * 1.3
            and fuerza >= 0.16
        )

        falsa_resistencia = falsa_ruptura(
            opens,
            closes,
            highs,
            lows,
            resistencia,
            "resistencia"
        )

        falsa_soporte = falsa_ruptura(
            opens,
            closes,
            highs,
            lows,
            soporte,
            "soporte"
        )

        # =========================
        # CONTINUACIÓN CONTROLADA
        # =========================
        continuacion_call = (
            direccion == "call"
            and vela_verde
            and c > c_prev
            and fuerza >= 0.16
            and fuerza <= 0.68
            and not cerca_resistencia
        )

        continuacion_put = (
            direccion == "put"
            and vela_roja
            and c < c_prev
            and fuerza >= 0.16
            and fuerza <= 0.68
            and not cerca_soporte
        )

        # =========================
        # PULLBACK RESPETADO
        # =========================
        pullback_call = (
            direccion == "call"
            and cerca_soporte
            and vela_verde
            and mecha_inf >= cuerpo * 0.8
            and fuerza >= 0.14
        )

        pullback_put = (
            direccion == "put"
            and cerca_resistencia
            and vela_roja
            and mecha_sup >= cuerpo * 0.8
            and fuerza >= 0.14
        )

        # =========================
        # CALL
        # =========================
        if direccion == "call":
            if rechazo_vendedor or falsa_resistencia[0] == -1:
                return {
                    "estado": "OPERAR_CONTRARIO",
                    "direccion": "put",
                    "tipo": "RECHAZO_RESISTENCIA",
                    "razon": "PUT contrario: rechazo vendedor/falsa ruptura en resistencia"
                }
            if pullback_call:
                return {
                    "estado": "OPERAR",
                    "tipo": "PULLBACK_SOPORTE_CONFIRMADO",
                    "razon": "CALL operar: pullback respetó soporte con reacción compradora"
                }

            if continuacion_call:
                return {
                    "estado": "OPERAR",
                    "tipo": "CONTINUACION_CALL",
                    "razon": "CALL operar: continuación alcista controlada"
                }

            return {
                "estado": "ESPERAR",
                "tipo": ruptura.get("tipo", "SIN_RUPTURA_RESISTENCIA"),
                "razon": ruptura.get("razon", "esperando ruptura/reacción alcista")
            }

        # =========================
        # PUT
        # =========================
        if direccion == "put":
            if rechazo_comprador or falsa_soporte[0] == 1:
                return {
                    "estado": "OPERAR_CONTRARIO",
                    "direccion": "call",
                    "tipo": "RECHAZO_SOPORTE",
                    "razon": "CALL contrario: rechazo comprador/falsa ruptura en soporte"
                }

            if pullback_put:
                return {
                    "estado": "OPERAR",
                    "tipo": "PULLBACK_RESISTENCIA_CONFIRMADO",
                    "razon": "PUT operar: pullback respetó resistencia con reacción vendedora"
                }

            if continuacion_put:
                return {
                    "estado": "OPERAR",
                    "tipo": "CONTINUACION_PUT",
                    "razon": "PUT operar: continuación bajista controlada"
                }

            return {
                "estado": "ESPERAR",
                "tipo": ruptura.get("tipo", "SIN_RUPTURA_SOPORTE"),
                "razon": ruptura.get("razon", "esperando ruptura/reacción bajista")
            }

        return {
            "estado": "CANCELAR",
            "tipo": "DIRECCION_INVALIDA",
            "razon": "zona pendiente: dirección inválida"
        }

    except Exception as e:
        return {
            "estado": "ESPERAR",
            "tipo": "ERROR",
            "razon": "error resolviendo zona pendiente: " + str(e)
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

        distancia_soporte = abs(precio - soporte)
        distancia_resistencia = abs(resistencia - precio)

        cerca_soporte = distancia_soporte <= vol * 0.75
        cerca_resistencia = distancia_resistencia <= vol * 0.75

        patron_txt = str(patron).lower()

        mercado_delicado = (
            tipo_mercado in ["RANGO", "COMPRESION", "EXPANSION", "INDEFINIDO"]
            or calidad_mercado in ["SUCIO", "CAOTICO"]
        )

        es_retest = (
            "breakout" in patron_txt
            or "retest" in patron_txt
            or tipo_ruptura in [
                "RUPTURA_RESISTENCIA_CONFIRMADA",
                "RUPTURA_SOPORTE_CONFIRMADA"
            ]
        )

        # =========================
        # CALL cerca de resistencia
        # =========================
        if direccion == "call" and cerca_resistencia:
            if ruptura_confirmada or es_retest:
                return True, "CALL permitido: resistencia rota/retest confirmado"
        
            if puntaje >= 18 and calidad_mercado in ["LIMPIO", "NORMAL"]:
                return True, "CALL permitido: señal fuerte cerca de resistencia"
        
            return False, "CALL bloqueado: resistencia cerca sin ruptura confirmada"
        # =========================
        # PUT cerca de soporte
        # =========================
        if direccion == "put" and cerca_soporte:
            if ruptura_confirmada or es_retest:
                return True, "PUT permitido: soporte roto/retest confirmado"
        
            if puntaje >= 18 and calidad_mercado in ["LIMPIO", "NORMAL"]:
                return True, "PUT permitido: señal fuerte cerca de soporte"
        
            return False, "PUT bloqueado: soporte cerca sin ruptura confirmada"
        # =========================
        # ZONA FAVORABLE
        # =========================
        if direccion == "call" and cerca_soporte:
            return True, "CALL permitido: cerca de soporte"

        if direccion == "put" and cerca_resistencia:
            return True, "PUT permitido: cerca de resistencia"

        if mercado_delicado and puntaje < 20:
            return False, "zona bloqueada: mercado delicado requiere mejor confirmación"

        return True, "zona válida"

    except Exception as e:
        return False, "error validando soporte/resistencia: " + str(e)
def evaluar_fuerza_zona(zona):
    if zona is None:
        return "DEBIL"

    toques = zona.get("toques", 0)

    if toques >= 6:
        return "MUY_FUERTE"

    if toques >= 4:
        return "FUERTE"

    if toques >= 3:
        return "MEDIA"

    return "DEBIL"

def evaluar_memoria_zona(
    opens,
    closes,
    highs,
    lows,
    precio_zona,
    vol,
    tipo="resistencia",
    lookback=80
):
    try:
        if len(closes) < 20:
            return {
                "rechazos": 0,
                "rupturas": 0,
                "falsas_rupturas": 0,
                "fuerza": "DEBIL",
                "sesgo": "SIN_DATOS",
                "razon": "memoria zona: velas insuficientes"
            }

        if vol <= 0:
            vol = abs(closes[-1]) * 0.0001

        tolerancia = vol * 1.10

        rechazos = 0
        rupturas = 0
        falsas_rupturas = 0

        inicio = max(-lookback, -len(closes))

        for i in range(inicio, -1):
            o = opens[i]
            c = closes[i]
            h = highs[i]
            l = lows[i]

            rango = h - l
            cuerpo = abs(c - o)

            if rango <= 0:
                continue

            mecha_sup = h - max(o, c)
            mecha_inf = min(o, c) - l

            if tipo == "resistencia":
                toca = abs(h - precio_zona) <= tolerancia or h >= precio_zona

                if toca and c < precio_zona and c < o and mecha_sup >= cuerpo * 1.1:
                    rechazos += 1

                if c > precio_zona + (vol * 0.30):
                    rupturas += 1

                if h > precio_zona + (vol * 0.25) and c < precio_zona:
                    falsas_rupturas += 1

            if tipo == "soporte":
                toca = abs(l - precio_zona) <= tolerancia or l <= precio_zona

                if toca and c > precio_zona and c > o and mecha_inf >= cuerpo * 1.1:
                    rechazos += 1

                if c < precio_zona - (vol * 0.30):
                    rupturas += 1

                if l < precio_zona - (vol * 0.25) and c > precio_zona:
                    falsas_rupturas += 1

        if rechazos >= 5:
            fuerza = "MUY_FUERTE"
        elif rechazos >= 3:
            fuerza = "FUERTE"
        elif rechazos >= 2:
            fuerza = "MEDIA"
        else:
            fuerza = "DEBIL"

        if rechazos > rupturas:
            sesgo = "RECHAZO"
        elif rupturas > rechazos:
            sesgo = "RUPTURA"
        else:
            sesgo = "NEUTRO"

        return {
            "rechazos": rechazos,
            "rupturas": rupturas,
            "falsas_rupturas": falsas_rupturas,
            "fuerza": fuerza,
            "sesgo": sesgo,
            "razon": f"memoria zona: {rechazos} rechazos, {rupturas} rupturas, {falsas_rupturas} falsas rupturas"
        }

    except Exception as e:
        return {
            "rechazos": 0,
            "rupturas": 0,
            "falsas_rupturas": 0,
            "fuerza": "ERROR",
            "sesgo": "ERROR",
            "razon": "error memoria zona: " + str(e)
        }
