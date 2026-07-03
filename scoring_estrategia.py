
from diagnostico_estrategia import evaluar_confianza_price_action
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
