from estadisticas import activos_bloqueables

from price_action import validar_patron_con_contexto

from zonas_reaccion import evaluar_reaccion_en_zona

from validaciones_estrategia import memoria_operativa

from clasificador_senal import (
    clasificar_senal_profesional,
    pa_profesional_apoya,
    score_final_senal_profesional,
)

from motor_consenso import aplicar_consenso_senal
from motor_candidatos import crear_candidato

def crear_senal_profesional(activo, direccion, estrategia, puntaje, rsi, razones, ctx=None):
    calidad, prioridad = clasificar_senal_profesional(puntaje, razones, estrategia, rsi)

    if prioridad <= 0:
        return None

    permitido, razon_memoria = memoria_operativa(
        activo,
        direccion,
        estrategia
    )

    if not permitido:
        print("Señal bloqueada por memoria:", activo, razon_memoria)
        return None

    razones.append("calidad " + calidad)
    razones.append(razon_memoria)

    return {
        "activo": activo,
        "direccion": direccion,
        "puntaje": puntaje,
        "patron": estrategia,
        "rsi": round(rsi, 2),
        "razon": ", ".join(razones),
        "calidad": calidad,
        "prioridad": prioridad,
        "accion_precio": (
            ctx.get("accion_precio_call", "SIN_DATOS")
            if ctx and direccion == "call"
            else ctx.get("accion_precio_put", "SIN_DATOS")
            if ctx and direccion == "put"
            else "SIN_DATOS"
        ),
        "razon_accion_precio": (
            ctx.get("razon_accion_precio_call", "")
            if ctx and direccion == "call"
            else ctx.get("razon_accion_precio_put", "")
            if ctx and direccion == "put"
            else ""
        ),
        "pa_tipo": ctx.get("pa_tipo", "SIN_DATOS") if ctx else "SIN_DATOS",
        "pa_direccion": ctx.get("pa_direccion", "NEUTRA") if ctx else "NEUTRA",
        "pa_fuerza": ctx.get("pa_fuerza", 0) if ctx else 0,
        "pa_razon": ctx.get("pa_razon", "") if ctx else "",
        "pa_evidencias": ctx.get("pa_profesional", {}).get("evidencias", []) if ctx else [],
        "posicion_rango": ctx.get("posicion_rango", 0.5) if ctx else 0.5,
        "rechazo_hist_direccion": ctx.get("rechazo_hist_direccion", "NEUTRA") if ctx else "NEUTRA",
        "impulso_alcista": ctx.get("impulso_alcista", False) if ctx else False,
        "impulso_bajista": ctx.get("impulso_bajista", False) if ctx else False,
        "rechazo_alcista_real": ctx.get("rechazo_alcista_real", False) if ctx else False,
        "rechazo_bajista_real": ctx.get("rechazo_bajista_real", False) if ctx else False,
        "direccion_tendencia": ctx.get("direccion_tendencia", "NEUTRA") if ctx else "NEUTRA",
        "fuerza_tendencia": ctx.get("fuerza_tendencia", 0) if ctx else 0,
    }

def motor_estrategias_profesional(ctx):
    senales = []
    candidatos = []
    activo = ctx["activo"]
    rsi = ctx["rsi"]

    activos_malos = activos_bloqueables()

    if activo in activos_malos:
        return None

    direccion_presion = ctx.get("direccion_presion", "NEUTRA")
    razon_presion = ctx.get("razon_presion", "")
    fuerza_presion = ctx.get("fuerza_presion", 0)

    patron_call_ok, razon_patron_call = validar_patron_con_contexto(
        "call",
        ctx["nombre_patron"],
        ctx["opens"],
        ctx["closes"],
        ctx["highs"],
        ctx["lows"],
        ctx["soporte"],
        ctx["resistencia"],
        ctx["vol"]
    )

    patron_put_ok, razon_patron_put = validar_patron_con_contexto(
        "put",
        ctx["nombre_patron"],
        ctx["opens"],
        ctx["closes"],
        ctx["highs"],
        ctx["lows"],
        ctx["soporte"],
        ctx["resistencia"],
        ctx["vol"]
    )

    # =========================
    # 1. LIQUIDITY SWEEP ALCISTA
    # =========================
    if (
        ctx["liquidity_sweep"] == 1
        and ctx["patron"] != -1
        and 30 <= rsi <= 58
        and (
            ctx["rechazo"] == 1
            or ctx["patron"] == 1
            or ctx["cerca_soporte"]
            or direccion_presion in ["COMPRA", "ALCISTA"]
        )
    ):
        puntaje = 20
        razones = [
            "ESTRATEGIA: liquidity sweep alcista",
            ctx["nombre_liquidity_sweep"],
            "barrida de mínimos con recuperación confirmada",
            "presión: " + razon_presion,
            "RSI: " + str(round(rsi, 2))
        ]

        if ctx["cerca_soporte"]:
            puntaje += 2
            razones.append("recuperación en zona de soporte")

        if ctx["rechazo"] == 1:
            puntaje += 2
            razones.append(ctx["nombre_rechazo"])

        if ctx["patron"] == 1:
            puntaje += ctx["puntos_patron_vela"]
            razones.append(ctx["nombre_patron"])

        if patron_call_ok:
            puntaje += 2
            razones.append("patrón contexto: " + razon_patron_call)

        if ctx["choch"] == 1:
            puntaje += 1
            razones.append(ctx["nombre_choch"])
        candidatos.append(
            crear_candidato(
                activo,
                "call",
                "reacción compradora en soporte",
                rsi,
                razones.copy(),
                ctx
            )
        )
        senales.append(
            crear_senal_profesional(
                activo,
                "call",
                "liquidity sweep alcista",
                puntaje,
                rsi,
                razones,
                ctx
            )
        )

    # =========================
    # 2. LIQUIDITY SWEEP BAJISTA
    # =========================
    if (
        ctx["liquidity_sweep"] == -1
        and ctx["patron"] != 1
        and 45 <= rsi <= 68
        and (
            ctx["rechazo"] == -1
            or ctx["patron"] == -1
            or ctx["cerca_resistencia"]
            or direccion_presion in ["VENTA", "BAJISTA"]
        )
    ):
        puntaje = 20
        razones = [
            "ESTRATEGIA: liquidity sweep bajista",
            ctx["nombre_liquidity_sweep"],
            "barrida de máximos con rechazo",
            "presión: " + razon_presion,
            "RSI: " + str(round(rsi, 2))
        ]

        if ctx["cerca_resistencia"]:
            puntaje += 2
            razones.append("rechazo en zona de resistencia")

        if ctx["rechazo"] == -1:
            puntaje += 2
            razones.append(ctx["nombre_rechazo"])

        if ctx["patron"] == -1:
            puntaje += ctx["puntos_patron_vela"]
            razones.append(ctx["nombre_patron"])

        if patron_put_ok:
            puntaje += 2
            razones.append("patrón contexto: " + razon_patron_put)

        if ctx["choch"] == -1:
            puntaje += 1
            razones.append(ctx["nombre_choch"])

        senales.append(
            crear_senal_profesional(
                activo,
                "put",
                "liquidity sweep bajista",
                puntaje,
                rsi,
                razones,
                ctx
            )
        )

    # =========================
    # 3. BREAKOUT + RETEST ALCISTA
    # =========================
    if (
        ctx.get("br_call", 0) == 1
        and ctx.get("ema_alcista", False)
        and ctx.get("patron", 0) != -1
        and 42 <= rsi <= 66
        and direccion_presion in ["ALCISTA", "COMPRA", "NEUTRA"]
    ):
        puntaje = 20
        razones = [
            "ESTRATEGIA: breakout retest alcista",
            ctx.get("nombre_br_call", "ruptura/retest alcista"),
            "ruptura y retest de resistencia confirmado",
            "EMA favorece compra",
            "presión: " + razon_presion,
            "RSI: " + str(round(rsi, 2))
        ]

        if ctx.get("rechazo", 0) == 1:
            puntaje += 2
            razones.append(ctx.get("nombre_rechazo", "rechazo comprador"))

        if ctx.get("patron", 0) == 1:
            puntaje += ctx.get("puntos_patron_vela", 0)
            razones.append(ctx.get("nombre_patron", "patrón alcista"))

        if patron_call_ok:
            puntaje += 2
            razones.append("patrón contexto: " + razon_patron_call)

        senales.append(
            crear_senal_profesional(
                activo,
                "call",
                "breakout retest alcista",
                puntaje,
                rsi,
                razones,
                ctx
            )
        )

    # =========================
    # 4. BREAKOUT + RETEST BAJISTA
    # =========================
    if (
        ctx.get("br_put", 0) == -1
        and ctx.get("ema_bajista", False)
        and ctx.get("patron", 0) != 1
        and 34 <= rsi <= 58
        and direccion_presion in ["BAJISTA", "VENTA", "NEUTRA"]
    ):
        puntaje = 20
        razones = [
            "ESTRATEGIA: breakout retest bajista",
            ctx.get("nombre_br_put", "ruptura/retest bajista"),
            "ruptura y retest de soporte confirmado",
            "EMA favorece venta",
            "presión: " + razon_presion,
            "RSI: " + str(round(rsi, 2))
        ]

        if ctx.get("rechazo", 0) == -1:
            puntaje += 2
            razones.append(ctx.get("nombre_rechazo", "rechazo vendedor"))

        if ctx.get("patron", 0) == -1:
            puntaje += ctx.get("puntos_patron_vela", 0)
            razones.append(ctx.get("nombre_patron", "patrón bajista"))

        if patron_put_ok:
            puntaje += 2
            razones.append("patrón contexto: " + razon_patron_put)

        senales.append(
            crear_senal_profesional(
                activo,
                "put",
                "breakout retest bajista",
                puntaje,
                rsi,
                razones,
                ctx
            )
        )

    # =========================
    # 5. REACCIÓN COMPRADORA EN SOPORTE
    # =========================
    call_reaccion, razon_call_reaccion = evaluar_reaccion_en_zona(
        "call",
        ctx["opens"],
        ctx["closes"],
        ctx["highs"],
        ctx["lows"],
        ctx["soporte"],
        ctx["resistencia"],
        ctx["vol"]
    )

    if (
        call_reaccion
        and ctx["patron"] != -1
        and 30 <= rsi <= 56
        and not (
            ctx["tipo_mercado"] == "TENDENCIA_BAJISTA"
            and ctx["estado_tendencia"].startswith("BAJISTA")
            and ctx["liquidity_sweep"] != 1
        )
        and (
            ctx["cerca_soporte"]
            or patron_call_ok
            or direccion_presion in ["COMPRA", "ALCISTA"]
        )
    ):
        puntaje = 18
        razones = [
            "ESTRATEGIA: reacción compradora en soporte",
            razon_call_reaccion,
            "precio reaccionando en soporte",
            "presión: " + razon_presion,
            "RSI: " + str(round(rsi, 2))
        ]

        if ctx["rechazo"] == 1:
            puntaje += 2
            razones.append(ctx["nombre_rechazo"])

        if ctx["patron"] == 1:
            puntaje += ctx["puntos_patron_vela"]
            razones.append(ctx["nombre_patron"])

        if patron_call_ok:
            puntaje += 2
            razones.append("patrón contexto: " + razon_patron_call)

        if ctx["liquidity_sweep"] == 1:
            puntaje += 2
            razones.append(ctx["nombre_liquidity_sweep"])

        senales.append(
            crear_senal_profesional(
                activo,
                "call",
                "reacción compradora en soporte",
                puntaje,
                rsi,
                razones,
                ctx
            )
        )

    # =========================
    # 6. REACCIÓN VENDEDORA EN RESISTENCIA
    # =========================
    put_reaccion, razon_put_reaccion = evaluar_reaccion_en_zona(
        "put",
        ctx["opens"],
        ctx["closes"],
        ctx["highs"],
        ctx["lows"],
        ctx["soporte"],
        ctx["resistencia"],
        ctx["vol"]
    )

    if (
        put_reaccion
        and ctx["patron"] != 1
        and 44 <= rsi <= 70
        and (
            ctx["cerca_resistencia"]
            or patron_put_ok
            or direccion_presion in ["VENTA", "BAJISTA"]
        )
    ):
        puntaje = 18
        razones = [
            "ESTRATEGIA: reacción vendedora en resistencia",
            razon_put_reaccion,
            "precio reaccionando en resistencia",
            "presión: " + razon_presion,
            "RSI: " + str(round(rsi, 2))
        ]

        if ctx["rechazo"] == -1:
            puntaje += 2
            razones.append(ctx["nombre_rechazo"])

        if ctx["patron"] == -1:
            puntaje += ctx["puntos_patron_vela"]
            razones.append(ctx["nombre_patron"])

        if patron_put_ok:
            puntaje += 2
            razones.append("patrón contexto: " + razon_patron_put)

        if ctx["liquidity_sweep"] == -1:
            puntaje += 2
            razones.append(ctx["nombre_liquidity_sweep"])

        senales.append(
            crear_senal_profesional(
                activo,
                "put",
                "reacción vendedora en resistencia",
                puntaje,
                rsi,
                razones,
                ctx
            )
        )

       # =========================
    # 7. CHOCH ALCISTA
    # CHOCH con rechazo histórico inteligente
    # =========================
    if (
        ctx["choch"] == 1
        and ctx["ema_alcista"]
        and 42 <= rsi <= 62
        and ctx["fuerza_tendencia"] >= 45
        and ctx.get("rechazo_hist_direccion", "NEUTRA") != "PUT"
        and not (
            ctx["cerca_resistencia"]
            and ctx.get("br_call", 0) != 1
            and ctx.get("pa_direccion", "NEUTRA") != "CALL"
            and ctx.get("rechazo_hist_direccion", "NEUTRA") != "CALL"
        )
        and ctx["posicion_rango"] <= 0.82
        and not ctx.get("vela_climax_alcista", False)
        and not ctx.get("rechazo_bajista_real", False)
        and (
            direccion_presion in ["ALCISTA", "COMPRA", "NEUTRA"]
            or ctx.get("pa_direccion", "NEUTRA") in ["CALL", "NEUTRA"]
            or ctx.get("rechazo_hist_direccion", "NEUTRA") in ["CALL", "NEUTRA"]
            or ctx.get("impulso_alcista", False)
        )
        and not (
            ctx.get("accion_precio") == "CALL_RESISTENCIA_CERCA_SIN_RUPTURA"
            and ctx.get("pa_tipo") != "IMPULSO_ALCISTA_FUERTE"
        )
        and pa_profesional_apoya(ctx, "call", minimo_fuerza=0.35, aceptar_neutro=True)
        and rsi <= 60
    ):
        puntaje = 16
        razones = [
            "ESTRATEGIA: CHOCH alcista",
            ctx["nombre_choch"],
            "EMA favorece compra",
            "CHOCH con contexto confirmado",
            "rechazo histórico: " + ctx.get("rechazo_hist_razon", ""),
            "presión: " + razon_presion,
            "patrón contexto: " + razon_patron_call,
            "RSI: " + str(round(rsi, 2))
        ]

        if ctx["cerca_soporte"]:
            puntaje += 2
            razones.append("CHOCH apoyado en soporte")

        if ctx["rechazo"] == 1:
            puntaje += 2
            razones.append(ctx["nombre_rechazo"])

        if ctx.get("rechazo_hist_direccion", "NEUTRA") == "CALL":
            puntaje += 3
            razones.append("rechazo comprador histórico confirmado")

        if ctx["patron"] == 1:
            puntaje += ctx["puntos_patron_vela"]
            razones.append(ctx["nombre_patron"])

        if ctx.get("br_call", 0) == 1:
            puntaje += 3
            razones.append(ctx.get("nombre_br_call", "ruptura/retest alcista"))

        if ctx.get("pa_direccion", "NEUTRA") == "CALL":
            puntaje += 2
            razones.append("price action profesional favorece CALL: " + ctx.get("pa_razon", ""))

        if ctx.get("impulso_alcista", False):
            puntaje += 1
            razones.append("micro contexto: impulso alcista")

        senales.append(
            crear_senal_profesional(
                activo,
                "call",
                "CHOCH alcista",
                puntaje,
                rsi,
                razones,
                ctx
            )
        )
        # =========================
    # 8. CHOCH BAJISTA
    # CHOCH con rechazo histórico inteligente
    # =========================
    if (
        ctx["choch"] == -1
        and ctx["ema_bajista"]
        and 38 <= rsi <= 58
        and ctx["fuerza_tendencia"] >= 45
        and ctx.get("rechazo_hist_direccion", "NEUTRA") != "CALL"
        and not (
            ctx["cerca_soporte"]
            and ctx.get("br_put", 0) != -1
            and ctx.get("pa_direccion", "NEUTRA") != "PUT"
            and ctx.get("rechazo_hist_direccion", "NEUTRA") != "PUT"
        )
        and ctx["posicion_rango"] >= 0.18
        and not ctx.get("vela_climax_bajista", False)
        and not ctx.get("rechazo_alcista_real", False)
        and (
            direccion_presion in ["BAJISTA", "VENTA", "NEUTRA"]
            or ctx.get("pa_direccion", "NEUTRA") in ["PUT", "NEUTRA"]
            or ctx.get("rechazo_hist_direccion", "NEUTRA") in ["PUT", "NEUTRA"]
            or ctx.get("impulso_bajista", False)
        )
        and not (
            ctx.get("accion_precio") == "PUT_SOPORTE_CERCA_SIN_RUPTURA"
            and ctx.get("pa_tipo") == "SIN_CONTEXTO_CLARO"
        )
        and not (
            ctx.get("accion_precio") == "PUT_SOPORTE_CERCA_SIN_RUPTURA"
            and ctx.get("pa_tipo") in [
                "AGOTAMIENTO_BAJISTA_CONFIRMADO",
                "RECHAZO_COMPRADOR_CONFIRMADO"
            ]
        )
        and not (
            ctx.get("accion_precio") == "PUT_SOPORTE_CERCA_SIN_RUPTURA"
            and rsi < 43
            and ctx["fuerza_tendencia"] < 65
        )
    ):
        puntaje = 16
        razones = [
            "ESTRATEGIA: CHOCH bajista",
            ctx["nombre_choch"],
            "EMA favorece venta",
            "CHOCH con contexto confirmado",
            "rechazo histórico: " + ctx.get("rechazo_hist_razon", ""),
            "presión: " + razon_presion,
            "patrón contexto: " + razon_patron_put,
            "RSI: " + str(round(rsi, 2))
        ]

        if ctx["cerca_resistencia"]:
            puntaje += 2
            razones.append("CHOCH apoyado en resistencia")

        if ctx["rechazo"] == -1:
            puntaje += 2
            razones.append(ctx["nombre_rechazo"])

        if ctx.get("rechazo_hist_direccion", "NEUTRA") == "PUT":
            puntaje += 3
            razones.append("rechazo vendedor histórico confirmado")

        if ctx["patron"] == -1:
            puntaje += ctx["puntos_patron_vela"]
            razones.append(ctx["nombre_patron"])

        if ctx.get("br_put", 0) == -1:
            puntaje += 3
            razones.append(ctx.get("nombre_br_put", "ruptura/retest bajista"))

        if ctx.get("pa_direccion", "NEUTRA") == "PUT":
            puntaje += 2
            razones.append("price action profesional favorece PUT: " + ctx.get("pa_razon", ""))

        if ctx.get("impulso_bajista", False):
            puntaje += 1
            razones.append("micro contexto: impulso bajista")

        senales.append(
            crear_senal_profesional(
                activo,
                "put",
                "CHOCH bajista",
                puntaje,
                rsi,
                razones,
                ctx
            )
        )

    # =========================
    # 9. PULLBACK ALCISTA A EMA
    # =========================
    if (
        ctx["entrada_pullback_call"]
        and ctx["ema_alcista"]
        and ctx["tipo_mercado"] == "TENDENCIA_ALCISTA"
        and ctx["calidad_mercado"] in ["LIMPIO", "NORMAL"]
        and str(ctx["estado_tendencia"]).startswith("ALCISTA")
        and ctx["fuerza_tendencia"] >= 58
        and 42 <= rsi <= 58
        and not ctx["cerca_resistencia"]
        and ctx["posicion_rango"] <= 0.72
        and not ctx.get("vela_climax_alcista", False)
        and not ctx.get("rechazo_bajista_real", False)
        and ctx.get("presion_corta", "NEUTRA") in ["ALCISTA", "NEUTRA"]
        and (
            ctx["rechazo"] == 1
            or ctx["patron"] == 1
            or patron_call_ok
            or direccion_presion in ["ALCISTA", "COMPRA"]
        )
        and not (
            ctx["fuerza_ultima"] >= 0.78
            and ctx["ultima_close"] > ctx["ultima_open"]
            and ctx["posicion_rango"] >= 0.65
        )
    ):
        puntaje = 14
        razones = [
            "ESTRATEGIA: pullback alcista a EMA",
            "pullback alcista válido",
            "EMA favorece compra",
            "presión: " + razon_presion,
            "RSI: " + str(round(rsi, 2))
        ]

        if ctx["rechazo"] == 1:
            puntaje += 2
            razones.append(ctx["nombre_rechazo"])

        if ctx["patron"] == 1:
            puntaje += ctx["puntos_patron_vela"]
            razones.append(ctx["nombre_patron"])

        if patron_call_ok:
            puntaje += 2
            razones.append("patrón contexto: " + razon_patron_call)

        senales.append(
            crear_senal_profesional(
                activo,
                "call",
                "pullback alcista a EMA",
                puntaje,
                rsi,
                razones,
                ctx
            )
        )

    # =========================
    # 10. PULLBACK BAJISTA A EMA
    # =========================
    if (
        ctx["entrada_pullback_put"]
        and ctx["ema_bajista"]
        and ctx["tipo_mercado"] == "TENDENCIA_BAJISTA"
        and ctx["calidad_mercado"] in ["LIMPIO", "NORMAL"]
        and str(ctx["estado_tendencia"]).startswith("BAJISTA")
        and 40 <= rsi <= 64
        and (
            ctx["patron"] == -1
            or ctx["rechazo"] == -1
            or patron_put_ok
            or direccion_presion in ["BAJISTA", "VENTA"]
        )
    ):
        puntaje = 14
        razones = [
            "ESTRATEGIA: pullback bajista a EMA",
            "pullback bajista válido",
            "EMA favorece venta",
            "presión: " + razon_presion,
            "RSI: " + str(round(rsi, 2))
        ]

        if ctx["rechazo"] == -1:
            puntaje += 2
            razones.append(ctx["nombre_rechazo"])

        if ctx["patron"] == -1:
            puntaje += ctx["puntos_patron_vela"]
            razones.append(ctx["nombre_patron"])

        if patron_put_ok:
            puntaje += 2
            razones.append("patrón contexto: " + razon_patron_put)

        senales.append(
            crear_senal_profesional(
                activo,
                "put",
                "pullback bajista a EMA",
                puntaje,
                rsi,
                razones,
                ctx
            )
        )

    # =========================
    # 11. CONTINUACIÓN ALCISTA
    # =========================
    if (
        ctx["tendencia"] == 1
        and ctx["estructura"] == 1
        and ctx["ema_alcista"]
        and ctx["micro"] == 1
        and 45 <= rsi <= 62
        and ctx["patron"] != -1
        and direccion_presion in ["ALCISTA", "COMPRA"]
    ):
        puntaje = 11
        razones = [
            "ESTRATEGIA: continuación alcista con tendencia",
            "tendencia alcista",
            "estructura alcista",
            "EMA favorece compra",
            "micro tendencia alcista",
            "presión: " + razon_presion,
            "RSI: " + str(round(rsi, 2))
        ]

        if ctx["rechazo"] == 1:
            puntaje += 2
            razones.append(ctx["nombre_rechazo"])

        if ctx["patron"] == 1:
            puntaje += ctx["puntos_patron_vela"]
            razones.append(ctx["nombre_patron"])

        if puntaje >= 14:
            senales.append(
                crear_senal_profesional(
                    activo,
                    "call",
                    "continuación alcista con tendencia",
                    puntaje,
                    rsi,
                    razones,
                    ctx
                )
            )

    # =========================
    # 12. CONTINUACIÓN BAJISTA
    # =========================
    if (
        ctx["tendencia"] == -1
        and ctx["estructura"] == -1
        and ctx["ema_bajista"]
        and ctx["micro"] == -1
        and 38 <= rsi <= 55
        and ctx["patron"] != 1
        and direccion_presion in ["BAJISTA", "VENTA"]
    ):
        puntaje = 11
        razones = [
            "ESTRATEGIA: continuación bajista con tendencia",
            "tendencia bajista",
            "estructura bajista",
            "EMA favorece venta",
            "micro tendencia bajista",
            "presión: " + razon_presion,
            "RSI: " + str(round(rsi, 2))
        ]

        if ctx["rechazo"] == -1:
            puntaje += 2
            razones.append(ctx["nombre_rechazo"])

        if ctx["patron"] == -1:
            puntaje += ctx["puntos_patron_vela"]
            razones.append(ctx["nombre_patron"])

        if puntaje >= 14:
            senales.append(
                crear_senal_profesional(
                    activo,
                    "put",
                    "continuación bajista con tendencia",
                    puntaje,
                    rsi,
                    razones,
                    ctx
                )
            )

    senales = [s for s in senales if s is not None]

    if not senales:
        return None

    for s in senales:
        s = aplicar_consenso_senal(s, ctx)
        s["score_final"] = score_final_senal_profesional(s) 
    senales = sorted(
        senales,
        key=lambda x: (
            x.get("score_final", 0),
            x.get("prioridad", 0),
            x.get("puntaje", 0)
        ),
        reverse=True
    )

    print("RANKING DE SEÑALES:")
    for s in senales[:5]:
       print(
            s.get("activo", activo),
            "|",
            s.get("direccion"),
            "|",
            s.get("patron"),
            "| puntaje:",
            s.get("puntaje"),
            "| prioridad:",
            s.get("prioridad"),
            "| consenso:",
            s.get("consenso"),
            s.get("nivel_consenso"),
            "| score final:",
            s.get("score_final")
        )
    if candidatos:
        ctx["candidatos_bootiq_v2"] = candidatos
        print("CANDIDATOS BOOTIQ V2:", len(candidatos))
    else:
        ctx["candidatos_bootiq_v2"] = []
    return senales

