from config import PUNTAJE_MINIMO

def clasificar_senal(puntaje, razones, rsi):
    texto = " | ".join(razones).lower()

    calidad = "C"
    prioridad = 0

    tiene_rechazo = "rechazo" in texto
    tiene_pullback = "pullback" in texto
    tiene_falsa = "falsa ruptura" in texto
    tiene_breakout = "breakout" in texto
    tiene_patron = (
        "pin bar" in texto
        or "martillo" in texto
        or "shooting star" in texto
        or "envolvente" in texto
    )

    if puntaje >= 15 and (tiene_rechazo or tiene_falsa or tiene_breakout):
        calidad = "A+"
        prioridad = 4

    elif puntaje >= 11 and (tiene_rechazo or tiene_pullback or tiene_patron):
        calidad = "A"
        prioridad = 3

    elif puntaje >= 7 and (tiene_rechazo or tiene_pullback or tiene_falsa or tiene_breakout):
        calidad = "B"
        prioridad = 2

    elif puntaje >= PUNTAJE_MINIMO:
        calidad = "C"
        prioridad = 1

    if rsi > 68 or rsi < 32:
        prioridad -= 1

    if prioridad <= 0:
        calidad = "C"
        prioridad = 0

    return calidad, prioridad

def clasificar_senal_profesional(puntaje, razones, estrategia, rsi):
    texto = " | ".join(razones).lower()
    estrategia = estrategia.lower()

    es_reaccion = "reacción" in estrategia or "reaccion" in estrategia

    tiene_confirmacion_fuerte = (
        "rechazo comprador fuerte" in texto
        or "rechazo vendedor fuerte" in texto
        or "pin bar" in texto
        or "martillo" in texto
        or "shooting star" in texto
        or "envolvente" in texto
        or "liquidity sweep" in texto
        or "presión compradora" in texto
        or "presion compradora" in texto
        or "presión vendedora" in texto
        or "presion vendedora" in texto
    )

    if es_reaccion and not tiene_confirmacion_fuerte:
        return "C", 0

    calidad = "C"
    prioridad = 0

    if puntaje >= 18:
        calidad = "A+"
        prioridad = 4

        if "choch" in estrategia and puntaje < 21:
            calidad = "A"
            prioridad = 3

    elif puntaje >= 14:
        calidad = "A"
        prioridad = 3

    elif puntaje >= 8:
        calidad = "B"
        prioridad = 2

    else:
        calidad = "C"
        prioridad = 0

    if calidad == "C":
        return "C", 0

    if rsi > 68 and "reversa" not in estrategia and "rechazo vendedor" not in texto:
        prioridad -= 1

    if rsi < 32 and "reversa" not in estrategia and "rechazo comprador" not in texto:
        prioridad -= 1

    if prioridad <= 0:
        return "C", 0
    return calidad, prioridad

def peso_estrategia_profesional(patron):
    patron = str(patron).lower()

    if "liquidity sweep" in patron:
        return 110

    if "choch" in patron:
        return 88

    if "breakout" in patron or "retest" in patron:
        return 95

    if "pullback alcista" in patron and "ema" in patron:
        return 82

    if "pullback bajista" in patron and "ema" in patron:
        return 72

    if "continuación" in patron or "continuacion" in patron:
        return 65

    if "reacción" in patron or "reaccion" in patron:
        return 80

    return 50

def score_final_senal_profesional(senal):
    patron = str(senal.get("patron", "")).lower()
    accion = str(senal.get("accion_precio", "")).upper()
    direccion = str(senal.get("direccion", "")).lower()
    pa_tipo = str(senal.get("pa_tipo", "")).upper()
    pa_direccion = str(senal.get("pa_direccion", "")).upper()

    peso = peso_estrategia_profesional(patron)
    puntaje = senal.get("puntaje", 0)
    prioridad = senal.get("prioridad", 0)

    score = peso + (puntaje * 2) + (prioridad * 5)

    if direccion == "call" and accion == "RECHAZO_COMPRADOR_SOPORTE":
        score += 12

    if direccion == "put" and accion == "RECHAZO_VENDEDOR_RESISTENCIA":
        score += 12

    if "liquidity sweep" in patron:
        score += 18

    if "pullback bajista" in patron:
        score -= 12

    if "pullback alcista" in patron:
        score -= 14

    if "continuación" in patron or "continuacion" in patron:
        if puntaje < 16:
            score -= 35
        else:
            score -= 20

    if puntaje >= 23:
        score += 10

    if senal.get("calidad") == "A+":
        score += 8

    ctx_pa = {
        "pa_direccion": pa_direccion,
        "pa_tipo": pa_tipo,
        "pa_fuerza": senal.get("pa_fuerza", 0),
        "accion_precio": senal.get("accion_precio", "SIN_DATOS"),
        "direccion_tendencia": senal.get("direccion_tendencia", "NEUTRA"),
        "fuerza_tendencia": senal.get("fuerza_tendencia", 0),
        "posicion_rango": senal.get("posicion_rango", 0.5),
        "rechazo_hist_direccion": senal.get("rechazo_hist_direccion", "NEUTRA"),
        "impulso_alcista": senal.get("impulso_alcista", False),
        "impulso_bajista": senal.get("impulso_bajista", False),
        "rechazo_alcista_real": senal.get("rechazo_alcista_real", False),
        "rechazo_bajista_real": senal.get("rechazo_bajista_real", False),
    }

    confianza_pa = evaluar_confianza_price_action(ctx_pa, direccion)

    if confianza_pa.get("nivel") == "ALTA":
        score += 18
    elif confianza_pa.get("nivel") == "MEDIA":
        score += 9
    elif confianza_pa.get("nivel") == "BAJA":
        score += 2
    elif confianza_pa.get("nivel") == "DEBIL":
        score -= 10

    return score


def evaluar_confianza_price_action(ctx, direccion):
    try:
        direccion = str(direccion).upper()

        pa_direccion = str(ctx.get("pa_direccion", "NEUTRA")).upper()
        pa_tipo = str(ctx.get("pa_tipo", "SIN_CONTEXTO_CLARO")).upper()
        pa_fuerza = float(ctx.get("pa_fuerza", 0) or 0)

        accion_precio = str(ctx.get("accion_precio", "SIN_DATOS")).upper()
        direccion_tendencia = str(ctx.get("direccion_tendencia", "NEUTRA")).upper()
        fuerza_tendencia = float(ctx.get("fuerza_tendencia", 0) or 0)
        posicion_rango = float(ctx.get("posicion_rango", 0.5) or 0.5)

        rechazo_hist_direccion = str(ctx.get("rechazo_hist_direccion", "NEUTRA")).upper()
        impulso_alcista = bool(ctx.get("impulso_alcista", False))
        impulso_bajista = bool(ctx.get("impulso_bajista", False))
        rechazo_alcista_real = bool(ctx.get("rechazo_alcista_real", False))
        rechazo_bajista_real = bool(ctx.get("rechazo_bajista_real", False))

        if pa_direccion != direccion:
            return {
                "nivel": "NINGUNA",
                "score": 0,
                "pa_valido": False,
                "razon": "price action no coincide con dirección"
            }

        score = 0
        razones = []

        if pa_tipo in [
            "RECHAZO_COMPRADOR_CONFIRMADO",
            "RECHAZO_VENDEDOR_CONFIRMADO",
            "AGOTAMIENTO_BAJISTA_CONFIRMADO",
            "AGOTAMIENTO_ALCISTA_CONFIRMADO",
            "IMPULSO_ALCISTA_FUERTE",
            "IMPULSO_BAJISTA_FUERTE"
        ]:
            score += 25
            razones.append("tipo PA válido")

        if pa_fuerza >= 0.70:
            score += 30
            razones.append("PA fuerte")
        elif pa_fuerza >= 0.55:
            score += 20
            razones.append("PA medio")
        elif pa_fuerza >= 0.45:
            score += 10
            razones.append("PA mínimo")
        else:
            score -= 25
            razones.append("PA débil")

        if direccion == "CALL":
            if accion_precio == "CALL_RESISTENCIA_CERCA_SIN_RUPTURA":
                score -= 25
                razones.append("CALL cerca de resistencia sin ruptura")

            if posicion_rango >= 0.78:
                score -= 15
                razones.append("CALL alto en rango")

            if rechazo_bajista_real:
                score -= 25
                razones.append("rechazo bajista contra CALL")

            if impulso_alcista:
                score += 10
                razones.append("micro impulso alcista")

            if direccion_tendencia == "ALCISTA" and fuerza_tendencia >= 55:
                score += 10
                razones.append("tendencia apoya CALL")

            if rechazo_hist_direccion == "CALL":
                score += 12
                razones.append("rechazo histórico apoya CALL")

        if direccion == "PUT":
            if accion_precio == "PUT_SOPORTE_CERCA_SIN_RUPTURA":
                score -= 30
                razones.append("PUT cerca de soporte sin ruptura")

            if posicion_rango <= 0.25:
                score -= 18
                razones.append("PUT bajo en rango")

            if rechazo_alcista_real:
                score -= 25
                razones.append("rechazo alcista contra PUT")

            if impulso_bajista:
                score += 10
                razones.append("micro impulso bajista")

            if direccion_tendencia == "BAJISTA" and fuerza_tendencia >= 55:
                score += 10
                razones.append("tendencia apoya PUT")

            if rechazo_hist_direccion == "PUT":
                score += 12
                razones.append("rechazo histórico apoya PUT")

        if score >= 65:
            nivel = "ALTA"
            pa_valido = True
        elif score >= 45:
            nivel = "MEDIA"
            pa_valido = True
        elif score >= 30:
            nivel = "BAJA"
            pa_valido = False
        else:
            nivel = "DEBIL"
            pa_valido = False

        return {
            "nivel": nivel,
            "score": score,
            "pa_valido": pa_valido,
            "razon": " | ".join(razones)
        }

    except Exception as e:
        return {
            "nivel": "ERROR",
            "score": 0,
            "pa_valido": False,
            "razon": "error evaluando confianza PA: " + str(e)
        }

def pa_profesional_apoya(ctx, direccion, minimo_fuerza=0.35, aceptar_neutro=False):
    direccion = str(direccion).upper()

    pa_direccion = str(ctx.get("pa_direccion", "NEUTRA")).upper()
    pa_tipo = str(ctx.get("pa_tipo", "SIN_CONTEXTO_CLARO")).upper()
    pa_fuerza = float(ctx.get("pa_fuerza", 0) or 0)

    if pa_tipo == "SIN_CONTEXTO_CLARO":
        return False

    if pa_direccion == direccion and pa_fuerza >= minimo_fuerza:
        return True

    if aceptar_neutro and pa_direccion == "NEUTRA" and pa_fuerza >= minimo_fuerza:
        return True

    return False


