def _vela(o, c, h, l):
    rango = h - l
    cuerpo = abs(c - o)

    if rango <= 0:
        rango = 0.0000001

    mecha_sup = h - max(o, c)
    mecha_inf = min(o, c) - l

    return {
        "rango": rango,
        "cuerpo": cuerpo,
        "fuerza": cuerpo / rango,
        "mecha_sup": mecha_sup,
        "mecha_inf": mecha_inf,
        "mecha_sup_ratio": mecha_sup / rango,
        "mecha_inf_ratio": mecha_inf / rango,
        "verde": c > o,
        "roja": c < o,
        "cierre_pos": (c - l) / rango,
    }


def rechazo_confirmado(opens, closes, highs, lows, soporte, resistencia, vol):
    """
    Detecta rechazo real + confirmación.
    No mira solo una vela. Mira rechazo y continuidad.
    """
    try:
        if len(closes) < 6:
            return {
                "tipo": "SIN_DATOS",
                "direccion": "NEUTRA",
                "confirmado": False,
                "fuerza": 0,
                "razon": "rechazo confirmado: velas insuficientes"
            }

        if vol <= 0:
            vol = abs(closes[-1]) * 0.0001

        # vela de rechazo = penúltima
        o_rej = opens[-2]
        c_rej = closes[-2]
        h_rej = highs[-2]
        l_rej = lows[-2]

        # vela de confirmación = última
        o_conf = opens[-1]
        c_conf = closes[-1]
        h_conf = highs[-1]
        l_conf = lows[-1]

        rej = _vela(o_rej, c_rej, h_rej, l_rej)
        conf = _vela(o_conf, c_conf, h_conf, l_conf)

        cerca_soporte = abs(c_rej - soporte) <= vol * 1.35 or abs(l_rej - soporte) <= vol * 1.35
        cerca_resistencia = abs(resistencia - c_rej) <= vol * 1.35 or abs(resistencia - h_rej) <= vol * 1.35

        rechazo_comprador = (
            cerca_soporte
            and rej["mecha_inf_ratio"] >= 0.38
            and rej["cierre_pos"] >= 0.52
        )

        confirma_call = (
            conf["verde"]
            and c_conf > c_rej
            and c_conf >= l_conf + (conf["rango"] * 0.55)
        )

        if rechazo_comprador and confirma_call:
            fuerza = (
                rej["mecha_inf_ratio"]
                + conf["fuerza"]
            ) / 2

            return {
                "tipo": "RECHAZO_COMPRADOR_CONFIRMADO",
                "direccion": "CALL",
                "confirmado": True,
                "fuerza": round(fuerza, 3),
                "razon": "rechazo comprador confirmado: soporte + recuperación + vela de confirmación"
            }

        rechazo_vendedor = (
            cerca_resistencia
            and rej["mecha_sup_ratio"] >= 0.38
            and rej["cierre_pos"] <= 0.48
        )

        confirma_put = (
            conf["roja"]
            and c_conf < c_rej
            and c_conf <= h_conf - (conf["rango"] * 0.55)
        )

        if rechazo_vendedor and confirma_put:
            fuerza = (
                rej["mecha_sup_ratio"]
                + conf["fuerza"]
            ) / 2

            return {
                "tipo": "RECHAZO_VENDEDOR_CONFIRMADO",
                "direccion": "PUT",
                "confirmado": True,
                "fuerza": round(fuerza, 3),
                "razon": "rechazo vendedor confirmado: resistencia + rechazo + vela de confirmación"
            }

        return {
            "tipo": "SIN_RECHAZO_CONFIRMADO",
            "direccion": "NEUTRA",
            "confirmado": False,
            "fuerza": 0,
            "razon": "sin rechazo confirmado"
        }

    except Exception as e:
        return {
            "tipo": "ERROR",
            "direccion": "NEUTRA",
            "confirmado": False,
            "fuerza": 0,
            "razon": "error rechazo confirmado: " + str(e)
        }


def impulso_profesional(opens, closes, highs, lows, cantidad=5):
    try:
        if len(closes) < cantidad:
            return {
                "direccion": "NEUTRA",
                "fuerza": 0,
                "tipo": "SIN_DATOS",
                "razon": "impulso: velas insuficientes"
            }

        alcistas = 0
        bajistas = 0
        cuerpos_fuertes = 0
        fuerza_total = 0

        for i in range(-cantidad, 0):
            v = _vela(opens[i], closes[i], highs[i], lows[i])

            fuerza_total += v["fuerza"]

            if v["verde"]:
                alcistas += 1

            if v["roja"]:
                bajistas += 1

            if v["fuerza"] >= 0.48:
                cuerpos_fuertes += 1

        fuerza_promedio = fuerza_total / cantidad

        if alcistas >= 4 and cuerpos_fuertes >= 3 and fuerza_promedio >= 0.42:
            return {
                "direccion": "CALL",
                "fuerza": round(fuerza_promedio, 3),
                "tipo": "IMPULSO_ALCISTA_FUERTE",
                "razon": "impulso alcista fuerte: mayoría de velas verdes con cuerpo real"
            }

        if bajistas >= 4 and cuerpos_fuertes >= 3 and fuerza_promedio >= 0.42:
            return {
                "direccion": "PUT",
                "fuerza": round(fuerza_promedio, 3),
                "tipo": "IMPULSO_BAJISTA_FUERTE",
                "razon": "impulso bajista fuerte: mayoría de velas rojas con cuerpo real"
            }

        return {
            "direccion": "NEUTRA",
            "fuerza": round(fuerza_promedio, 3),
            "tipo": "IMPULSO_DEBIL",
            "razon": "impulso débil o mixto"
        }

    except Exception as e:
        return {
            "direccion": "NEUTRA",
            "fuerza": 0,
            "tipo": "ERROR",
            "razon": "error impulso profesional: " + str(e)
        }


def agotamiento_profesional(opens, closes, highs, lows, soporte, resistencia, vol, cantidad=6):
    try:
        if len(closes) < cantidad:
            return {
                "direccion": "NEUTRA",
                "tipo": "SIN_DATOS",
                "confirmado": False,
                "razon": "agotamiento: velas insuficientes"
            }

        if vol <= 0:
            vol = abs(closes[-1]) * 0.0001

        precio = closes[-1]

        cerca_resistencia = abs(resistencia - precio) <= vol * 1.40
        cerca_soporte = abs(precio - soporte) <= vol * 1.40

        verdes = 0
        rojas = 0
        mechas_sup = 0
        mechas_inf = 0
        cuerpos = []

        for i in range(-cantidad, 0):
            v = _vela(opens[i], closes[i], highs[i], lows[i])

            cuerpos.append(v["cuerpo"])

            if v["verde"]:
                verdes += 1

            if v["roja"]:
                rojas += 1

            if v["mecha_sup_ratio"] >= 0.35:
                mechas_sup += 1

            if v["mecha_inf_ratio"] >= 0.35:
                mechas_inf += 1

        cuerpos_decrecen = cuerpos[-1] < cuerpos[0] if cuerpos else False

        if cerca_resistencia and verdes >= 4 and mechas_sup >= 3 and cuerpos_decrecen:
            return {
                "direccion": "PUT",
                "tipo": "AGOTAMIENTO_ALCISTA_CONFIRMADO",
                "confirmado": True,
                "razon": "agotamiento alcista confirmado: resistencia + avance cansado + mechas superiores"
            }

        if cerca_soporte and rojas >= 4 and mechas_inf >= 3 and cuerpos_decrecen:
            return {
                "direccion": "CALL",
                "tipo": "AGOTAMIENTO_BAJISTA_CONFIRMADO",
                "confirmado": True,
                "razon": "agotamiento bajista confirmado: soporte + caída cansada + mechas inferiores"
            }

        return {
            "direccion": "NEUTRA",
            "tipo": "SIN_AGOTAMIENTO_CONFIRMADO",
            "confirmado": False,
            "razon": "sin agotamiento confirmado"
        }

    except Exception as e:
        return {
            "direccion": "NEUTRA",
            "tipo": "ERROR",
            "confirmado": False,
            "razon": "error agotamiento profesional: " + str(e)
        }


def contexto_price_action_profesional(opens, closes, highs, lows, soporte, resistencia, vol):
    rechazo = rechazo_confirmado(
        opens,
        closes,
        highs,
        lows,
        soporte,
        resistencia,
        vol
    )

    impulso = impulso_profesional(
        opens,
        closes,
        highs,
        lows,
        5
    )

    agotamiento = agotamiento_profesional(
        opens,
        closes,
        highs,
        lows,
        soporte,
        resistencia,
        vol,
        6
    )

    direccion = "NEUTRA"
    tipo = "SIN_CONTEXTO_CLARO"
    fuerza = 0
    razones = []

    if rechazo.get("confirmado"):
        direccion = rechazo.get("direccion", "NEUTRA")
        tipo = rechazo.get("tipo", "RECHAZO_CONFIRMADO")
        fuerza += rechazo.get("fuerza", 0)
        razones.append(rechazo.get("razon", ""))

    if agotamiento.get("confirmado"):
        direccion = agotamiento.get("direccion", direccion)
        tipo = agotamiento.get("tipo", tipo)
        fuerza += 0.35
        razones.append(agotamiento.get("razon", ""))

    if impulso.get("direccion") != "NEUTRA":
        razones.append(impulso.get("razon", ""))

        if direccion == "NEUTRA":
            direccion = impulso.get("direccion")
            tipo = impulso.get("tipo")
            fuerza += impulso.get("fuerza", 0)

    return {
        "direccion": direccion,
        "tipo": tipo,
        "fuerza": round(fuerza, 3),
        "rechazo": rechazo,
        "impulso": impulso,
        "agotamiento": agotamiento,
        "razon": " | ".join([r for r in razones if r])
    }