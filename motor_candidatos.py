# motor_candidatos.py

def crear_candidato(activo, direccion, estrategia, rsi, evidencias=None, ctx=None):
    """
    Candidato BootIQ V2.

    No es una señal.
    No decide operación.
    No tiene puntaje final.
    Solo describe una oportunidad detectada.
    """

    if evidencias is None:
        evidencias = []

    return {
        "activo": activo,
        "direccion": direccion,
        "estrategia": estrategia,
        "patron": estrategia,
        "rsi": round(rsi, 2),
        "evidencias": evidencias,
        "ctx_ref": {
            "accion_precio": ctx.get("accion_precio", "SIN_DATOS") if ctx else "SIN_DATOS",
            "pa_tipo": ctx.get("pa_tipo", "SIN_CONTEXTO_CLARO") if ctx else "SIN_CONTEXTO_CLARO",
            "pa_direccion": ctx.get("pa_direccion", "NEUTRA") if ctx else "NEUTRA",
            "pa_fuerza": ctx.get("pa_fuerza", 0) if ctx else 0,
            "tipo_mercado": ctx.get("tipo_mercado", "INDEFINIDO") if ctx else "INDEFINIDO",
            "calidad_mercado": ctx.get("calidad_mercado", "SIN_DATOS") if ctx else "SIN_DATOS",
            "estado_tendencia": ctx.get("estado_tendencia", "INDEFINIDA") if ctx else "INDEFINIDA",
            "fuerza_tendencia": ctx.get("fuerza_tendencia", 0) if ctx else 0,
            "direccion_tendencia": ctx.get("direccion_tendencia", "INDEFINIDA") if ctx else "INDEFINIDA",
            "posicion_rango": ctx.get("posicion_rango", 0.5) if ctx else 0.5,
        }
    }


def candidato_a_senal(candidato, puntaje_base=14, prioridad_base=2):
    """
    Conversión temporal de candidato a señal.

    Esto permite probar candidatos sin romper el flujo viejo.
    Más adelante DecisionBootIQ hará esta conversión.
    """

    evidencias = candidato.get("evidencias", [])

    return {
        "activo": candidato.get("activo", ""),
        "direccion": candidato.get("direccion", ""),
        "puntaje": puntaje_base,
        "patron": candidato.get("patron", ""),
        "rsi": candidato.get("rsi", 0),
        "razon": ", ".join(evidencias),
        "calidad": "B",
        "prioridad": prioridad_base,
    }