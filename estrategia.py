from config import PUNTAJE_MINIMO
from estadisticas import estrategias_bloqueables, activos_bloqueables
from historial import cargar_historial
from indicadores import *
from price_action import *
from zonas import *
from mercado import obtener_velas
from motor_setup import enriquecer_senal_con_setup
import time
import estado
from motor_adaptativo import ajustar_fortalezas_riesgos_por_aprendizaje
from contexto_mercado import (
    detectar_tipo_mercado,
    diagnostico_maestro_mercado,
    validar_estrategia_por_mercado,
    clasificar_setup_estrategico,
    diagnostico_calidad_mercado,
    diagnostico_tendencia_avanzada,
    construir_evidencias_mercado
)
from utils import estrategia_en_cooldown,registrar_bloqueo
from price_action_profesional import contexto_price_action_profesional,rechazo_historico_inteligente
from motor_consenso import aplicar_consenso_senal
from motor_candidatos import crear_candidato, candidato_a_senal
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
        precio = closes[-1]

        if vol <= 0:
            vol = abs(precio) * 0.0001

        ultimas = 8

        opens_r = opens[-ultimas:]
        closes_r = closes[-ultimas:]
        highs_r = highs[-ultimas:]
        lows_r = lows[-ultimas:]

        distancia_soporte = abs(precio - soporte)
        distancia_resistencia = abs(resistencia - precio)

        cerca_soporte = distancia_soporte <= vol * 1.20
        cerca_resistencia = distancia_resistencia <= vol * 1.20

        zona_total = abs(resistencia - soporte)

        if zona_total <= 0:
            zona_total = vol * 2

        posicion_rango = distancia_soporte / zona_total

        # 0.00 = pegado al soporte
        # 1.00 = pegado a resistencia

        mechas_superiores = 0
        mechas_inferiores = 0
        velas_rojas = 0
        velas_verdes = 0
        cuerpos_fuertes_rojos = 0
        cuerpos_fuertes_verdes = 0

        for o, c, h, l in zip(opens_r, closes_r, highs_r, lows_r):
            rango = h - l

            if rango <= 0:
                continue

            cuerpo = abs(c - o)
            fuerza = cuerpo / rango

            mecha_sup = h - max(o, c)
            mecha_inf = min(o, c) - l

            if mecha_sup >= rango * 0.35:
                mechas_superiores += 1

            if mecha_inf >= rango * 0.35:
                mechas_inferiores += 1

            if c < o:
                velas_rojas += 1
                if fuerza >= 0.45:
                    cuerpos_fuertes_rojos += 1

            if c > o:
                velas_verdes += 1
                if fuerza >= 0.45:
                    cuerpos_fuertes_verdes += 1

        o1 = opens[-1]
        c1 = closes[-1]
        h1 = highs[-1]
        l1 = lows[-1]

        rango1 = h1 - l1

        if rango1 <= 0:
            return False, "rango inválido en zona"

        cuerpo1 = abs(c1 - o1)
        fuerza1 = cuerpo1 / rango1

        mecha_sup_1 = h1 - max(o1, c1)
        mecha_inf_1 = min(o1, c1) - l1

        vela_roja = c1 < o1
        vela_verde = c1 > o1

        rechazo_vendedor_fuerte = (
            cerca_resistencia
            and vela_roja
            and mecha_sup_1 >= rango1 * 0.32
            and fuerza1 >= 0.18
        )

        rechazo_comprador_fuerte = (
            cerca_soporte
            and vela_verde
            and mecha_inf_1 >= rango1 * 0.32
            and fuerza1 >= 0.18
        )

        presion_vendedora_en_resistencia = (
            cerca_resistencia
            and mechas_superiores >= 3
            and velas_rojas >= 3
            and cuerpos_fuertes_rojos >= 1
        )

        presion_compradora_en_soporte = (
            cerca_soporte
            and mechas_inferiores >= 3
            and velas_verdes >= 3
            and cuerpos_fuertes_verdes >= 1
        )

        agotamiento_alcista = (
            cerca_resistencia
            and velas_verdes >= 4
            and mechas_superiores >= 2
            and fuerza1 < 0.55
        )

        agotamiento_bajista = (
            cerca_soporte
            and velas_rojas >= 4
            and mechas_inferiores >= 2
            and fuerza1 < 0.55
        )
        pa_profesional = contexto_price_action_profesional(
            opens,
            closes,
            highs,
            lows,
            soporte,
            resistencia,
            vol
        )
       
        # =========================
        # PUT EN RESISTENCIA
        # =========================
        if direccion == "put":
            if not cerca_resistencia:
                return False, "PUT sin cercanía real a resistencia"
            if (
                pa_profesional.get("direccion") == "PUT"
                and pa_profesional.get("tipo") in [
                    "RECHAZO_VENDEDOR_CONFIRMADO",
                    "AGOTAMIENTO_ALCISTA_CONFIRMADO"
                ]
            ):
                return True, "PUT válido por price action profesional: " + pa_profesional.get("razon", "")
            if cerca_soporte or posicion_rango <= 0.25:
                return False, "PUT rechazado: soporte demasiado cerca"

            if rechazo_vendedor_fuerte:
                return True, "PUT válido: rechazo vendedor fuerte en resistencia"

            if presion_vendedora_en_resistencia:
                return True, "PUT válido: presión vendedora en resistencia"

            if agotamiento_alcista:
                return True, "PUT válido: agotamiento alcista en resistencia"

            return False, "PUT sin reacción suficiente en resistencia"

        # =========================
        # CALL EN SOPORTE
        # =========================
        if direccion == "call":
            if not cerca_soporte:
                return False, "CALL sin cercanía real a soporte"
            if (
                pa_profesional.get("direccion") == "CALL"
                and pa_profesional.get("tipo") in [
                    "RECHAZO_COMPRADOR_CONFIRMADO",
                    "AGOTAMIENTO_BAJISTA_CONFIRMADO"
                ]
            ):
                return True, "CALL válido por price action profesional: " + pa_profesional.get("razon", "")
            if cerca_resistencia or posicion_rango >= 0.75:
                return False, "CALL rechazado: resistencia demasiado cerca"

            if rechazo_comprador_fuerte:
                return True, "CALL válido: rechazo comprador fuerte en soporte"

            if presion_compradora_en_soporte:
                return True, "CALL válido: presión compradora en soporte"

            if agotamiento_bajista:
                return True, "CALL válido: agotamiento bajista en soporte"

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
def leer_micro_contexto_profesional(ctx):
    try:
        opens = ctx["opens"]
        closes = ctx["closes"]
        highs = ctx["highs"]
        lows = ctx["lows"]

        if len(closes) < 20:
            return {}

        o = opens[-1]
        c = closes[-1]
        h = highs[-1]
        l = lows[-1]

        rango = h - l
        cuerpo = abs(c - o)

        if rango <= 0:
            rango = 0.0000001

        fuerza_cuerpo = cuerpo / rango
        mecha_sup = h - max(o, c)
        mecha_inf = min(o, c) - l

        vela_verde = c > o
        vela_roja = c < o

        cierres_5 = closes[-5:]
        subidas = sum(1 for i in range(1, len(cierres_5)) if cierres_5[i] > cierres_5[i - 1])
        bajadas = sum(1 for i in range(1, len(cierres_5)) if cierres_5[i] < cierres_5[i - 1])

        impulso_alcista = subidas >= 3 and vela_verde and fuerza_cuerpo >= 0.45
        impulso_bajista = bajadas >= 3 and vela_roja and fuerza_cuerpo >= 0.45

        rechazo_alcista_real = (
            vela_verde
            and mecha_inf >= rango * 0.35
            and fuerza_cuerpo >= 0.25
        )

        rechazo_bajista_real = (
            vela_roja
            and mecha_sup >= rango * 0.35
            and fuerza_cuerpo >= 0.25
        )

        vela_climax_alcista = (
            vela_verde
            and fuerza_cuerpo >= 0.75
            and ctx.get("posicion_rango", 0.5) >= 0.70
        )

        vela_climax_bajista = (
            vela_roja
            and fuerza_cuerpo >= 0.75
            and ctx.get("posicion_rango", 0.5) <= 0.30
        )

        presion_corta = "NEUTRA"

        if subidas >= 3:
            presion_corta = "ALCISTA"
        elif bajadas >= 3:
            presion_corta = "BAJISTA"

        return {
            "fuerza_cuerpo": round(fuerza_cuerpo, 4),
            "mecha_sup_ratio": round(mecha_sup / rango, 4),
            "mecha_inf_ratio": round(mecha_inf / rango, 4),
            "vela_verde": vela_verde,
            "vela_roja": vela_roja,
            "impulso_alcista": impulso_alcista,
            "impulso_bajista": impulso_bajista,
            "rechazo_alcista_real": rechazo_alcista_real,
            "rechazo_bajista_real": rechazo_bajista_real,
            "vela_climax_alcista": vela_climax_alcista,
            "vela_climax_bajista": vela_climax_bajista,
            "presion_corta": presion_corta,
            "subidas_5": subidas,
            "bajadas_5": bajadas,
        }

    except Exception as e:
        print("Error leyendo micro contexto:", e)
        return {}
def clasificar_senal_profesional(puntaje, razones, estrategia, rsi):
    texto = " | ".join(razones).lower()
    estrategia = estrategia.lower()

    es_reaccion = "reacción" in estrategia or "reaccion" in estrategia

    tiene_confirmacion_fuerte = (
        "rechazo comprador fuerte" in texto
        or "rechazo vendedor fuerte" in texto
        or "pin bar" in texto
        or "martillo" in texto
        or "shooting star" in texto
        or "envolvente" in texto
        or "liquidity sweep" in texto
        or "presión compradora" in texto
        or "presion compradora" in texto
        or "presión vendedora" in texto
        or "presion vendedora" in texto
    )

    if es_reaccion and not tiene_confirmacion_fuerte:
        return "C", 0

    calidad = "C"
    prioridad = 0

    if puntaje >= 18:
        calidad = "A+"
        prioridad = 4

        if "choch" in estrategia and puntaje < 21:
            calidad = "A"
            prioridad = 3

    elif puntaje >= 14:
        calidad = "A"
        prioridad = 3

    elif puntaje >= 8:
        calidad = "B"
        prioridad = 2

    else:
        calidad = "C"
        prioridad = 0

    if calidad == "C":
        return "C", 0

    if rsi > 68 and "reversa" not in estrategia and "rechazo vendedor" not in texto:
        prioridad -= 1

    if rsi < 32 and "reversa" not in estrategia and "rechazo comprador" not in texto:
        prioridad -= 1

    if prioridad <= 0:
        return "C", 0
    return calidad, prioridad
def detectar_cambio_estructura_choch(highs, lows, closes, opens=None, lookback=10):
    try:
        if len(closes) < lookback + 4:
            return 0, "sin datos suficientes para CHOCH"

        highs_previos = highs[-lookback-2:-2]
        lows_previos = lows[-lookback-2:-2]

        ultimo_open = opens[-1] if opens else closes[-2]
        ultimo_close = closes[-1]
        ultimo_high = highs[-1]
        ultimo_low = lows[-1]

        max_prev = max(highs_previos)
        min_prev = min(lows_previos)

        rango = ultimo_high - ultimo_low
        cuerpo = abs(ultimo_close - ultimo_open)

        if rango <= 0:
            return 0, "rango inválido para CHOCH"

        fuerza_cuerpo = cuerpo / rango

        if fuerza_cuerpo < 0.45:
            return 0, "CHOCH débil: cuerpo insuficiente"

        if ultimo_close > max_prev:
            fuerza_ruptura = (ultimo_close - max_prev) / rango

            if fuerza_ruptura < 0.15:
                return 0, "CHOCH alcista débil: ruptura pequeña"

            if ultimo_close <= ultimo_open:
                return 0, "CHOCH alcista inválido: vela no alcista"

            return 1, "CHOCH alcista confirmado: ruptura con cuerpo"

        if ultimo_close < min_prev:
            fuerza_ruptura = (min_prev - ultimo_close) / rango

            if fuerza_ruptura < 0.15:
                return 0, "CHOCH bajista débil: ruptura pequeña"

            if ultimo_close >= ultimo_open:
                return 0, "CHOCH bajista inválido: vela no bajista"

            return -1, "CHOCH bajista confirmado: ruptura con cuerpo"

        return 0, "sin cambio de estructura"

    except Exception as e:
        print("Error detectando CHOCH:", e)
        return 0, "error CHOCH"
def detectar_liquidity_sweep(opens, closes, highs, lows, lookback=12):
    """
    Detecta barridas de liquidez con validación profesional.

    Retorna:
        -1 = sweep bajista / posible PUT
         1 = sweep alcista / posible CALL
         0 = sin sweep válido

    Mantiene compatibilidad con el flujo actual:
        return direccion, razon
    """

    try:
        if len(closes) < lookback + 5:
            return 0, "sin barrida de liquidez: velas insuficientes"

        high_actual = highs[-1]
        low_actual = lows[-1]
        close_actual = closes[-1]
        open_actual = opens[-1]

        high_prev = highs[-2]
        low_prev = lows[-2]
        close_prev = closes[-2]
        open_prev = opens[-2]

        rango_actual = max(high_actual - low_actual, 0.0000001)
        cuerpo_actual = abs(close_actual - open_actual)

        mecha_superior = high_actual - max(open_actual, close_actual)
        mecha_inferior = min(open_actual, close_actual) - low_actual

        cuerpo_pct = cuerpo_actual / rango_actual
        mecha_sup_pct = mecha_superior / rango_actual
        mecha_inf_pct = mecha_inferior / rango_actual

        highs_previos = highs[-lookback-1:-1]
        lows_previos = lows[-lookback-1:-1]
        closes_previos = closes[-lookback-1:-1]

        max_prev = max(highs_previos)
        min_prev = min(lows_previos)

        rango_promedio = sum(
            max(highs[i] - lows[i], 0.0000001)
            for i in range(len(highs) - lookback - 1, len(highs) - 1)
        ) / lookback

        vela_roja = close_actual < open_actual
        vela_verde = close_actual > open_actual

        cierre_en_parte_baja = close_actual <= low_actual + (rango_actual * 0.45)
        cierre_en_parte_alta = close_actual >= high_actual - (rango_actual * 0.45)

        # Ruptura real sobre zonas previas
        barrio_maximo = high_actual > max_prev
        barrio_minimo = low_actual < min_prev

        # Evita barridas microscópicas
        exceso_maximo = high_actual - max_prev
        exceso_minimo = min_prev - low_actual

        exceso_max_pct = exceso_maximo / rango_promedio if rango_promedio else 0
        exceso_min_pct = exceso_minimo / rango_promedio if rango_promedio else 0

        # Confirmación de retorno dentro de la zona
        recupero_debajo_max = close_actual < max_prev
        recupero_arriba_min = close_actual > min_prev

        # Filtro de vela demasiado débil
        vela_con_rango_valido = rango_actual >= rango_promedio * 0.65
        vela_no_doji = cuerpo_pct >= 0.18

        # =========================
        # SWEEP BAJISTA / PUT
        # =========================
        if barrio_maximo and recupero_debajo_max:
            score = 0
            razones = ["liquidity sweep bajista: barrida de máximos"]

            if vela_roja:
                score += 20
                razones.append("vela roja confirma rechazo")

            if mecha_sup_pct >= 0.35:
                score += 20
                razones.append("mecha superior dominante")

            if cierre_en_parte_baja:
                score += 15
                razones.append("cierre en zona baja de la vela")

            if exceso_max_pct >= 0.10:
                score += 10
                razones.append("barrida con exceso suficiente")

            if vela_con_rango_valido:
                score += 10
                razones.append("rango de vela válido")

            if vela_no_doji:
                score += 10
                razones.append("cuerpo de vela suficiente")

            if close_actual < close_prev:
                score += 10
                razones.append("cierre actual confirma presión bajista")

            if high_actual > high_prev and close_actual < close_prev:
                score += 5
                razones.append("estructura inmediata rechaza máximos")

            if score >= 55:
                razones.append(f"score_sweep={score}")
                return -1, " | ".join(razones)

            return 0, "sweep bajista débil: " + " | ".join(razones) + f" | score_sweep={score}"

        # =========================
        # SWEEP ALCISTA / CALL
        # =========================
        if barrio_minimo and recupero_arriba_min:
            score = 0
            razones = ["liquidity sweep alcista: barrida de mínimos"]

            if vela_verde:
                score += 20
                razones.append("vela verde confirma rechazo")

            if mecha_inf_pct >= 0.35:
                score += 20
                razones.append("mecha inferior dominante")

            if cierre_en_parte_alta:
                score += 15
                razones.append("cierre en zona alta de la vela")

            if exceso_min_pct >= 0.10:
                score += 10
                razones.append("barrida con exceso suficiente")

            if vela_con_rango_valido:
                score += 10
                razones.append("rango de vela válido")

            if vela_no_doji:
                score += 10
                razones.append("cuerpo de vela suficiente")

            if close_actual > close_prev:
                score += 10
                razones.append("cierre actual confirma presión alcista")

            if low_actual < low_prev and close_actual > close_prev:
                score += 5
                razones.append("estructura inmediata rechaza mínimos")

            # Sweep alcista venía débil en el aprendizaje.
            # Por eso exige un poco más de calidad que el bajista.
            if score >= 65:
                razones.append(f"score_sweep={score}")
                return 1, " | ".join(razones)

            return 0, "sweep alcista débil: " + " | ".join(razones) + f" | score_sweep={score}"

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
def peso_estrategia_profesional(patron):
    patron = str(patron).lower()

    if "liquidity sweep" in patron:
        return 110

    if "choch" in patron:
        return 88

    if "breakout" in patron or "retest" in patron:
        return 95

    if "pullback alcista" in patron and "ema" in patron:
        return 82

    if "pullback bajista" in patron and "ema" in patron:
        return 72

    if "continuación" in patron or "continuacion" in patron:
        return 65

    if "reacción" in patron or "reaccion" in patron:
        return 80

    return 50
def score_final_senal_profesional(senal):
    patron = str(senal.get("patron", "")).lower()
    accion = str(senal.get("accion_precio", "")).upper()
    direccion = str(senal.get("direccion", "")).lower()
    pa_tipo = str(senal.get("pa_tipo", "")).upper()
    pa_direccion = str(senal.get("pa_direccion", "")).upper()

    peso = peso_estrategia_profesional(patron)
    puntaje = senal.get("puntaje", 0)
    prioridad = senal.get("prioridad", 0)

    score = peso + (puntaje * 2) + (prioridad * 5)

    if direccion == "call" and accion == "RECHAZO_COMPRADOR_SOPORTE":
        score += 12

    if direccion == "put" and accion == "RECHAZO_VENDEDOR_RESISTENCIA":
        score += 12

    if "liquidity sweep" in patron:
        score += 18

    if "pullback bajista" in patron:
        score -= 12

    if "pullback alcista" in patron:
        score -= 14

    if "continuación" in patron or "continuacion" in patron:
        if puntaje < 16:
            score -= 35
        else:
            score -= 20

    if puntaje >= 23:
        score += 10

    if senal.get("calidad") == "A+":
        score += 8

    ctx_pa = {
        "pa_direccion": pa_direccion,
        "pa_tipo": pa_tipo,
        "pa_fuerza": senal.get("pa_fuerza", 0),
        "accion_precio": senal.get("accion_precio", "SIN_DATOS"),
        "direccion_tendencia": senal.get("direccion_tendencia", "NEUTRA"),
        "fuerza_tendencia": senal.get("fuerza_tendencia", 0),
        "posicion_rango": senal.get("posicion_rango", 0.5),
        "rechazo_hist_direccion": senal.get("rechazo_hist_direccion", "NEUTRA"),
        "impulso_alcista": senal.get("impulso_alcista", False),
        "impulso_bajista": senal.get("impulso_bajista", False),
        "rechazo_alcista_real": senal.get("rechazo_alcista_real", False),
        "rechazo_bajista_real": senal.get("rechazo_bajista_real", False),
    }

    confianza_pa = evaluar_confianza_price_action(ctx_pa, direccion)

    if confianza_pa.get("nivel") == "ALTA":
        score += 18
    elif confianza_pa.get("nivel") == "MEDIA":
        score += 9
    elif confianza_pa.get("nivel") == "BAJA":
        score += 2
    elif confianza_pa.get("nivel") == "DEBIL":
        score -= 10

    return score
def pa_profesional_apoya(ctx, direccion, minimo_fuerza=0.35, aceptar_neutro=False):
    direccion = str(direccion).upper()

    pa_direccion = str(ctx.get("pa_direccion", "NEUTRA")).upper()
    pa_tipo = str(ctx.get("pa_tipo", "SIN_CONTEXTO_CLARO")).upper()
    pa_fuerza = float(ctx.get("pa_fuerza", 0) or 0)

    if pa_tipo == "SIN_CONTEXTO_CLARO":
        return False

    if pa_direccion == direccion and pa_fuerza >= minimo_fuerza:
        return True

    if aceptar_neutro and pa_direccion == "NEUTRA" and pa_fuerza >= minimo_fuerza:
        return True

    return False
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

    senal["tipo_setup"] = setup.get("tipo_setup", "INDEFINIDO")
    senal["calidad_setup"] = setup.get("calidad_setup", "MEDIA")
    senal["modo_entrada_setup"] = setup.get("modo_entrada", "DIRECTA")
    senal["puntaje_extra_setup"] = setup.get("puntaje_extra_setup", 0)
    senal["riesgo_extra_setup"] = setup.get("riesgo_extra_setup", 0)
    senal["balance_setup"] = setup.get("balance_setup", 0)
    senal["a_favor_tendencia"] = setup.get("a_favor_tendencia", False)
    senal["razones_setup"] = " | ".join(setup.get("razones_setup", []))

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
    senal = enriquecer_senal_con_setup(senal)

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
    from decision_bootiq import aplicar_decision_unificada_a_senal

    resultado_bootiq = aplicar_decision_unificada_a_senal(
        senal,
        ctx
    )

    senal = resultado_bootiq["senal"]
    if senal.get("decision_unificada_accion") == "NO_OPERAR":
      return None
    return senal
def analizar_activo(activo):
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