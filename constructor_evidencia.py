def normalizar(valor, defecto="SIN_DATO"):
    if valor is None:
        return defecto

    valor = str(valor).strip()

    if not valor:
        return defecto

    return valor


def construir_evidencia_operacion(senal, ctx=None):
    """
    Convierte una señal del bot en un formato estándar para Fase 4.

    Este archivo no decide.
    Este archivo no bloquea.
    Solo organiza la evidencia.
    """

    ctx = ctx or {}

    evidencia = {
        "activo": normalizar(senal.get("activo")),
        "direccion": normalizar(senal.get("direccion")).lower(),
        "patron": normalizar(senal.get("patron")),

        "puntaje": senal.get("puntaje", 0),
        "prioridad": senal.get("prioridad", 0),
        "score_final": senal.get("score_final", 0),

        "consenso": senal.get("consenso", 0),
        "nivel_consenso": normalizar(senal.get("nivel_consenso")),
        "ajuste_consenso": senal.get("ajuste_consenso", 0),

        "tipo_mercado": normalizar(
            senal.get("tipo_mercado", ctx.get("tipo_mercado"))
        ),
        "calidad_mercado": normalizar(
            senal.get("calidad_mercado", ctx.get("calidad_mercado"))
        ),
        "score_mercado": senal.get(
            "score_mercado",
            ctx.get("score_mercado", 0)
        ),

        "estado_tendencia": normalizar(
            senal.get("estado_tendencia", ctx.get("estado_tendencia"))
        ),
        "fuerza_tendencia": senal.get(
            "fuerza_tendencia",
            ctx.get("fuerza_tendencia", 0)
        ),
        "direccion_tendencia": normalizar(
            senal.get("direccion_tendencia", ctx.get("direccion_tendencia"))
        ),

        "accion_precio": normalizar(
            senal.get("accion_precio", ctx.get("accion_precio"))
        ),
        "pa_tipo": normalizar(
            senal.get("pa_tipo", ctx.get("pa_tipo"))
        ),
        "pa_direccion": normalizar(
            senal.get("pa_direccion", ctx.get("pa_direccion", "NEUTRA"))
        ),
        "pa_fuerza": senal.get(
            "pa_fuerza",
            ctx.get("pa_fuerza", 0)
        ),

        "base_estrategia": normalizar(senal.get("base_estrategia")),
        "riesgos_base": normalizar(senal.get("riesgos_base")),
        "fortalezas_base": normalizar(senal.get("fortalezas_base")),

        "ruptura_confirmada": senal.get("ruptura_confirmada", False),
        "tipo_ruptura": normalizar(senal.get("tipo_ruptura")),
        "familia_setup": normalizar(senal.get("familia_setup")),
        "subtipo_setup": normalizar(senal.get("subtipo_setup")),
        "protocolo_sugerido": normalizar(senal.get("protocolo_sugerido")),
        "nivel_setup": normalizar(senal.get("nivel_setup")),
        "estado_setup": normalizar(senal.get("estado_setup")),
        "confianza_setup": senal.get("confianza_setup", 50),
        "razones_clasificador_setup": normalizar(
            senal.get("razones_clasificador_setup")
        ),
    }

    return evidencia


def imprimir_evidencia(evidencia):
    print("\n===== EVIDENCIA OPERACIÓN =====")
    for clave, valor in evidencia.items():
        print(clave + ":", valor)


if __name__ == "__main__":
    ejemplo_senal = {
        "activo": "BIDU-OTC",
        "direccion": "put",
        "patron": "CHOCH bajista",
        "puntaje": 22,
        "prioridad": 4,
        "score_final": 178,
        "consenso": 98,
        "nivel_consenso": "PREMIUM",
        "tipo_mercado": "TENDENCIA_BAJISTA",
        "calidad_mercado": "NORMAL",
        "estado_tendencia": "BAJISTA_FUERTE",
        "pa_tipo": "IMPULSO_BAJISTA_FUERTE",
        "pa_direccion": "PUT",
    }

    evidencia = construir_evidencia_operacion(ejemplo_senal)
    imprimir_evidencia(evidencia)