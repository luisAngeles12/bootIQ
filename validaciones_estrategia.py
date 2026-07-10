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
