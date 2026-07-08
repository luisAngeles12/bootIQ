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
    """
    Lee impulso profesional.

    Mejora:
    - Mantiene impulso alcista fuerte porque el histórico lo favorece.
    - Endurece impulso bajista fuerte porque venía flojo.
    - Crea impulsos medios para no forzar todo como FUERTE.
    - Detecta pérdida de fuerza para evitar entrar tarde.
    """
    try:
        if len(closes) < cantidad + 1:
            return {
                "direccion": "NEUTRA",
                "fuerza": 0,
                "tipo": "SIN_DATOS",
                "razon": "impulso: velas insuficientes"
            }

        velas = []

        for i in range(-cantidad, 0):
            v = _vela(opens[i], closes[i], highs[i], lows[i])

            velas.append({
                "verde": v["verde"],
                "roja": v["roja"],
                "fuerza": v["fuerza"],
                "cuerpo": v["cuerpo"],
                "cierre_pos": v["cierre_pos"],
                "mecha_sup_ratio": v["mecha_sup_ratio"],
                "mecha_inf_ratio": v["mecha_inf_ratio"],
                "close": closes[i],
            })

        alcistas = sum(1 for v in velas if v["verde"])
        bajistas = sum(1 for v in velas if v["roja"])

        cuerpos_fuertes = sum(1 for v in velas if v["fuerza"] >= 0.48)
        cuerpos_medios = sum(1 for v in velas if v["fuerza"] >= 0.32)

        fuerza_promedio = sum(v["fuerza"] for v in velas) / cantidad

        cierres_altos = sum(1 for v in velas if v["cierre_pos"] >= 0.58)
        cierres_bajos = sum(1 for v in velas if v["cierre_pos"] <= 0.42)

        mechas_superiores_altas = sum(1 for v in velas if v["mecha_sup_ratio"] >= 0.38)
        mechas_inferiores_altas = sum(1 for v in velas if v["mecha_inf_ratio"] >= 0.38)

        cierre_inicio = velas[0]["close"]
        cierre_final = velas[-1]["close"]

        desplazamiento = abs(cierre_final - cierre_inicio)

        sube = cierre_final > cierre_inicio
        baja = cierre_final < cierre_inicio

        fuerza_inicio = sum(v["fuerza"] for v in velas[:2]) / 2
        fuerza_final = sum(v["fuerza"] for v in velas[-2:]) / 2

        fuerza_decrece = fuerza_final < fuerza_inicio * 0.82

        # =========================
        # IMPULSO ALCISTA
        # =========================
        impulso_alcista_fuerte = (
            alcistas >= 4
            and cuerpos_fuertes >= 3
            and fuerza_promedio >= 0.42
            and cierres_altos >= 3
            and sube
            and not fuerza_decrece
        )

        impulso_alcista_medio = (
            alcistas >= 3
            and cuerpos_medios >= 3
            and fuerza_promedio >= 0.34
            and cierres_altos >= 3
            and sube
        )

        if impulso_alcista_fuerte:
            return {
                "direccion": "CALL",
                "fuerza": round(fuerza_promedio, 3),
                "tipo": "IMPULSO_ALCISTA_FUERTE",
                "razon": "impulso alcista fuerte: avance limpio, cierres altos y fuerza sostenida"
            }

        if impulso_alcista_medio:
            return {
                "direccion": "CALL",
                "fuerza": round(fuerza_promedio, 3),
                "tipo": "IMPULSO_ALCISTA_MEDIO",
                "razon": "impulso alcista medio: avance válido pero no dominante"
            }

        # =========================
        # IMPULSO BAJISTA
        # =========================
        impulso_bajista_fuerte = (
            bajistas >= 4
            and cuerpos_fuertes >= 4
            and fuerza_promedio >= 0.48
            and cierres_bajos >= 4
            and baja
            and not fuerza_decrece
            and mechas_inferiores_altas <= 1
        )

        impulso_bajista_medio = (
            bajistas >= 3
            and cuerpos_medios >= 3
            and fuerza_promedio >= 0.36
            and cierres_bajos >= 3
            and baja
            and mechas_inferiores_altas <= 2
        )

        if impulso_bajista_fuerte:
            return {
                "direccion": "PUT",
                "fuerza": round(fuerza_promedio, 3),
                "tipo": "IMPULSO_BAJISTA_FUERTE",
                "razon": "impulso bajista fuerte: caída limpia, cierres bajos y poca absorción compradora"
            }

        if impulso_bajista_medio:
            return {
                "direccion": "PUT",
                "fuerza": round(fuerza_promedio, 3),
                "tipo": "IMPULSO_BAJISTA_MEDIO",
                "razon": "impulso bajista medio: caída válida pero con fuerza moderada"
            }

        # =========================
        # IMPULSO AGOTADO
        # =========================
        if sube and alcistas >= 3 and fuerza_decrece:
            return {
                "direccion": "CALL",
                "fuerza": round(fuerza_promedio, 3),
                "tipo": "IMPULSO_ALCISTA_AGOTANDOSE",
                "razon": "impulso alcista con pérdida de fuerza"
            }

        if baja and bajistas >= 3 and fuerza_decrece:
            return {
                "direccion": "PUT",
                "fuerza": round(fuerza_promedio, 3),
                "tipo": "IMPULSO_BAJISTA_AGOTANDOSE",
                "razon": "impulso bajista con pérdida de fuerza"
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
    rechazo_historico = rechazo_historico_inteligente(
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
    rechazo_historico_dir = rechazo_historico.get("direccion", "NEUTRA")

    # =========================
    # EVIDENCIA: RECHAZO
    # =========================
    if rechazo.get("confirmado"):
        evidencia = {
            "modulo": "price_action",
            "categoria": "PRICE_ACTION",
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
            "modulo": "price_action",
            "categoria": "PRICE_ACTION",
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
            "modulo": "price_action",
            "categoria": "PRICE_ACTION",    
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
    # EVIDENCIA: RECHAZO HISTÓRICO
    # =========================
    if rechazo_historico_dir != "NEUTRA":
        tipo_hist = rechazo_historico.get("tipo", "RECHAZO_HISTORICO")
        fuerza_hist = rechazo_historico.get("fuerza", 0)
    
        es_confirmado_hist = tipo_hist in [
            "RECHAZO_COMPRADOR_HISTORICO",
            "RECHAZO_VENDEDOR_HISTORICO"
        ]
    
        es_observado_hist = tipo_hist in [
            "RECHAZO_COMPRADOR_OBSERVADO",
            "RECHAZO_VENDEDOR_OBSERVADO"
        ]
    
        if es_confirmado_hist:
            peso_hist = 20
            confirmada_hist = True
        else:
            peso_hist = 8
            confirmada_hist = False
    
        evidencia = {
            "modulo": "price_action",
            "categoria": "PRICE_ACTION",
            "tipo": tipo_hist,
            "direccion": rechazo_historico_dir,
            "peso": peso_hist,
            "fuerza": fuerza_hist,
            "confirmada": confirmada_hist,
            "razon": rechazo_historico.get("razon", "")
        }
    
        evidencias.append(evidencia)
        razones.append(rechazo_historico.get("razon", ""))
    
        if es_confirmado_hist:
            if direccion == "NEUTRA":
                direccion = rechazo_historico_dir
                tipo = tipo_hist
                fuerza += min(0.42, fuerza_hist * 0.25)
    
            elif rechazo_historico_dir == direccion:
                fuerza += min(0.22, fuerza_hist * 0.12)
    
            else:
                contradicciones.append("rechazo histórico confirmado contradice price action")
    
        elif es_observado_hist:
            if direccion == "NEUTRA":
                direccion = rechazo_historico_dir
                tipo = tipo_hist
                fuerza += min(0.24, fuerza_hist * 0.18)
    
            elif rechazo_historico_dir == direccion:
                fuerza += min(0.12, fuerza_hist * 0.08)
    
            else:
                # Observado no debe forzar contradicción fuerte.
                razones.append("rechazo histórico observado contrario, no dominante")
    # =========================
    # CONTRADICCIONES
    # =========================
    if contradicciones:
        evidencias.append({
            "modulo": "price_action",
            "categoria": "PRICE_ACTION",
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
    if fuerza < 0.32:
        direccion = "NEUTRA"
        tipo = "SIN_CONTEXTO_CLARO"
    elif fuerza < 0.45 and direccion != "NEUTRA":
        if not tipo.endswith("_DEBIL") and not tipo.endswith("_OBSERVADO"):
            tipo = tipo + "_DEBIL"
    return {
        "direccion": direccion,
        "tipo": tipo,
        "fuerza": fuerza,
        "rechazo": rechazo,
        "impulso": impulso,
        "agotamiento": agotamiento,
        "rechazo_historico": rechazo_historico,
        "contradicciones": contradicciones,
        "evidencias": evidencias,
        "razon": " | ".join([r for r in razones if r])
    }
def rechazo_historico_inteligente(opens, closes, highs, lows, soporte, resistencia, vol, velas=6):
    """
    Detecta rechazo histórico real.

    Mejora:
    - No basta con ver mechas.
    - Exige zona + reacción + cambio de cierre + estructura mínima.
    - Evita clasificar ruido como rechazo histórico.
    """
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

        datos = []

        for i in range(-velas, 0):
            v = _vela(opens[i], closes[i], highs[i], lows[i])

            datos.append({
                "open": opens[i],
                "close": closes[i],
                "high": highs[i],
                "low": lows[i],
                "verde": v["verde"],
                "roja": v["roja"],
                "fuerza": v["fuerza"],
                "cierre_pos": v["cierre_pos"],
                "mecha_sup_ratio": v["mecha_sup_ratio"],
                "mecha_inf_ratio": v["mecha_inf_ratio"],
            })

        rechazos_call = 0
        rechazos_put = 0
        cierres_call = 0
        cierres_put = 0
        velas_call = 0
        velas_put = 0

        for d in datos:
            cerca_soporte = (
                abs(d["close"] - soporte) <= vol * 1.25
                or abs(d["low"] - soporte) <= vol * 1.25
            )

            cerca_resistencia = (
                abs(resistencia - d["close"]) <= vol * 1.25
                or abs(resistencia - d["high"]) <= vol * 1.25
            )

            if (
                cerca_soporte
                and d["mecha_inf_ratio"] >= 0.42
                and d["cierre_pos"] >= 0.58
                and d["fuerza"] >= 0.16
            ):
                rechazos_call += 1

            if (
                cerca_resistencia
                and d["mecha_sup_ratio"] >= 0.42
                and d["cierre_pos"] <= 0.42
                and d["fuerza"] >= 0.16
            ):
                rechazos_put += 1

            if d["cierre_pos"] >= 0.62:
                cierres_call += 1

            if d["cierre_pos"] <= 0.38:
                cierres_put += 1

            if d["verde"]:
                velas_call += 1

            if d["roja"]:
                velas_put += 1

        primer_cierre = datos[0]["close"]
        ultimo_cierre = datos[-1]["close"]

        desplazamiento = abs(ultimo_cierre - primer_cierre)

        sube = ultimo_cierre > primer_cierre
        baja = ultimo_cierre < primer_cierre

        fuerza_promedio = sum(d["fuerza"] for d in datos) / len(datos)

        estructura_call = (
            rechazos_call >= 2
            and cierres_call >= 3
            and velas_call >= 3
            and sube
            and desplazamiento >= vol * 0.55
            and fuerza_promedio >= 0.18
        )

        estructura_put = (
            rechazos_put >= 2
            and cierres_put >= 3
            and velas_put >= 3
            and baja
            and desplazamiento >= vol * 0.55
            and fuerza_promedio >= 0.18
        )

        if estructura_call and not estructura_put:
            fuerza = min(1, 0.35 + (rechazos_call * 0.12) + (fuerza_promedio * 0.35))

            return {
                "direccion": "CALL",
                "tipo": "RECHAZO_COMPRADOR_HISTORICO",
                "fuerza": round(fuerza, 3),
                "razon": "rechazo comprador histórico real: zona + cierres altos + estructura alcista"
            }

        if estructura_put and not estructura_call:
            fuerza = min(1, 0.35 + (rechazos_put * 0.12) + (fuerza_promedio * 0.35))

            return {
                "direccion": "PUT",
                "tipo": "RECHAZO_VENDEDOR_HISTORICO",
                "fuerza": round(fuerza, 3),
                "razon": "rechazo vendedor histórico real: zona + cierres bajos + estructura bajista"
            }

        # Rechazo débil solo si hay evidencia, pero sin estructura completa.
        if rechazos_call >= 2 and cierres_call >= 2 and velas_call >= 2:
            return {
                "direccion": "CALL",
                "tipo": "RECHAZO_COMPRADOR_OBSERVADO",
                "fuerza": round(min(0.45, 0.18 + rechazos_call * 0.08), 3),
                "razon": "rechazo comprador observado, sin estructura completa"
            }

        if rechazos_put >= 2 and cierres_put >= 2 and velas_put >= 2:
            return {
                "direccion": "PUT",
                "tipo": "RECHAZO_VENDEDOR_OBSERVADO",
                "fuerza": round(min(0.45, 0.18 + rechazos_put * 0.08), 3),
                "razon": "rechazo vendedor observado, sin estructura completa"
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