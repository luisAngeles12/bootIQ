from config import PUNTAJE_MINIMO
from estadisticas import estrategias_bloqueables, activos_bloqueables
from historial import cargar_historial
from indicadores import *
from price_action import *
from zonas import *
from mercado import obtener_velas
import time
import estado
from contexto_mercado import detectar_tipo_mercado, validar_estrategia_por_mercado, diagnostico_calidad_mercado, diagnostico_tendencia_avanzada
from utils import estrategia_en_cooldown,registrar_bloqueo

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


def detectar_estrategias_price_action(patron, nombre_patron, rechazo, nombre_rechazo, zona_call, zona_put, falsa_call, nombre_falsa_call, falsa_put, nombre_falsa_put, br_call, nombre_br_call, br_put, nombre_br_put, triple_soporte, triple_resistencia, entrada_pullback_call, entrada_pullback_put, micro, rsi):
    senales_call = []
    senales_put = []
    if falsa_call == 1:
        senales_call.append(("falsa ruptura alcista", 5, nombre_falsa_call))
    if falsa_put == -1:
        senales_put.append(("falsa ruptura bajista", 5, nombre_falsa_put))
    if br_call == 1:
        senales_call.append(("breakout retest alcista", 4, nombre_br_call))
    if br_put == -1:
        senales_put.append(("breakout retest bajista", 4, nombre_br_put))
    if rechazo == 1 and zona_call:
        senales_call.append(("rechazo comprador en soporte", 4, nombre_rechazo))
    if rechazo == -1 and zona_put:
        senales_put.append(("rechazo vendedor en resistencia", 4, nombre_rechazo))
    if triple_soporte:
        senales_call.append(("triple rechazo en soporte", 3, "triple rechazo en soporte"))
    if triple_resistencia:
        senales_put.append(("triple rechazo en resistencia", 3, "triple rechazo en resistencia"))
    if entrada_pullback_call:
        senales_call.append(("pullback alcista", 3, "pullback válido para compra"))
    if entrada_pullback_put:
        senales_put.append(("pullback bajista", 3, "pullback válido para venta"))
    if patron == 1 and zona_call and rechazo == 1 and rsi <= 55:
        senales_call.append(("patrón alcista confirmado", 3, nombre_patron))
    if patron == -1 and zona_put and rechazo == -1 and rsi >= 45:
        senales_put.append(("patrón bajista confirmado", 3, nombre_patron))
    if micro == 1 and zona_call and 42 <= rsi <= 58:
        senales_call.append(("micro tendencia alcista en zona", 2, "micro tendencia alcista"))
    if micro == -1 and zona_put and 42 <= rsi <= 58:
        senales_put.append(("micro tendencia bajista en zona", 2, "micro tendencia bajista"))
    return senales_call, senales_put


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


def ajustar_puntaje_por_ubicacion(
    direccion,
    puntaje,
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
            return puntaje, "rango inválido"

        mecha_sup = h - max(o, c)
        mecha_inf = min(o, c) - l

        distancia_resistencia = abs(resistencia - price)
        distancia_soporte = abs(price - soporte)

        rango_total = abs(resistencia - soporte)

        if rango_total <= 0:
            rango_total = vol * 2

        posicion_rango = distancia_soporte / rango_total

        penalizaciones = []

        if direccion == "call":
            if distancia_resistencia <= vol * 0.8:
                puntaje -= 2
                penalizaciones.append("penalizado: cerca resistencia")

            if posicion_rango >= 0.75:
                puntaje -= 2
                penalizaciones.append("penalizado: alto en rango")

            if cuerpo > 0 and mecha_sup >= cuerpo * 1.8:
                puntaje -= 2
                penalizaciones.append("penalizado: mecha superior")

        if direccion == "put":
            if distancia_soporte <= vol * 0.8:
                puntaje -= 2
                penalizaciones.append("penalizado: cerca soporte")

            if posicion_rango <= 0.25:
                puntaje -= 2
                penalizaciones.append("penalizado: bajo en rango")

            if cuerpo > 0 and mecha_inf >= cuerpo * 1.8:
                puntaje -= 2
                penalizaciones.append("penalizado: mecha inferior")

        if not penalizaciones:
            return puntaje, "ubicación sin penalización"

        return puntaje, ", ".join(penalizaciones)

    except Exception as e:
        print("Error ajustando ubicación:", e)
        return puntaje, "error ubicación"


def clasificar_senal(puntaje, razones, rsi):
    texto = " | ".join(razones).lower()

    calidad = "C"
    prioridad = 0

    tiene_rechazo = "rechazo" in texto
    tiene_pullback = "pullback" in texto
    tiene_falsa = "falsa ruptura" in texto
    tiene_breakout = "breakout" in texto
    tiene_patron = (
        "pin bar" in texto
        or "martillo" in texto
        or "shooting star" in texto
        or "envolvente" in texto
    )

    if puntaje >= 15 and (tiene_rechazo or tiene_falsa or tiene_breakout):
        calidad = "A+"
        prioridad = 4

    elif puntaje >= 11 and (tiene_rechazo or tiene_pullback or tiene_patron):
        calidad = "A"
        prioridad = 3

    elif puntaje >= 7 and (tiene_rechazo or tiene_pullback or tiene_falsa or tiene_breakout):
        calidad = "B"
        prioridad = 2

    elif puntaje >= PUNTAJE_MINIMO:
        calidad = "C"
        prioridad = 1

    if rsi > 68 or rsi < 32:
        prioridad -= 1

    if prioridad <= 0:
        calidad = "C"
        prioridad = 0

    return calidad, prioridad


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


def evaluar_reaccion_en_zona(
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

        ultimas = 8

        opens_r = opens[-ultimas:]
        closes_r = closes[-ultimas:]
        highs_r = highs[-ultimas:]
        lows_r = lows[-ultimas:]

        distancia_resistencia = abs(resistencia - price)
        distancia_soporte = abs(price - soporte)

        cerca_resistencia = distancia_resistencia <= vol * 1.2
        cerca_soporte = distancia_soporte <= vol * 1.2

        mechas_superiores = 0
        mechas_inferiores = 0
        velas_rojas = 0
        velas_verdes = 0

        for o, c, h, l in zip(opens_r, closes_r, highs_r, lows_r):
            rango = h - l
            cuerpo = abs(c - o)

            if rango <= 0:
                continue

            mecha_sup = h - max(o, c)
            mecha_inf = min(o, c) - l

            if mecha_sup >= cuerpo * 1.3:
                mechas_superiores += 1

            if mecha_inf >= cuerpo * 1.3:
                mechas_inferiores += 1

            if c < o:
                velas_rojas += 1

            if c > o:
                velas_verdes += 1

        o1 = opens[-1]
        c1 = closes[-1]
        h1 = highs[-1]
        l1 = lows[-1]

        rango1 = h1 - l1
        cuerpo1 = abs(c1 - o1)

        if rango1 <= 0:
            return False, "rango inválido en zona"

        mecha_sup_1 = h1 - max(o1, c1)
        mecha_inf_1 = min(o1, c1) - l1

        vela_roja = c1 < o1
        vela_verde = c1 > o1

        rechazo_vendedor = (
            cerca_resistencia
            and mecha_sup_1 >= cuerpo1 * 1.4
            and vela_roja
        )

        rechazo_comprador = (
            cerca_soporte
            and mecha_inf_1 >= cuerpo1 * 1.4
            and vela_verde
        )

        if direccion == "put":
            if cerca_resistencia and (
                rechazo_vendedor
                or mechas_superiores >= 3
                or velas_rojas >= 5
            ):
                return True, "PUT válido por reacción en resistencia"

            return False, "PUT sin reacción suficiente en resistencia"

        if direccion == "call":
            if cerca_soporte and (
                rechazo_comprador
                or mechas_inferiores >= 3
                or velas_verdes >= 5
            ):
                return True, "CALL válido por reacción en soporte"

            return False, "CALL sin reacción suficiente en soporte"

        return False, "dirección inválida"

    except Exception as e:
        print("Error evaluando reacción en zona:", e)
        return False, "error reacción zona"


def intentar_operacion_contraria_en_zona(
    activo,
    direccion_bloqueada,
    razon_bloqueo,
    puntaje_call,
    puntaje_put,
    razones_call,
    razones_put,
    rsi,
    rechazo,
    patron,
    micro,
    triple_soporte,
    triple_resistencia,
    cerca_banda_inferior,
    cerca_banda_superior,
    call_reaccion,
    razon_call_reaccion,
    put_reaccion,
    razon_put_reaccion
):
    try:
        texto = razon_bloqueo.lower()

        # Si CALL fue bloqueado cerca de resistencia,
        # buscamos PUT desde resistencia.
        if direccion_bloqueada == "call" and "cerca de resistencia" in texto:

            if not put_reaccion:
                return None

            if not (
                rechazo == -1
                or patron == -1
                or micro == -1
                or triple_resistencia
                or cerca_banda_superior
            ):
                return None

            razones = razones_put.copy()
            razones.append("inversión inteligente: CALL bloqueado en resistencia")
            razones.append(razon_put_reaccion)

            puntaje = max(puntaje_put, PUNTAJE_MINIMO + 2)

            calidad, prioridad = clasificar_senal(
                puntaje,
                razones,
                rsi
            )

            if prioridad <= 0:
                return None

            permitido, razon_memoria = memoria_operativa(
                activo,
                "put",
                razones[0] if razones else "PUT por reacción en resistencia"
            )

            if not permitido:
                print("PUT contrario bloqueado por memoria:", activo, razon_memoria)
                return None

            razones.append("calidad " + calidad)
            razones.append(razon_memoria)

            print("PUT contrario aprobado por resistencia:", activo)

            return {
                "activo": activo,
                "direccion": "put",
                "puntaje": puntaje,
                "patron": razones[0] if razones else "PUT por reacción en resistencia",
                "rsi": round(rsi, 2),
                "razon": ", ".join(razones),
                "calidad": calidad,
                "prioridad": prioridad
            }

        # Si PUT fue bloqueado cerca de soporte,
        # buscamos CALL desde soporte.
        if direccion_bloqueada == "put" and "cerca de soporte" in texto:

            if not call_reaccion:
                return None

            if not (
                rechazo == 1
                or patron == 1
                or micro == 1
                or triple_soporte
                or cerca_banda_inferior
            ):
                return None

            razones = razones_call.copy()
            razones.append("inversión inteligente: PUT bloqueado en soporte")
            razones.append(razon_call_reaccion)

            puntaje = max(puntaje_call, PUNTAJE_MINIMO + 2)

            calidad, prioridad = clasificar_senal(
                puntaje,
                razones,
                rsi
            )

            if prioridad <= 0:
                return None

            permitido, razon_memoria = memoria_operativa(
                activo,
                "call",
                razones[0] if razones else "CALL por reacción en soporte"
            )

            if not permitido:
                print("CALL contrario bloqueado por memoria:", activo, razon_memoria)
                return None

            razones.append("calidad " + calidad)
            razones.append(razon_memoria)

            print("CALL contrario aprobado por soporte:", activo)

            return {
                "activo": activo,
                "direccion": "call",
                "puntaje": puntaje,
                "patron": razones[0] if razones else "CALL por reacción en soporte",
                "rsi": round(rsi, 2),
                "razon": ", ".join(razones),
                "calidad": calidad,
                "prioridad": prioridad
            }

        return None

    except Exception as e:
        print("Error intentando operación contraria:", activo, e)
        return None

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
def crear_senal_profesional(activo, direccion, estrategia, puntaje, rsi, razones):
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
        "prioridad": prioridad
    }

def fuerza_patron_vela(nombre_patron):
    try:
        texto = str(nombre_patron).lower()

        # Máxima fuerza
        if "envolvente" in texto:
            return 3, "patrón fuerte: envolvente"

        if "morning star" in texto:
            return 3, "patrón fuerte: morning star"

        if "evening star" in texto:
            return 3, "patrón fuerte: evening star"

        # Fuerza media
        if "pin bar" in texto:
            return 2, "patrón medio: pin bar"

        if "martillo" in texto:
            return 2, "patrón medio: martillo"

        if "shooting star" in texto:
            return 2, "patrón medio: shooting star"

        # Fuerza baja
        if "doji" in texto:
            return 1, "patrón débil: doji"

        return 0, "sin patrón fuerte"

    except Exception as e:
        print("Error fuerza patrón:", e)
        return 0, "error patrón"
def clasificar_senal_profesional(puntaje, razones, estrategia, rsi):
    texto = " | ".join(razones).lower()
    estrategia = estrategia.lower()

    calidad = "C"
    prioridad = 0

    if puntaje >= 18:
        calidad = "A+"
        prioridad = 4

    elif puntaje >= 14:
        calidad = "A"
        prioridad = 3

    elif puntaje >= 8:
        calidad = "B"
        prioridad = 2

    else:
        calidad = "C"
        prioridad = 0

    # No permitir operaciones pobres.
    if calidad == "C":
        return "C", 0

    # Bloqueo por RSI extremo si no hay reversa fuerte.
    if rsi > 68 and "reversa" not in estrategia and "rechazo vendedor" not in texto:
        prioridad -= 1

    if rsi < 32 and "reversa" not in estrategia and "rechazo comprador" not in texto:
        prioridad -= 1

    if prioridad <= 0:
        return "C", 0

    return calidad, prioridad
def detectar_cambio_estructura_choch(highs, lows, closes, lookback=10):
    try:
        if len(closes) < lookback + 4:
            return 0, "sin cambio de estructura"

        highs_previos = highs[-lookback-2:-2]
        lows_previos = lows[-lookback-2:-2]

        ultimo_close = closes[-1]

        max_prev = max(highs_previos)
        min_prev = min(lows_previos)

        # CHOCH alcista
        if ultimo_close > max_prev:
            return 1, "CHOCH alcista: rompe estructura superior"

        # CHOCH bajista
        if ultimo_close < min_prev:
            return -1, "CHOCH bajista: rompe estructura inferior"

        return 0, "sin cambio de estructura"

    except Exception as e:
        print("Error detectando CHOCH:", e)
        return 0, "error CHOCH"
def detectar_liquidity_sweep(opens, closes, highs, lows, lookback=12):
    try:
        if len(closes) < lookback + 3:
            return 0, "sin barrida de liquidez"

        high_actual = highs[-1]
        low_actual = lows[-1]
        close_actual = closes[-1]
        open_actual = opens[-1]

        max_prev = max(highs[-lookback-1:-1])
        min_prev = min(lows[-lookback-1:-1])

        vela_roja = close_actual < open_actual
        vela_verde = close_actual > open_actual

        # Barre máximo anterior y cierra debajo = posible PUT
        if high_actual > max_prev and close_actual < max_prev and vela_roja:
            return -1, "liquidity sweep bajista: barrida de máximos"

        # Barre mínimo anterior y cierra arriba = posible CALL
        if low_actual < min_prev and close_actual > min_prev and vela_verde:
            return 1, "liquidity sweep alcista: barrida de mínimos"

        return 0, "sin barrida de liquidez"

    except Exception as e:
        print("Error detectando liquidity sweep:", e)
        return 0, "error liquidity sweep"
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
        opens,
        closes,
        highs,
        lows
    )

    rechazo, nombre_rechazo = rechazo_real(
        opens,
        closes,
        highs,
        lows
    )

    vol = volatilidad(highs, lows, 14)

    if vol <= 0:
        return None

    soporte_zona, resistencia_zona = soporte_resistencia_zonas(
        price,
        highs,
        lows,
        vol
    )

    soporte = soporte_zona["precio"]
    resistencia = resistencia_zona["precio"]

    bb_superior, bb_media, bb_inferior = bollinger_bands(
        closes,
        20,
        2
    )

    if bb_superior is None:
        return None

    tolerancia_soporte = soporte_zona.get("tolerancia", vol * 0.45)
    tolerancia_resistencia = resistencia_zona.get("tolerancia", vol * 0.45)

    cerca_soporte = abs(price - soporte) <= tolerancia_soporte * 1.25
    cerca_resistencia = abs(resistencia - price) <= tolerancia_resistencia * 1.25

    if cerca_soporte and cerca_resistencia:
        distancia_soporte = abs(price - soporte)
        distancia_resistencia = abs(resistencia - price)

        fuerza_soporte = soporte_zona.get(
            "fuerza",
            soporte_zona.get("toques", 1)
        )

        fuerza_resistencia = resistencia_zona.get(
            "fuerza",
            resistencia_zona.get("toques", 1)
        )

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

    triple_soporte = triple_rechazo(
        highs,
        lows,
        soporte_zona,
        "soporte",
        25
    )

    triple_resistencia = triple_rechazo(
        highs,
        lows,
        resistencia_zona,
        "resistencia",
        25
    )

    falsa_call, nombre_falsa_call = falsa_ruptura(
        opens,
        closes,
        highs,
        lows,
        soporte_zona,
        "soporte"
    )

    falsa_put, nombre_falsa_put = falsa_ruptura(
        opens,
        closes,
        highs,
        lows,
        resistencia_zona,
        "resistencia"
    )

    br_call, nombre_br_call = breakout_retest(
        opens,
        closes,
        highs,
        lows,
        resistencia_zona,
        "resistencia"
    )

    br_put, nombre_br_put = breakout_retest(
        opens,
        closes,
        highs,
        lows,
        soporte_zona,
        "soporte"
    )

    extension = movimiento_extendido(opens, closes, 5)
    micro = micro_tendencia(opens, closes, 6)

    entrada_pullback_call = entrada_pullback(
        "call",
        price,
        ema21,
        soporte,
        resistencia,
        vol,
        patron,
        rechazo
    )

    entrada_pullback_put = entrada_pullback(
        "put",
        price,
        ema21,
        soporte,
        resistencia,
        vol,
        patron,
        rechazo
    )

    call_reaccion, razon_call_reaccion = evaluar_reaccion_en_zona(
        "call",
        opens,
        closes,
        highs,
        lows,
        soporte,
        resistencia,
        vol
    )

    put_reaccion, razon_put_reaccion = evaluar_reaccion_en_zona(
        "put",
        opens,
        closes,
        highs,
        lows,
        soporte,
        resistencia,
        vol
    )

    liquidity_sweep, nombre_liquidity_sweep = detectar_liquidity_sweep(
        opens,
        closes,
        highs,
        lows
    )

    choch, nombre_choch = detectar_cambio_estructura_choch(
        highs,
        lows,
        closes
    )

    puntos_patron_vela, razon_patron_vela = fuerza_patron_vela(
        nombre_patron
    )

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

    ctx = {
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
    }

    return ctx
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
def motor_estrategias_profesional(ctx):
    señales = []

    activo = ctx["activo"]
    rsi = ctx["rsi"]

    tipo_mercado = ctx.get("tipo_mercado", "INDEFINIDO")
    razon_mercado = ctx.get("razon_mercado", "")

    estrategias_malas = estrategias_bloqueables()
    activos_malos = activos_bloqueables()

    if activo in activos_malos:
        return None

    # =========================
    # 1. LIQUIDITY SWEEP ALCISTA MEJORADO
    # =========================
    if (
        ctx["liquidity_sweep"] == 1
        and ctx["patron"] != -1
        and 30 <= rsi <= 58
        and (
            ctx["rechazo"] == 1
            or ctx["patron"] == 1
            or ctx["cerca_soporte"]
        )
    ):
        puntaje = 18
        razones = [
            "ESTRATEGIA: liquidity sweep alcista",
            ctx["nombre_liquidity_sweep"],
            "barrida de mínimos con recuperación confirmada",
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

        if ctx["choch"] == 1:
            puntaje += 2
            razones.append(ctx["nombre_choch"])

        señales.append(
            crear_senal_profesional(activo, "call", "liquidity sweep alcista", puntaje, rsi, razones)
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
        )
    ):
        puntaje = 18
        razones = [
            "ESTRATEGIA: liquidity sweep bajista",
            ctx["nombre_liquidity_sweep"],
            "barrida de máximos con rechazo",
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

        if ctx["choch"] == -1:
            puntaje += 2
            razones.append(ctx["nombre_choch"])

        señales.append(
            crear_senal_profesional(activo, "put", "liquidity sweep bajista", puntaje, rsi, razones)
        )

    # =========================
    # 3. CHOCH ALCISTA MEJORADO
    # =========================
    if (
        ctx["choch"] == 1
        and ctx["patron"] != -1
        and ctx["ema_alcista"]
        and 38 <= rsi <= 62
        and (
            ctx["rechazo"] == 1
            or ctx["patron"] == 1
            or ctx["cerca_soporte"]
            or ctx["liquidity_sweep"] == 1
        )
    ):
        puntaje = 17
        razones = [
            "ESTRATEGIA: CHOCH alcista",
            ctx["nombre_choch"],
            "EMA favorece compra",
            "RSI: " + str(round(rsi, 2))
        ]

        if ctx["rechazo"] == 1:
            puntaje += 2
            razones.append(ctx["nombre_rechazo"])

        if ctx["patron"] == 1:
            puntaje += ctx["puntos_patron_vela"]
            razones.append(ctx["nombre_patron"])

        if ctx["cerca_soporte"]:
            puntaje += 1
            razones.append("CHOCH apoyado en soporte")

        if ctx["liquidity_sweep"] == 1:
            puntaje += 2
            razones.append("CHOCH con liquidity sweep alcista")

        señales.append(
            crear_senal_profesional(activo, "call", "CHOCH alcista", puntaje, rsi, razones)
        )

    # =========================
    # 4. CHOCH BAJISTA MEJORADO
    # =========================
    if (
        ctx["choch"] == -1
        and ctx["patron"] != 1
        and ctx["ema_bajista"]
        and 38 <= rsi <= 62
        and (
            ctx["rechazo"] == -1
            or ctx["patron"] == -1
            or ctx["cerca_resistencia"]
            or ctx["liquidity_sweep"] == -1
        )
    ):
        puntaje = 17
        razones = [
            "ESTRATEGIA: CHOCH bajista",
            ctx["nombre_choch"],
            "EMA favorece venta",
            "RSI: " + str(round(rsi, 2))
        ]

        if ctx["rechazo"] == -1:
            puntaje += 2
            razones.append(ctx["nombre_rechazo"])

        if ctx["patron"] == -1:
            puntaje += ctx["puntos_patron_vela"]
            razones.append(ctx["nombre_patron"])

        if ctx["cerca_resistencia"]:
            puntaje += 1
            razones.append("CHOCH apoyado en resistencia")

        if ctx["liquidity_sweep"] == -1:
            puntaje += 2
            razones.append("CHOCH con liquidity sweep bajista")

        señales.append(
            crear_senal_profesional(activo, "put", "CHOCH bajista", puntaje, rsi, razones)
        )

    # =========================
    # 5. FALSA RUPTURA ALCISTA
    # =========================
    if (
        ctx["falsa_call"] == 1
        and ctx["patron"] != -1
        and rsi <= 64
    ):
        puntaje = 18
        razones = [
            "ESTRATEGIA: falsa ruptura alcista",
            ctx["nombre_falsa_call"],
            "recuperación de soporte",
            "RSI: " + str(round(rsi, 2))
        ]

        if ctx["rechazo"] == 1:
            puntaje += 2
            razones.append(ctx["nombre_rechazo"])

        if ctx["call_reaccion"]:
            puntaje += 2
            razones.append(ctx["razon_call_reaccion"])

        if ctx["patron"] == 1:
            puntaje += ctx["puntos_patron_vela"]
            razones.append(ctx["nombre_patron"])

        señales.append(
            crear_senal_profesional(activo, "call", "falsa ruptura alcista", puntaje, rsi, razones)
        )

    # =========================
    # 6. FALSA RUPTURA BAJISTA
    # =========================
    if (
        ctx["falsa_put"] == -1
        and ctx["patron"] != 1
        and rsi >= 36
    ):
        puntaje = 18
        razones = [
            "ESTRATEGIA: falsa ruptura bajista",
            ctx["nombre_falsa_put"],
            "rechazo de resistencia",
            "RSI: " + str(round(rsi, 2))
        ]

        if ctx["rechazo"] == -1:
            puntaje += 2
            razones.append(ctx["nombre_rechazo"])

        if ctx["put_reaccion"]:
            puntaje += 2
            razones.append(ctx["razon_put_reaccion"])

        if ctx["patron"] == -1:
            puntaje += ctx["puntos_patron_vela"]
            razones.append(ctx["nombre_patron"])

        señales.append(
            crear_senal_profesional(activo, "put", "falsa ruptura bajista", puntaje, rsi, razones)
        )

    # =========================
    # 7. BREAKOUT RETEST ALCISTA
    # =========================
    if (
        ctx["br_call"] == 1
        and ctx["ema_alcista"]
        and ctx["tendencia"] >= 0
        and not ctx["cerca_resistencia"]
        and rsi <= 64
    ):
        puntaje = 17
        razones = [
            "ESTRATEGIA: breakout retest alcista",
            ctx["nombre_br_call"],
            "EMA favorece compra",
            "RSI: " + str(round(rsi, 2))
        ]

        if ctx["estructura"] == 1:
            puntaje += 2
            razones.append("estructura alcista")

        if ctx["patron"] == 1:
            puntaje += ctx["puntos_patron_vela"]
            razones.append(ctx["nombre_patron"])

        señales.append(
            crear_senal_profesional(activo, "call", "breakout retest alcista", puntaje, rsi, razones)
        )

    # =========================
    # 8. BREAKOUT RETEST BAJISTA
    # =========================
    if (
        ctx["br_put"] == -1
        and ctx["ema_bajista"]
        and ctx["tendencia"] <= 0
        and not ctx["cerca_soporte"]
        and rsi >= 36
    ):
        puntaje = 17
        razones = [
            "ESTRATEGIA: breakout retest bajista",
            ctx["nombre_br_put"],
            "EMA favorece venta",
            "RSI: " + str(round(rsi, 2))
        ]

        if ctx["estructura"] == -1:
            puntaje += 2
            razones.append("estructura bajista")

        if ctx["patron"] == -1:
            puntaje += ctx["puntos_patron_vela"]
            razones.append(ctx["nombre_patron"])

        señales.append(
            crear_senal_profesional(activo, "put", "breakout retest bajista", puntaje, rsi, razones)
        )

    # =========================
    # 9. PULLBACK A EMA ALCISTA
    # =========================
    if (
        ctx["entrada_pullback_call"]
        and ctx["ema_alcista"]
        and ctx["tendencia"] >= 0
        and ctx["estructura"] >= 0
        and 36 <= rsi <= 62
        and not ctx["cerca_resistencia"]
    ):
        puntaje = 14
        razones = [
            "ESTRATEGIA: pullback alcista a EMA/zona",
            "EMA favorece compra",
            "pullback válido para compra",
            "RSI: " + str(round(rsi, 2))
        ]

        if ctx["tendencia"] == 1:
            puntaje += 2
            razones.append("tendencia alcista")

        if ctx["estructura"] == 1:
            puntaje += 2
            razones.append("estructura alcista")

        if ctx["patron"] == 1:
            puntaje += ctx["puntos_patron_vela"]
            razones.append(ctx["nombre_patron"])

        if ctx["rechazo"] == 1:
            puntaje += 2
            razones.append(ctx["nombre_rechazo"])

        señales.append(
            crear_senal_profesional(activo, "call", "pullback alcista a EMA", puntaje, rsi, razones)
        )

    # =========================
    # 10. PULLBACK A EMA BAJISTA MEJORADO
    # =========================
    if (
        ctx["entrada_pullback_put"]
        and ctx["ema_bajista"]
        and ctx["tendencia"] <= 0
        and ctx["estructura"] <= 0
        and 38 <= rsi <= 64
        and not ctx["cerca_soporte"]
        and (
            (
                ctx["rechazo"] == -1
                and ctx["patron"] == -1
            )
            or (
                ctx["rechazo"] == -1
                and ctx["cerca_resistencia"]
            )
        )
    ):
        puntaje = 14
        razones = [
            "ESTRATEGIA: pullback bajista a EMA/zona",
            "EMA favorece venta",
            "pullback bajista confirmado",
            "RSI: " + str(round(rsi, 2))
        ]

        if ctx["tendencia"] == -1:
            puntaje += 2
            razones.append("tendencia bajista")

        if ctx["estructura"] == -1:
            puntaje += 2
            razones.append("estructura bajista")

        if ctx["cerca_resistencia"]:
            puntaje += 1
            razones.append("pullback cerca de resistencia")

        if ctx["patron"] == -1:
            puntaje += ctx["puntos_patron_vela"]
            razones.append(ctx["nombre_patron"])

        if ctx["rechazo"] == -1:
            puntaje += 2
            razones.append(ctx["nombre_rechazo"])

        señales.append(
            crear_senal_profesional(activo, "put", "pullback bajista a EMA", puntaje, rsi, razones)
        )

    # =========================
    # 11. RECHAZO COMPRADOR EN SOPORTE
    # =========================
    if (
        ctx["cerca_soporte"]
        and ctx["rechazo"] == 1
        and ctx["patron"] != -1
        and 30 <= rsi <= 55
    ):
        puntaje = 9
        razones = [
            "ESTRATEGIA: rechazo comprador en soporte",
            ctx["nombre_rechazo"],
            "zona soporte activa",
            "RSI válido para compra: " + str(round(rsi, 2))
        ]

        if ctx["call_reaccion"]:
            puntaje += 2
            razones.append(ctx["razon_call_reaccion"])

        if ctx["triple_soporte"]:
            puntaje += 2
            razones.append("triple rechazo en soporte")

        if ctx["patron"] == 1:
            puntaje += ctx["puntos_patron_vela"]
            razones.append(ctx["nombre_patron"])

        if ctx["ema_alcista"]:
            puntaje += 1
            razones.append("EMA favorece compra")

        señales.append(
            crear_senal_profesional(activo, "call", "rechazo comprador en soporte", puntaje, rsi, razones)
        )

    # =========================
    # 12. RECHAZO VENDEDOR EN RESISTENCIA
    # =========================
    if (
        ctx["cerca_resistencia"]
        and ctx["rechazo"] == -1
        and ctx["patron"] != 1
        and 45 <= rsi <= 70
    ):
        puntaje = 9
        razones = [
            "ESTRATEGIA: rechazo vendedor en resistencia",
            ctx["nombre_rechazo"],
            "zona resistencia activa",
            "RSI válido para venta: " + str(round(rsi, 2))
        ]

        if ctx["put_reaccion"]:
            puntaje += 2
            razones.append(ctx["razon_put_reaccion"])

        if ctx["triple_resistencia"]:
            puntaje += 2
            razones.append("triple rechazo en resistencia")

        if ctx["patron"] == -1:
            puntaje += ctx["puntos_patron_vela"]
            razones.append(ctx["nombre_patron"])

        if ctx["ema_bajista"]:
            puntaje += 1
            razones.append("EMA favorece venta")

        señales.append(
            crear_senal_profesional(activo, "put", "rechazo vendedor en resistencia", puntaje, rsi, razones)
        )

    # =========================
    # 13. CONTINUACIÓN ALCISTA
    # =========================
    if (
        ctx["tendencia"] == 1
        and ctx["estructura"] == 1
        and ctx["ema_alcista"]
        and ctx["micro"] == 1
        and not ctx["cerca_resistencia"]
        and 42 <= rsi <= 60
        and ctx["fuerza_ultima"] <= 0.70
    ):
        puntaje = 11
        razones = [
            "ESTRATEGIA: continuación alcista con tendencia",
            "tendencia alcista",
            "estructura alcista",
            "EMA favorece compra",
            "micro tendencia alcista",
            "RSI: " + str(round(rsi, 2))
        ]

        if ctx["patron"] == 1:
            puntaje += ctx["puntos_patron_vela"]
            razones.append(ctx["nombre_patron"])

        señales.append(
            crear_senal_profesional(activo, "call", "continuación alcista con tendencia", puntaje, rsi, razones)
        )

    # =========================
    # 14. CONTINUACIÓN BAJISTA
    # =========================
    if (
        ctx["tendencia"] == -1
        and ctx["estructura"] == -1
        and ctx["ema_bajista"]
        and ctx["micro"] == -1
        and not ctx["cerca_soporte"]
        and 40 <= rsi <= 58
        and ctx["fuerza_ultima"] <= 0.70
    ):
        puntaje = 11
        razones = [
            "ESTRATEGIA: continuación bajista con tendencia",
            "tendencia bajista",
            "estructura bajista",
            "EMA favorece venta",
            "micro tendencia bajista",
            "RSI: " + str(round(rsi, 2))
        ]

        if ctx["patron"] == -1:
            puntaje += ctx["puntos_patron_vela"]
            razones.append(ctx["nombre_patron"])

        señales.append(
            crear_senal_profesional(activo, "put", "continuación bajista con tendencia", puntaje, rsi, razones)
        )

    # =========================
    # FILTRO FINAL
    # =========================
    señales = [
        s for s in señales
        if s is not None and s.get("patron") not in estrategias_malas
    ]

    if not señales:
        return None

    señales = sorted(
        señales,
        key=lambda x: (
            x.get("prioridad", 0),
            x.get("puntaje", 0)
        ),
        reverse=True
    )

    mejor_senal = señales[0]

    mejor_senal["tipo_mercado"] = tipo_mercado
    mejor_senal["razon_mercado"] = razon_mercado
    # mejor_senal["razon"] = (
    #     mejor_senal["razon"]
    #     + ", MERCADO: "
    #     + tipo_mercado
    #     + " - "
    #     + razon_mercado
    # )

    return mejor_senal
def analizar_activo(activo):
    ctx = leer_contexto_grafico(activo)

    if ctx is None:
        return None

    # =========================
    # FASE 1: LECTURA DEL MERCADO
    # =========================
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

        ctx["tipo_mercado"] = tipo_mercado
        ctx["razon_mercado"] = razon_mercado
        ctx["calidad_mercado"] = diagnostico.get("calidad", "SIN_DATOS")
        ctx["score_mercado"] = diagnostico.get("score", 0)
        ctx["detalle_calidad_mercado"] = diagnostico

        ctx["estado_tendencia"] = diagnostico_tendencia.get("estado_tendencia", "INDEFINIDA")
        ctx["fuerza_tendencia"] = diagnostico_tendencia.get("fuerza_tendencia", 0)
        ctx["direccion_tendencia"] = diagnostico_tendencia.get("direccion_tendencia", "INDEFINIDA")
        ctx["razon_tendencia"] = diagnostico_tendencia.get("razon_tendencia", "")
        ctx["detalle_tendencia"] = diagnostico_tendencia

        estado.snapshot_mercados[activo] = {
            "tipo": ctx.get("tipo_mercado", "INDEFINIDO"),
            "calidad": ctx.get("calidad_mercado", "SIN_DATOS"),
            "score": ctx.get("score_mercado", 0),
            "tendencia": ctx.get("estado_tendencia", "INDEFINIDA"),
            "fuerza": ctx.get("fuerza_tendencia", 0)
        }

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

    # ====================================
    # FILTRO DE MERCADO EN TIEMPO REAL
    # Si el activo ya no está bueno,
    # sacarlo temporalmente del análisis.
    # ====================================
    calidad = ctx.get("calidad_mercado", "SIN_DATOS")
    score = ctx.get("score_mercado", 0)
    tendencia_estado = ctx.get("estado_tendencia", "INDEFINIDA")

    if calidad not in ["LIMPIO", "NORMAL"]:
        estado.cooldown_activos[activo] = time.time() + 600
        return None

    if score < 58:
        estado.cooldown_activos[activo] = time.time() + 600
        return None

    if "DEBIL" in tendencia_estado:
        estado.cooldown_activos[activo] = time.time() + 600
        return None

    if tendencia_estado == "INDEFINIDA":
        estado.cooldown_activos[activo] = time.time() + 600
        return None

    senal = motor_estrategias_profesional(ctx)

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

    ok_mercado, razon_validacion_mercado = validar_estrategia_por_mercado(
        senal,
        ctx
    )

    if not ok_mercado:
        print(
            senal["direccion"].upper(),
            "bloqueado por contexto de mercado:",
            activo,
            razon_validacion_mercado
        )
        return None

    # =========================
    # FASE 3B: RUPTURA ANTES DE SOPORTE/RESISTENCIA
    # IMPORTANTE:
    # Esto debe calcularse antes de validar zonas.
    # =========================
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
        print(
            senal["direccion"].upper(),
            "bloqueado por soporte/resistencia:",
            activo,
            razon_zona_sr
        )
        return None

    # =========================
    # FASE 3.1: DIAGNÓSTICO ACCIÓN DEL PRECIO
    # OJO: por ahora NO bloquea, solo registra.
    # =========================
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

    bloqueada_contraria, razon_contraria = vela_contraria_reciente(
        ctx,
        senal["direccion"]
    )

    if bloqueada_contraria:
        print(
            senal["direccion"].upper(),
            "bloqueado por vela contraria reciente:",
            activo,
            razon_contraria
        )
        return None

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

    if bloqueada:
        print(
            senal["direccion"].upper(),
            "bloqueado por zona operada:",
            activo,
            razon_zona
        )
        return None

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

    if not ok_ubicacion:
        print(
            senal["direccion"].upper(),
            "bloqueado por ubicación/fatiga:",
            activo,
            razon_ubicacion
        )
        return None

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

    senal["tipo_mercado"] = ctx.get("tipo_mercado", "INDEFINIDO")
    senal["razon_mercado"] = ctx.get("razon_mercado", "")
    senal["calidad_mercado"] = ctx.get("calidad_mercado", "SIN_DATOS")
    senal["score_mercado"] = ctx.get("score_mercado", 0)

    senal["estado_tendencia"] = ctx.get("estado_tendencia", "INDEFINIDA")
    senal["fuerza_tendencia"] = ctx.get("fuerza_tendencia", 0)
    senal["direccion_tendencia"] = ctx.get("direccion_tendencia", "INDEFINIDA")

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

    return senal