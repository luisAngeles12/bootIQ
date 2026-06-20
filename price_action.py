# Patrones de velas y lectura de price action

def cuerpo_y_mechas(o, c, h, l):
    cuerpo = abs(c - o)
    rango = h - l
    if rango == 0:
        return 0, 0, 0, 0
    mecha_sup = h - max(o, c)
    mecha_inf = min(o, c) - l
    fuerza = cuerpo / rango
    return cuerpo, mecha_sup, mecha_inf, fuerza


def patron_velas(opens, closes, highs, lows):
    o1, c1 = opens[-1], closes[-1]
    o2, c2 = opens[-2], closes[-2]
    h1, l1 = highs[-1], lows[-1]
    cuerpo = abs(c1 - o1)
    rango = h1 - l1
    if rango == 0:
        return 0, "sin patrón"
    cuerpo_relativo = cuerpo / rango
    mecha_superior = h1 - max(o1, c1)
    mecha_inferior = min(o1, c1) - l1
    if cuerpo_relativo <= 0.18:
        return 99, "doji/indecisión"
    if c2 < o2 and c1 > o1 and c1 > o2 and o1 < c2 and cuerpo_relativo >= 0.40:
        return 1, "envolvente alcista"
    if c2 > o2 and c1 < o1 and c1 < o2 and o1 > c2 and cuerpo_relativo >= 0.40:
        return -1, "envolvente bajista"
    if mecha_inferior > cuerpo * 2 and c1 > o1:
        return 1, "rechazo alcista"
    if mecha_superior > cuerpo * 2 and c1 < o1:
        return -1, "rechazo bajista"
    return 0, "sin patrón"


def rechazo_real(opens, closes, highs, lows):
    o, c, h, l = opens[-1], closes[-1], highs[-1], lows[-1]
    cuerpo = abs(c - o)
    rango = h - l
    if rango == 0:
        return 0, "sin rechazo"
    mecha_sup = h - max(o, c)
    mecha_inf = min(o, c) - l
    if mecha_inf >= cuerpo * 1.8 and c > o:
        return 1, "rechazo comprador fuerte"
    if mecha_sup >= cuerpo * 1.8 and c < o:
        return -1, "rechazo vendedor fuerte"
    return 0, "sin rechazo"


def pin_bar(opens, closes, highs, lows):
    o, c, h, l = opens[-1], closes[-1], highs[-1], lows[-1]
    cuerpo, mecha_sup, mecha_inf, _ = cuerpo_y_mechas(o, c, h, l)
    if cuerpo == 0:
        return 0, "sin pin bar"
    if mecha_inf >= cuerpo * 2.5 and mecha_sup <= cuerpo * 1.2:
        return 1, "pin bar alcista"
    if mecha_sup >= cuerpo * 2.5 and mecha_inf <= cuerpo * 1.2:
        return -1, "pin bar bajista"
    return 0, "sin pin bar"


def martillo_shooting_star(opens, closes, highs, lows):
    o, c, h, l = opens[-1], closes[-1], highs[-1], lows[-1]
    cuerpo, mecha_sup, mecha_inf, _ = cuerpo_y_mechas(o, c, h, l)
    if cuerpo == 0:
        return 0, "sin martillo"
    if mecha_inf >= cuerpo * 2 and mecha_sup <= cuerpo and c > o:
        return 1, "martillo alcista"
    if mecha_sup >= cuerpo * 2 and mecha_inf <= cuerpo and c < o:
        return -1, "shooting star bajista"
    return 0, "sin martillo"


def morning_evening_star(opens, closes, highs, lows):
    o1, c1 = opens[-3], closes[-3]
    o2, c2 = opens[-2], closes[-2]
    o3, c3 = opens[-1], closes[-1]
    h2, l2 = highs[-2], lows[-2]
    cuerpo2 = abs(c2 - o2)
    rango2 = h2 - l2
    if rango2 == 0:
        return 0, "sin estrella"
    vela2_pequena = cuerpo2 / rango2 <= 0.30
    if c1 < o1 and vela2_pequena and c3 > o3 and c3 > ((o1 + c1) / 2):
        return 1, "morning star alcista"
    if c1 > o1 and vela2_pequena and c3 < o3 and c3 < ((o1 + c1) / 2):
        return -1, "evening star bajista"
    return 0, "sin estrella"


def master_candle(highs, lows, lookback=4):
    h_master = highs[-lookback - 1]
    l_master = lows[-lookback - 1]
    dentro = 0
    for i in range(-lookback, 0):
        if highs[i] <= h_master and lows[i] >= l_master:
            dentro += 1
    if dentro == lookback:
        return True, h_master, l_master, "master candle"
    return False, None, None, "sin master candle"


def ruptura_master_candle(closes, highs, lows):
    es_master, h_master, l_master, _ = master_candle(highs, lows, 4)
    if not es_master:
        return 0, "sin ruptura master"
    if closes[-1] > h_master:
        return 1, "ruptura alcista de master candle"
    if closes[-1] < l_master:
        return -1, "ruptura bajista de master candle"
    return 0, "sin ruptura master"


def patron_price_action_avanzado(opens, closes, highs, lows):
    patrones = []
    for detector, peso in [(morning_evening_star, 5), (pin_bar, 5), (martillo_shooting_star, 4), (patron_velas, 3)]:
        p, n = detector(opens, closes, highs, lows)
        if p != 0 and p != 99:
            patrones.append((p, n, peso))
    p, n = ruptura_master_candle(closes, highs, lows)
    if p != 0:
        patrones.append((p, n, 4))
    if not patrones:
        return 0, "sin patrón", 0
    patrones = sorted(patrones, key=lambda x: x[2], reverse=True)
    return patrones[0]

def diagnostico_accion_precio_zona(
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
                "accion": "SIN_DATOS",
                "permite": True,
                "razon": "acción precio: velas insuficientes"
            }

        if vol <= 0:
            vol = abs(closes[-1]) * 0.0001

        o = opens[-1]
        c = closes[-1]
        h = highs[-1]
        l = lows[-1]

        o_prev = opens[-2]
        c_prev = closes[-2]

        rango = h - l
        cuerpo = abs(c - o)

        if rango <= 0:
            return {
                "accion": "RANGO_INVALIDO",
                "permite": True,
                "razon": "acción precio: rango inválido"
            }

        mecha_sup = h - max(o, c)
        mecha_inf = min(o, c) - l

        margen = vol * 0.30

        cerca_resistencia = abs(resistencia - c) <= vol * 1.20
        cerca_soporte = abs(c - soporte) <= vol * 1.20

        ruptura_alcista = c > resistencia + margen
        ruptura_bajista = c < soporte - margen

        rechazo_vendedor = (
            cerca_resistencia
            and mecha_sup >= cuerpo * 1.8
            and c < o
        )

        rechazo_comprador = (
            cerca_soporte
            and mecha_inf >= cuerpo * 1.8
            and c > o
        )

        falsa_ruptura_alcista = (
            h > resistencia + margen
            and c < resistencia
            and mecha_sup >= cuerpo * 1.2
        )

        falsa_ruptura_bajista = (
            l < soporte - margen
            and c > soporte
            and mecha_inf >= cuerpo * 1.2
        )

        # =========================
        # CALL
        # =========================
        if direccion == "call":

            if falsa_ruptura_alcista:
                return {
                    "accion": "FALSA_RUPTURA_RESISTENCIA",
                    "permite": False,
                    "razon": "acción precio: falsa ruptura alcista en resistencia"
                }

            if ruptura_alcista:
                return {
                    "accion": "RUPTURA_ALCISTA_CONFIRMADA",
                    "permite": True,
                    "razon": "acción precio: resistencia rota con cierre encima"
                }

            if cerca_resistencia:
                return {
                    "accion": "CALL_RESISTENCIA_CERCA_SIN_RUPTURA",
                    "permite": True,
                    "requiere_pendiente": True,
                    "razon": "acción precio: CALL con resistencia cerca; decisión delegada a zonas"
                }
            if rechazo_comprador:
                return {
                    "accion": "RECHAZO_COMPRADOR_SOPORTE",
                    "permite": True,
                    "razon": "acción precio: rechazo comprador en soporte"
                }

            return {
                "accion": "CALL_ZONA_NEUTRA",
                "permite": True,
                "razon": "acción precio: CALL sin conflicto fuerte de zona"
            }

        # =========================
        # PUT
        # =========================
        if direccion == "put":

            if falsa_ruptura_bajista:
                return {
                    "accion": "FALSA_RUPTURA_SOPORTE",
                    "permite": False,
                    "razon": "acción precio: falsa ruptura bajista en soporte"
                }

            if ruptura_bajista:
                return {
                    "accion": "RUPTURA_BAJISTA_CONFIRMADA",
                    "permite": True,
                    "razon": "acción precio: soporte roto con cierre debajo"
                }

            if cerca_soporte:
                return {
                    "accion": "PUT_SOPORTE_CERCA_SIN_RUPTURA",
                    "permite": True,
                    "requiere_pendiente": True,
                    "razon": "acción precio: PUT con soporte cerca; decisión delegada a zonas"
                }

            if rechazo_vendedor:
                return {
                    "accion": "RECHAZO_VENDEDOR_RESISTENCIA",
                    "permite": True,
                    "razon": "acción precio: rechazo vendedor en resistencia"
                }

            return {
                "accion": "PUT_ZONA_NEUTRA",
                "permite": True,
                "razon": "acción precio: PUT sin conflicto fuerte de zona"
            }

        return {
            "accion": "DIRECCION_INVALIDA",
            "permite": True,
            "razon": "acción precio: dirección inválida"
        }

    except Exception as e:
        return {
            "accion": "ERROR",
            "permite": True,
            "razon": "acción precio: error " + str(e)
        }

def presion_ultimas_velas(opens, closes, highs, lows, cantidad=8):
    try:
        if len(closes) < cantidad:
            return {
                "direccion": "INDEFINIDA",
                "fuerza": 0,
                "alcistas": 0,
                "bajistas": 0,
                "razon": "velas insuficientes"
            }

        alcistas = 0
        bajistas = 0
        fuerza_total = 0
        mechas_sup = 0
        mechas_inf = 0

        for i in range(-cantidad, 0):
            o = opens[i]
            c = closes[i]
            h = highs[i]
            l = lows[i]

            rango = h - l
            cuerpo = abs(c - o)

            if rango <= 0:
                continue

            fuerza = cuerpo / rango
            fuerza_total += fuerza

            mecha_sup = h - max(o, c)
            mecha_inf = min(o, c) - l

            if c > o:
                alcistas += 1

            if c < o:
                bajistas += 1

            if mecha_sup >= rango * 0.35:
                mechas_sup += 1

            if mecha_inf >= rango * 0.35:
                mechas_inf += 1

        fuerza_promedio = fuerza_total / cantidad

        if alcistas >= 5 and fuerza_promedio >= 0.28:
            return {
                "direccion": "ALCISTA",
                "fuerza": round(fuerza_promedio, 2),
                "alcistas": alcistas,
                "bajistas": bajistas,
                "razon": "presión alcista reciente"
            }

        if bajistas >= 5 and fuerza_promedio >= 0.28:
            return {
                "direccion": "BAJISTA",
                "fuerza": round(fuerza_promedio, 2),
                "alcistas": alcistas,
                "bajistas": bajistas,
                "razon": "presión bajista reciente"
            }

        if mechas_sup >= 4:
            return {
                "direccion": "VENTA",
                "fuerza": round(fuerza_promedio, 2),
                "alcistas": alcistas,
                "bajistas": bajistas,
                "razon": "presión vendedora por mechas superiores"
            }

        if mechas_inf >= 4:
            return {
                "direccion": "COMPRA",
                "fuerza": round(fuerza_promedio, 2),
                "alcistas": alcistas,
                "bajistas": bajistas,
                "razon": "presión compradora por mechas inferiores"
            }

        return {
            "direccion": "NEUTRA",
            "fuerza": round(fuerza_promedio, 2),
            "alcistas": alcistas,
            "bajistas": bajistas,
            "razon": "presión neutral"
        }

    except Exception as e:
        return {
            "direccion": "ERROR",
            "fuerza": 0,
            "alcistas": 0,
            "bajistas": 0,
            "razon": "error presión velas: " + str(e)
        }

def validar_patron_con_contexto(
    direccion,
    nombre_patron,
    opens,
    closes,
    highs,
    lows,
    soporte,
    resistencia,
    vol
):
    try:
        if len(closes) < 20:
            return False, "patrón sin contexto suficiente"

        if vol <= 0:
            vol = abs(closes[-1]) * 0.0001

        precio = closes[-1]
        patron = str(nombre_patron).lower()

        cerca_soporte = abs(precio - soporte) <= vol * 1.40
        cerca_resistencia = abs(resistencia - precio) <= vol * 1.40

        presion = presion_ultimas_velas(
            opens,
            closes,
            highs,
            lows,
            8
        )

        direccion_presion = presion.get("direccion", "NEUTRA")

        if direccion == "call":
            if (
                ("martillo" in patron or "pin bar" in patron or "envolvente alcista" in patron or "rechazo alcista" in patron)
                and cerca_soporte
                and direccion_presion in ["COMPRA", "ALCISTA", "NEUTRA"]
            ):
                return True, "patrón alcista válido en soporte con contexto"

            if (
                "morning star" in patron
                and cerca_soporte
                and direccion_presion in ["COMPRA", "ALCISTA"]
            ):
                return True, "morning star válido en soporte"

            return False, "patrón alcista sin contexto suficiente"

        if direccion == "put":
            if (
                ("shooting star" in patron or "pin bar" in patron or "envolvente bajista" in patron or "rechazo bajista" in patron)
                and cerca_resistencia
                and direccion_presion in ["VENTA", "BAJISTA", "NEUTRA"]
            ):
                return True, "patrón bajista válido en resistencia con contexto"

            if (
                "evening star" in patron
                and cerca_resistencia
                and direccion_presion in ["VENTA", "BAJISTA"]
            ):
                return True, "evening star válido en resistencia"

            return False, "patrón bajista sin contexto suficiente"

        return False, "dirección inválida"

    except Exception as e:
        return False, "error validando patrón contexto: " + str(e)