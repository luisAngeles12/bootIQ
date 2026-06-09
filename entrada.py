import time
import estado
from config import CANDLE_TIME
from utils import segundo_actual
from mercado import obtener_velas

def detectar_intencion_en_entrada(activo, direccion_original):
    try:
        candles = estado.Iq.get_candles(activo, CANDLE_TIME, 5, time.time())

        if not candles or len(candles) < 4:
            return direccion_original, "sin cambio"

        candles = sorted(candles, key=lambda x: x["from"])

        v = candles[-1]
        a = candles[-2]

        o = float(v["open"])
        c = float(v["close"])
        h = float(v["max"])
        l = float(v["min"])

        ao = float(a["open"])
        ac = float(a["close"])
        ah = float(a["max"])
        al = float(a["min"])

        rango = h - l
        cuerpo = abs(c - o)

        if rango <= 0:
            return direccion_original, "sin cambio"

        fuerza = cuerpo / rango
        mecha_sup = h - max(o, c)
        mecha_inf = min(o, c) - l

        vela_roja = c < o
        vela_verde = c > o

        rechazo_vendedor = (
            mecha_sup >= cuerpo * 1.8
            and vela_roja
            and fuerza >= 0.22
        )

        rechazo_comprador = (
            mecha_inf >= cuerpo * 1.8
            and vela_verde
            and fuerza >= 0.22
        )

        pierde_minimo_anterior = c < al and vela_roja and fuerza >= 0.30
        rompe_maximo_anterior = c > ah and vela_verde and fuerza >= 0.30

        # Si esperaba CALL, pero aparece rechazo vendedor fuerte, cambia a PUT.
        if direccion_original == "call":
            if rechazo_vendedor or pierde_minimo_anterior:
                return "put", "cambio a PUT por intención bajista"

        # Si esperaba PUT, pero aparece rechazo comprador fuerte, cambia a CALL.
        if direccion_original == "put":
            if rechazo_comprador or rompe_maximo_anterior:
                return "call", "cambio a CALL por intención alcista"

        return direccion_original, "sin cambio"

    except Exception as e:
        print("Error detectando intención:", activo, e)
        return direccion_original, "sin cambio"


def validar_vela_exacta_entrada(activo, direccion):
    try:
        candles = estado.Iq.get_candles(activo, CANDLE_TIME, 5, time.time())

        if not candles or len(candles) < 4:
            return False, "velas insuficientes"

        candles = sorted(candles, key=lambda x: x["from"])

        actual = candles[-1]
        anterior = candles[-2]

        o = float(actual["open"])
        c = float(actual["close"])
        h = float(actual["max"])
        l = float(actual["min"])
        ac = float(anterior["close"])

        rango = h - l
        cuerpo = abs(c - o)

        if rango <= 0:
            return False, "rango inválido"

        fuerza = cuerpo / rango
        posicion = (c - l) / rango

        mecha_sup = h - max(o, c)
        mecha_inf = min(o, c) - l

        vela_verde = c > o
        vela_roja = c < o

        if fuerza < 0.06:
            return False, "vela débil o indecisa"

        if direccion == "call":
            if vela_roja and not (mecha_inf >= cuerpo * 1.2 and posicion >= 0.35):
                return False, "CALL sin recuperación compradora"

            if posicion >= 0.96 and fuerza >= 0.58:
                return False, "CALL tarde cerca del máximo"

            if mecha_sup >= cuerpo * 3.0 and fuerza < 0.32:
                return False, "absorción vendedora fuerte"

            return True, "vela exacta CALL válida"

        if direccion == "put":
            if vela_verde and not (mecha_sup >= cuerpo * 1.2 and posicion <= 0.65):
                return False, "PUT sin rechazo vendedor"

            if posicion <= 0.04 and fuerza >= 0.58:
                return False, "PUT tarde cerca del mínimo"

            if mecha_inf >= cuerpo * 3.0 and fuerza < 0.32:
                return False, "absorción compradora fuerte"

            return True, "vela exacta PUT válida"

        return False, "dirección inválida"

    except Exception as e:
        print("Error validando vela exacta:", activo, e)
        return False, "error validando vela"
def validar_microestructura_entrada(
    direccion,
    opens,
    closes,
    highs,
    lows
):
    try:
        ultimas = 4

        velas = []

        for i in range(-ultimas, 0):
            o = opens[i]
            c = closes[i]
            h = highs[i]
            l = lows[i]

            rango = h - l

            if rango <= 0:
                continue

            cuerpo = abs(c - o)

            fuerza = cuerpo / rango

            velas.append({
                "alcista": c > o,
                "bajista": c < o,
                "fuerza": fuerza,
                "mecha_sup": h - max(o, c),
                "mecha_inf": min(o, c) - l,
                "cuerpo": cuerpo
            })

        if len(velas) < 3:
            return False, "microestructura insuficiente"

        alcistas = sum(1 for v in velas if v["alcista"])
        bajistas = sum(1 for v in velas if v["bajista"])

        fuerza_promedio = sum(v["fuerza"] for v in velas) / len(velas)

        ultima = velas[-1]

        # =========================
        # CALL
        # =========================
        if direccion == "call":

            # Ya no exigir perfección.
            if alcistas >= 2 and fuerza_promedio >= 0.22:

                # Bloquea solo absorción MUY fuerte.
                if (
                    ultima["mecha_sup"] >= ultima["cuerpo"] * 2.8
                    and ultima["fuerza"] < 0.28
                ):
                    return False, "absorción vendedora fuerte"

                return True, "microestructura alcista válida"

        # =========================
        # PUT
        # =========================
        if direccion == "put":

            if bajistas >= 2 and fuerza_promedio >= 0.28:

                if (
                    ultima["mecha_inf"] >= ultima["cuerpo"] * 2.8
                    and ultima["fuerza"] < 0.28
                ):
                    return False, "absorción compradora fuerte"

                return True, "microestructura bajista válida"

        return False, "microestructura débil"

    except Exception as e:
        print("Error validando microestructura:", e)
        return False, "error microestructura"


def decidir_entrada(activo, direccion, candles, precio_referencia):
    try:
        candles = sorted(candles, key=lambda x: x["from"])

        if len(candles) < 4:
            return "esperar", "velas insuficientes"

        vela_actual = candles[-1]
        vela_anterior = candles[-2]

        o = float(vela_actual["open"])
        c = float(vela_actual["close"])
        h = float(vela_actual["max"])
        l = float(vela_actual["min"])

        ao = float(vela_anterior["open"])
        ac = float(vela_anterior["close"])
        ah = float(vela_anterior["max"])
        al = float(vela_anterior["min"])

        rango = h - l
        cuerpo = abs(c - o)

        if rango <= 0:
            return "esperar", "rango inválido"

        fuerza = cuerpo / rango

        mecha_superior = h - max(o, c)
        mecha_inferior = min(o, c) - l

        posicion = (c - l) / rango
        cerca_high = posicion >= 0.88
        cerca_low = posicion <= 0.12

        vela_verde = c > o
        vela_roja = c < o

        segundo = segundo_actual()

        if precio_referencia is not None:
            movimiento = abs(c - precio_referencia)

            if movimiento > rango * 1.20:
                return "cancelar", "precio se alejó demasiado"

        if segundo > 36:
            return "cancelar", "se pasó la ventana segura"

        # Evitar entrar en vela ya explotada.
        if fuerza > 0.82 and segundo > 14:
            return "cancelar", "vela demasiado corrida"

        # =========================
        # CALL
        # =========================
        if direccion == "call":
            rechazo_comprador = (
                mecha_inferior >= cuerpo * 1.2
                and posicion >= 0.42
                and fuerza >= 0.14
            )

            recuperacion = (
                c > ac
                and posicion >= 0.40
                and fuerza >= 0.14
                and not cerca_high
            )

            ruptura_controlada = (
                c > ah
                and fuerza <= 0.72
                and segundo <= 28
                and not cerca_high
            )

            continuacion_sana = (
                vela_verde
                and c > ac
                and 0.16 <= fuerza <= 0.72
                and posicion < 0.84
            )

            if cerca_high and fuerza >= 0.55:
                return "esperar", "CALL alto en vela, esperar retroceso"

            if rechazo_comprador:
                return "entrar", "CALL por rechazo comprador confirmado"

            if ruptura_controlada:
                return "entrar", "CALL por ruptura controlada"

            if continuacion_sana:
                return "entrar", "CALL por continuación sana"

            if recuperacion:
                return "entrar", "CALL por recuperación"

            return "esperar", "CALL sin confirmación suficiente"

        # =========================
        # PUT
        # =========================
        if direccion == "put":
            rechazo_vendedor = (
                mecha_superior >= cuerpo * 1.2
                and posicion <= 0.58
                and fuerza >= 0.14
            )

            recuperacion_bajista = (
                c < ac
                and posicion <= 0.60
                and fuerza >= 0.14
                and not cerca_low
            )

            ruptura_controlada = (
                c < al
                and fuerza <= 0.72
                and segundo <= 28
                and not cerca_low
            )

            continuacion_sana = (
                vela_roja
                and c < ac
                and 0.16 <= fuerza <= 0.72
                and posicion > 0.16
            )

            if cerca_low and fuerza >= 0.55:
                return "esperar", "PUT bajo en vela, esperar retroceso"

            if rechazo_vendedor:
                return "entrar", "PUT por rechazo vendedor confirmado"

            if ruptura_controlada:
                return "entrar", "PUT por ruptura controlada"

            if continuacion_sana:
                return "entrar", "PUT por continuación sana"

            if recuperacion_bajista:
                return "entrar", "PUT por recuperación bajista"

            return "esperar", "PUT sin confirmación suficiente"

        return "cancelar", "dirección inválida"

    except Exception as e:
        print("Error decidiendo entrada:", activo, e)
        return "cancelar", "error decidiendo entrada"
def esperar_mejor_entrada(senal):
    activo = senal["activo"]
    direccion = senal["direccion"]

    print("Buscando mejor punto de entrada:", activo, direccion)

    tiempo_inicio = time.time()
    precio_referencia = None
    TIEMPO_MAXIMO_ESPERA = 6

    while True:
        segundo = segundo_actual()

        if segundo < 4:
            time.sleep(0.07)
            continue

        if segundo > 38:
            print("Entrada cancelada:", activo, "se pasó la ventana segura")
            return False

        if time.time() - tiempo_inicio > TIEMPO_MAXIMO_ESPERA:
            print("Entrada cancelada:", activo, "no confirmó rápido")
            return False

        try:
            candles = estado.Iq.get_candles(
                activo,
                CANDLE_TIME,
                5,
                time.time()
            )

            if not candles or len(candles) < 4:
                time.sleep(0.07)
                continue

            candles = sorted(candles, key=lambda x: x["from"])
            precio_actual = float(candles[-1]["close"])

            if precio_referencia is None:
                precio_referencia = precio_actual

            decision, razon_decision = decidir_entrada(
                activo,
                direccion,
                candles,
                precio_referencia
            )

            if decision == "cancelar":
                print("Entrada cancelada:", activo, razon_decision)
                return False

            if decision == "esperar":
                time.sleep(0.07)
                continue

            if decision == "entrar":
                ok_vela, razon_vela = validar_vela_exacta_entrada(
                    activo,
                    direccion
                )

                if not ok_vela:
                    print("Entrada bloqueada:", activo, razon_vela)
                    return False

                ok_micro, razon_micro = validar_microestructura_entrada(
                    direccion,
                    [x["open"] for x in candles],
                    [x["close"] for x in candles],
                    [x["max"] for x in candles],
                    [x["min"] for x in candles]
                )

                if not ok_micro:
                    print("Microestructura bloqueada:", activo, razon_micro)
                    return False

                print(
                    "Entrada",
                    direccion.upper(),
                    "confirmada:",
                    activo,
                    "| segundo:", segundo,
                    "| decisión:", razon_decision,
                    "| vela:", razon_vela,
                    "| micro:", razon_micro
                )

                return True

        except Exception as e:
            print("Error buscando mejor entrada:", activo, e)
            return False

        time.sleep(0.07)

def guardar_senal_pendiente(senal):
    import time
    import estado
    from config import CANDLE_TIME

    activo = senal["activo"]

    for s in estado.senales_pendientes:
        if s["activo"] == activo:
            return False

    senal_pendiente = senal.copy()
    senal_pendiente["hora_detectada"] = time.time()
    senal_pendiente["vela_detectada"] = int(time.time() // CANDLE_TIME)

    estado.senales_pendientes.append(senal_pendiente)

    print(
        "SEÑAL PENDIENTE GUARDADA:",
        activo,
        senal["direccion"],
        senal["patron"]
    )

    return True

def procesar_senales_pendientes(abrir_operacion):
    import time
    import estado
    from config import CANDLE_TIME, MAX_OPERACIONES_ABIERTAS
    from utils import segundo_actual
    from entrada import (
        decidir_entrada,
        validar_vela_exacta_entrada,
        validar_microestructura_entrada,
        validar_punto_entrada_en_vela
    )

    if not estado.senales_pendientes:
        return 0

    abiertas = 0
    restantes = []
    vela_actual = int(time.time() // CANDLE_TIME)
    segundo = segundo_actual()

    for senal in estado.senales_pendientes:
        try:
            activo = senal["activo"]
            direccion = senal["direccion"]

            if len(estado.operaciones_abiertas) >= MAX_OPERACIONES_ABIERTAS:
                restantes.append(senal)
                continue

            if any(op["activo"] == activo for op in estado.operaciones_abiertas):
                continue

            if vela_actual <= senal["vela_detectada"]:
                restantes.append(senal)
                continue

            if vela_actual - senal["vela_detectada"] > 6:
                print("SEÑAL PENDIENTE EXPIRADA:", activo)
                continue

            if segundo < 2:
                restantes.append(senal)
                continue

            if segundo > 30:
                print("SEÑAL PENDIENTE CANCELADA POR TIEMPO:", activo)
                continue

            candles = estado.Iq.get_candles(
                activo,
                CANDLE_TIME,
                5,
                time.time()
            )

            if not candles or len(candles) < 4:
                restantes.append(senal)
                continue

            candles = sorted(candles, key=lambda x: x["from"])

            ok_punto, razon_punto = validar_punto_entrada_en_vela(
                direccion,
                candles
            )

            if not ok_punto:
                print("SEÑAL PENDIENTE BLOQUEADA:", activo, razon_punto)
                continue

            decision, razon = decidir_entrada(
                activo,
                direccion,
                candles,
                None
            )

            if decision != "entrar":
                restantes.append(senal)
                continue

            ok_vela, razon_vela = validar_vela_exacta_entrada(
                activo,
                direccion
            )

            if not ok_vela:
                print("SEÑAL PENDIENTE BLOQUEADA:", activo, razon_vela)
                continue

            ok_micro, razon_micro = validar_microestructura_entrada(
                direccion,
                [x["open"] for x in candles],
                [x["close"] for x in candles],
                [x["max"] for x in candles],
                [x["min"] for x in candles]
            )

            if not ok_micro:
                print("SEÑAL PENDIENTE BLOQUEADA:", activo, razon_micro)
                continue

            print(
                "SEÑAL PENDIENTE CONFIRMADA:",
                activo,
                direccion,
                "|",
                razon
            )

            if abrir_operacion(senal):
                abiertas += 1

        except Exception as e:
            print("Error procesando señal pendiente:", e)

    estado.senales_pendientes = restantes

    return abiertas
def validar_punto_entrada_en_vela(direccion, candles):
    try:
        candles = sorted(candles, key=lambda x: x["from"])

        if len(candles) < 4:
            return False, "velas insuficientes"

        actual = candles[-1]

        o = float(actual["open"])
        c = float(actual["close"])
        h = float(actual["max"])
        l = float(actual["min"])

        rango = h - l
        if rango <= 0:
            return False, "rango inválido"

        cuerpo = abs(c - o)
        fuerza = cuerpo / rango
        posicion = (c - l) / rango

        mecha_sup = h - max(o, c)
        mecha_inf = min(o, c) - l

        vela_verde = c > o
        vela_roja = c < o

        if fuerza < 0.06:
            return False, "vela sin cuerpo suficiente"

        if direccion == "call":
            if posicion >= 0.96 and fuerza >= 0.58:
                return False, "CALL bloqueado: precio demasiado arriba"

            if vela_roja:
                if not (mecha_inf >= cuerpo * 1.15 and posicion >= 0.34):
                    return False, "CALL bloqueado: vela roja sin recuperación real"

            if mecha_sup >= cuerpo * 3.0 and fuerza < 0.32:
                return False, "CALL bloqueado: absorción vendedora"

            return True, "punto CALL válido"

        if direccion == "put":
            if posicion <= 0.04 and fuerza >= 0.58:
                return False, "PUT bloqueado: precio demasiado abajo"

            if vela_verde:
                if not (mecha_sup >= cuerpo * 1.15 and posicion <= 0.66):
                    return False, "PUT bloqueado: vela verde sin rechazo real"

            if mecha_inf >= cuerpo * 3.0 and fuerza < 0.32:
                return False, "PUT bloqueado: absorción compradora"

            return True, "punto PUT válido"

        return False, "dirección inválida"

    except Exception as e:
        print("Error validando punto de entrada:", e)
        return False, "error punto entrada"
def entrada_rapida_disponible(senal):
    activo = senal["activo"]
    direccion = senal["direccion"]

    try:
        segundo = segundo_actual()

        if segundo < 2 or segundo > 45:
            print("Entrada rápida cancelada:", activo, "fuera de ventana segura:", segundo)
            return False

        candles = estado.Iq.get_candles(
            activo,
            CANDLE_TIME,
            5,
            time.time()
        )

        if not candles or len(candles) < 4:
            return False

        candles = sorted(candles, key=lambda x: x["from"])

        ok_punto, razon_punto = validar_punto_entrada_en_vela(
            direccion,
            candles
        )

        if not ok_punto:
            print("Entrada rápida bloqueada:", activo, razon_punto)
            return False

        actual = candles[-1]

        o = float(actual["open"])
        c = float(actual["close"])
        h = float(actual["max"])
        l = float(actual["min"])

        rango = h - l
        cuerpo = abs(c - o)

        if rango <= 0:
            return False

        fuerza = cuerpo / rango

        cerca_high = (h - c) <= rango * 0.08
        cerca_low = (c - l) <= rango * 0.08

        senal_premium = (
             senal.get("puntaje", 0) >= 21
             and senal.get("calidad") == "A+"
             and senal.get("calidad_mercado") in ["LIMPIO", "NORMAL"]
        )
        
        if fuerza >= 0.78 and segundo > 18 and not senal_premium:
            print("Entrada rápida cancelada:", activo, "vela corrida | fuerza:", round(fuerza, 2))
            return False

        if direccion == "call" and cerca_high and fuerza >= 0.68 and not senal_premium:
            print("Entrada rápida cancelada:", activo, "CALL cerca del máximo")
            return False

        if direccion == "put" and cerca_low and fuerza >= 0.68 and not senal_premium:
            print("Entrada rápida cancelada:", activo, "PUT cerca del mínimo")
            return False

        decision, razon = decidir_entrada(
            activo,
            direccion,
            candles,
            None
        )

        if decision != "entrar":
            return False

        ok_vela, razon_vela = validar_vela_exacta_entrada(
            activo,
            direccion
        )

        if not ok_vela:
            print("Entrada rápida bloqueada:", activo, razon_vela)
            return False

        ok_micro, razon_micro = validar_microestructura_entrada(
            direccion,
            [x["open"] for x in candles],
            [x["close"] for x in candles],
            [x["max"] for x in candles],
            [x["min"] for x in candles]
        )

        if not ok_micro:
            print("Entrada rápida bloqueada:", activo, razon_micro)
            return False

        print(
            "Entrada rápida aprobada:",
            activo,
            direccion,
            "| segundo:",
            segundo,
            "| fuerza:",
            round(fuerza, 2),
            "|",
            razon
        )

        return True

    except Exception as e:
        print("Error en entrada rápida:", activo, e)
        return False