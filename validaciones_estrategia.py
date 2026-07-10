import time
import pandas as pd

import estado
from config import PUNTAJE_MINIMO
from historial import cargar_historial

def contexto_operacion(direccion, tendencia, estructura, patron, rechazo, zona_call, zona_put, rsi, extension):
    if direccion == "call":
        if patron == -1:
            return False, "bloqueado: patrón bajista"
        if zona_put and not zona_call:
            return False, "bloqueado: está en resistencia"
        if extension == 1:
            return False, "bloqueado: movimiento alcista extendido"
        if rsi > 62:
            return False, "bloqueado: RSI alto para call"
        if tendencia == -1 and not zona_call and rechazo != 1:
            return False, "bloqueado: call contra tendencia sin rechazo"
        return True, "contexto válido para call"
    if direccion == "put":
        if patron == 1:
            return False, "bloqueado: patrón alcista"
        if zona_call and not zona_put:
            return False, "bloqueado: está en soporte"
        if extension == -1:
            return False, "bloqueado: movimiento bajista extendido"
        if rsi < 38:
            return False, "bloqueado: RSI bajo para put"
        if tendencia == 1 and not zona_put and rechazo != -1:
            return False, "bloqueado: put contra tendencia sin rechazo"
        return True, "contexto válido para put"
    return False, "sin dirección"


def filtro_calidad_senal(
    direccion,
    puntaje,
    razones,
    rsi,
    tendencia,
    estructura,
    ema9,
    ema21,
    rechazo,
    falsa_call,
    falsa_put,
    br_call,
    br_put,
    patron
):
    texto = " | ".join(razones).lower()

    if puntaje < PUNTAJE_MINIMO:
        return False, "puntaje bajo"

    # Bloqueo fuerte: no operar zona sola
    if "zona de compra" in texto or "zona de venta" in texto:
        tiene_confirmacion_fuerte = (
            "rechazo" in texto
            or "pin bar" in texto
            or "martillo" in texto
            or "shooting star" in texto
            or "falsa ruptura" in texto
            or "breakout" in texto
            or "pullback" in texto
        )

        if not tiene_confirmacion_fuerte:
            return False, "zona sin confirmación fuerte"

    # Triple rechazo necesita confirmación real
    if "triple rechazo" in texto:
        confirmaciones = 0

        if direccion == "call":
            if tendencia == 1:
                confirmaciones += 1
            if estructura == 1:
                confirmaciones += 1
            if ema9 > ema21:
                confirmaciones += 1
            if rechazo == 1:
                confirmaciones += 1
            if falsa_call == 1:
                confirmaciones += 1
            if br_call == 1:
                confirmaciones += 1
            if patron == 1:
                confirmaciones += 1

        if direccion == "put":
            if tendencia == -1:
                confirmaciones += 1
            if estructura == -1:
                confirmaciones += 1
            if ema9 < ema21:
                confirmaciones += 1
            if rechazo == -1:
                confirmaciones += 1
            if falsa_put == -1:
                confirmaciones += 1
            if br_put == -1:
                confirmaciones += 1
            if patron == -1:
                confirmaciones += 1

        if confirmaciones < 3:
            return False, "triple rechazo sin confirmación suficiente"

    if direccion == "call" and rsi < 35 and rechazo != 1:
        return False, "RSI bajo sin rechazo comprador"

    if direccion == "put" and rsi > 65 and rechazo != -1:
        return False, "RSI alto sin rechazo vendedor"

    if direccion == "call":
        if tendencia == -1 and estructura == -1 and rechazo != 1 and falsa_call != 1:
            return False, "call contra tendencia fuerte"

    if direccion == "put":
        if tendencia == 1 and estructura == 1 and rechazo != -1 and falsa_put != -1:
            return False, "put contra tendencia fuerte"

    return True, "calidad aceptada"


def triple_rechazo_debil(
    direccion,
    razones,
    rechazo,
    falsa_call,
    falsa_put,
    br_call,
    br_put,
    tendencia,
    estructura,
    ema9,
    ema21,
    nombre_patron,
    puntaje
):
    texto = " | ".join(razones).lower()

    if "triple rechazo" not in texto:
        return False

    if direccion == "call":
        confirmaciones = 0

        if rechazo == 1:
            confirmaciones += 1

        if falsa_call == 1:
            confirmaciones += 1

        if br_call == 1:
            confirmaciones += 1

        if tendencia == 1:
            confirmaciones += 1

        if estructura == 1:
            confirmaciones += 1

        if ema9 > ema21:
            confirmaciones += 1

        if "pin bar" in nombre_patron or "martillo" in nombre_patron:
            confirmaciones += 1

        if puntaje >= 14:
            confirmaciones += 1

        return confirmaciones < 3

    if direccion == "put":
        confirmaciones = 0

        if rechazo == -1:
            confirmaciones += 1

        if falsa_put == -1:
            confirmaciones += 1

        if br_put == -1:
            confirmaciones += 1

        if tendencia == -1:
            confirmaciones += 1

        if estructura == -1:
            confirmaciones += 1

        if ema9 < ema21:
            confirmaciones += 1

        if "pin bar" in nombre_patron or "shooting star" in nombre_patron or "rechazo bajista" in nombre_patron:
            confirmaciones += 1

        if puntaje >= 14:
            confirmaciones += 1

        return confirmaciones < 3

    return True

def filtro_fatiga_y_ubicacion(
    direccion,
    opens,
    closes,
    highs,
    lows,
    soporte,
    resistencia,
    vol
):
    try:
        price = closes[-1]

        o = opens[-1]
        c = closes[-1]
        h = highs[-1]
        l = lows[-1]

        rango = h - l
        cuerpo = abs(c - o)

        if rango <= 0:
            return False, "rango inválido"

        fuerza = cuerpo / rango

        mecha_sup = h - max(o, c)
        mecha_inf = min(o, c) - l

        distancia_resistencia = abs(resistencia - price)
        distancia_soporte = abs(price - soporte)

        rango_total = abs(resistencia - soporte)

        if rango_total <= 0:
            rango_total = vol * 2

        posicion_rango = distancia_soporte / rango_total

        # =========================
        # CALL
        # =========================
        if direccion == "call":

            # Solo bloquea si está MUY pegado a resistencia
            # y además muestra rechazo vendedor.
            if (
                distancia_resistencia <= vol * 0.45
                and mecha_sup >= cuerpo * 1.6
            ):
                return False, "call rechazado en resistencia"

            # No comprar demasiado arriba.
            if posicion_rango >= 0.88:
                return False, "call demasiado arriba en rango"

            # Fatiga real, no cualquier mecha.
            if (
                mecha_sup >= cuerpo * 3.2
                and fuerza < 0.35
            ):
                return False, "fatiga alcista real"

            # Vela demasiado explotada.
            if (
                c > o
                and fuerza >= 0.82
                and posicion_rango >= 0.70
            ):
                return False, "vela alcista demasiado extendida"

        # =========================
        # PUT
        # =========================
        if direccion == "put":

            # Solo bloquea si está MUY pegado a soporte
            # y además muestra rechazo comprador.
            if (
                distancia_soporte <= vol * 0.45
                and mecha_inf >= cuerpo * 1.6
            ):
                return False, "put rechazado en soporte"

            # No vender demasiado abajo.
            if posicion_rango <= 0.12:
                return False, "put demasiado abajo en rango"

            # Fatiga real, no cualquier mecha.
            if (
                mecha_inf >= cuerpo * 3.2
                and fuerza < 0.35
            ):
                return False, "fatiga bajista real"

            # Vela demasiado explotada.
            if (
                c < o
                and fuerza >= 0.82
                and posicion_rango <= 0.30
            ):
                return False, "vela bajista demasiado extendida"

        return True, "ubicación válida"

    except Exception as e:
        print("Error filtro fatiga:", e)
        return False, "error filtro fatiga"

def filtro_final_operacion(direccion, calidad, razones):
    texto = " | ".join(razones).lower()

    if calidad == "C":
        return False, "calidad C bloqueada"

    if direccion == "call":
        if "penalizado: cerca resistencia" in texto:
            return False, "call bloqueado cerca de resistencia"

        if "penalizado: mecha superior" in texto:
            return False, "call bloqueado por mecha superior"

    if direccion == "put":
        if "penalizado: cerca soporte" in texto:
            return False, "put bloqueado cerca de soporte"

        if "penalizado: mecha inferior" in texto:
            return False, "put bloqueado por mecha inferior"

    return True, "filtro final aprobado"

def vela_contraria_reciente(ctx, direccion):
    try:
        opens = ctx["opens"]
        closes = ctx["closes"]
        highs = ctx["highs"]
        lows = ctx["lows"]

        # Revisamos las últimas 2 velas cerradas antes de la actual.
        for i in [-2, -3]:
            o = opens[i]
            c = closes[i]
            h = highs[i]
            l = lows[i]

            rango = h - l
            cuerpo = abs(c - o)

            if rango <= 0:
                continue

            mecha_sup = h - max(o, c)
            mecha_inf = min(o, c) - l

            vela_verde = c > o
            vela_roja = c < o

            martillo_alcista = (
                mecha_inf >= cuerpo * 2.0
                and mecha_inf >= rango * 0.45
                and vela_verde
            )

            rechazo_comprador_fuerte = (
                mecha_inf >= cuerpo * 2.5
                and mecha_inf >= rango * 0.50
            )

            shooting_bajista = (
                mecha_sup >= cuerpo * 2.0
                and mecha_sup >= rango * 0.45
                and vela_roja
            )

            rechazo_vendedor_fuerte = (
                mecha_sup >= cuerpo * 2.5
                and mecha_sup >= rango * 0.50
            )

            if direccion == "put" and (
                martillo_alcista
                or rechazo_comprador_fuerte
            ):
                return True, "PUT bloqueado: martillo/rechazo comprador reciente"

            if direccion == "call" and (
                shooting_bajista
                or rechazo_vendedor_fuerte
            ):
                return True, "CALL bloqueado: shooting/rechazo vendedor reciente"

        return False, "sin vela contraria reciente"

    except Exception as e:
        print("Error vela contraria reciente:", e)
        return False, "error vela contraria reciente"


def clave_zona(activo, direccion, precio_zona, vol):
    try:
        if vol <= 0:
            vol = abs(precio_zona) * 0.0001

        zona_redondeada = round(precio_zona / vol)

        return f"{activo}_{direccion}_{zona_redondeada}"

    except Exception:
        return f"{activo}_{direccion}_zona"

def zona_ya_operada(activo, direccion, precio_zona, vol):
    try:
        clave = clave_zona(activo, direccion, precio_zona, vol)

        if clave not in estado.zonas_operadas:
            return False, "zona libre"

        ultima_vez = estado.zonas_operadas[clave]

        # Bloquea la misma zona durante 3 minutos.
        if time.time() - ultima_vez < 180:
            return True, "zona ya operada recientemente"

        del estado.zonas_operadas[clave]
        return False, "zona liberada"

    except Exception:
        return False, "memoria de zona no disponible"

def registrar_zona_operada(activo, direccion, precio_zona, vol):
    try:
        clave = clave_zona(activo, direccion, precio_zona, vol)
        estado.zonas_operadas[clave] = time.time()

    except Exception:
        pass

def memoria_operativa(activo, direccion, patron):
    
    df = cargar_historial()

    if df is None:
        return True, "sin historial suficiente"

    try:
        df = df.copy()
        df["resultado"] = pd.to_numeric(df["resultado"], errors="coerce")
        df = df.dropna(subset=["resultado"])

        if df.empty:
            return True, "sin historial válido"

        df_activo = df[df["activo"] == activo]

        if len(df_activo) >= 3:
            ultimas = df_activo.tail(3)

            if all(ultimas["resultado"] < 0):
                return False, "activo bloqueado por 3 pérdidas seguidas"

        df_dir = df[
            (df["activo"] == activo)
            & (df["direccion"] == direccion)
        ]

        if len(df_dir) >= 3:
            ultimas_dir = df_dir.tail(3)

            if all(ultimas_dir["resultado"] < 0):
                return False, "dirección bloqueada por 3 pérdidas seguidas"

        df_patron = df[df["patron"] == patron]

        if len(df_patron) >= 5:
            winrate = len(df_patron[df_patron["resultado"] > 0]) / len(df_patron)

            if winrate < 0.30:
                return False, "patrón bloqueado por bajo winrate"

        df_activo_patron = df[
            (df["activo"] == activo)
            & (df["patron"] == patron)
        ]

        if len(df_activo_patron) >= 3:
            ultimas_ap = df_activo_patron.tail(3)

            if all(ultimas_ap["resultado"] < 0):
                return False, "activo/patrón bloqueado por 3 pérdidas seguidas"

        return True, "memoria permite operación"

    except Exception as e:
        print("Error en memoria operativa:", e)
        return True, "memoria no disponible"

def validar_estrategia_por_mercado(senal, ctx):
    if not senal:
        return False, "señal vacía"

    tipo_mercado = ctx.get("tipo_mercado", "INDEFINIDO")
    calidad_mercado = ctx.get("calidad_mercado", "NORMAL")
    patron = str(senal.get("patron", "")).lower()
    direccion = senal.get("direccion", "")
    puntaje = senal.get("puntaje", 0)

    estado_tendencia = ctx.get("estado_tendencia", "INDEFINIDA")
    direccion_tendencia = ctx.get("direccion_tendencia", "INDEFINIDA")

    cerca_soporte = ctx.get("cerca_soporte", False)
    cerca_resistencia = ctx.get("cerca_resistencia", False)

    rechazo = ctx.get("rechazo", 0)
    liquidity_sweep = ctx.get("liquidity_sweep", 0)
    patron_vela = ctx.get("patron", 0)
    regimen_mercado = ctx.get("regimen_mercado", "SIN_DATOS")
    modo_mercado = ctx.get("modo_mercado", "SIN_DATOS")
    riesgo_mercado = ctx.get("riesgo_mercado", "MEDIO")
    direccion_senal = "ALCISTA" if direccion == "call" else "BAJISTA"
    a_favor = direccion_senal == direccion_tendencia

    tendencia_debil = "DEBIL" in estado_tendencia
    tendencia_indefinida = estado_tendencia == "INDEFINIDA"
    tendencia_agotada = "AGOTADA" in estado_tendencia

    mercado_delicado = (
        tipo_mercado == "RANGO"
        or calidad_mercado == "SUCIO"
        or tendencia_debil
        or tendencia_indefinida
    )
    ruptura_confirmada = ctx.get("ruptura_confirmada", False)
    confirmacion_fuerte = (
        rechazo != 0
        or patron_vela != 0
        or liquidity_sweep != 0
        or ruptura_confirmada
        or puntaje >= 18
    )

    agotamiento_real_call = (
        direccion == "call"
        and cerca_soporte
        and (
            rechazo == 1
            or patron_vela == 1
            or liquidity_sweep == 1
            or tendencia_agotada
        )
    )

    agotamiento_real_put = (
        direccion == "put"
        and cerca_resistencia
        and (
            rechazo == -1
            or patron_vela == -1
            or liquidity_sweep == -1
            or tendencia_agotada
        )
    )

    agotamiento_real = agotamiento_real_call or agotamiento_real_put
    
    # =========================
    # FILTRO MAESTRO DE MERCADO
    # =========================
    if regimen_mercado == "EXPANSION_PELIGROSA":
        if "liquidity sweep" in patron and puntaje >= 25 and agotamiento_real:
            return True, "mercado peligroso: solo sweep premium con agotamiento real"

        return False, "mercado peligroso: señal bloqueada por régimen maestro"
    if regimen_mercado == "RANGO_SUCIO":
        if "liquidity sweep" in patron and puntaje >= 24:
            return True, "rango sucio: sweep premium permitido"

        return False, "rango sucio: señal bloqueada"
    if regimen_mercado == "COMPRESION_PRE_RUPTURA":
        if ruptura_confirmada and puntaje >= 22:
            return True, "compresión resuelta: ruptura confirmada"

        return False, "compresión: esperar ruptura confirmada"

    if regimen_mercado == "TENDENCIA_SUCIA":
        if "liquidity sweep" in patron and puntaje >= 23 and agotamiento_real:
            return True, "tendencia sucia: sweep permitido solo con agotamiento"
    
        if "pullback alcista" in patron and direccion == "call" and puntaje >= 19 and a_favor:
            return True, "tendencia sucia: pullback alcista permitido con puntaje alto"
    
        if "pullback bajista" in patron and direccion == "put" and puntaje >= 20 and a_favor:
            return True, "tendencia sucia: pullback bajista permitido con puntaje alto"
    
        if "choch" in patron and puntaje < 22:
            return False, "tendencia sucia: CHOCH débil bloqueado"
        
    if regimen_mercado == "TENDENCIA_LIMPIA":
        if "pullback" in patron and not a_favor:
            return False, "tendencia limpia: pullback contra tendencia bloqueado"

        if "continuacion" in patron or "continuación" in patron:
            if puntaje >= 16 and a_favor:
                return True, "tendencia limpia: continuación permitida a favor"

    if regimen_mercado == "RANGO_LIMPIO":
        if "pullback" in patron:
            return False, "rango limpio: pullback EMA bloqueado, preferir extremos"

        if "liquidity sweep" in patron and puntaje >= 22:
            return True, "rango limpio: sweep permitido"

        if ("reaccion" in patron or "reacción" in patron) and agotamiento_real:
            return True, "rango limpio: reacción en extremo permitida"

    # =========================
    # MERCADO CAÓTICO
    # =========================
    if calidad_mercado == "CAOTICO":
        if puntaje >= 25 and agotamiento_real:
            return True, "mercado caótico: solo señal premium con agotamiento real"

        return False, "mercado caótico: señal bloqueada"

    # =========================
    # CHOCH
    # =========================
    if "choch" in patron:

        if "choch alcista" in patron and direccion == "call":
            if cerca_resistencia and puntaje < 19:
                return False, "CHOCH CALL bloqueado: resistencia cerca requiere ruptura/retest o puntaje >= 22"

        if "choch bajista" in patron and direccion == "put":
            if cerca_soporte and puntaje < 19:
                return False, "CHOCH PUT bloqueado: soporte cerca requiere ruptura/retest o puntaje >= 22"

        if a_favor:
            if mercado_delicado and puntaje < 18:
                return False, "CHOCH bloqueado: mercado delicado requiere mínimo puntaje 18"

            if puntaje >= 18 and confirmacion_fuerte:
                return True, "CHOCH permitido a favor de tendencia con confirmación"
            
            if (
                puntaje >= 20
                and calidad_mercado in ["LIMPIO", "NORMAL"]
                and tipo_mercado in ["TENDENCIA_ALCISTA", "TENDENCIA_BAJISTA"]
                and a_favor
            ):
                return True, "CHOCH permitido por contexto fuerte aunque confirmación no sea perfecta"
            
            return False, "CHOCH bloqueado: sin confirmación fuerte"

        # CHOCH contra tendencia
        if not a_favor:
            if puntaje >= 23 and agotamiento_real:
                return True, "CHOCH contra tendencia permitido por agotamiento real"

            return False, "CHOCH contra tendencia bloqueado"

    # =========================
    # PULLBACK
    # =========================
    if "pullback" in patron:
        if calidad_mercado == "CAOTICO":
            return False, "pullback bloqueado en mercado caótico"
    
        if not a_favor:
            return False, "pullback fuera de contexto"
    
        if "pullback alcista" in patron:
            if tipo_mercado != "TENDENCIA_ALCISTA":
                return False, "pullback alcista requiere tendencia alcista"
    
            if calidad_mercado not in ["LIMPIO", "NORMAL"]:
                return False, "pullback alcista requiere mercado operable"
            
            if estado_tendencia not in ["ALCISTA_NORMAL", "ALCISTA_FUERTE"]:
                return False, "pullback alcista requiere tendencia alcista válida"
            if puntaje < 16:
                return False, "pullback alcista requiere mínimo 16 puntos"
    
            if rechazo != 1 and patron_vela != 1:
                return False, "pullback alcista requiere rechazo o patrón alcista"
    
            return True, "pullback alcista permitido con filtro reforzado"
    
        if "pullback bajista" in patron:
            if tipo_mercado != "TENDENCIA_BAJISTA":
                return False, "pullback bajista requiere tendencia bajista"

            if calidad_mercado not in ["LIMPIO", "NORMAL"]:
                return False, "pullback bajista requiere mercado operable"

            if estado_tendencia not in ["BAJISTA_NORMAL", "BAJISTA_FUERTE"]:
                return False, "pullback bajista requiere tendencia bajista válida"

            if puntaje < 18:
                return False, "pullback bajista requiere mínimo 18 puntos"

            if rechazo != -1 and patron_vela != -1:
                return False, "pullback bajista requiere rechazo o patrón bajista"
            if cerca_soporte and puntaje < 21:
                return False, "pullback bajista bloqueado: demasiado cerca de soporte"
            
            if estado_tendencia != "BAJISTA_FUERTE" and puntaje < 20:
                return False, "pullback bajista requiere tendencia bajista fuerte o puntaje alto"
            return True, "pullback bajista permitido con filtro reforzado"
    
        return False, "pullback no reconocido"
    # =========================
    # BREAKOUT + RETEST
    # =========================
    if "breakout" in patron or "retest" in patron:
        if puntaje >= 20:
            return True, "breakout/retest permitido"

        return False, "breakout/retest bloqueado: puntaje bajo"

    # =========================
    # LIQUIDITY SWEEP
    # =========================
    if "liquidity sweep" in patron:
        if a_favor:
            if mercado_delicado and puntaje < 21:
                return False, "sweep bloqueado: mercado delicado requiere mínimo 21"

            if puntaje >= 20 and confirmacion_fuerte:
                return True, "sweep permitido a favor de tendencia"

            return False, "sweep bloqueado: sin confirmación fuerte"

        # Sweep contra tendencia:
        # Solo permitir si hay agotamiento real.
        if not a_favor:
            if puntaje >= 24 and (
                agotamiento_real
                or rechazo != 0
                or liquidity_sweep != 0
            ):
                return True, "sweep contra tendencia permitido por barrida/rechazo fuerte"
        
            return False, "sweep contra tendencia bloqueado: sin agotamiento suficiente"
    # =========================
    # TENDENCIA ALCISTA
    # =========================
    if tipo_mercado == "TENDENCIA_ALCISTA":
        if direccion == "call":
            return True, "CALL permitido a favor de tendencia alcista"

        if direccion == "put":
            if puntaje >= 24 and agotamiento_real_put:
                return True, "PUT contra tendencia permitido por agotamiento alcista"

            return False, "PUT bloqueado contra tendencia alcista"

    # =========================
    # TENDENCIA BAJISTA
    # =========================
    if tipo_mercado == "TENDENCIA_BAJISTA":
        if direccion == "put":
            return True, "PUT permitido a favor de tendencia bajista"

        if direccion == "call":
            if puntaje >= 24 and agotamiento_real_call:
                return True, "CALL contra tendencia permitido por agotamiento bajista"

            return False, "CALL bloqueado contra tendencia bajista"

    # =========================
    # COMPRESIÓN
    # =========================
    if tipo_mercado == "COMPRESION":
        return False, "mercado en compresión: esperar ruptura"

    # =========================
    # EXPANSIÓN
    # =========================
    if tipo_mercado == "EXPANSION":
        if puntaje >= 24 and confirmacion_fuerte:
            return True, "señal premium permitida en expansión"

        return False, "mercado en expansión: evitar perseguir precio"

    # =========================
    # INDEFINIDO
    # =========================
    if tipo_mercado == "INDEFINIDO":
        if calidad_mercado in ["LIMPIO", "NORMAL"] and puntaje >= 20 and confirmacion_fuerte:
            return True, "señal fuerte permitida en mercado indefinido operable"
    
        if "choch" in patron and puntaje >= 20 and calidad_mercado in ["LIMPIO", "NORMAL"]:
            return True, "CHOCH permitido en indefinido operable"
    
        return False, "mercado indefinido: señal bloqueada"

    return True, "mercado permitido"
