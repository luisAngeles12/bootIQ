def normalizar(valor, defecto="SIN_DATO"):
    if valor is None:
        return defecto

    valor = str(valor).strip()

    if not valor:
        return defecto

    return valor
def normalizar_numero(valor, defecto=0):
    try:
        return float(valor)
    except Exception:
        return defecto


def normalizar_evidencia_item(ev, modulo_defecto="desconocido"):
    if not isinstance(ev, dict):
        return None

    return {
        "modulo": normalizar(ev.get("modulo", ev.get("fuente", modulo_defecto))),
        "tipo": normalizar(ev.get("tipo")),
        "direccion": normalizar(ev.get("direccion", "NEUTRA")).upper(),
        "peso": normalizar_numero(ev.get("peso", 0)),
        "confianza": normalizar_numero(ev.get("confianza", 50)),
        "fuerza": normalizar_numero(ev.get("fuerza", 0)),
        "confirmada": bool(ev.get("confirmada", False)),
        "razon": normalizar(ev.get("razon"), ""),
        "categoria": normalizar(ev.get("categoria"), "GENERAL"),
        "datos": ev.get("datos", {}),
    }


def normalizar_lista_evidencias(evidencias, modulo_defecto="desconocido"):
    resultado = []

    for ev in evidencias or []:
        item = normalizar_evidencia_item(ev, modulo_defecto)
        if item:
            resultado.append(item)

    return resultado

def construir_evidencia_operacion(senal, ctx=None):
    """
    Convierte una señal del bot en un formato estándar para Fase 4.

    Este archivo no decide.
    Este archivo no bloquea.
    Solo organiza la evidencia.
    """

    ctx = ctx or {}
    setup_completo = senal.get("setup_completo", {})
    
    if not isinstance(setup_completo, dict):
        setup_completo = {}

    evidencia = {
        "activo": normalizar(senal.get("activo")),
        "direccion": normalizar(senal.get("direccion")).lower(),
        "patron": normalizar(senal.get("patron")),
        "tipo": normalizar(senal.get("tipo", ctx.get("tipo"))),
       
        "tipo_setup": normalizar(
            setup_completo.get(
                "tipo_setup",
                senal.get("tipo_setup")
            )
        ),
        
        "modo_entrada_setup": normalizar(
            setup_completo.get(
                "modo_entrada_setup",
                senal.get("modo_entrada_setup")
            )
        ),
        
        "calidad_setup": normalizar(
            setup_completo.get(
                "calidad_setup",
                senal.get("calidad_setup")
            )
        ),
        
        "balance_setup": setup_completo.get(
            "balance_setup",
            senal.get("balance_setup", 0)
        ),
        
        "puntaje_extra_setup": setup_completo.get(
            "puntaje_extra_setup",
            senal.get("puntaje_extra_setup", 0)
        ),
        
        "riesgo_extra_setup": setup_completo.get(
            "riesgo_extra_setup",
            senal.get("riesgo_extra_setup", 0)
        ),

        "accion_confirmacion_ia": normalizar(senal.get("accion_confirmacion_ia")),
        "nivel_confirmacion_ia": normalizar(senal.get("nivel_confirmacion_ia")),
        "indice_confirmacion_ia": senal.get("indice_confirmacion_ia", 0),
        "motivo_ejecucion": normalizar(senal.get("motivo_ejecucion")),
        "puntaje": senal.get("puntaje", 0),
        "prioridad": senal.get("prioridad", 0),
        "score_final": senal.get("score_final", 0),
        "estado_operativo_setup": normalizar(
            setup_completo.get(
                "estado_operativo_setup",
                senal.get("estado_operativo_setup")
            )
        ),
        
        "requiere_ruptura_setup": setup_completo.get(
            "requiere_ruptura_setup",
            senal.get("requiere_ruptura_setup", False)
        ),
        
        "requiere_confirmacion_setup": setup_completo.get(
            "requiere_confirmacion_setup",
            senal.get("requiere_confirmacion_setup", False)
        ),
        
        "riesgo_estructural_critico_setup": setup_completo.get(
            "riesgo_estructural_critico_setup",
            senal.get("riesgo_estructural_critico_setup", False)
        ),
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
       
        "familia_setup": normalizar(
            setup_completo.get(
                "familia_setup",
                senal.get("familia_setup")
            )
        ),
        
        "subtipo_setup": normalizar(
            setup_completo.get(
                "subtipo_setup",
                senal.get("subtipo_setup")
            )
        ),
        
        "protocolo_sugerido": normalizar(
            setup_completo.get(
                "protocolo_sugerido",
                senal.get("protocolo_sugerido")
            )
        ),
        
        "nivel_setup": normalizar(
            setup_completo.get(
                "nivel_setup",
                senal.get("nivel_setup")
            )
        ),
        
        "estado_setup": normalizar(
            setup_completo.get(
                "estado_setup",
                senal.get("estado_setup")
            )
        ),
        
        "confianza_setup": setup_completo.get(
            "confianza_setup",
            senal.get("confianza_setup", 50)
        ),

        "razones_clasificador_setup": normalizar(
            senal.get("razones_clasificador_setup")
        ),
        "pa_evidencias": normalizar_lista_evidencias(
            senal.get("pa_evidencias", ctx.get("pa_evidencias", [])),
            "price_action"
        ),
        "mercado_evidencias": normalizar_lista_evidencias(
            senal.get("mercado_evidencias", ctx.get("mercado_evidencias", [])),
            "mercado"
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

def construir_evidencias_mercado(ctx):
    """
    Construye evidencias descriptivas del contexto de mercado.

    No decide.
    No bloquea.
    No calcula la confianza final.

    Cada evidencia representa una característica diferente del mercado.
    """

    ctx = ctx or {}
    evidencias = []

    tipo_mercado = str(
        ctx.get("tipo_mercado", "INDEFINIDO") or "INDEFINIDO"
    ).upper().strip()

    calidad = str(
        ctx.get("calidad_mercado", "SIN_DATOS") or "SIN_DATOS"
    ).upper().strip()

    estado = str(
        ctx.get("estado_tendencia", "INDEFINIDA") or "INDEFINIDA"
    ).upper().strip()

    direccion_tendencia = str(
        ctx.get("direccion_tendencia", "INDEFINIDA") or "INDEFINIDA"
    ).upper().strip()

    regimen = str(
        ctx.get("regimen_mercado", "SIN_DATOS") or "SIN_DATOS"
    ).upper().strip()

    riesgo = str(
        ctx.get("riesgo_mercado", "MEDIO") or "MEDIO"
    ).upper().strip()

    score = normalizar_numero(
        ctx.get("score_mercado", 0),
        0,
    )

    fuerza = normalizar_numero(
        ctx.get("fuerza_tendencia", 0),
        0,
    )

    if direccion_tendencia == "ALCISTA":
        direccion_ev = "CALL"

    elif direccion_tendencia == "BAJISTA":
        direccion_ev = "PUT"

    else:
        direccion_ev = "NEUTRA"

    # ========================================================
    # TIPO PRINCIPAL DE MERCADO
    # ========================================================

    if tipo_mercado == "TENDENCIA_ALCISTA":
        evidencias.append({
            "fuente": "mercado",
            "tipo": "TENDENCIA_ALCISTA",
            "direccion": "CALL",
            "peso": 6,
            "fuerza": fuerza,
            "confirmada": fuerza >= 45,
            "razon": "mercado con tendencia alcista",
            "categoria": "TIPO_MERCADO",
        })

    elif tipo_mercado == "TENDENCIA_BAJISTA":
        evidencias.append({
            "fuente": "mercado",
            "tipo": "TENDENCIA_BAJISTA",
            "direccion": "PUT",
            "peso": 6,
            "fuerza": fuerza,
            "confirmada": fuerza >= 45,
            "razon": "mercado con tendencia bajista",
            "categoria": "TIPO_MERCADO",
        })

    elif tipo_mercado == "RANGO":
        evidencias.append({
            "fuente": "mercado",
            "tipo": "MERCADO_RANGO",
            "direccion": "NEUTRA",
            "peso": 8,
            "fuerza": score,
            "confirmada": True,
            "razon": "mercado operando dentro de un rango",
            "categoria": "TIPO_MERCADO",
        })

    elif tipo_mercado == "COMPRESION":
        evidencias.append({
            "fuente": "mercado",
            "tipo": "MERCADO_COMPRESION",
            "direccion": "NEUTRA",
            "peso": -4,
            "fuerza": score,
            "confirmada": True,
            "razon": "mercado en compresión",
            "categoria": "TIPO_MERCADO",
        })

    # ========================================================
    # CALIDAD DEL MERCADO
    # ========================================================

    if calidad == "LIMPIO":
        evidencias.append({
            "fuente": "mercado",
            "tipo": "MERCADO_LIMPIO",
            "direccion": "NEUTRA",
            "peso": 0,
            "fuerza": score,
            "confirmada": True,
            "razon": (
                "mercado clasificado como limpio; "
                "no implica fortaleza automática"
            ),
            "categoria": "CALIDAD_MERCADO",
        })

    elif calidad == "NORMAL":
        evidencias.append({
            "fuente": "mercado",
            "tipo": "MERCADO_NORMAL",
            "direccion": "NEUTRA",
            "peso": 2,
            "fuerza": score,
            "confirmada": True,
            "razon": "mercado normal y operable",
            "categoria": "CALIDAD_MERCADO",
        })

    elif calidad in ["SUCIO", "CAOTICO"]:
        evidencias.append({
            "fuente": "mercado",
            "tipo": "MERCADO_SUCIO",
            "direccion": "NEUTRA",
            "peso": -10,
            "fuerza": score,
            "confirmada": True,
            "razon": "mercado sucio o caótico",
            "categoria": "CALIDAD_MERCADO",
        })

    # ========================================================
    # ESTADO DE LA TENDENCIA
    # ========================================================

    if "DEBIL" in estado:
        evidencias.append({
            "fuente": "mercado",
            "tipo": "TENDENCIA_DEBIL",
            "direccion": direccion_ev,
            "peso": 0,
            "fuerza": fuerza,
            "confirmada": True,
            "razon": (
                "tendencia débil detectada; "
                "se conserva como diagnóstico"
            ),
            "categoria": "ESTADO_TENDENCIA",
        })

    if "FUERTE" in estado:
        evidencias.append({
            "fuente": "mercado",
            "tipo": "TENDENCIA_FUERTE",
            "direccion": direccion_ev,
            "peso": 0,
            "fuerza": fuerza,
            "confirmada": True,
            "razon": (
                "tendencia fuerte detectada; "
                "sin bono automático"
            ),
            "categoria": "ESTADO_TENDENCIA",
        })

    if "AGOTADA" in estado:
        evidencias.append({
            "fuente": "mercado",
            "tipo": "TENDENCIA_AGOTADA",
            "direccion": direccion_ev,
            "peso": -6,
            "fuerza": fuerza,
            "confirmada": True,
            "razon": "tendencia con señales de agotamiento",
            "categoria": "ESTADO_TENDENCIA",
        })

    # ========================================================
    # RÉGIMEN DEL MERCADO
    # ========================================================

    if regimen == "TENDENCIA_LIMPIA":
        evidencias.append({
            "fuente": "mercado",
            "tipo": "TENDENCIA_LIMPIA",
            "direccion": direccion_ev,
            "peso": 0,
            "fuerza": fuerza,
            "confirmada": True,
            "razon": (
                "régimen de tendencia limpia; "
                "sin premio automático"
            ),
            "categoria": "REGIMEN_MERCADO",
        })

    elif regimen == "EXPANSION_PELIGROSA":
        evidencias.append({
            "fuente": "mercado",
            "tipo": "EXPANSION_PELIGROSA",
            "direccion": "NEUTRA",
            "peso": -10,
            "fuerza": score,
            "confirmada": True,
            "razon": "expansión de mercado potencialmente peligrosa",
            "categoria": "REGIMEN_MERCADO",
        })

    elif regimen == "RANGO_SUCIO":
        evidencias.append({
            "fuente": "mercado",
            "tipo": "RANGO_SUCIO",
            "direccion": "NEUTRA",
            "peso": -10,
            "fuerza": score,
            "confirmada": True,
            "razon": "rango desordenado o sucio",
            "categoria": "REGIMEN_MERCADO",
        })

    # ========================================================
    # SCORE DE MERCADO
    # Umbrales provisionales para comprobarlos en backtest.
    # ========================================================

    if score >= 70:
        evidencias.append({
            "fuente": "mercado",
            "tipo": "SCORE_MERCADO_ALTO",
            "direccion": "NEUTRA",
            "peso": 2,
            "fuerza": score,
            "confirmada": True,
            "razon": "score de mercado alto",
            "categoria": "SCORE_MERCADO",
        })

    elif 0 < score < 45:
        evidencias.append({
            "fuente": "mercado",
            "tipo": "SCORE_MERCADO_BAJO",
            "direccion": "NEUTRA",
            "peso": -4,
            "fuerza": score,
            "confirmada": True,
            "razon": "score de mercado bajo",
            "categoria": "SCORE_MERCADO",
        })

    # ========================================================
    # RIESGO DEL MERCADO
    # ========================================================

    if riesgo == "ALTO":
        evidencias.append({
            "fuente": "mercado",
            "tipo": "RIESGO_MERCADO_ALTO",
            "direccion": "NEUTRA",
            "peso": -8,
            "fuerza": score,
            "confirmada": True,
            "razon": "riesgo de mercado alto",
            "categoria": "RIESGO_MERCADO",
        })

    return evidencias