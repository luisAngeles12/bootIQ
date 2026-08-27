import time
import sys
import threading
from iqoptionapi.stable_api import IQ_Option

import estado
from config import EMAIL, PASSWORD, MODO_CUENTA
_lock_reconexion = threading.Lock()

def actualizar_activos_opcode():
    try:
        print("Actualizando OPCODE ligero binary/turbo...", flush=True)

        # Esta parte actualiza los códigos de binary y turbo
        # sin llamar forex/crypto/cfd.
        estado.Iq.get_ALL_Binary_ACTIVES_OPCODE()

        try:
            activos_opcode = estado.Iq.get_all_ACTIVES_OPCODE()
            print("Total de activos en OPCODE:", len(activos_opcode), flush=True)
        except Exception:
            pass

        print("OPCODE ligero actualizado correctamente", flush=True)
        return True

    except Exception as e:
        print("No se pudo actualizar OPCODE ligero:", e, flush=True)
        return False
def conectar():
    print("Conectando a IQ Option...", flush=True)

    estado.Iq = IQ_Option(EMAIL, PASSWORD)
    check, reason = estado.Iq.connect()

    if not check:
        print("Error conectando:", reason, flush=True)
        sys.exit()

    print("Conectado correctamente", flush=True)

    try:
        estado.Iq.change_balance(MODO_CUENTA)
        print("Cuenta seleccionada:", MODO_CUENTA, flush=True)
    except Exception as e:
        print("No se pudo cambiar el balance:", e, flush=True)

    # IMPORTANTE:
    # No actualizar OPCODE aquí porque puede congelar la conexión.
    actualizar_activos_opcode()

    # IMPORTANTE:
    # No usamos get_profile_ansyc porque también puede quedarse colgado.
    # Mejor usamos get_balance(), que ya estás usando en bot.py.
    try:
        print("Obteniendo balance inicial...", flush=True)
        estado.balance_inicial = float(estado.Iq.get_balance())
    except Exception as e:
        print("No se pudo obtener balance inicial:", e, flush=True)
        estado.balance_inicial = 0

    print("Balance inicial:", estado.balance_inicial, flush=True)
    return True


def reconectar_iq(intentos=3):
    """
    Punto único de reconexión controlada de BootIQ.

    Solo devuelve True cuando la conexión quedó
    realmente restablecida.
    """

    with _lock_reconexion:

        # Tal vez otra parte ya reconectó mientras
        # esperábamos el lock.
        try:
            if (
                estado.Iq is not None
                and estado.Iq.check_connect()
            ):
                return True
        except Exception:
            pass

        if estado.Iq is None:
            print(
                "No existe instancia IQ para reconectar.",
                flush=True
            )
            return False

        print(
            "Conexión IQ perdida. "
            "Iniciando reconexión controlada...",
            flush=True
        )

        for intento in range(1, intentos + 1):

            try:
                print(
                    f"Reconexión IQ {intento}/{intentos}...",
                    flush=True
                )

                check, reason = estado.Iq.connect()

                try:
                    conectado = (
                        bool(check)
                        and estado.Iq.check_connect()
                    )
                except Exception:
                    conectado = False

                if conectado:

                    try:
                        estado.Iq.change_balance(
                            MODO_CUENTA
                        )
                
                    except Exception as e:
                        print(
                            "Reconexión incompleta: "
                            "no se pudo restaurar la cuenta "
                            f"{MODO_CUENTA}:",
                            e,
                            flush=True
                        )
                
                        time.sleep(2)
                        continue
                
                    print(
                        "IQ Option reconectado correctamente.",
                        "| cuenta:",
                        MODO_CUENTA,
                        flush=True
                    )
                
                    # NO actualizar OPCODE aquí.
                    # Ya tenemos los códigos cargados.
                    return True

                print(
                    "Reconexión no confirmada:",
                    reason,
                    flush=True
                )

            except Exception as e:
                print(
                    "Error durante reconexión IQ:",
                    e,
                    flush=True
                )

            time.sleep(2)

        print(
            "IQ Option continúa desconectado.",
            flush=True
        )

        return False