import time
import sys
from iqoptionapi.stable_api import IQ_Option

import estado
from config import EMAIL, PASSWORD, MODO_CUENTA


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


def reconectar_iq():
    try:
        print("Reconectando IQ Option...", flush=True)

        try:
            estado.Iq.connect()
        except Exception:
            pass

        time.sleep(2)

        try:
            estado.Iq.change_balance(MODO_CUENTA)
        except Exception:
            pass

        # No actualizar OPCODE en reconexión.
        actualizar_activos_opcode()

        return True

    except Exception as e:
        print("No se pudo reconectar:", e, flush=True)
        return False