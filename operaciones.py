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
    actualizar_historial_cierre,
    perdidas_consecutivas_activo,
    perdidas_consecutivas_patron
)
from validaciones_estrategia import registrar_zona_operada


def normalizar_resultado(resultado):
    try:
        resultado = round(float(resultado), 2)
        print(
            "RESULTADO BRUTO IQ:",
            resultado
        )
        if resultado > MONTO_BASE * 1.2:
            return round(MONTO_BASE * 0.87, 2)

        if resultado < -MONTO_BASE:
            return -MONTO_BASE

        return resultado

    except Exception:
        return None


def abrir_operacion(senal):
    # ==========================================
    # AUTORIZACIÓN FINAL DEL CEREBRO ÚNICO
    # ==========================================
    decision_cerebro = str(
        senal.get("cerebro_unico_decision", "")
    ).upper().strip()

    protocolo_confirmado = bool(
        senal.get("protocolo_confirmado", False)
    )

    if decision_cerebro == "NO_OPERAR":
        print(
            "OPERACIÓN BLOQUEADA POR CEREBRO ÚNICO:",
            senal.get("activo", ""),
            "| decisión: NO_OPERAR"
        )
        return False

    if decision_cerebro not in [
        "OPERAR",
        "OPERAR_CON_PROTOCOLO"
    ]:
        print(
            "OPERACIÓN BLOQUEADA: DECISIÓN INVÁLIDA O VACÍA:",
            senal.get("activo", ""),
            "| decisión:",
            decision_cerebro or "VACÍA"
        )
        return False

    if (
        decision_cerebro == "OPERAR_CON_PROTOCOLO"
        and not protocolo_confirmado
    ):
        print(
            "OPERACIÓN BLOQUEADA: PROTOCOLO NO CONFIRMADO:",
            senal.get("activo", "")
        )
        return False

    activo = str(
        senal.get("activo", "")
    ).strip()
    
    direccion = str(
        senal.get("direccion", "")
    ).lower().strip()
    
    tipo = str(
        senal.get("tipo", "turbo")
    ).lower().strip()
    
    puntaje = senal.get("puntaje", 0)
    patron = senal.get("patron", "")
    rsi = senal.get("rsi", "")
    razon = senal.get("razon", "")
    if not activo:
        print("OPERACIÓN NO ENVIADA: ACTIVO VACÍO")
        return False
    
    if direccion not in ["call", "put"]:
        print(
            "OPERACIÓN NO ENVIADA: DIRECCIÓN INVÁLIDA:",
            direccion or "VACÍA"
        )
        return False
    
    if tipo not in ["turbo", "binary", "digital"]:
        print(
            "OPERACIÓN NO ENVIADA: TIPO NO SOPORTADO:",
            tipo or "VACÍO"
        )
        return False
    from utils import segundo_actual
    segundo_antes = segundo_actual()
    tiempo_antes = time.time()
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
        segundo_despues = segundo_actual()
        demora_envio = round(time.time() - tiempo_antes, 3)
        
        if segundo_despues > 38:
            print(
                "ADVERTENCIA: operación enviada tarde:",
                activo,
                "| segundo antes:",
                segundo_antes,
                "| segundo después:",
                segundo_despues,
                "| demora:",
                demora_envio
            )
        
        op = {
            "order_id": order_id,
            "activo": activo,
            "tipo": tipo,
            "direccion": direccion,
            "puntaje": puntaje,
            "patron": patron,
            "rsi": rsi,
            "razon": razon,
            "hora_apertura": time.time(),
            "balance_antes": balance_antes,
            "segundo_entrada": segundo_despues,
            "demora_envio": demora_envio,
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

            "puntaje": puntaje,
            "patron": patron,
            "rsi": rsi,
            "razon": razon,

            "resultado": "",
            "segundo_entrada": segundo_despues,
            "demora_envio": demora_envio,
        })

        print("OPERACIÓN ABIERTA:", activo, tipo, direccion)
        print("ID:", order_id)
        print("Operaciones abiertas:", len(estado.operaciones_abiertas))

        print("Puntaje:", puntaje)
        print("Patrón:", patron)
        print("Segundo entrada:", segundo_despues, "| demora envío:", demora_envio)

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
            bloqueo_activo_aplicado = False

            if resultado < 0:
            
                if perdidas_consecutivas_activo(op["activo"], 3):
            
                    estado.cooldown_activos[op["activo"]] = (
                        time.time() + 1800
                    )
            
                    bloqueo_activo_aplicado = True
            
                    print(
                        "ACTIVO BLOQUEADO 30 MIN POR 3 PÉRDIDAS:",
                        op["activo"]
                    )
            
                if not hasattr(estado, "cooldown_estrategias"):
                    estado.cooldown_estrategias = {}
            
                if perdidas_consecutivas_patron(op["patron"], 3):
            
                    estado.cooldown_estrategias[op["patron"]] = (
                        time.time() + 1800
                    )
            
                    print(
                        "ESTRATEGIA BLOQUEADA 30 MIN POR 3 PÉRDIDAS:",
                        op["patron"]
                    )
            
            print(
                "OPERACIÓN CERRADA:",
                op["activo"],
                op["tipo"],
                op["direccion"]
            )
            
            print("Resultado real por order_id:", resultado)
            
            if not bloqueo_activo_aplicado:
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