from indicadores import *
from price_action import *
from zonas import *
from mercado import obtener_velas
from motor_setup import (enriquecer_senal_con_setup,clasificar_setup_estrategico)

import time
import estado

from contexto_mercado import (
    detectar_tipo_mercado,
    diagnostico_maestro_mercado,
    diagnostico_calidad_mercado,
    diagnostico_tendencia_avanzada,
)
from constructor_evidencia import construir_evidencias_mercado
from contexto_grafico import (
    fuerza_patron_vela,
    leer_micro_contexto_profesional,
    detectar_cambio_estructura_choch,
    detectar_liquidity_sweep,
)

from validaciones_estrategia import (
    filtro_fatiga_y_ubicacion,
    vela_contraria_reciente,
    zona_ya_operada,
    validar_estrategia_por_mercado,
)

from clasificador_senal import evaluar_confianza_price_action

from zonas_reaccion import evaluar_reaccion_en_zona
from utils import estrategia_en_cooldown

from price_action_profesional import (
    contexto_price_action_profesional,
    rechazo_historico_inteligente,
)

from motor_estrategias import motor_estrategias_profesional

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
    diagnostico_pa_call = diagnostico_accion_precio_zona(
        "call",
        opens,
        closes,
        highs,
        lows,
        soporte,
        resistencia,
        vol
    )
    
    diagnostico_pa_put = diagnostico_accion_precio_zona(
        "put",
        opens,
        closes,
        highs,
        lows,
        soporte,
        resistencia,
        vol
    )
    
    accion_precio_call = diagnostico_pa_call.get("accion", "SIN_DATOS")
    razon_accion_precio_call = diagnostico_pa_call.get("razon", "")
    
    accion_precio_put = diagnostico_pa_put.get("accion", "SIN_DATOS")
    razon_accion_precio_put = diagnostico_pa_put.get("razon", "")
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

        "accion_precio_call": accion_precio_call,
        "razon_accion_precio_call": razon_accion_precio_call,
        
        "accion_precio_put": accion_precio_put,
        "razon_accion_precio_put": razon_accion_precio_put,
        
        # Compatibilidad vieja: se mantiene para no romper otros módulos.
        "accion_precio": accion_precio_call,
        "razon_accion_precio": razon_accion_precio_call,

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

def preparar_contexto_mercado(activo, ctx):
    try:
        candles_contexto = []

        for i in range(len(ctx["closes"])):
            candles_contexto.append({
                "from": i,
                "open": ctx["opens"][i],
                "close": ctx["closes"][i],
                "max": ctx["highs"][i],
                "min": ctx["lows"][i]
            })

        tipo_mercado, razon_mercado = detectar_tipo_mercado(candles_contexto)
        diagnostico = diagnostico_calidad_mercado(candles_contexto)
        diagnostico_tendencia = diagnostico_tendencia_avanzada(candles_contexto)
        maestro = diagnostico_maestro_mercado(candles_contexto)

        ctx["tipo_mercado"] = tipo_mercado
        ctx["razon_mercado"] = razon_mercado
        ctx["calidad_mercado"] = diagnostico.get("calidad", "SIN_DATOS")
        ctx["score_mercado"] = diagnostico.get("score", 0)
        ctx["detalle_calidad_mercado"] = diagnostico
        ctx["regimen_mercado"] = maestro.get("regimen", "SIN_DATOS")
        ctx["modo_mercado"] = maestro.get("modo", "SIN_DATOS")
        ctx["riesgo_mercado"] = maestro.get("riesgo", "MEDIO")
        ctx["razon_regimen"] = maestro.get("razon", "")

        ctx["estado_tendencia"] = diagnostico_tendencia.get("estado_tendencia", "INDEFINIDA")
        ctx["fuerza_tendencia"] = diagnostico_tendencia.get("fuerza_tendencia", 0)
        ctx["direccion_tendencia"] = diagnostico_tendencia.get("direccion_tendencia", "INDEFINIDA")
        ctx["razon_tendencia"] = diagnostico_tendencia.get("razon_tendencia", "")
        ctx["detalle_tendencia"] = diagnostico_tendencia
        ctx["mercado_evidencias"] = construir_evidencias_mercado(ctx)
        estado.snapshot_mercados[activo] = {
            "tipo": ctx.get("tipo_mercado", "INDEFINIDO"),
            "calidad": ctx.get("calidad_mercado", "SIN_DATOS"),
            "score": ctx.get("score_mercado", 0),
            "tendencia": ctx.get("estado_tendencia", "INDEFINIDA"),
            "fuerza": ctx.get("fuerza_tendencia", 0)
        }

        return ctx

    except Exception as e:
        ctx["tipo_mercado"] = "INDEFINIDO"
        ctx["razon_mercado"] = "error leyendo mercado: " + str(e)
        ctx["calidad_mercado"] = "SIN_DATOS"
        ctx["score_mercado"] = 0
        ctx["detalle_calidad_mercado"] = {}
        ctx["estado_tendencia"] = "INDEFINIDA"
        ctx["fuerza_tendencia"] = 0
        ctx["direccion_tendencia"] = "INDEFINIDA"
        ctx["razon_tendencia"] = "error leyendo tendencia"

        return ctx

def validar_contexto_base(activo, ctx):
    calidad = ctx.get("calidad_mercado", "SIN_DATOS")
    score = ctx.get("score_mercado", 0)
    tendencia_estado = ctx.get("estado_tendencia", "INDEFINIDA")

    if calidad not in ["LIMPIO", "NORMAL"]:
        estado.cooldown_activos[activo] = time.time() + 600
        return False

    if score < 52:
        estado.cooldown_activos[activo] = time.time() + 600
        return False

    if "DEBIL" in tendencia_estado and score < 62:
        estado.cooldown_activos[activo] = time.time() + 600
        return False

    if tendencia_estado == "INDEFINIDA":
        estado.cooldown_activos[activo] = time.time() + 600
        return False

    return True

def evaluar_senal_candidata(activo, ctx, senal):
    if senal is None:
        return None

    if estrategia_en_cooldown(senal.get("patron", "")):
        print(
            senal["direccion"].upper(),
            "bloqueado por cooldown de estrategia:",
            activo,
            senal.get("patron", "")
        )
        return None

    setup = clasificar_setup_estrategico(senal, ctx)
    # Conservar la salida completa de la capa estratégica.
    # Se utilizará después para construir el contrato final
    # sin recalcular esta capa.
    senal["_setup_estrategico"] = setup.copy()
    senal["tipo_setup"] = setup.get("tipo_setup", "INDEFINIDO")
    senal["calidad_setup"] = setup.get("calidad_setup", "MEDIA")
    senal["modo_entrada_setup"] = setup.get("modo_entrada", "DIRECTA")
    senal["puntaje_extra_setup"] = setup.get("puntaje_extra_setup", 0)
    senal["riesgo_extra_setup"] = setup.get("riesgo_extra_setup", 0)
    senal["balance_setup"] = setup.get("balance_setup", 0)
    senal["a_favor_tendencia"] = setup.get("a_favor_tendencia", False)
    senal["razones_setup"] = " | ".join(setup.get("razones_setup", []))
    senal["estado_operativo_setup"] = setup.get(
        "estado_operativo_setup",
        "LISTO"
    )
    
    senal["requiere_ruptura_setup"] = setup.get(
        "requiere_ruptura_setup",
        False
    )
    
    senal["requiere_confirmacion_setup"] = setup.get(
        "requiere_confirmacion_setup",
        False
    )
    
    senal["riesgo_estructural_critico_setup"] = setup.get(
        "riesgo_estructural_critico_setup",
        False
    )
    senal["puntaje"] = senal.get("puntaje", 0) + setup.get("puntaje_extra_setup", 0)

    if setup.get("riesgo_extra_setup", 0) >= 4:
        senal["puntaje"] -= 2

    ok_mercado, razon_validacion_mercado = validar_estrategia_por_mercado(
        senal,
        ctx
    )

    senal["validacion_mercado_ok"] = ok_mercado
    senal["razon_validacion_mercado"] = razon_validacion_mercado
    
    if not ok_mercado:
        senal["riesgos_base"] = (
            str(senal.get("riesgos_base", "")) 
            + "|MERCADO_NO_VALIDADO"
        ).strip("|")
    
        senal["razon"] += (
            ", advertencia mercado: "
            + razon_validacion_mercado
            + ", enviada al cerebro único como evidencia"
        )
    ruptura = confirmar_ruptura_zona(
        senal["direccion"],
        ctx["opens"],
        ctx["closes"],
        ctx["highs"],
        ctx["lows"],
        ctx["soporte"],
        ctx["resistencia"],
        ctx["vol"]
    )

    senal["ruptura_confirmada"] = ruptura.get("confirmada", False)
    senal["tipo_ruptura"] = ruptura.get("tipo", "SIN_DATOS")
    senal["razon_ruptura"] = ruptura.get("razon", "")

    ok_zona_sr, razon_zona_sr = validar_interaccion_soporte_resistencia(
        senal["direccion"],
        ctx["opens"],
        ctx["closes"],
        ctx["highs"],
        ctx["lows"],
        ctx["soporte"],
        ctx["resistencia"],
        ctx["vol"],
        senal.get("puntaje", 0),
        senal.get("patron", ""),
        ctx.get("tipo_mercado", "INDEFINIDO"),
        ctx.get("calidad_mercado", "NORMAL"),
        senal.get("ruptura_confirmada", False),
        senal.get("tipo_ruptura", "SIN_DATOS")
    )

    if not ok_zona_sr:
        senal["validacion_zona_sr_ok"] = False
        senal["razon_zona_sr"] = razon_zona_sr
    
        senal["riesgos_base"] = (
            str(senal.get("riesgos_base", ""))
            + "|ZONA_SR_NO_VALIDADA"
        ).strip("|")
    
        senal["razon"] += (
            ", advertencia zona SR: "
            + razon_zona_sr
            + ", enviada al cerebro único como evidencia"
        )
    
    else:
        senal["validacion_zona_sr_ok"] = True
        senal["razon_zona_sr"] = razon_zona_sr
    diagnostico_pa = diagnostico_accion_precio_zona(
        senal["direccion"],
        ctx["opens"],
        ctx["closes"],
        ctx["highs"],
        ctx["lows"],
        ctx["soporte"],
        ctx["resistencia"],
        ctx["vol"]
    )

    senal["accion_precio"] = diagnostico_pa.get("accion", "SIN_DATOS")
    senal["razon_accion_precio"] = diagnostico_pa.get("razon", "")

    riesgos_previos = str(senal.get("riesgos_base", "")).strip("|")
    fortalezas_previas = str(senal.get("fortalezas_base", "")).strip("|")
    
    diagnostico_base = diagnosticar_base_estrategia(senal, ctx)
    
    riesgos_nuevos = "|".join(diagnostico_base.get("riesgos_base", []))
    fortalezas_nuevas = "|".join(diagnostico_base.get("fortalezas_base", []))
    
    senal["base_estrategia"] = diagnostico_base.get("base_estrategia", "MEDIA")
    
    senal["riesgos_base"] = "|".join(
        x for x in [riesgos_previos, riesgos_nuevos]
        if x
    )
    
    senal["fortalezas_base"] = "|".join(
        x for x in [fortalezas_previas, fortalezas_nuevas]
        if x
    )

    patron_lower = str(senal.get("patron", "")).lower()
    accion_precio = senal.get("accion_precio", "")

    if "choch" in patron_lower:
        if accion_precio in ["CALL_ZONA_NEUTRA", "PUT_ZONA_NEUTRA"]:
            senal["puntaje"] += 2
            senal["razon"] += ", CHOCH en zona neutra"

        if accion_precio == "RECHAZO_COMPRADOR_SOPORTE" and senal["direccion"] == "call":
            senal["puntaje"] += 4
            senal["razon"] += ", CHOCH apoyado por rechazo comprador en soporte"

        if accion_precio == "RECHAZO_VENDEDOR_RESISTENCIA" and senal["direccion"] == "put":
            senal["puntaje"] += 4
            senal["razon"] += ", CHOCH apoyado por rechazo vendedor en resistencia"

        if accion_precio == "CALL_RESISTENCIA_CERCA_SIN_RUPTURA" and senal["direccion"] == "call":
            senal["puntaje"] -= 3
            senal["razon"] += ", CHOCH cerca de resistencia sin ruptura: penalizado, no bloqueado"

        if accion_precio == "PUT_SOPORTE_CERCA_SIN_RUPTURA" and senal["direccion"] == "put":
            senal["puntaje"] -= 3
            senal["razon"] += ", CHOCH cerca de soporte sin ruptura: penalizado, no bloqueado"

    if diagnostico_pa.get("permite") is False:
        razon_pa = diagnostico_pa.get("razon", "").lower()
    
        senal["validacion_accion_precio_ok"] = False
        senal["razon_validacion_accion_precio"] = diagnostico_pa.get("razon", "")
    
        senal["riesgos_base"] = (
            str(senal.get("riesgos_base", ""))
            + "|ACCION_PRECIO_NO_VALIDADA"
        ).strip("|")
    
        if "resistencia cerca" in razon_pa:
            senal["riesgos_base"] = (
                str(senal.get("riesgos_base", ""))
                + "|ESPERANDO_RUPTURA_RESISTENCIA"
            ).strip("|")
    
        elif "soporte cerca" in razon_pa:
            senal["riesgos_base"] = (
                str(senal.get("riesgos_base", ""))
                + "|ESPERANDO_RUPTURA_SOPORTE"
            ).strip("|")
    
        senal["razon"] += (
            ", advertencia acción precio: "
            + diagnostico_pa.get("razon", "")
            + ", enviada al cerebro único como evidencia"
        )
    
    else:
        senal["validacion_accion_precio_ok"] = True
        senal["razon_validacion_accion_precio"] = diagnostico_pa.get("razon", "")
    bloqueada_contraria, razon_contraria = vela_contraria_reciente(
        ctx,
        senal["direccion"]
    )
    
    senal["vela_contraria_reciente"] = bloqueada_contraria
    senal["razon_vela_contraria"] = razon_contraria
    
    if bloqueada_contraria:
        senal["riesgos_base"] = (
            str(senal.get("riesgos_base", ""))
            + "|VELA_CONTRARIA_RECIENTE"
        ).strip("|")
    
        senal["razon"] += (
            ", advertencia vela contraria reciente: "
            + razon_contraria
            + ", enviada al cerebro único como evidencia"
        )
    if senal["direccion"] == "call":
        precio_zona = ctx["soporte"]
    else:
        precio_zona = ctx["resistencia"]

    bloqueada, razon_zona = zona_ya_operada(
        activo,
        senal["direccion"],
        precio_zona,
        ctx["vol"]
    )
    
    senal["zona_operada"] = bloqueada
    senal["razon_zona_operada"] = razon_zona
    
    if bloqueada:
    
        senal["riesgos_base"] = (
            str(senal.get("riesgos_base", ""))
            + "|ZONA_OPERADA_RECIENTE"
        ).strip("|")
    
        senal["razon"] += (
            ", advertencia zona operada: "
            + razon_zona
            + ", enviada al cerebro único como evidencia"
        )

    ok_ubicacion, razon_ubicacion = filtro_fatiga_y_ubicacion(
        senal["direccion"],
        ctx["opens"],
        ctx["closes"],
        ctx["highs"],
        ctx["lows"],
        ctx["soporte"],
        ctx["resistencia"],
        ctx["vol"]
    )
    
    senal["validacion_ubicacion_ok"] = ok_ubicacion
    senal["razon_ubicacion"] = razon_ubicacion
    
    if not ok_ubicacion:
        senal["riesgos_base"] = (
            str(senal.get("riesgos_base", ""))
            + "|UBICACION_FATIGA_NO_VALIDADA"
        ).strip("|")
    
        senal["razon"] += (
            ", advertencia ubicación/fatiga: "
            + razon_ubicacion
            + ", enviada al cerebro único como evidencia"
        )
    
    senal["razon"] = (
        senal["razon"]
        + ", "
        + razon_ubicacion
        + ", MERCADO: "
        + ctx.get("tipo_mercado", "INDEFINIDO")
        + " - "
        + ctx.get("razon_mercado", "")
        + ", CALIDAD MERCADO: "
        + ctx.get("calidad_mercado", "SIN_DATOS")
        + " score "
        + str(ctx.get("score_mercado", 0))
        + ", TENDENCIA AVANZADA: "
        + ctx.get("estado_tendencia", "INDEFINIDA")
        + " fuerza "
        + str(ctx.get("fuerza_tendencia", 0))
        + ", VALIDACIÓN MERCADO: "
        + razon_validacion_mercado
        + ", ZONA SR: "
        + razon_zona_sr
        + ", ACCION PRECIO: "
        + senal.get("razon_accion_precio", "")
        + ", RUPTURA: "
        + senal.get("razon_ruptura", "")
    )
    
    senal["precio_zona"] = precio_zona
    senal["vol"] = ctx["vol"]
    senal["tipo_setup"] = senal.get("tipo_setup", "INDEFINIDO")
    senal["calidad_setup"] = senal.get("calidad_setup", "MEDIA")
    senal["modo_entrada_setup"] = senal.get("modo_entrada_setup", "DIRECTA")
    senal["balance_setup"] = senal.get("balance_setup", 0)
    senal["razones_setup"] = senal.get("razones_setup", "")
    senal["tipo_mercado"] = ctx.get("tipo_mercado", "INDEFINIDO")
    senal["razon_mercado"] = ctx.get("razon_mercado", "")
    senal["calidad_mercado"] = ctx.get("calidad_mercado", "SIN_DATOS")
    senal["score_mercado"] = ctx.get("score_mercado", 0)
    senal["estado_tendencia"] = ctx.get("estado_tendencia", "INDEFINIDA")
    senal["fuerza_tendencia"] = ctx.get("fuerza_tendencia", 0)
    senal["direccion_tendencia"] = ctx.get("direccion_tendencia", "INDEFINIDA")
    senal["soporte"] = ctx["soporte"]
    senal["resistencia"] = ctx["resistencia"]
    senal["vol"] = ctx["vol"]

    print(
        "CONTEXTO FINAL:",
        activo,
        senal["direccion"],
        senal["patron"],
        "| MERCADO:",
        senal.get("tipo_mercado"),
        "| CALIDAD:",
        senal.get("calidad_mercado"),
        senal.get("score_mercado"),
        "| TENDENCIA:",
        senal.get("estado_tendencia"),
        senal.get("fuerza_tendencia"),
        "| ACCION:",
        senal.get("accion_precio")
    )
    # Recalcular setup cuando la señal ya contiene
    # todas las validaciones, riesgos y evidencias finales.
    senal = enriquecer_senal_con_setup(senal)
    from decision_bootiq import aplicar_decision_unificada_a_senal

    resultado_bootiq = aplicar_decision_unificada_a_senal(
        senal,
        ctx
    )

    senal = resultado_bootiq["senal"]

    # En producción, una señal descartada por el Cerebro Único
    # no continúa hacia la ejecución.
    #
    # En backtest diagnóstico sí debe devolverse para medir:
    # - bloqueos correctos;
    # - WIN bloqueadas;
    # - LOSS bloqueadas;
    # - precisión del cerebro.
    modo_diagnostico = bool(
        ctx.get("_modo_backtest_diagnostico", False)
    )
    
    if (
        senal.get("decision_unificada_accion") == "NO_OPERAR"
        and not modo_diagnostico
    ):
        return None
    
    return senal

def analizar_activo(activo, modo_backtest_diagnostico=False):
    """
    Orquestador principal del análisis por activo.

    Responsabilidad:
    - leer contexto gráfico
    - preparar contexto de mercado
    - generar señales candidatas
    - evaluar cada candidata
    - devolver la primera señal válida

    No debe duplicar lógica de evaluación.
    No debe contener filtros largos.
    """

    ctx = leer_contexto_grafico(activo)

    if ctx is None:
        return None

    ctx = preparar_contexto_mercado(activo, ctx)
    ctx["_modo_backtest_diagnostico"] = bool(
        modo_backtest_diagnostico
    )
    if not validar_contexto_base(activo, ctx):
        return None

    senales = motor_estrategias_profesional(ctx)

    if not senales:
        return None

    if isinstance(senales, dict):
        senales = [senales]

    for senal in senales[:4]:
        senal_final = evaluar_senal_candidata(activo, ctx, senal)

        if senal_final is not None:
            return senal_final

    return None