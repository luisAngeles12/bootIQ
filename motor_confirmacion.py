# motor_confirmacion.py
from motor_aprendizaje_historico import evaluar_aprendizaje_historico
def _txt(v):
    return str(v or "").lower().strip()


def _num(v, default=0):
    try:
        return float(v or default)
    except Exception:
        return default


def evaluar_contexto(senal):
    
    score = 0
    razones = []

    mercado = _txt(senal.get("mercado"))
    calidad_mercado = _txt(senal.get("calidad_mercado"))
    tendencia = _txt(senal.get("tendencia") or senal.get("estado_tendencia"))
    direccion = _txt(senal.get("direccion"))

    if calidad_mercado == "limpio":
        score += 2
        razones.append("mercado limpio")
    elif calidad_mercado == "normal":
        score += 10
        razones.append("mercado normal")
    elif calidad_mercado == "sucio":
        score -= 20
        razones.append("mercado sucio")

    if direccion == "call" and "alcista" in tendencia:
        score += 10
        razones.append("tendencia apoya CALL")

    if direccion == "put" and "bajista" in tendencia:
        score += 10
        razones.append("tendencia apoya PUT")

    if "debil" in tendencia or "débil" in tendencia:
        score -= 8
        razones.append("tendencia débil")

    if mercado == "rango":
        score -= 12
        razones.append("mercado en rango")
    if "alcista_debil" in tendencia or "alcista débil" in tendencia:
        score -= 15
        razones.append("alcista débil")
    
    if "bajista_fuerte" in tendencia or "bajista fuerte" in tendencia:
        score += 12
        razones.append("bajista fuerte")
    
    if "alcista_fuerte" in tendencia or "alcista fuerte" in tendencia:
        score += 4
        razones.append("alcista fuerte")
    return score, razones


def evaluar_price_action(senal):
    score = 0
    razones = []

    direccion = _txt(senal.get("direccion"))
    pa_direccion = _txt(senal.get("pa_direccion"))
    pa_tipo = _txt(senal.get("pa_tipo"))
    accion_precio = _txt(senal.get("accion_precio"))

    if pa_direccion == direccion:
        score += 15
        razones.append("PA a favor")

    if pa_direccion and pa_direccion != "neutra" and pa_direccion != direccion:
        score -= 20
        razones.append("PA en contra")

    if "rechazo_vendedor_confirmado" in pa_tipo:
        score += 18
        razones.append("rechazo vendedor confirmado")

    if "rechazo_comprador_confirmado" in pa_tipo:
        score -= 8
        razones.append("rechazo comprador confirmado débil")
    if "impulso_bajista_fuerte" in pa_tipo:
        score += 14
        razones.append("impulso bajista fuerte")

    if "impulso_alcista_fuerte" in pa_tipo:
        score += 2
        razones.append("impulso alcista fuerte")
    if "call_resistencia_cerca_sin_ruptura" in accion_precio:
        score -= 35
        razones.append("CALL cerca de resistencia sin ruptura")

    if "put_soporte_cerca_sin_ruptura" in accion_precio:
        score += 18
        razones.append("PUT cerca de soporte sin ruptura históricamente aceptable")

    return score, razones


def evaluar_setup(senal):
    score = 0
    razones = []

    estado = _txt(senal.get("estado_setup"))
    nivel = _txt(senal.get("nivel_setup"))
    calidad = _txt(senal.get("calidad_setup"))
    balance = _num(senal.get("balance_setup"))

    if estado == "maduro":
        score += 30
        razones.append("setup maduro")
    elif estado == "confirmable":
        score += 20
        razones.append("setup confirmable")
    elif estado == "pendiente_confirmacion":
        score -= 20
        razones.append("setup pendiente confirmación")
    elif estado == "inmaduro":
        score -= 30
        razones.append("setup inmaduro")

    if nivel == "alto":
        score += 25
        razones.append("nivel setup alto")
    elif nivel == "medio_alto":
        score += 15
        razones.append("nivel setup medio alto")
    elif nivel == "medio_bajo":
        score -= 20
        razones.append("nivel setup medio bajo")

    if calidad in ["premium", "alta", "buena"]:
        score += 10
        razones.append("calidad setup aceptable")

    if balance >= 2:
        score += 12
        razones.append("balance setup positivo")
    elif balance < 0:
        score -= 8
        razones.append("balance setup negativo")

    return score, razones


def evaluar_consenso(senal):
    score = 0
    razones = []

    nivel = _txt(senal.get("nivel_consenso"))
    consenso = _num(senal.get("consenso"))

    if nivel == "alto":
        score += 25
        razones.append("consenso alto")
    elif nivel == "premium":
        score += 22
        razones.append("consenso premium")
    elif nivel == "bueno":
        score += 6
        razones.append("consenso bueno")
    elif nivel == "medio":
        score -= 10
        razones.append("consenso medio")
    elif nivel in ["bajo", "muy_bajo"]:
        score -= 18
        razones.append("consenso bajo")

    if consenso >= 70:
        score += 8
        razones.append("consenso numérico fuerte")

    return score, razones


def evaluar_riesgo(senal):
    score = 0
    razones = []

    riesgo = _num(senal.get("riesgo_protocolo"), 50)

    if riesgo <= 25:
        score += 25
        razones.append("riesgo protocolo muy bajo")
    elif riesgo <= 40:
        score += 15
        razones.append("riesgo protocolo bajo")
    elif riesgo >= 70:
        score -= 40
        razones.append("riesgo protocolo alto")
    elif riesgo >= 55:
        score -= 12
        razones.append("riesgo protocolo medio alto")

    return score, razones


def evaluar_score_final(senal):
    score = 0
    razones = []

    score_final = _num(senal.get("score_final"))

    if score_final >= 180:
        score += 25
        razones.append("score final alto")
    elif score_final >= 145:
        score += 18
        razones.append("score final aceptable")
    elif score_final >= 120:
        score += 10
        razones.append("score final medio")
    elif score_final and score_final < 100:
        score -= 20
        razones.append("score final bajo")

    return score, razones

def evaluar_historico(senal):
    score = 0
    razones = []

    hist = evaluar_aprendizaje_historico(senal)

    senal["aprendizaje_encontrado"] = hist.get("aprendizaje_encontrado", False)
    senal["decision_aprendizaje"] = hist.get("decision_aprendizaje", "SIN_DATOS")
    senal["ajuste_confianza_aprendizaje"] = hist.get("ajuste_confianza_aprendizaje", 0)
    senal["motivo_aprendizaje"] = hist.get("motivo_aprendizaje", "")

    decision = _txt(hist.get("decision_aprendizaje"))
    ajuste = _num(hist.get("ajuste_confianza_aprendizaje"))

    if decision == "favorable":
        score += 15 + ajuste
        razones.append("histórico favorable")

    elif decision == "debil":
        score -= 20
        razones.append("histórico débil")

    elif decision == "muestra_insuficiente":
        score -= 2
        razones.append("histórico insuficiente")

    else:
        razones.append("sin histórico útil")

    return score, razones

def calcular_indice_confirmacion(senal):
    total = 20
    razones = []

    evaluadores = [
        evaluar_contexto,
        evaluar_price_action,
        evaluar_setup,
        evaluar_consenso,
        evaluar_riesgo,
        evaluar_score_final,
        evaluar_historico,
    ]
    for evaluar in evaluadores:
        puntos, r = evaluar(senal)
        total += puntos
        razones.extend(r)

    total = max(0, min(100, round(total, 2)))

    if total >= 88:
        nivel = "PREMIUM"
        accion = "ENTRAR"
    elif total >= 72:
        nivel = "ALTO"
        accion = "ESPERAR_2"
    elif total >= 55:
        nivel = "MEDIO"
        accion = "ESPERAR_3"
    else:
        nivel = "BAJO"
        accion = "CANCELAR"

    return {
        "indice": total,
        "nivel": nivel,
        "accion": accion,
        "razones": razones,
        "razon": " | ".join(razones)
    }


def decidir_confirmacion(senal):
    return calcular_indice_confirmacion(senal)