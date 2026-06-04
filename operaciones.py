import time
import queue
import threading
from datetime import datetime

import estado
from config import MONTO_BASE, TIEMPO_EXPIRACION
from historial import (
    guardar_operaciones_pendientes,
    asegurar_historial_csv,
    guardar_historial,
    actualizar_historial_cierre
)
from estrategia import registrar_zona_operada


def normalizar_resultado(resultado):
    try:
        resultado = round(float(resultado), 2)

        if resultado > MONTO_BASE * 1.2:
            return round(MONTO_BASE * 0.87, 2)

        if resultado < -MONTO_BASE:
            return -MONTO_BASE

        return resultado

    except Exception:
        return None


def abrir_operacion(senal):
    activo = senal["activo"]
    direccion = senal["direccion"]
    tipo = senal.get("tipo", "turbo")

    try:
        balance_antes = estado.Iq.get_balance()

        if tipo in ["turbo", "binary"]:
            check, order_id = estado.Iq.buy(
                MONTO_BASE,
                activo,
                direccion,
                TIEMPO_EXPIRACION
            )

        elif tipo == "digital":
            check, order_id = estado.Iq.buy_digital_spot_v2(
                activo,
                MONTO_BASE,
                direccion,
                TIEMPO_EXPIRACION
            )

        else:
            print("Tipo no soportado:", tipo)
            return False

        if not check:
            print("Operación rechazada:", activo, tipo)
            estado.cooldown_activos[activo] = time.time()
            return False

        order_id = str(order_id)

        op = {
            "order_id": order_id,
            "activo": activo,
            "tipo": tipo,
            "direccion": direccion,
            "puntaje": senal["puntaje"],
            "patron": senal["patron"],
            "rsi": senal["rsi"],
            "razon": senal["razon"],
            "hora_apertura": time.time(),
            "balance_antes": balance_antes
        }

        estado.operaciones_abiertas.append(op)
        guardar_operaciones_pendientes()

        try:
            if "precio_zona" in senal and "vol" in senal:
                registrar_zona_operada(
                    activo,
                    direccion,
                    senal["precio_zona"],
                    senal["vol"]
                )
        except Exception:
            pass

        asegurar_historial_csv()

        guardar_historial({
            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "estado": "ABIERTA",
            "order_id": order_id,
            "activo": activo,
            "tipo": tipo,
            "direccion": direccion,
            "puntaje": senal["puntaje"],
            "patron": senal["patron"],
            "rsi": senal["rsi"],
            "resultado": "",
            "razon": senal["razon"]
        })

        print("OPERACIÓN ABIERTA:", activo, tipo, direccion)
        print("ID:", order_id)
        print("Operaciones abiertas:", len(estado.operaciones_abiertas))
        print("Puntaje:", senal["puntaje"])
        print("Patrón:", senal["patron"])

        estado.cooldown_activos[activo] = time.time()
        return True

    except Exception as e:
        print("Error abriendo operación:", activo, tipo, e)
        estado.cooldown_activos[activo] = time.time()
        return False


def check_win_v3_con_timeout(order_id, timeout=35):
    q = queue.Queue()

    def worker():
        try:
            resultado = estado.Iq.check_win_v3(int(order_id), timeout=30)
            q.put(resultado)
        except Exception as e:
            print("check_win_v3 falló:", order_id, e)
            q.put(None)

    hilo = threading.Thread(target=worker)
    hilo.daemon = True
    hilo.start()

    try:
        return q.get(timeout=timeout)
    except queue.Empty:
        print("check_win_v3 timeout final:", order_id)
        return None
def obtener_resultado_operacion(op):
    try:
        order_id = op["order_id"]
        tipo = op["tipo"]

        tiempo_abierta = time.time() - float(op["hora_apertura"])
        tiempo_minimo = (TIEMPO_EXPIRACION * 60) + 15

        if tiempo_abierta < tiempo_minimo:
            return None

        if tipo in ["turbo", "binary"]:
            resultado = check_win_v3_con_timeout(order_id, timeout=35)

            if resultado is None:
                return None

            # Si check_win_v3 devuelve tupla: ("win", 17.4)
            if isinstance(resultado, tuple):
                if len(resultado) >= 2:
                    return normalizar_resultado(resultado[1])

            # Si devuelve directo: 17.4
            return normalizar_resultado(resultado)

        if tipo == "digital":
            for intento in range(1, 11):
                check, win = estado.Iq.check_win_digital_v2(order_id)

                if check:
                    return normalizar_resultado(win)

                time.sleep(0.5)

            return None

    except Exception as e:
        print("Error obteniendo resultado:", op["activo"], op["tipo"], e)

    return None
def revisar_operaciones_abiertas():

    if not estado.operaciones_abiertas:
        return

    pendientes = []

    for op in estado.operaciones_abiertas:

        tiempo_abierta = time.time() - float(op["hora_apertura"])
        tiempo_cierre = (TIEMPO_EXPIRACION * 60) + 10

        if tiempo_abierta < tiempo_cierre:
            pendientes.append(op)
            continue

        resultado = obtener_resultado_operacion(op)

        if resultado is not None:
            actualizar_historial_cierre(
                op["order_id"],
                resultado
            )

            print(
                "OPERACIÓN CERRADA:",
                op["activo"],
                op["tipo"],
                op["direccion"]
            )
            print("Resultado real por order_id:", resultado)

            estado.cooldown_activos[op["activo"]] = time.time()
            continue

        # No cerrar por balance.
        # Si IQ no devuelve el resultado por order_id, queda pendiente.
        print(
            "Resultado real aún no disponible por order_id:",
            op["activo"],
            op["order_id"]
        )

        pendientes.append(op)

    estado.operaciones_abiertas = pendientes
    guardar_operaciones_pendientes()