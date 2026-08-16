from indicadores import *
from price_action import *
from zonas import *
from mercado import obtener_velas
from motor_setup import (enriquecer_senal_con_setup,clasificar_setup_estrategico)

from motor_candidatos import seleccionar_mejor_candidata_v3
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
    froms = data.get("from", [])
    
    if len(froms) != len(closes):
        return None
    
    vela_senal_from = int(froms[-1])
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
        
        # PASO 5.5A
        "froms": froms,
        "vela_senal_from": vela_senal_from,
        
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
        # Evidencias estructuradas generadas por Price Action.
        "pa_evidencias": pa_profesional.get(
            "evidencias",
            [],
        ),
        "rechazo_hist": rechazo_hist,
        "rechazo_hist_direccion": rechazo_hist.get("direccion", "NEUTRA"),
        "rechazo_hist_tipo": rechazo_hist.get("tipo", "SIN_RECHAZO_HISTORICO"),
        "rechazo_hist_fuerza": rechazo_hist.get("fuerza", 0),
        "rechazo_hist_razon": rechazo_hist.get("razon", ""),
    }


def diagnosticar_base_estrategia(senal, ctx):
    """
    Detecta hechos estratégicos sin clasificarlos como fortaleza o riesgo.

    Esta capa no decide si una evidencia es favorable o desfavorable.
    Solo describe lo observado y lo entrega al Cerebro Único para que
    este lo interprete junto con el aprendizaje histórico.

    Se conservan las claves ``riesgos_base`` y ``fortalezas_base`` vacías
    para mantener compatibilidad con módulos anteriores.
    """
    try:
        patron = str(senal.get("patron", "")).lower()
        direccion = str(senal.get("direccion", "")).lower()
        direccion_mayus = direccion.upper() or "NEUTRA"

        accion_precio = str(
            senal.get("accion_precio", "SIN_DATOS")
        ).upper()
        pa_tipo = str(
            ctx.get("pa_tipo", "SIN_CONTEXTO_CLARO")
        ).upper()
        pa_direccion = str(
            ctx.get("pa_direccion", "NEUTRA")
        ).upper()
        fuerza_tendencia = float(
            ctx.get("fuerza_tendencia", 0) or 0
        )
        direccion_tendencia = str(
            ctx.get("direccion_tendencia", "NEUTRA")
        ).upper()

        confianza_pa = evaluar_confianza_price_action(
            ctx,
            direccion,
        )
        nivel_pa = str(
            confianza_pa.get("nivel", "NINGUNA")
        ).upper()
        pa_valido = bool(
            confianza_pa.get("pa_valido", False)
        )

        tendencia_a_favor = (
            direccion == "call"
            and direccion_tendencia == "ALCISTA"
        ) or (
            direccion == "put"
            and direccion_tendencia == "BAJISTA"
        )

        evidencias = []
        tipos_registrados = set()

        def evidencia(tipo, razon, datos=None):
            tipo = str(tipo).strip().upper()
            if not tipo or tipo in tipos_registrados:
                return

            tipos_registrados.add(tipo)
            evidencias.append({
                "modulo": "estrategia",
                "fuente": "diagnosticar_base_estrategia",
                "tipo": tipo,
                "direccion": direccion_mayus,
                "peso": 0,
                "fuerza": 0,
                "confirmada": True,
                "razon": razon,
                "categoria": "HECHO_ESTRATEGICO",
                "datos": datos or {},
            })

        # Ubicación de la señal respecto a soporte y resistencia.
        if (
            direccion == "call"
            and accion_precio
            == "CALL_RESISTENCIA_CERCA_SIN_RUPTURA"
        ):
            evidencia(
                "CALL_RESISTENCIA_CERCA_SIN_RUPTURA",
                "La señal CALL está cerca de resistencia sin ruptura confirmada.",
                {"accion_precio": accion_precio},
            )

        if (
            direccion == "put"
            and accion_precio
            == "PUT_SOPORTE_CERCA_SIN_RUPTURA"
        ):
            evidencia(
                "PUT_SOPORTE_CERCA_SIN_RUPTURA",
                "La señal PUT está cerca de soporte sin ruptura confirmada.",
                {"accion_precio": accion_precio},
            )

        # Hechos de Price Action. No se etiquetan como buenos o malos.
        if pa_direccion == "NEUTRA" or pa_tipo == "SIN_CONTEXTO_CLARO":
            evidencia(
                "PA_SIN_CONTEXTO_CLARO",
                "Price Action no presenta una dirección clara.",
                {
                    "pa_tipo": pa_tipo,
                    "pa_direccion": pa_direccion,
                    "nivel_pa": nivel_pa,
                    "pa_valido": pa_valido,
                },
            )
        elif pa_direccion == direccion_mayus:
            evidencia(
                "PA_DIRECCION_A_FAVOR",
                "La dirección de Price Action coincide con la señal candidata.",
                {
                    "pa_tipo": pa_tipo,
                    "pa_direccion": pa_direccion,
                    "nivel_pa": nivel_pa,
                    "pa_valido": pa_valido,
                },
            )
        else:
            evidencia(
                "PA_DIRECCION_CONTRARIA",
                "La dirección de Price Action contradice la señal candidata.",
                {
                    "pa_tipo": pa_tipo,
                    "pa_direccion": pa_direccion,
                    "nivel_pa": nivel_pa,
                    "pa_valido": pa_valido,
                },
            )

        evidencia(
            "PA_NIVEL_" + nivel_pa,
            "Nivel de confianza detectado por Price Action: " + nivel_pa + ".",
            {
                "nivel_pa": nivel_pa,
                "pa_valido": pa_valido,
                "pa_tipo": pa_tipo,
            },
        )

        # Hechos de tendencia. Tampoco se convierten aquí en riesgo o fortaleza.
        if tendencia_a_favor:
            evidencia(
                "TENDENCIA_A_FAVOR",
                "La dirección de la tendencia coincide con la señal candidata.",
                {
                    "direccion_tendencia": direccion_tendencia,
                    "fuerza_tendencia": fuerza_tendencia,
                },
            )
        elif direccion_tendencia in ["ALCISTA", "BAJISTA"]:
            evidencia(
                "TENDENCIA_CONTRARIA",
                "La dirección de la tendencia contradice la señal candidata.",
                {
                    "direccion_tendencia": direccion_tendencia,
                    "fuerza_tendencia": fuerza_tendencia,
                },
            )
        else:
            evidencia(
                "TENDENCIA_SIN_DIRECCION_CLARA",
                "La tendencia no presenta una dirección definida.",
                {
                    "direccion_tendencia": direccion_tendencia,
                    "fuerza_tendencia": fuerza_tendencia,
                },
            )

        if fuerza_tendencia >= 65:
            nivel_fuerza = "ALTA"
        elif fuerza_tendencia >= 45:
            nivel_fuerza = "MEDIA"
        else:
            nivel_fuerza = "BAJA"

        evidencia(
            "FUERZA_TENDENCIA_" + nivel_fuerza,
            "Fuerza de tendencia detectada: " + nivel_fuerza + ".",
            {"fuerza_tendencia": fuerza_tendencia},
        )

        # Hechos propios de cada familia estratégica.
        if "choch" in patron:
            evidencia(
                "SETUP_CHOCH",
                "La señal candidata pertenece a la familia CHOCH.",
                {
                    "pa_valido": pa_valido,
                    "nivel_pa": nivel_pa,
                    "pa_direccion": pa_direccion,
                    "fuerza_tendencia": fuerza_tendencia,
                },
            )
            evidencia(
                "CHOCH_PA_COINCIDE"
                if pa_direccion == direccion_mayus
                else "CHOCH_PA_NO_COINCIDE",
                "Relación observada entre CHOCH y la dirección de Price Action.",
                {
                    "pa_valido": pa_valido,
                    "nivel_pa": nivel_pa,
                    "pa_direccion": pa_direccion,
                },
            )

        if "liquidity sweep" in patron:
            evidencia(
                "SETUP_LIQUIDITY_SWEEP",
                "La señal candidata pertenece a la familia liquidity sweep.",
                {
                    "pa_tipo": pa_tipo,
                    "pa_valido": pa_valido,
                    "nivel_pa": nivel_pa,
                },
            )
            evidencia(
                "SWEEP_CON_RECHAZO_O_AGOTAMIENTO"
                if ("RECHAZO" in pa_tipo or "AGOTAMIENTO" in pa_tipo)
                else "SWEEP_SIN_RECHAZO_O_AGOTAMIENTO",
                "Relación observada entre el sweep y el contexto de Price Action.",
                {
                    "pa_tipo": pa_tipo,
                    "pa_valido": pa_valido,
                    "nivel_pa": nivel_pa,
                },
            )

        if "pullback" in patron:
            evidencia(
                "SETUP_PULLBACK",
                "La señal candidata pertenece a la familia pullback.",
                {
                    "tendencia_a_favor": tendencia_a_favor,
                    "fuerza_tendencia": fuerza_tendencia,
                    "pa_valido": pa_valido,
                },
            )

        if "reacción" in patron or "reaccion" in patron:
            evidencia(
                "SETUP_REACCION_ZONA",
                "La señal candidata pertenece a la familia reacción en zona.",
                {
                    "pa_tipo": pa_tipo,
                    "pa_valido": pa_valido,
                    "nivel_pa": nivel_pa,
                },
            )

        if "continuación" in patron or "continuacion" in patron:
            evidencia(
                "SETUP_CONTINUACION",
                "La señal candidata pertenece a la familia continuación.",
                {
                    "tendencia_a_favor": tendencia_a_favor,
                    "fuerza_tendencia": fuerza_tendencia,
                    "pa_valido": pa_valido,
                },
            )

        return {
            # La clasificación queda pendiente del Cerebro Único.
            "base_estrategia": "MEDIA",
            "riesgos_base": [],
            "fortalezas_base": [],
            "evidencias_base": evidencias,
            "clasificacion_pendiente_cerebro": True,
        }

    except Exception as e:
        return {
            "base_estrategia": "ERROR",
            "riesgos_base": [],
            "fortalezas_base": [],
            "evidencias_base": [{
                "modulo": "estrategia",
                "fuente": "diagnosticar_base_estrategia",
                "tipo": "ERROR_DIAGNOSTICO_BASE",
                "direccion": str(
                    senal.get("direccion", "NEUTRA")
                ).upper(),
                "peso": 0,
                "fuerza": 0,
                "confirmada": False,
                "razon": str(e),
                "categoria": "ERROR_DATOS",
                "datos": {},
            }],
            "clasificacion_pendiente_cerebro": True,
            "error_base": str(e),
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
    """
    Diagnostica el contexto base del activo.

    No bloquea.
    No coloca cooldown.
    No decide si se opera.

    Convierte las condiciones desfavorables en evidencias
    para que el Cerebro Único tome la decisión final.
    """

    calidad = str(
        ctx.get("calidad_mercado", "SIN_DATOS")
    ).upper()

    score = float(
        ctx.get("score_mercado", 0) or 0
    )

    tendencia_estado = str(
        ctx.get("estado_tendencia", "INDEFINIDA")
    ).upper()

    riesgos_contexto = []

    mercado_evidencias = ctx.get("mercado_evidencias", [])

    if not isinstance(mercado_evidencias, list):
        mercado_evidencias = []

    def agregar_evidencia(tipo, razon):
        mercado_evidencias.append({
            "tipo": tipo,
            "razon": razon,
            "origen": "validar_contexto_base",
        })

    if calidad not in ["LIMPIO", "NORMAL"]:
        riesgos_contexto.append("MERCADO_SUCIO")

        agregar_evidencia(
            "mercado_sucio",
            "Calidad de mercado no limpia o normal.",
        )

    if score < 52:
        riesgos_contexto.append("SCORE_MERCADO_BAJO")

        agregar_evidencia(
            "score_mercado_bajo",
            "Score de mercado inferior a 52.",
        )

    if "DEBIL" in tendencia_estado and score < 62:
        riesgos_contexto.append("TENDENCIA_DEBIL")

        agregar_evidencia(
            "tendencia_debil",
            "Tendencia débil con score de mercado inferior a 62.",
        )

    if tendencia_estado == "INDEFINIDA":
        riesgos_contexto.append("TENDENCIA_INDEFINIDA")

        agregar_evidencia(
            "tendencia_indefinida",
            "No existe una tendencia suficientemente definida.",
        )

    ctx["riesgos_contexto_base"] = riesgos_contexto
    ctx["contexto_base_valido"] = not bool(riesgos_contexto)
    ctx["mercado_evidencias"] = mercado_evidencias

    # Siempre continúa.
    # El Cerebro Único decidirá.
    return True
def evaluar_senal_candidata(activo, ctx, senal):
    if senal is None:
        return None

    en_cooldown = estrategia_en_cooldown(
        senal.get("patron", "")
    )
    
    senal["estrategia_en_cooldown"] = bool(en_cooldown)
    
    if en_cooldown:
        print(
            senal["direccion"].upper(),
            "estrategia en cooldown enviada como evidencia:",
            activo,
            senal.get("patron", "")
        )
    
        riesgos_actuales = str(
            senal.get("riesgos_base", "")
        ).strip("|")
    
        senal["riesgos_base"] = "|".join(
            x for x in [
                riesgos_actuales,
                "ESTRATEGIA_EN_COOLDOWN",
            ]
            if x
        )
    
        senal["razon"] = (
            str(senal.get("razon", ""))
            + ", estrategia actualmente en cooldown; "
            + "enviada al Cerebro Único como evidencia"
        )
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
    # ==========================================================
    # BOOTIQ V3 — EL SETUP SOLO APORTA EVIDENCIA
    # ==========================================================
    # estrategia.py no modifica el puntaje de la señal.
    #
    # Los valores del setup ya fueron almacenados en:
    # - puntaje_extra_setup
    # - riesgo_extra_setup
    # - balance_setup
    # - calidad_setup
    # - modo_entrada_setup
    #
    # El Cerebro Único será responsable de interpretar
    # estos valores y convertirlos en confianza o decisión.
    senal["puntaje_antes_setup"] = senal.get("puntaje", 0)
    senal["setup_modifico_puntaje"] = False
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

    # Incorporar los hechos detectados por la capa estratégica.
    # Se mantienen con peso cero: estrategia.py observa; el Cerebro decide.
    evidencias_base = diagnostico_base.get("evidencias_base", [])
    if not isinstance(evidencias_base, list):
        evidencias_base = []

    evidencias_actuales = senal.get("estrategia_evidencias", [])
    if not isinstance(evidencias_actuales, list):
        evidencias_actuales = []

    tipos_actuales = {
        str(item.get("tipo", "")).upper()
        for item in evidencias_actuales
        if isinstance(item, dict)
    }

    for item in evidencias_base:
        if not isinstance(item, dict):
            continue
        tipo_item = str(item.get("tipo", "")).upper()
        if tipo_item and tipo_item not in tipos_actuales:
            evidencias_actuales.append(item)
            tipos_actuales.add(tipo_item)

    senal["estrategia_evidencias"] = evidencias_actuales
    senal["clasificacion_base_pendiente_cerebro"] = bool(
        diagnostico_base.get(
            "clasificacion_pendiente_cerebro",
            True,
        )
    )

    patron_lower = str(senal.get("patron", "")).lower()
    accion_precio = senal.get("accion_precio", "")

    # ==========================================================
    # BOOTIQ V3 — EVIDENCIAS CHOCH SIN ALTERAR PUNTAJE
    # ==========================================================
    evidencias_estrategia = senal.get("estrategia_evidencias", [])
    
    if not isinstance(evidencias_estrategia, list):
        evidencias_estrategia = []
    
    if "choch" in patron_lower:
        if accion_precio in ["CALL_ZONA_NEUTRA", "PUT_ZONA_NEUTRA"]:
            evidencias_estrategia.append({
                "modulo": "estrategia",
                "fuente": "estrategia",
                "tipo": "CHOCH_ZONA_NEUTRA",
                "direccion": senal.get("direccion", "neutra").upper(),
                "peso": 0,
                "fuerza": 0,
                "confirmada": True,
                "razon": "CHOCH detectado en zona neutra.",
                "categoria": "ESTRATEGIA_PRICE_ACTION",
                "datos": {
                    "accion_precio": accion_precio,
                    "ajuste_anterior": 2,
                },
            })
    
        if (
            accion_precio == "RECHAZO_COMPRADOR_SOPORTE"
            and senal["direccion"] == "call"
        ):
            evidencias_estrategia.append({
                "modulo": "estrategia",
                "fuente": "estrategia",
                "tipo": "CHOCH_RECHAZO_COMPRADOR_SOPORTE",
                "direccion": "CALL",
                "peso": 0,
                "fuerza": 0,
                "confirmada": True,
                "razon": "CHOCH apoyado por rechazo comprador en soporte.",
                "categoria": "ESTRATEGIA_PRICE_ACTION",
                "datos": {
                    "accion_precio": accion_precio,
                    "ajuste_anterior": 4,
                },
            })
    
        if (
            accion_precio == "RECHAZO_VENDEDOR_RESISTENCIA"
            and senal["direccion"] == "put"
        ):
            evidencias_estrategia.append({
                "modulo": "estrategia",
                "fuente": "estrategia",
                "tipo": "CHOCH_RECHAZO_VENDEDOR_RESISTENCIA",
                "direccion": "PUT",
                "peso": 0,
                "fuerza": 0,
                "confirmada": True,
                "razon": "CHOCH apoyado por rechazo vendedor en resistencia.",
                "categoria": "ESTRATEGIA_PRICE_ACTION",
                "datos": {
                    "accion_precio": accion_precio,
                    "ajuste_anterior": 4,
                },
            })
    
        if (
            accion_precio == "CALL_RESISTENCIA_CERCA_SIN_RUPTURA"
            and senal["direccion"] == "call"
        ):
            evidencias_estrategia.append({
                "modulo": "estrategia",
                "fuente": "estrategia",
                "tipo": "CHOCH_RESISTENCIA_CERCANA_SIN_RUPTURA",
                "direccion": "CALL",
                "peso": 0,
                "fuerza": 0,
                "confirmada": True,
                "razon": "CHOCH cerca de resistencia sin ruptura confirmada.",
                "categoria": "RIESGO_PRICE_ACTION",
                "datos": {
                    "accion_precio": accion_precio,
                    "ajuste_anterior": -3,
                },
            })
    
        if (
            accion_precio == "PUT_SOPORTE_CERCA_SIN_RUPTURA"
            and senal["direccion"] == "put"
        ):
            evidencias_estrategia.append({
                "modulo": "estrategia",
                "fuente": "estrategia",
                "tipo": "CHOCH_SOPORTE_CERCANO_SIN_RUPTURA",
                "direccion": "PUT",
                "peso": 0,
                "fuerza": 0,
                "confirmada": True,
                "razon": "CHOCH cerca de soporte sin ruptura confirmada.",
                "categoria": "RIESGO_PRICE_ACTION",
                "datos": {
                    "accion_precio": accion_precio,
                    "ajuste_anterior": -3,
                },
            })
    
    senal["estrategia_evidencias"] = evidencias_estrategia
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
    # ============================================================
    # PASO 5.5A — IDENTIDAD EXACTA DE LA VELA DE SEÑAL
    # ============================================================
    
    senal["vela_senal_from"] = int(
        ctx.get("vela_senal_from", 0) or 0
    )
    
    # OHLC exacto de la vela que originó la señal.
    # Solo diagnóstico de paridad; no modifica ninguna decisión.
    senal["vela_senal_open"] = float(
        ctx.get("ultima_open", 0) or 0
    )
    senal["vela_senal_close"] = float(
        ctx.get("ultima_close", 0) or 0
    )
    senal["vela_senal_high"] = float(
        ctx.get("ultima_high", 0) or 0
    )
    senal["vela_senal_low"] = float(
        ctx.get("ultima_low", 0) or 0
    )
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
    # ========================================================
    # EVIDENCIAS ESTRUCTURADAS
    # ========================================================
    
    pa_evidencias = ctx.get("pa_evidencias", [])
    
    if not isinstance(pa_evidencias, list):
        pa_evidencias = []
    
    mercado_evidencias = ctx.get(
        "mercado_evidencias",
        [],
    )
    
    if not isinstance(mercado_evidencias, list):
        mercado_evidencias = []
    
    senal["pa_evidencias"] = list(pa_evidencias)
    senal["mercado_evidencias"] = list(
        mercado_evidencias
    )
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
    
    # Auditoría completa del Cerebro Único.
    resultado_cerebro = resultado_bootiq.get("resultado", {})
    
    if not isinstance(resultado_cerebro, dict):
        resultado_cerebro = {}
    
    resultado_confianza = resultado_cerebro.get(
        "resultado_confianza",
        {},
    )
    
    if not isinstance(resultado_confianza, dict):
        resultado_confianza = {}
    
    resultado_pa = resultado_cerebro.get(
        "resultado_price_action",
        {},
    )
    
    if not isinstance(resultado_pa, dict):
        resultado_pa = {}
    
    resultado_mercado = resultado_cerebro.get(
        "resultado_mercado",
        {},
    )
    
    if not isinstance(resultado_mercado, dict):
        resultado_mercado = {}
    
    resultado_estrategia = resultado_cerebro.get(
        "resultado_estrategia",
        {},
    )
    
    if not isinstance(resultado_estrategia, dict):
        resultado_estrategia = {}
    
    senal["auditoria_confianza_base"] = resultado_confianza.get(
        "confianza_base",
        resultado_cerebro.get("confianza_base", 50),
    )
    
    senal["auditoria_ajuste_aprendizaje"] = resultado_confianza.get(
        "ajuste_aprendizaje",
        resultado_cerebro.get(
            "ajuste_confianza_aprendizaje",
            0,
        ),
    )
    
    senal["auditoria_ajuste_price_action"] = resultado_pa.get(
        "ajuste",
        0,
    )
    
    senal["auditoria_ajuste_mercado"] = resultado_mercado.get(
        "ajuste",
        0,
    )
    
    senal["auditoria_ajuste_estrategia"] = (
        resultado_estrategia.get("ajuste", 0)
    )
    
    senal["auditoria_ajuste_evidencias"] = resultado_confianza.get(
        "ajuste_evidencias",
        resultado_cerebro.get("ajuste_evidencias", 0),
    )
    
    senal["auditoria_ajuste_ponderacion"] = resultado_confianza.get(
        "ajuste_ponderacion",
        resultado_cerebro.get("ajuste_ponderacion", 0),
    )
    
    senal["auditoria_confianza_antes_ponderacion"] = (
        resultado_confianza.get(
            "confianza_antes_ponderacion",
            0,
        )
    )
    
    senal["auditoria_confianza_final"] = resultado_confianza.get(
        "confianza",
        resultado_cerebro.get("confianza", 0),
    )
    
    senal["auditoria_motivos_price_action"] = " | ".join(
        str(x)
        for x in resultado_pa.get("motivos", [])
    )
    
    senal["auditoria_motivos_mercado"] = " | ".join(
        str(x)
        for x in resultado_mercado.get("motivos", [])
    )
    
    senal["auditoria_motivos_estrategia"] = " | ".join(
        str(x)
        for x in resultado_estrategia.get("motivos", [])
    )

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

def analizar_activo(
    activo,
    modo_backtest_diagnostico=False,
):
    """
    Orquestador principal del análisis por activo.

    Responsabilidades:
    - leer el contexto gráfico;
    - preparar el contexto de mercado;
    - generar todas las señales candidatas;
    - evaluar cada candidata con el Cerebro Único;
    - ordenar las candidatas usando el ranking oficial V3;
    - devolver la mejor señal disponible.

    estrategia.py NO decide si una operación es buena o mala.

    Todas las candidatas son evaluadas primero por el Cerebro Único.
    Después motor_candidatos.py selecciona cuál de las candidatas
    ya evaluadas tiene mayor prioridad estadística V3.
    """

    ctx = leer_contexto_grafico(activo)

    if ctx is None:
        return None

    ctx = preparar_contexto_mercado(
        activo,
        ctx,
    )

    ctx["_modo_backtest_diagnostico"] = bool(
        modo_backtest_diagnostico
    )

    if not validar_contexto_base(
        activo,
        ctx,
    ):
        return None

    senales = motor_estrategias_profesional(
        ctx
    )

    if not senales:
        return None

    if isinstance(senales, dict):
        senales = [senales]

    candidatas_evaluadas = []

    # ========================================================
    # EVALUAR TODAS LAS CANDIDATAS PRINCIPALES
    # ========================================================
    #
    # Ninguna señal gana por aparecer primero.
    #
    # motor_estrategias genera candidatos.
    # estrategia prepara evidencia.
    # Cerebro Único evalúa cada candidato.
    # motor_candidatos selecciona posteriormente.
    # ========================================================

    for posicion, senal in enumerate(
        senales[:4],
        start=1,
    ):
        if not isinstance(senal, dict):
            continue

        senal[
            "_ranking_estrategia_inicial"
        ] = posicion

        senal_final = evaluar_senal_candidata(
            activo,
            ctx,
            senal,
        )

        if senal_final is None:
            continue

        candidatas_evaluadas.append(
            senal_final
        )

    if not candidatas_evaluadas:
        return None

    # ========================================================
    # FASE C-B1 — RANKING ÚNICO V3
    # ========================================================
    #
    # ANTES:
    #
    # estrategia.py volvía a escoger usando:
    # - confianza legacy;
    # - consenso;
    # - score_final;
    # - puntaje;
    # - prioridad.
    #
    # Y paralelamente calculaba cuál habría elegido V3,
    # pero solamente como sombra.
    #
    # AHORA:
    #
    # Las candidatas ya fueron evaluadas por el Cerebro Único.
    # estrategia.py NO vuelve a decidir.
    #
    # motor_candidatos.py únicamente las ORDENA utilizando
    # información ya producida por V3:
    #
    # - decisión oficial;
    # - probabilidad histórica V3;
    # - muestra histórica;
    # - score/puntaje únicamente como desempate.
    #
    # No se calcula aprendizaje aquí.
    # No se recalcula probabilidad.
    # No se crea otro Cerebro.
    # ========================================================

    mejor_senal = (
        seleccionar_mejor_candidata_v3(
            candidatas_evaluadas
        )
    )

    if mejor_senal is None:
        return None

    # ========================================================
    # AUDITORÍA DE COMPETENCIA ENTRE ESTRATEGIAS
    # ========================================================

    mejor_senal[
        "cantidad_candidatas_evaluadas"
    ] = len(
        candidatas_evaluadas
    )

    mejor_senal[
        "resumen_competencia_estrategias"
    ] = [
        {
            "patron": candidata.get(
                "patron",
                "SIN_PATRON",
            ),

            "direccion": candidata.get(
                "direccion",
                "SIN_DIRECCION",
            ),

            "decision": candidata.get(
                "cerebro_unico_decision",
                candidata.get(
                    "decision_unificada_accion",
                    candidata.get(
                        "decision_bootiq",
                        "NO_OPERAR",
                    ),
                ),
            ),

            # Se conserva para diagnóstico legacy.
            "confianza": candidata.get(
                "auditoria_confianza_final",
                candidata.get(
                    "confianza_final_cerebro",
                    candidata.get(
                        "confianza_bootiq",
                        0,
                    ),
                ),
            ),

            # Información V3 que ahora sí importa
            # para entender por qué ganó.
            "probabilidad_v3": candidata.get(
                "probabilidad_v3",
                candidata.get(
                    "probabilidad_estimada",
                    0,
                ),
            ),

            "muestra_probabilidad": (
                candidata.get(
                    "muestra_probabilidad",
                    0,
                )
            ),

            "confiabilidad_probabilidad": (
                candidata.get(
                    "confiabilidad_probabilidad",
                    "SIN_DATOS",
                )
            ),

            "fuente_probabilidad_principal": (
                candidata.get(
                    "fuente_probabilidad_principal",
                    "",
                )
            ),

            # Compatibilidad / desempate.
            "score_final": candidata.get(
                "score_final",
                0,
            ),

            "nivel_consenso": candidata.get(
                "nivel_consenso",
                "MUY_BAJO",
            ),

            "ranking_inicial": candidata.get(
                "_ranking_estrategia_inicial",
                0,
            ),
        }

        for candidata in candidatas_evaluadas
    ]

    # ========================================================
    # COMPATIBILIDAD CON REPORTES V3 SOMBRA ANTERIORES
    # ========================================================
    #
    # Estos nombres se mantienen temporalmente para que
    # backtest_bot_real.py no pierda columnas/reportes.
    #
    # Ya NO existe una segunda selección V3 en estrategia.py.
    # La candidata V3 oficial es mejor_senal.
    # ========================================================

    mejor_senal[
        "seleccion_v3_sombra_patron"
    ] = mejor_senal.get(
        "patron",
        "",
    )

    mejor_senal[
        "seleccion_v3_sombra_direccion"
    ] = mejor_senal.get(
        "direccion",
        "",
    )

    mejor_senal[
        "seleccion_v3_sombra_probabilidad"
    ] = mejor_senal.get(
        "probabilidad_v3",
        mejor_senal.get(
            "probabilidad_estimada",
            0,
        ),
    )

    mejor_senal[
        "seleccion_v3_sombra_decision"
    ] = mejor_senal.get(
        "cerebro_unico_decision",
        mejor_senal.get(
            "decision_estadistica_sombra",
            "SIN_DATOS",
        ),
    )

    mejor_senal[
        "seleccion_v3_sombra_misma_que_actual"
    ] = True

    mejor_senal[
        "seleccion_v3_sombra_muestra"
    ] = mejor_senal.get(
        "muestra_probabilidad",
        0,
    )

    # Auditoría explícita de la nueva arquitectura.
    mejor_senal[
        "ranking_candidatas_origen"
    ] = "MOTOR_CANDIDATOS_V3"

    mejor_senal[
        "ranking_candidatas_probabilidad"
    ] = mejor_senal.get(
        "probabilidad_v3",
        mejor_senal.get(
            "probabilidad_estimada",
            0,
        ),
    )

    mejor_senal[
        "ranking_candidatas_muestra"
    ] = mejor_senal.get(
        "muestra_probabilidad",
        0,
    )

    return mejor_senal