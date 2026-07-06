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
    Más estricto para evitar llamar favorable a rechazos débiles.
    """
    try:
        if len(closes) < 8:
            return {
                "tipo": "SIN_DATOS",
                "direccion": "NEUTRA",
                "confirmado": False,
                "fuerza": 0,
                "razon": "rechazo confirmado: velas insuficientes"
            }

        if vol <= 0:
            vol = abs(closes[-1]) * 0.0001

        o_rej, c_rej, h_rej, l_rej = opens[-2], closes[-2], highs[-2], lows[-2]
        o_conf, c_conf, h_conf, l_conf = opens[-1], closes[-1], highs[-1], lows[-1]

        rej = _vela(o_rej, c_rej, h_rej, l_rej)
        conf = _vela(o_conf, c_conf, h_conf, l_conf)

        precio = closes[-1]
        rango_total = abs(resistencia - soporte)

        if rango_total <= 0:
            rango_total = vol * 2

        posicion_rango = abs(precio - soporte) / rango_total

        cerca_soporte = (
            abs(c_rej - soporte) <= vol * 1.05
            or abs(l_rej - soporte) <= vol * 1.05
        )

        cerca_resistencia = (
            abs(resistencia - c_rej) <= vol * 1.05
            or abs(resistencia - h_rej) <= vol * 1.05
        )

        distancia_resistencia = abs(resistencia - precio)
        distancia_soporte = abs(precio - soporte)

        # =========================
        # RECHAZO COMPRADOR / CALL
        # =========================
        rechazo_comprador = (
            cerca_soporte
            and rej["mecha_inf_ratio"] >= 0.45
            and rej["cierre_pos"] >= 0.58
            and posicion_rango <= 0.62
        )

        confirma_call = (
            conf["verde"]
            and conf["fuerza"] >= 0.38
            and c_conf > c_rej
            and c_conf > o_rej
            and conf["cierre_pos"] >= 0.62
            and distancia_resistencia > vol * 0.70
        )

        sin_rechazo_vendedor_actual = conf["mecha_sup_ratio"] <= 0.42

        if rechazo_comprador and confirma_call and sin_rechazo_vendedor_actual:
            fuerza = (
                rej["mecha_inf_ratio"]
                + conf["fuerza"]
                + conf["cierre_pos"]
            ) / 3

            return {
                "tipo": "RECHAZO_COMPRADOR_CONFIRMADO",
                "direccion": "CALL",
                "confirmado": True,
                "fuerza": round(fuerza, 3),
                "razon": "rechazo comprador confirmado: soporte + cierre alto + confirmación sin resistencia inmediata"
            }

        # =========================
        # RECHAZO VENDEDOR / PUT
        # =========================
        rechazo_vendedor = (
            cerca_resistencia
            and rej["mecha_sup_ratio"] >= 0.42
            and rej["cierre_pos"] <= 0.44
            and posicion_rango >= 0.38
        )

        confirma_put = (
            conf["roja"]
            and conf["fuerza"] >= 0.34
            and c_conf < c_rej
            and c_conf < o_rej
            and conf["cierre_pos"] <= 0.42
            and distancia_soporte > vol * 0.75
        )

        sin_rechazo_comprador_actual = conf["mecha_inf_ratio"] <= 0.45

        if rechazo_vendedor and confirma_put and sin_rechazo_comprador_actual:
            fuerza = (
                rej["mecha_sup_ratio"]
                + conf["fuerza"]
                + (1 - conf["cierre_pos"])
            ) / 3

            return {
                "tipo": "RECHAZO_VENDEDOR_CONFIRMADO",
                "direccion": "PUT",
                "confirmado": True,
                "fuerza": round(fuerza, 3),
                "razon": "rechazo vendedor confirmado: resistencia + cierre bajo + confirmación sin soporte inmediato"
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
        if len(closes) < cantidad + 1:
            return {
                "direccion": "NEUTRA",
                "tipo": "SIN_DATOS",
                "confirmado": False,
                "fuerza": 0,
                "razon": "agotamiento: velas insuficientes"
            }

        if vol <= 0:
            vol = abs(closes[-1]) * 0.0001

        precio = closes[-1]
        rango_total = abs(resistencia - soporte)

        if rango_total <= 0:
            rango_total = vol * 2

        posicion_rango = abs(precio - soporte) / rango_total

        cerca_resistencia = abs(resistencia - precio) <= vol * 1.15
        cerca_soporte = abs(precio - soporte) <= vol * 1.15

        verdes = 0
        rojas = 0
        mechas_sup = 0
        mechas_inf = 0
        cuerpos = []
        fuerzas = []

        for i in range(-cantidad, 0):
            v = _vela(opens[i], closes[i], highs[i], lows[i])

            cuerpos.append(v["cuerpo"])
            fuerzas.append(v["fuerza"])

            if v["verde"]:
                verdes += 1

            if v["roja"]:
                rojas += 1

            if v["mecha_sup_ratio"] >= 0.38:
                mechas_sup += 1

            if v["mecha_inf_ratio"] >= 0.38:
                mechas_inf += 1

        cuerpo_inicio = sum(cuerpos[:3]) / 3
        cuerpo_final = sum(cuerpos[-3:]) / 3

        fuerza_inicio = sum(fuerzas[:3]) / 3
        fuerza_final = sum(fuerzas[-3:]) / 3

        cuerpos_decrecen = cuerpo_final < cuerpo_inicio * 0.82
        fuerza_decrece = fuerza_final < fuerza_inicio * 0.88

        ultima = _vela(opens[-1], closes[-1], highs[-1], lows[-1])

        confirmacion_bajista = (
            ultima["roja"]
            and ultima["cierre_pos"] <= 0.45
            and ultima["mecha_sup_ratio"] >= 0.28
        )

        confirmacion_alcista = (
            ultima["verde"]
            and ultima["cierre_pos"] >= 0.55
            and ultima["mecha_inf_ratio"] >= 0.28
        )

        if (
            cerca_resistencia
            and posicion_rango >= 0.68
            and verdes >= 4
            and mechas_sup >= 3
            and cuerpos_decrecen
            and fuerza_decrece
            and confirmacion_bajista
        ):
            fuerza = min(1, (mechas_sup / cantidad) + (fuerza_inicio - fuerza_final))

            return {
                "direccion": "PUT",
                "tipo": "AGOTAMIENTO_ALCISTA_CONFIRMADO",
                "confirmado": True,
                "fuerza": round(fuerza, 3),
                "razon": "agotamiento alcista confirmado: resistencia + pérdida de fuerza + confirmación bajista"
            }

        if (
            cerca_soporte
            and posicion_rango <= 0.32
            and rojas >= 4
            and mechas_inf >= 3
            and cuerpos_decrecen
            and fuerza_decrece
            and confirmacion_alcista
        ):
            fuerza = min(1, (mechas_inf / cantidad) + (fuerza_inicio - fuerza_final))

            return {
                "direccion": "CALL",
                "tipo": "AGOTAMIENTO_BAJISTA_CONFIRMADO",
                "confirmado": True,
                "fuerza": round(fuerza, 3),
                "razon": "agotamiento bajista confirmado: soporte + pérdida de fuerza + confirmación alcista"
            }

        return {
            "direccion": "NEUTRA",
            "tipo": "SIN_AGOTAMIENTO_CONFIRMADO",
            "confirmado": False,
            "fuerza": 0,
            "razon": "sin agotamiento confirmado"
        }

    except Exception as e:
        return {
            "direccion": "NEUTRA",
            "tipo": "ERROR",
            "confirmado": False,
            "fuerza": 0,
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
    contradicciones = []
    evidencias = []

    rechazo_dir = rechazo.get("direccion", "NEUTRA")
    impulso_dir = impulso.get("direccion", "NEUTRA")
    agotamiento_dir = agotamiento.get("direccion", "NEUTRA")

    # =========================
    # EVIDENCIA: RECHAZO
    # =========================
    if rechazo.get("confirmado"):
        evidencia = {
            "fuente": "price_action",
            "tipo": rechazo.get("tipo", "RECHAZO_CONFIRMADO"),
            "direccion": rechazo_dir,
            "peso": 30,
            "fuerza": rechazo.get("fuerza", 0),
            "confirmada": True,
            "razon": rechazo.get("razon", "")
        }
        evidencias.append(evidencia)

        direccion = rechazo_dir
        tipo = rechazo.get("tipo", "RECHAZO_CONFIRMADO")
        fuerza += rechazo.get("fuerza", 0)
        razones.append(rechazo.get("razon", ""))

    # =========================
    # EVIDENCIA: AGOTAMIENTO
    # =========================
    if agotamiento.get("confirmado"):
        evidencia = {
            "fuente": "price_action",
            "tipo": agotamiento.get("tipo", "AGOTAMIENTO_CONFIRMADO"),
            "direccion": agotamiento_dir,
            "peso": 26,
            "fuerza": agotamiento.get("fuerza", 0),
            "confirmada": True,
            "razon": agotamiento.get("razon", "")
        }
        evidencias.append(evidencia)

        if direccion == "NEUTRA":
            direccion = agotamiento_dir
            tipo = agotamiento.get("tipo", tipo)
            fuerza += agotamiento.get("fuerza", 0)
            razones.append(agotamiento.get("razon", ""))

        elif agotamiento_dir == direccion:
            fuerza += agotamiento.get("fuerza", 0) * 0.70
            razones.append(agotamiento.get("razon", ""))

        else:
            contradicciones.append("agotamiento contradice rechazo")

    # =========================
    # EVIDENCIA: IMPULSO
    # =========================
    if impulso_dir != "NEUTRA":
        evidencia = {
            "fuente": "price_action",
            "tipo": impulso.get("tipo", "IMPULSO"),
            "direccion": impulso_dir,
            "peso": 18,
            "fuerza": impulso.get("fuerza", 0),
            "confirmada": impulso.get("tipo", "") in [
                "IMPULSO_ALCISTA_FUERTE",
                "IMPULSO_BAJISTA_FUERTE"
            ],
            "razon": impulso.get("razon", "")
        }
        evidencias.append(evidencia)

        razones.append(impulso.get("razon", ""))

        if direccion == "NEUTRA":
            direccion = impulso_dir
            tipo = impulso.get("tipo")
            fuerza += impulso.get("fuerza", 0)

        elif impulso_dir == direccion:
            fuerza += impulso.get("fuerza", 0) * 0.45

        else:
            contradicciones.append("impulso contrario a price action")

    # =========================
    # CONTRADICCIONES
    # =========================
    if contradicciones:
        evidencias.append({
            "fuente": "price_action",
            "tipo": "CONTRADICCION_PA",
            "direccion": "NEUTRA",
            "peso": -22,
            "fuerza": 0,
            "confirmada": True,
            "razon": " | ".join(contradicciones)
        })

        fuerza *= 0.55
        razones.append("contradicciones: " + " | ".join(contradicciones))

        if fuerza < 0.55:
            direccion = "NEUTRA"
            tipo = "PA_CONTRADICTORIO"

    fuerza = round(min(fuerza, 1), 3)

    # Compatibilidad: mantenemos la lógica actual.
    # Todavía no cambiamos comportamiento del bot.
    if fuerza < 0.45:
        direccion = "NEUTRA"
        tipo = "SIN_CONTEXTO_CLARO"

    return {
        "direccion": direccion,
        "tipo": tipo,
        "fuerza": fuerza,
        "rechazo": rechazo,
        "impulso": impulso,
        "agotamiento": agotamiento,
        "contradicciones": contradicciones,
        "evidencias": evidencias,
        "razon": " | ".join([r for r in razones if r])
    }
def rechazo_historico_inteligente(opens, closes, highs, lows, soporte, resistencia, vol, velas=6):
    try:
        if len(closes) < velas + 2:
            return {
                "direccion": "NEUTRA",
                "tipo": "SIN_DATOS",
                "fuerza": 0,
                "razon": "rechazo histórico: velas insuficientes"
            }

        if vol <= 0:
            vol = abs(closes[-1]) * 0.0001

        rechazos_compradores = 0
        rechazos_vendedores = 0
        cierres_altos = 0
        cierres_bajos = 0

        for i in range(-velas, 0):
            o = opens[i]
            c = closes[i]
            h = highs[i]
            l = lows[i]

            rango = h - l
            if rango <= 0:
                continue

            cuerpo = abs(c - o)
            mecha_sup = h - max(o, c)
            mecha_inf = min(o, c) - l

            cierre_pos = (c - l) / rango

            cerca_soporte = abs(c - soporte) <= vol * 1.80 or abs(l - soporte) <= vol * 1.80
            cerca_resistencia = abs(resistencia - c) <= vol * 1.80 or abs(resistencia - h) <= vol * 1.80

            if cerca_soporte and mecha_inf / rango >= 0.35 and cierre_pos >= 0.55:
                rechazos_compradores += 1

            if cerca_resistencia and mecha_sup / rango >= 0.35 and cierre_pos <= 0.45:
                rechazos_vendedores += 1

            if cierre_pos >= 0.65:
                cierres_altos += 1

            if cierre_pos <= 0.35:
                cierres_bajos += 1

        if rechazos_compradores >= 2 and cierres_altos >= 2:
            return {
                "direccion": "CALL",
                "tipo": "RECHAZO_COMPRADOR_HISTORICO",
                "fuerza": rechazos_compradores,
                "razon": "rechazo comprador confirmado por varias velas previas"
            }

        if rechazos_vendedores >= 2 and cierres_bajos >= 2:
            return {
                "direccion": "PUT",
                "tipo": "RECHAZO_VENDEDOR_HISTORICO",
                "fuerza": rechazos_vendedores,
                "razon": "rechazo vendedor confirmado por varias velas previas"
            }

        if rechazos_compradores > rechazos_vendedores:
            return {
                "direccion": "CALL",
                "tipo": "RECHAZO_COMPRADOR_DEBIL",
                "fuerza": rechazos_compradores,
                "razon": "hay rechazo comprador, pero no está plenamente confirmado"
            }

        if rechazos_vendedores > rechazos_compradores:
            return {
                "direccion": "PUT",
                "tipo": "RECHAZO_VENDEDOR_DEBIL",
                "fuerza": rechazos_vendedores,
                "razon": "hay rechazo vendedor, pero no está plenamente confirmado"
            }

        return {
            "direccion": "NEUTRA",
            "tipo": "SIN_RECHAZO_HISTORICO",
            "fuerza": 0,
            "razon": "sin rechazo histórico dominante"
        }

    except Exception as e:
        return {
            "direccion": "ERROR",
            "tipo": "ERROR",
            "fuerza": 0,
            "razon": "error rechazo histórico: " + str(e)
        }