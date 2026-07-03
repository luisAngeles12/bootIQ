# diagnostico_estrategia.py
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

def diagnosticar_base_estrategia(senal, ctx):
    try:
        patron = str(senal.get("patron", "")).lower()
        direccion = str(senal.get("direccion", "")).lower()

        accion_precio = str(senal.get("accion_precio", "SIN_DATOS")).upper()
        pa_tipo = str(ctx.get("pa_tipo", "SIN_CONTEXTO_CLARO")).upper()
        pa_direccion = str(ctx.get("pa_direccion", "NEUTRA")).upper()
        fuerza_tendencia = float(ctx.get("fuerza_tendencia", 0) or 0)
        direccion_tendencia = str(ctx.get("direccion_tendencia", "NEUTRA")).upper()

        diagnostico = {
            "base_estrategia": "MEDIA",
            "riesgos_base": [],
            "fortalezas_base": []
        }

        def riesgo(nombre):
            if nombre not in diagnostico["riesgos_base"]:
                diagnostico["riesgos_base"].append(nombre)

        def fortaleza(nombre):
            if nombre not in diagnostico["fortalezas_base"]:
                diagnostico["fortalezas_base"].append(nombre)

        confianza_pa = evaluar_confianza_price_action(ctx, direccion)
        nivel_pa = str(confianza_pa.get("nivel", "NINGUNA")).upper()
        pa_valido = bool(confianza_pa.get("pa_valido", False))

        # ZONAS
        if direccion == "call" and accion_precio == "CALL_RESISTENCIA_CERCA_SIN_RUPTURA":
            riesgo("CALL_RESISTENCIA_SIN_RUPTURA")

        if direccion == "put" and accion_precio == "PUT_SOPORTE_CERCA_SIN_RUPTURA":
            riesgo("PUT_SOPORTE_SIN_RUPTURA")

        # PRICE ACTION
        if pa_direccion == "NEUTRA" or pa_tipo == "SIN_CONTEXTO_CLARO":
            riesgo("SIN_CONTEXTO_CLARO")

        elif pa_direccion != direccion.upper():
            riesgo("PA_CONTRA_" + direccion.upper())

        elif pa_valido and nivel_pa in ["MEDIA", "ALTA"]:
            fortaleza("PA_A_FAVOR_" + direccion.upper() + "_" + nivel_pa)

        else:
            riesgo("PA_A_FAVOR_" + direccion.upper() + "_DEBIL")

        # No todo PA confirmado es fortaleza. Solo dejamos los que mostraron mejor comportamiento.
        if pa_tipo in ["RECHAZO_COMPRADOR_CONFIRMADO", "IMPULSO_BAJISTA_FUERTE"]:
            fortaleza(pa_tipo)

        if pa_tipo in ["IMPULSO_ALCISTA_FUERTE", "RECHAZO_VENDEDOR_CONFIRMADO"]:
            riesgo(pa_tipo + "_DEBIL_HISTORICO")

        # TENDENCIA
        tendencia_a_favor = (
            direccion == "call" and direccion_tendencia == "ALCISTA"
        ) or (
            direccion == "put" and direccion_tendencia == "BAJISTA"
        )

        if tendencia_a_favor and fuerza_tendencia >= 65:
            riesgo("TENDENCIA_FUERTE_NO_CONFIABLE")
        elif tendencia_a_favor:
            riesgo("TENDENCIA_A_FAVOR_NO_PREDICTIVA")
        elif not tendencia_a_favor and direccion_tendencia in ["ALCISTA", "BAJISTA"]:
            riesgo("CONTRA_TENDENCIA")

        if fuerza_tendencia < 45:
            riesgo("FUERZA_TENDENCIA_BAJA")

        # ESTRATEGIAS
        if "choch" in patron:
            if fuerza_tendencia < 55:
                riesgo("CHOCH_CON_TENDENCIA_DEBIL")
            if pa_direccion == direccion.upper() and pa_valido and nivel_pa in ["MEDIA", "ALTA"]:
                fortaleza("CHOCH_CON_PA_VALIDO")
            else:
                riesgo("CHOCH_SIN_PA_VALIDO")

        if "liquidity sweep" in patron:
            if (
                ("RECHAZO" in pa_tipo or "AGOTAMIENTO" in pa_tipo)
                and pa_valido
                and nivel_pa in ["MEDIA", "ALTA"]
            ):
                fortaleza("SWEEP_CON_PA_VALIDO")
            else:
                riesgo("SWEEP_CON_CONFIRMACION_PA_DEBIL")

            if pa_tipo == "SIN_CONTEXTO_CLARO":
                riesgo("SWEEP_SIN_CONFIRMACION_PA")

        if "pullback" in patron:
            if tendencia_a_favor and 50 <= fuerza_tendencia <= 64 and pa_valido:
                fortaleza("PULLBACK_CON_PA_Y_TENDENCIA")
            else:
                riesgo("PULLBACK_TENDENCIA_INSUFICIENTE")

        if "reacción" in patron or "reaccion" in patron:
            if ("RECHAZO" in pa_tipo or "AGOTAMIENTO" in pa_tipo) and pa_valido:
                fortaleza("REACCION_CONFIRMADA")
            else:
                riesgo("REACCION_SIN_CONFIRMACION_FUERTE")

        if "continuación" in patron or "continuacion" in patron:
            if tendencia_a_favor and fuerza_tendencia >= 55 and pa_valido:
                fortaleza("CONTINUACION_CON_PA_VALIDO")
            else:
                riesgo("CONTINUACION_TENDENCIA_INSUFICIENTE")

        riesgos = len(diagnostico["riesgos_base"])
        fortalezas = len(diagnostico["fortalezas_base"])

        if fortalezas >= 3 and riesgos <= 1:
            diagnostico["base_estrategia"] = "FUERTE"
        elif riesgos >= 3 and fortalezas <= 1:
            diagnostico["base_estrategia"] = "DEBIL"
        else:
            diagnostico["base_estrategia"] = "MEDIA"

        return diagnostico

    except Exception as e:
        return {
            "base_estrategia": "ERROR",
            "riesgos_base": ["ERROR_DIAGNOSTICO_BASE"],
            "fortalezas_base": [],
            "error_base": str(e)
        }
