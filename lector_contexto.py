from indicadores import *
from price_action import *
from zonas import *
from mercado import obtener_velas
from price_action_profesional import (
    contexto_price_action_profesional,
    rechazo_historico_inteligente
)
def leer_contexto_grafico(activo):
    data = obtener_velas(activo)

    if data is None:
        return None

    opens = data["open"]
    closes = data["close"]
    highs = data["high"]
    lows = data["low"]

    if len(closes) < 130:
        return None

    price = closes[-1]
    rsi = calcular_rsi(closes)

    if rsi is None:
        return None

    ema9 = ema(closes, 9)
    ema21 = ema(closes, 21)

    tendencia = tendencia_regresion(closes, 80)
    estructura = estructura_mercado(highs, lows, 30)

    patron, nombre_patron, fuerza_patron = patron_price_action_avanzado(
        opens, closes, highs, lows
    )

    presion = presion_ultimas_velas(
        opens, closes, highs, lows, 8
    )

    rechazo, nombre_rechazo = rechazo_real(
        opens, closes, highs, lows
    )

    vol = volatilidad(highs, lows, 14)

    if vol <= 0:
        return None

    soporte_zona, resistencia_zona = soporte_resistencia_zonas(
        price, highs, lows, vol
    )

    soporte = soporte_zona["precio"]
    resistencia = resistencia_zona["precio"]

    bb_superior, bb_media, bb_inferior = bollinger_bands(closes, 20, 2)

    if bb_superior is None:
        return None

    tolerancia_soporte = soporte_zona.get("tolerancia", vol * 0.45)
    tolerancia_resistencia = resistencia_zona.get("tolerancia", vol * 0.45)

    cerca_soporte = abs(price - soporte) <= tolerancia_soporte * 1.25
    cerca_resistencia = abs(resistencia - price) <= tolerancia_resistencia * 1.25

    if cerca_soporte and cerca_resistencia:
        distancia_soporte = abs(price - soporte)
        distancia_resistencia = abs(resistencia - price)

        fuerza_soporte = soporte_zona.get("fuerza", soporte_zona.get("toques", 1))
        fuerza_resistencia = resistencia_zona.get("fuerza", resistencia_zona.get("toques", 1))

        if distancia_soporte < distancia_resistencia:
            cerca_resistencia = False
        elif distancia_resistencia < distancia_soporte:
            cerca_soporte = False
        else:
            if fuerza_soporte > fuerza_resistencia:
                cerca_resistencia = False
            elif fuerza_resistencia > fuerza_soporte:
                cerca_soporte = False
            else:
                cerca_soporte = False
                cerca_resistencia = False

    cerca_banda_inferior = price <= bb_inferior + (vol * 1.3)
    cerca_banda_superior = price >= bb_superior - (vol * 1.3)

    triple_soporte = triple_rechazo(highs, lows, soporte_zona, "soporte", 25)
    triple_resistencia = triple_rechazo(highs, lows, resistencia_zona, "resistencia", 25)

    falsa_call, nombre_falsa_call = falsa_ruptura(
        opens, closes, highs, lows, soporte_zona, "soporte"
    )

    falsa_put, nombre_falsa_put = falsa_ruptura(
        opens, closes, highs, lows, resistencia_zona, "resistencia"
    )

    br_call, nombre_br_call = breakout_retest(
        opens, closes, highs, lows, resistencia_zona, "resistencia"
    )

    br_put, nombre_br_put = breakout_retest(
        opens, closes, highs, lows, soporte_zona, "soporte"
    )

    extension = movimiento_extendido(opens, closes, 5)
    micro = micro_tendencia(opens, closes, 6)

    entrada_pullback_call = entrada_pullback(
        "call", price, ema21, soporte, resistencia, vol, patron, rechazo
    )

    entrada_pullback_put = entrada_pullback(
        "put", price, ema21, soporte, resistencia, vol, patron, rechazo
    )

    call_reaccion, razon_call_reaccion = evaluar_reaccion_en_zona(
        "call", opens, closes, highs, lows, soporte, resistencia, vol
    )

    put_reaccion, razon_put_reaccion = evaluar_reaccion_en_zona(
        "put", opens, closes, highs, lows, soporte, resistencia, vol
    )

    liquidity_sweep, nombre_liquidity_sweep = detectar_liquidity_sweep(
        opens, closes, highs, lows
    )

    choch, nombre_choch = detectar_cambio_estructura_choch(
        highs, lows, closes, opens
    )

    puntos_patron_vela, razon_patron_vela = fuerza_patron_vela(nombre_patron)

    if falsa_call == 1 and tendencia == -1 and estructura == -1:
        falsa_call = 0
        nombre_falsa_call = "falsa ruptura alcista anulada por tendencia bajista"

    if falsa_put == -1 and tendencia == 1 and estructura == 1:
        falsa_put = 0
        nombre_falsa_put = "falsa ruptura bajista anulada por tendencia alcista"

    rango_total = abs(resistencia - soporte)

    if rango_total <= 0:
        rango_total = vol * 2

    posicion_rango = abs(price - soporte) / rango_total

    ultima_open = opens[-1]
    ultima_close = closes[-1]
    ultima_high = highs[-1]
    ultima_low = lows[-1]

    rango_ultima = ultima_high - ultima_low
    cuerpo_ultima = abs(ultima_close - ultima_open)

    if rango_ultima <= 0:
        fuerza_ultima = 0
        mecha_superior_ultima = 0
        mecha_inferior_ultima = 0
    else:
        fuerza_ultima = cuerpo_ultima / rango_ultima
        mecha_superior_ultima = ultima_high - max(ultima_open, ultima_close)
        mecha_inferior_ultima = min(ultima_open, ultima_close) - ultima_low

    micro_contexto = leer_micro_contexto_profesional({
        "opens": opens,
        "closes": closes,
        "highs": highs,
        "lows": lows,
        "posicion_rango": posicion_rango
    })
    pa_profesional = contexto_price_action_profesional(
       opens,
       closes,
       highs,
       lows,
       soporte,
       resistencia,
       vol
    )
    rechazo_hist = rechazo_historico_inteligente(
        opens,
        closes,
        highs,
        lows,
        soporte,
        resistencia,
        vol
    )
    diagnostico_pa_ctx = diagnostico_accion_precio_zona(
        "call",
        opens,
        closes,
        highs,
        lows,
        soporte,
        resistencia,
        vol
    )

    accion_precio_base = diagnostico_pa_ctx.get("accion", "SIN_DATOS")
    razon_accion_precio_base = diagnostico_pa_ctx.get("razon", "")
    return {
        "activo": activo,
        "opens": opens,
        "closes": closes,
        "highs": highs,
        "lows": lows,

        "price": price,
        "rsi": rsi,

        "ema9": ema9,
        "ema21": ema21,
        "ema_alcista": ema9 > ema21,
        "ema_bajista": ema9 < ema21,

        "tendencia": tendencia,
        "estructura": estructura,
        "micro": micro,
        "extension": extension,

        "patron": patron,
        "nombre_patron": nombre_patron,
        "fuerza_patron": fuerza_patron,
        "puntos_patron_vela": puntos_patron_vela,
        "razon_patron_vela": razon_patron_vela,

        "presion": presion,
        "direccion_presion": presion.get("direccion", "NEUTRA"),
        "razon_presion": presion.get("razon", ""),
        "fuerza_presion": presion.get("fuerza", 0),

        "rechazo": rechazo,
        "nombre_rechazo": nombre_rechazo,

        "vol": vol,

        "soporte_zona": soporte_zona,
        "resistencia_zona": resistencia_zona,
        "soporte": soporte,
        "resistencia": resistencia,
        "cerca_soporte": cerca_soporte,
        "cerca_resistencia": cerca_resistencia,
        "posicion_rango": posicion_rango,

        "bb_superior": bb_superior,
        "bb_media": bb_media,
        "bb_inferior": bb_inferior,
        "cerca_banda_inferior": cerca_banda_inferior,
        "cerca_banda_superior": cerca_banda_superior,

        "triple_soporte": triple_soporte,
        "triple_resistencia": triple_resistencia,

        "falsa_call": falsa_call,
        "nombre_falsa_call": nombre_falsa_call,
        "falsa_put": falsa_put,
        "nombre_falsa_put": nombre_falsa_put,

        "br_call": br_call,
        "nombre_br_call": nombre_br_call,
        "br_put": br_put,
        "nombre_br_put": nombre_br_put,

        "entrada_pullback_call": entrada_pullback_call,
        "entrada_pullback_put": entrada_pullback_put,

        "call_reaccion": call_reaccion,
        "razon_call_reaccion": razon_call_reaccion,
        "put_reaccion": put_reaccion,
        "razon_put_reaccion": razon_put_reaccion,

        "liquidity_sweep": liquidity_sweep,
        "nombre_liquidity_sweep": nombre_liquidity_sweep,

        "choch": choch,
        "nombre_choch": nombre_choch,

        "ultima_open": ultima_open,
        "ultima_close": ultima_close,
        "ultima_high": ultima_high,
        "ultima_low": ultima_low,
        "rango_ultima": rango_ultima,
        "cuerpo_ultima": cuerpo_ultima,
        "fuerza_ultima": fuerza_ultima,
        "mecha_superior_ultima": mecha_superior_ultima,
        "mecha_inferior_ultima": mecha_inferior_ultima,

        "micro_contexto": micro_contexto,
        "fuerza_cuerpo": micro_contexto.get("fuerza_cuerpo", 0),
        "mecha_sup_ratio": micro_contexto.get("mecha_sup_ratio", 0),
        "mecha_inf_ratio": micro_contexto.get("mecha_inf_ratio", 0),
        "impulso_alcista": micro_contexto.get("impulso_alcista", False),
        "impulso_bajista": micro_contexto.get("impulso_bajista", False),
        "rechazo_alcista_real": micro_contexto.get("rechazo_alcista_real", False),
        "rechazo_bajista_real": micro_contexto.get("rechazo_bajista_real", False),
        "vela_climax_alcista": micro_contexto.get("vela_climax_alcista", False),
        "vela_climax_bajista": micro_contexto.get("vela_climax_bajista", False),
        "presion_corta": micro_contexto.get("presion_corta", "NEUTRA"),

        "accion_precio": accion_precio_base,
        "razon_accion_precio": razon_accion_precio_base,

        "pa_profesional": pa_profesional,
        "pa_direccion": pa_profesional.get("direccion", "NEUTRA"),
        "pa_tipo": pa_profesional.get("tipo", "SIN_CONTEXTO_CLARO"),
        "pa_fuerza": pa_profesional.get("fuerza", 0),
        "pa_razon": pa_profesional.get("razon", ""),
        "rechazo_hist": rechazo_hist,
        "rechazo_hist_direccion": rechazo_hist.get("direccion", "NEUTRA"),
        "rechazo_hist_tipo": rechazo_hist.get("tipo", "SIN_RECHAZO_HISTORICO"),
        "rechazo_hist_fuerza": rechazo_hist.get("fuerza", 0),
        "rechazo_hist_razon": rechazo_hist.get("razon", ""),
    }
def leer_micro_contexto_profesional(ctx):
    try:
        opens = ctx["opens"]
        closes = ctx["closes"]
        highs = ctx["highs"]
        lows = ctx["lows"]

        if len(closes) < 20:
            return {}

        o = opens[-1]
        c = closes[-1]
        h = highs[-1]
        l = lows[-1]

        rango = h - l
        cuerpo = abs(c - o)

        if rango <= 0:
            rango = 0.0000001

        fuerza_cuerpo = cuerpo / rango
        mecha_sup = h - max(o, c)
        mecha_inf = min(o, c) - l

        vela_verde = c > o
        vela_roja = c < o

        cierres_5 = closes[-5:]
        subidas = sum(1 for i in range(1, len(cierres_5)) if cierres_5[i] > cierres_5[i - 1])
        bajadas = sum(1 for i in range(1, len(cierres_5)) if cierres_5[i] < cierres_5[i - 1])

        impulso_alcista = subidas >= 3 and vela_verde and fuerza_cuerpo >= 0.45
        impulso_bajista = bajadas >= 3 and vela_roja and fuerza_cuerpo >= 0.45

        rechazo_alcista_real = (
            vela_verde
            and mecha_inf >= rango * 0.35
            and fuerza_cuerpo >= 0.25
        )

        rechazo_bajista_real = (
            vela_roja
            and mecha_sup >= rango * 0.35
            and fuerza_cuerpo >= 0.25
        )

        vela_climax_alcista = (
            vela_verde
            and fuerza_cuerpo >= 0.75
            and ctx.get("posicion_rango", 0.5) >= 0.70
        )

        vela_climax_bajista = (
            vela_roja
            and fuerza_cuerpo >= 0.75
            and ctx.get("posicion_rango", 0.5) <= 0.30
        )

        presion_corta = "NEUTRA"

        if subidas >= 3:
            presion_corta = "ALCISTA"
        elif bajadas >= 3:
            presion_corta = "BAJISTA"

        return {
            "fuerza_cuerpo": round(fuerza_cuerpo, 4),
            "mecha_sup_ratio": round(mecha_sup / rango, 4),
            "mecha_inf_ratio": round(mecha_inf / rango, 4),
            "vela_verde": vela_verde,
            "vela_roja": vela_roja,
            "impulso_alcista": impulso_alcista,
            "impulso_bajista": impulso_bajista,
            "rechazo_alcista_real": rechazo_alcista_real,
            "rechazo_bajista_real": rechazo_bajista_real,
            "vela_climax_alcista": vela_climax_alcista,
            "vela_climax_bajista": vela_climax_bajista,
            "presion_corta": presion_corta,
            "subidas_5": subidas,
            "bajadas_5": bajadas,
        }

    except Exception as e:
        print("Error leyendo micro contexto:", e)
        return {}
def fuerza_patron_vela(nombre_patron):
    try:
        texto = str(nombre_patron).lower()

        # Máxima fuerza
        if "envolvente" in texto:
            return 3, "patrón fuerte: envolvente"

        if "morning star" in texto:
            return 3, "patrón fuerte: morning star"

        if "evening star" in texto:
            return 3, "patrón fuerte: evening star"

        # Fuerza media
        if "pin bar" in texto:
            return 2, "patrón medio: pin bar"

        if "martillo" in texto:
            return 2, "patrón medio: martillo"

        if "shooting star" in texto:
            return 2, "patrón medio: shooting star"

        # Fuerza baja
        if "doji" in texto:
            return 1, "patrón débil: doji"

        return 0, "sin patrón fuerte"

    except Exception as e:
        print("Error fuerza patrón:", e)
        return 0, "error patrón"
def detectar_liquidity_sweep(opens, closes, highs, lows, lookback=12):
    """
    Detecta barridas de liquidez con validación profesional.

    Retorna:
        -1 = sweep bajista / posible PUT
         1 = sweep alcista / posible CALL
         0 = sin sweep válido

    Mantiene compatibilidad con el flujo actual:
        return direccion, razon
    """

    try:
        if len(closes) < lookback + 5:
            return 0, "sin barrida de liquidez: velas insuficientes"

        high_actual = highs[-1]
        low_actual = lows[-1]
        close_actual = closes[-1]
        open_actual = opens[-1]

        high_prev = highs[-2]
        low_prev = lows[-2]
        close_prev = closes[-2]
        open_prev = opens[-2]

        rango_actual = max(high_actual - low_actual, 0.0000001)
        cuerpo_actual = abs(close_actual - open_actual)

        mecha_superior = high_actual - max(open_actual, close_actual)
        mecha_inferior = min(open_actual, close_actual) - low_actual

        cuerpo_pct = cuerpo_actual / rango_actual
        mecha_sup_pct = mecha_superior / rango_actual
        mecha_inf_pct = mecha_inferior / rango_actual

        highs_previos = highs[-lookback-1:-1]
        lows_previos = lows[-lookback-1:-1]
        closes_previos = closes[-lookback-1:-1]

        max_prev = max(highs_previos)
        min_prev = min(lows_previos)

        rango_promedio = sum(
            max(highs[i] - lows[i], 0.0000001)
            for i in range(len(highs) - lookback - 1, len(highs) - 1)
        ) / lookback

        vela_roja = close_actual < open_actual
        vela_verde = close_actual > open_actual

        cierre_en_parte_baja = close_actual <= low_actual + (rango_actual * 0.45)
        cierre_en_parte_alta = close_actual >= high_actual - (rango_actual * 0.45)

        # Ruptura real sobre zonas previas
        barrio_maximo = high_actual > max_prev
        barrio_minimo = low_actual < min_prev

        # Evita barridas microscópicas
        exceso_maximo = high_actual - max_prev
        exceso_minimo = min_prev - low_actual

        exceso_max_pct = exceso_maximo / rango_promedio if rango_promedio else 0
        exceso_min_pct = exceso_minimo / rango_promedio if rango_promedio else 0

        # Confirmación de retorno dentro de la zona
        recupero_debajo_max = close_actual < max_prev
        recupero_arriba_min = close_actual > min_prev

        # Filtro de vela demasiado débil
        vela_con_rango_valido = rango_actual >= rango_promedio * 0.65
        vela_no_doji = cuerpo_pct >= 0.18

        # =========================
        # SWEEP BAJISTA / PUT
        # =========================
        if barrio_maximo and recupero_debajo_max:
            score = 0
            razones = ["liquidity sweep bajista: barrida de máximos"]

            if vela_roja:
                score += 20
                razones.append("vela roja confirma rechazo")

            if mecha_sup_pct >= 0.35:
                score += 20
                razones.append("mecha superior dominante")

            if cierre_en_parte_baja:
                score += 15
                razones.append("cierre en zona baja de la vela")

            if exceso_max_pct >= 0.10:
                score += 10
                razones.append("barrida con exceso suficiente")

            if vela_con_rango_valido:
                score += 10
                razones.append("rango de vela válido")

            if vela_no_doji:
                score += 10
                razones.append("cuerpo de vela suficiente")

            if close_actual < close_prev:
                score += 10
                razones.append("cierre actual confirma presión bajista")

            if high_actual > high_prev and close_actual < close_prev:
                score += 5
                razones.append("estructura inmediata rechaza máximos")

            if score >= 55:
                razones.append(f"score_sweep={score}")
                return -1, " | ".join(razones)

            return 0, "sweep bajista débil: " + " | ".join(razones) + f" | score_sweep={score}"

        # =========================
        # SWEEP ALCISTA / CALL
        # =========================
        if barrio_minimo and recupero_arriba_min:
            score = 0
            razones = ["liquidity sweep alcista: barrida de mínimos"]

            if vela_verde:
                score += 20
                razones.append("vela verde confirma rechazo")

            if mecha_inf_pct >= 0.35:
                score += 20
                razones.append("mecha inferior dominante")

            if cierre_en_parte_alta:
                score += 15
                razones.append("cierre en zona alta de la vela")

            if exceso_min_pct >= 0.10:
                score += 10
                razones.append("barrida con exceso suficiente")

            if vela_con_rango_valido:
                score += 10
                razones.append("rango de vela válido")

            if vela_no_doji:
                score += 10
                razones.append("cuerpo de vela suficiente")

            if close_actual > close_prev:
                score += 10
                razones.append("cierre actual confirma presión alcista")

            if low_actual < low_prev and close_actual > close_prev:
                score += 5
                razones.append("estructura inmediata rechaza mínimos")

            # Sweep alcista venía débil en el aprendizaje.
            # Por eso exige un poco más de calidad que el bajista.
            if score >= 65:
                razones.append(f"score_sweep={score}")
                return 1, " | ".join(razones)

            return 0, "sweep alcista débil: " + " | ".join(razones) + f" | score_sweep={score}"

        return 0, "sin barrida de liquidez"

    except Exception as e:
        print("Error detectando liquidity sweep:", e)
        return 0, "error liquidity sweep"
def detectar_cambio_estructura_choch(highs, lows, closes, opens=None, lookback=10):
    try:
        if len(closes) < lookback + 4:
            return 0, "sin datos suficientes para CHOCH"

        highs_previos = highs[-lookback-2:-2]
        lows_previos = lows[-lookback-2:-2]

        ultimo_open = opens[-1] if opens else closes[-2]
        ultimo_close = closes[-1]
        ultimo_high = highs[-1]
        ultimo_low = lows[-1]

        max_prev = max(highs_previos)
        min_prev = min(lows_previos)

        rango = ultimo_high - ultimo_low
        cuerpo = abs(ultimo_close - ultimo_open)

        if rango <= 0:
            return 0, "rango inválido para CHOCH"

        fuerza_cuerpo = cuerpo / rango

        if fuerza_cuerpo < 0.45:
            return 0, "CHOCH débil: cuerpo insuficiente"

        if ultimo_close > max_prev:
            fuerza_ruptura = (ultimo_close - max_prev) / rango

            if fuerza_ruptura < 0.15:
                return 0, "CHOCH alcista débil: ruptura pequeña"

            if ultimo_close <= ultimo_open:
                return 0, "CHOCH alcista inválido: vela no alcista"

            return 1, "CHOCH alcista confirmado: ruptura con cuerpo"

        if ultimo_close < min_prev:
            fuerza_ruptura = (min_prev - ultimo_close) / rango

            if fuerza_ruptura < 0.15:
                return 0, "CHOCH bajista débil: ruptura pequeña"

            if ultimo_close >= ultimo_open:
                return 0, "CHOCH bajista inválido: vela no bajista"

            return -1, "CHOCH bajista confirmado: ruptura con cuerpo"

        return 0, "sin cambio de estructura"

    except Exception as e:
        print("Error detectando CHOCH:", e)
        return 0, "error CHOCH"
def evaluar_reaccion_en_zona(
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
        precio = closes[-1]

        if vol <= 0:
            vol = abs(precio) * 0.0001

        ultimas = 8

        opens_r = opens[-ultimas:]
        closes_r = closes[-ultimas:]
        highs_r = highs[-ultimas:]
        lows_r = lows[-ultimas:]

        distancia_soporte = abs(precio - soporte)
        distancia_resistencia = abs(resistencia - precio)

        cerca_soporte = distancia_soporte <= vol * 1.20
        cerca_resistencia = distancia_resistencia <= vol * 1.20

        zona_total = abs(resistencia - soporte)

        if zona_total <= 0:
            zona_total = vol * 2

        posicion_rango = distancia_soporte / zona_total

        # 0.00 = pegado al soporte
        # 1.00 = pegado a resistencia

        mechas_superiores = 0
        mechas_inferiores = 0
        velas_rojas = 0
        velas_verdes = 0
        cuerpos_fuertes_rojos = 0
        cuerpos_fuertes_verdes = 0

        for o, c, h, l in zip(opens_r, closes_r, highs_r, lows_r):
            rango = h - l

            if rango <= 0:
                continue

            cuerpo = abs(c - o)
            fuerza = cuerpo / rango

            mecha_sup = h - max(o, c)
            mecha_inf = min(o, c) - l

            if mecha_sup >= rango * 0.35:
                mechas_superiores += 1

            if mecha_inf >= rango * 0.35:
                mechas_inferiores += 1

            if c < o:
                velas_rojas += 1
                if fuerza >= 0.45:
                    cuerpos_fuertes_rojos += 1

            if c > o:
                velas_verdes += 1
                if fuerza >= 0.45:
                    cuerpos_fuertes_verdes += 1

        o1 = opens[-1]
        c1 = closes[-1]
        h1 = highs[-1]
        l1 = lows[-1]

        rango1 = h1 - l1

        if rango1 <= 0:
            return False, "rango inválido en zona"

        cuerpo1 = abs(c1 - o1)
        fuerza1 = cuerpo1 / rango1

        mecha_sup_1 = h1 - max(o1, c1)
        mecha_inf_1 = min(o1, c1) - l1

        vela_roja = c1 < o1
        vela_verde = c1 > o1

        rechazo_vendedor_fuerte = (
            cerca_resistencia
            and vela_roja
            and mecha_sup_1 >= rango1 * 0.32
            and fuerza1 >= 0.18
        )

        rechazo_comprador_fuerte = (
            cerca_soporte
            and vela_verde
            and mecha_inf_1 >= rango1 * 0.32
            and fuerza1 >= 0.18
        )

        presion_vendedora_en_resistencia = (
            cerca_resistencia
            and mechas_superiores >= 3
            and velas_rojas >= 3
            and cuerpos_fuertes_rojos >= 1
        )

        presion_compradora_en_soporte = (
            cerca_soporte
            and mechas_inferiores >= 3
            and velas_verdes >= 3
            and cuerpos_fuertes_verdes >= 1
        )

        agotamiento_alcista = (
            cerca_resistencia
            and velas_verdes >= 4
            and mechas_superiores >= 2
            and fuerza1 < 0.55
        )

        agotamiento_bajista = (
            cerca_soporte
            and velas_rojas >= 4
            and mechas_inferiores >= 2
            and fuerza1 < 0.55
        )
        pa_profesional = contexto_price_action_profesional(
            opens,
            closes,
            highs,
            lows,
            soporte,
            resistencia,
            vol
        )
       
        # =========================
        # PUT EN RESISTENCIA
        # =========================
        if direccion == "put":
            if not cerca_resistencia:
                return False, "PUT sin cercanía real a resistencia"
            if (
                pa_profesional.get("direccion") == "PUT"
                and pa_profesional.get("tipo") in [
                    "RECHAZO_VENDEDOR_CONFIRMADO",
                    "AGOTAMIENTO_ALCISTA_CONFIRMADO"
                ]
            ):
                return True, "PUT válido por price action profesional: " + pa_profesional.get("razon", "")
            if cerca_soporte or posicion_rango <= 0.25:
                return False, "PUT rechazado: soporte demasiado cerca"

            if rechazo_vendedor_fuerte:
                return True, "PUT válido: rechazo vendedor fuerte en resistencia"

            if presion_vendedora_en_resistencia:
                return True, "PUT válido: presión vendedora en resistencia"

            if agotamiento_alcista:
                return True, "PUT válido: agotamiento alcista en resistencia"

            return False, "PUT sin reacción suficiente en resistencia"

        # =========================
        # CALL EN SOPORTE
        # =========================
        if direccion == "call":
            if not cerca_soporte:
                return False, "CALL sin cercanía real a soporte"
            if (
                pa_profesional.get("direccion") == "CALL"
                and pa_profesional.get("tipo") in [
                    "RECHAZO_COMPRADOR_CONFIRMADO",
                    "AGOTAMIENTO_BAJISTA_CONFIRMADO"
                ]
            ):
                return True, "CALL válido por price action profesional: " + pa_profesional.get("razon", "")
            if cerca_resistencia or posicion_rango >= 0.75:
                return False, "CALL rechazado: resistencia demasiado cerca"

            if rechazo_comprador_fuerte:
                return True, "CALL válido: rechazo comprador fuerte en soporte"

            if presion_compradora_en_soporte:
                return True, "CALL válido: presión compradora en soporte"

            if agotamiento_bajista:
                return True, "CALL válido: agotamiento bajista en soporte"

            return False, "CALL sin reacción suficiente en soporte"

        return False, "dirección inválida"

    except Exception as e:
        print("Error evaluando reacción en zona:", e)
        return False, "error reacción zona"
