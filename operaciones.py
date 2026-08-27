import time
import queue
import threading
import json
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
# ============================================================
# PASO 5.5C — AUDITORÍA DE LA ORDEN REAL DEVUELTA POR IQ
# ============================================================

def obtener_auditoria_orden_async(
    order_id,
    timeout=1.2,
):
    inicio = time.time()

    while time.time() - inicio < timeout:
        try:
            datos = estado.Iq.get_async_order(
                int(order_id)
            )

            if datos is not None:
                return datos

        except Exception:
            pass

        time.sleep(0.05)

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
            print(
                "Operación rechazada:",
                activo,
                tipo
            )
            estado.cooldown_activos[
                activo
            ] = time.time()
            return False
        
        
        # ============================================================
        # PASO 5.5C — INSTANTE REAL DE RESPUESTA DE IQ
        # ============================================================
        
        segundo_despues = segundo_actual()
        tiempo_despues = time.time()
        
        demora_envio = round(
            tiempo_despues - tiempo_antes,
            3
        )
        
        order_id_original = order_id
        
        # Consultar los datos que IQ asocia realmente
        # a esta operación. Solo diagnóstico.
        orden_async_5_5c = None
        
        if tipo in ["turbo", "binary"]:
            orden_async_5_5c = (
                obtener_auditoria_orden_async(
                    order_id_original,
                    timeout=1.2,
                )
            )
        
        order_id = str(order_id_original)
        # ============================================================
        # PASO 5.5C — PERSISTIR RESPUESTA REAL DE IQ
        # ============================================================
        
        if orden_async_5_5c is None:
            auditoria_orden_iq_json = ""
        else:
            try:
                auditoria_orden_iq_json = json.dumps(
                    orden_async_5_5c,
                    ensure_ascii=False,
                    default=str,
                )
            except Exception:
                auditoria_orden_iq_json = str(
                    orden_async_5_5c
                )
        # ============================================================
        # PASO 5.5C — MOSTRAR ESTRUCTURA REAL DE LA ORDEN
        # ============================================================
        
        if orden_async_5_5c is None:
            print(
                "AUDITORIA 5.5C ORDEN IQ:",
                activo,
                "| order_id:",
                order_id,
                "| datos: NO_DISPONIBLES",
            )
        
        else:
            print(
                "AUDITORIA 5.5C ORDEN IQ:",
                activo,
                "| order_id:",
                order_id,
                "| tipo dato:",
                type(
                    orden_async_5_5c
                ).__name__,
            )
        
            if isinstance(
                orden_async_5_5c,
                dict,
            ):
                print(
                    "AUDITORIA 5.5C CLAVES IQ:",
                    activo,
                    "|",
                    list(
                        orden_async_5_5c.keys()
                    ),
                )
        
            print(
                "AUDITORIA 5.5C DATOS IQ:",
                activo,
                "|",
                orden_async_5_5c,
            )
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
            # ==========================================
            # PASO 5.5C — PARIDAD DE EJECUCIÓN
            # ==========================================
            
            "tiempo_envio_inicio": tiempo_antes,
            "tiempo_respuesta_iq": tiempo_despues,
            
            "segundo_antes": segundo_antes,
            "segundo_entrada": segundo_despues,
            
            "vela_confirmacion_from": senal.get(
                "protocolo_live_vela_entrada_from"
            ),
            
            "precio_confirmacion_close": senal.get(
                "protocolo_live_vela_entrada_close"
            ),
            
            "precio_confirmacion_open": senal.get(
                "protocolo_live_vela_entrada_open"
            ),
            
            "precio_confirmacion_high": senal.get(
                "protocolo_live_vela_entrada_high"
            ),
            
            "precio_confirmacion_low": senal.get(
                "protocolo_live_vela_entrada_low"
            ),
            "tiempo_expiracion": TIEMPO_EXPIRACION,

            "auditoria_orden_iq_json": (
                auditoria_orden_iq_json
            ),
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
            "fecha": datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
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
        
            # ==========================================
            # PASO 5.5C — PARIDAD DE EJECUCIÓN
            # ==========================================
        
            "segundo_antes": segundo_antes,
            "segundo_entrada": segundo_despues,
            "demora_envio": demora_envio,
        
            "tiempo_envio_inicio": tiempo_antes,
            "tiempo_respuesta_iq": tiempo_despues,
            "tiempo_expiracion": TIEMPO_EXPIRACION,
        
            "vela_confirmacion_from": senal.get(
                "protocolo_live_vela_entrada_from"
            ),
        
            "precio_confirmacion_open": senal.get(
                "protocolo_live_vela_entrada_open"
            ),
        
            "precio_confirmacion_close": senal.get(
                "protocolo_live_vela_entrada_close"
            ),
        
            "precio_confirmacion_high": senal.get(
                "protocolo_live_vela_entrada_high"
            ),
        
            "precio_confirmacion_low": senal.get(
                "protocolo_live_vela_entrada_low"
            ),
        
            "auditoria_orden_iq_json": (
                auditoria_orden_iq_json
            ),
        })
        print(
            "AUDITORIA EJECUCION 5.5C:",
            activo,
            "| vela confirmacion:",
            senal.get(
                "protocolo_live_vela_entrada_from"
            ),
            "| close confirmacion:",
            senal.get(
                "protocolo_live_vela_entrada_close"
            ),
            "| segundo antes:",
            segundo_antes,
            "| segundo despues:",
            segundo_despues,
            "| demora:",
            demora_envio,
        )
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