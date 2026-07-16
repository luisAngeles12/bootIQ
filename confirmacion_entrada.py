def _txt(v):
    return str(v or "").lower().strip()


def _num(v, defecto=0):
    try:
        return float(v)
    except Exception:
        return defecto
def _bool(v, default=False):
    if isinstance(v, bool):
        return v

    if v is None:
        return default

    texto = str(v).lower().strip()

    if texto in ["true", "1", "si", "sí", "yes"]:
        return True

    if texto in ["false", "0", "no", "none", "null", ""]:
        return False

    return default

def _limitar(valor, minimo=0, maximo=100):
    return max(minimo, min(maximo, valor))


def _analizar_vela_actual(candles):
    candles = sorted(candles, key=lambda x: x["from"])
    actual = candles[-1]
    anterior = candles[-2]

    o = float(actual["open"])
    c = float(actual["close"])
    h = float(actual["max"])
    l = float(actual["min"])

    ac = float(anterior["close"])
    ah = float(anterior["max"])
    al = float(anterior["min"])

    rango = h - l
    cuerpo = abs(c - o)

    if rango <= 0:
        return None

    fuerza = cuerpo / rango
    posicion = (c - l) / rango

    return {
        "open": o,
        "close": c,
        "high": h,
        "low": l,
        "anterior_close": ac,
        "anterior_high": ah,
        "anterior_low": al,
        "rango": rango,
        "cuerpo": cuerpo,
        "fuerza": fuerza,
        "posicion": posicion,
        "mecha_sup": h - max(o, c),
        "mecha_inf": min(o, c) - l,
        "vela_verde": c > o,
        "vela_roja": c < o,
        "cierra_sobre_anterior": c > ac,
        "cierra_bajo_anterior": c < ac,
        "rompe_high_anterior": c > ah,
        "rompe_low_anterior": c < al,
        "cerca_high": posicion >= 0.88,
        "cerca_low": posicion <= 0.12,
    }


def _analizar_microestructura(candles):
    candles = sorted(candles, key=lambda x: x["from"])

    velas = []

    for x in candles[-4:]:
        o = float(x["open"])
        c = float(x["close"])
        h = float(x["max"])
        l = float(x["min"])

        rango = h - l
        if rango <= 0:
            continue

        cuerpo = abs(c - o)

        velas.append({
            "alcista": c > o,
            "bajista": c < o,
            "fuerza": cuerpo / rango,
            "cuerpo": cuerpo,
            "mecha_sup": h - max(o, c),
            "mecha_inf": min(o, c) - l,
        })

    if len(velas) < 3:
        return {
            "ok": False,
            "alcistas": 0,
            "bajistas": 0,
            "fuerza_promedio": 0,
        }

    alcistas = sum(1 for v in velas if v["alcista"])
    bajistas = sum(1 for v in velas if v["bajista"])
    fuerza_promedio = sum(v["fuerza"] for v in velas) / len(velas)

    return {
        "ok": True,
        "alcistas": alcistas,
        "bajistas": bajistas,
        "fuerza_promedio": fuerza_promedio,
        "ultima": velas[-1],
    }


def evaluar_confirmacion_entrada(senal, candles, segundo=None):
    """
    Cerebro de entrada BootIQ.

    No abre operaciones.
    No guarda pendientes.
    No bloquea por sí solo.
    Solo evalúa si la entrada actual conviene.
    """

    if not candles or len(candles) < 4:
        return {
            "accion": "ESPERAR",
            "indice": 0,
            "nivel": "SIN_DATOS",
            "motivos": ["Velas insuficientes."]
        }

    direccion = _txt(senal.get("direccion"))
    patron = _txt(senal.get("patron"))
    accion_precio = _txt(senal.get("accion_precio"))
    tipo_setup = _txt(senal.get("tipo_setup"))
    subtipo_setup = _txt(senal.get("subtipo_setup"))
    calidad_setup = _txt(senal.get("calidad_setup"))
    # Campo legacy utilizado únicamente como respaldo temporal.
    modo_setup_legacy = _txt(
        senal.get("modo_entrada_setup")
    )
    
    # Evidencia neutral oficial del setup.
    riesgo_critico_setup = _bool(
        senal.get("riesgo_estructural_critico_setup"),
        default=(
            "no_operar" in modo_setup_legacy
            or "cancelar" in modo_setup_legacy
        )
    )
    calidad = _txt(senal.get("calidad"))
    calidad_mercado = _txt(senal.get("calidad_mercado"))
    nivel_consenso = _txt(senal.get("nivel_consenso"))
    decision_cerebro = _txt(senal.get("cerebro_unico_decision"))
    confianza_cerebro = _num(senal.get("cerebro_unico_confianza", 0))
    motivo_pendiente = _txt(senal.get("motivo_pendiente"))
    ruptura_confirmada = bool(senal.get("ruptura_confirmada", False))
    entrada_confirmada = bool(senal.get("entrada_confirmada", False))

    vela = _analizar_vela_actual(candles)
    micro = _analizar_microestructura(candles)

    if vela is None:
        return {
            "accion": "ESPERAR",
            "indice": 0,
            "nivel": "SIN_DATOS",
            "motivos": ["Rango inválido."]
        }

    indice = 50
    motivos = []

    # =========================
    # BASE DEL CEREBRO
    # =========================
    if decision_cerebro == "operar":
        indice += 10
        motivos.append("Cerebro único favorece operar.")

    elif decision_cerebro == "operar_con_protocolo":
        indice += 4
        motivos.append("Cerebro único permite con protocolo.")

    elif decision_cerebro == "no_operar":
        indice -= 12
        motivos.append("Cerebro único no favorece entrada.")

    if confianza_cerebro >= 70:
        indice += 6
        motivos.append("Confianza del cerebro alta.")

    elif confianza_cerebro >= 55:
        indice += 3
        motivos.append("Confianza del cerebro aceptable.")

    elif confianza_cerebro and confianza_cerebro < 40:
        indice -= 6
        motivos.append("Confianza del cerebro baja.")

    # =========================
    # SETUP / CONTEXTO
    # =========================
    if calidad == "a+":
        indice += 3
        motivos.append("Calidad de señal A+.")

    if calidad_setup in ["premium", "buena"]:
        indice += 3
        motivos.append("Setup de buena calidad.")

    if riesgo_critico_setup:
        indice -= 12
        motivos.append("Setup con riesgo estructural crítico.")
    if calidad_mercado in ["normal", "limpio"]:
        indice += 2
        motivos.append("Mercado operable.")

    if nivel_consenso in ["alto", "premium"]:
        indice += 4
        motivos.append("Consenso alto/premium.")

    elif nivel_consenso in ["bajo", "muy_bajo"]:
        indice -= 3
        motivos.append("Consenso bajo.")

    # =========================
    # CONFIRMACIÓN POR VELA
    # =========================
    if vela["fuerza"] < 0.06:
        indice -= 10
        motivos.append("Vela débil o indecisa.")

    if direccion == "call":
        rechazo = (
            vela["mecha_inf"] >= vela["cuerpo"] * 1.2
            and vela["posicion"] >= 0.38
            and vela["fuerza"] >= 0.12
        )

        recuperacion = (
            vela["cierra_sobre_anterior"]
            and vela["posicion"] >= 0.40
            and vela["fuerza"] >= 0.12
        )

        ruptura = (
            vela["rompe_high_anterior"]
            and vela["fuerza"] <= 0.76
        )

        if rechazo:
            indice += 12
            motivos.append("CALL con rechazo comprador.")

        if recuperacion:
            indice += 8
            motivos.append("CALL con recuperación.")

        if ruptura:
            indice += 8
            motivos.append("CALL con ruptura controlada.")

        if vela["cerca_high"] and vela["fuerza"] >= 0.75:
            indice -= 10
            motivos.append("CALL tarde cerca del máximo.")

        if vela["mecha_sup"] >= vela["cuerpo"] * 3.0 and vela["fuerza"] < 0.30:
            indice -= 10
            motivos.append("Absorción vendedora contra CALL.")

    elif direccion == "put":
        rechazo = (
            vela["mecha_sup"] >= vela["cuerpo"] * 1.2
            and vela["posicion"] <= 0.62
            and vela["fuerza"] >= 0.12
        )

        recuperacion = (
            vela["cierra_bajo_anterior"]
            and vela["posicion"] <= 0.60
            and vela["fuerza"] >= 0.12
        )

        ruptura = (
            vela["rompe_low_anterior"]
            and vela["fuerza"] <= 0.76
        )

        if rechazo:
            indice += 12
            motivos.append("PUT con rechazo vendedor.")

        if recuperacion:
            indice += 8
            motivos.append("PUT con recuperación bajista.")

        if ruptura:
            indice += 8
            motivos.append("PUT con ruptura controlada.")

        if vela["cerca_low"] and vela["fuerza"] >= 0.75:
            indice -= 10
            motivos.append("PUT tarde cerca del mínimo.")

        if vela["mecha_inf"] >= vela["cuerpo"] * 3.0 and vela["fuerza"] < 0.30:
            indice -= 10
            motivos.append("Absorción compradora contra PUT.")

    # =========================
    # MICROESTRUCTURA
    # =========================
    if micro["ok"]:
        if direccion == "call":
            if micro["alcistas"] >= 2 and micro["fuerza_promedio"] >= 0.20:
                indice += 7
                motivos.append("Microestructura CALL válida.")
            else:
                indice -= 4
                motivos.append("Microestructura CALL débil.")

        if direccion == "put":
            if micro["bajistas"] >= 2 and micro["fuerza_promedio"] >= 0.20:
                indice += 7
                motivos.append("Microestructura PUT válida.")
            else:
                indice -= 4
                motivos.append("Microestructura PUT débil.")

    else:
        indice -= 4
        motivos.append("Microestructura insuficiente.")

    # =========================
    # ZONAS / RUPTURAS
    # =========================
    if "resistencia_cerca_sin_ruptura" in accion_precio and direccion == "call":
        if ruptura_confirmada or entrada_confirmada:
            indice += 6
            motivos.append("CALL cerca de resistencia con confirmación.")
        else:
            indice -= 6
            motivos.append("CALL cerca de resistencia sin ruptura.")

    if "soporte_cerca_sin_ruptura" in accion_precio and direccion == "put":
        if ruptura_confirmada or entrada_confirmada:
            indice += 6
            motivos.append("PUT cerca de soporte con confirmación.")
        else:
            indice -= 6
            motivos.append("PUT cerca de soporte sin ruptura.")

    if "sweep" in patron or "sweep" in tipo_setup:
        if "rechazo" in accion_precio or ruptura_confirmada or entrada_confirmada:
            indice += 4
            motivos.append("Sweep con confirmación de zona.")
        else:
            indice -= 3
            motivos.append("Sweep sin confirmación clara.")

    if "pullback" in patron or "pullback" in subtipo_setup:
        if micro["ok"] and (
            (direccion == "call" and micro["alcistas"] >= 2)
            or (direccion == "put" and micro["bajistas"] >= 2)
        ):
            indice += 4
            motivos.append("Pullback con microestructura a favor.")
        else:
            indice -= 4
            motivos.append("Pullback sin microestructura suficiente.")

    # =========================
    # TIMING
    # =========================
    if segundo is not None:
        if segundo < 4:
            indice -= 6
            motivos.append("Entrada muy temprana en vela.")

        elif 5 <= segundo <= 32:
            indice += 4
            motivos.append("Timing dentro de ventana útil.")

        elif segundo > 40:
            indice -= 12
            motivos.append("Entrada tardía.")

    indice = round(_limitar(indice), 2)

    if indice >=66:
        accion = "ENTRAR"
        nivel = "ALTO"
    elif indice >= 47:
        accion = "ESPERAR"
        nivel = "MEDIO"
    else:
        accion = "CANCELAR"
        nivel = "BAJO"

    return {
        "accion": accion,
        "indice": indice,
        "nivel": nivel,
        "motivos": motivos,
        "vela": vela,
        "micro": micro,
    }