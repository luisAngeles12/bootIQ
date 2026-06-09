import time
import sys
from iqoptionapi.stable_api import IQ_Option

import estado
from config import EMAIL, PASSWORD, MODO_CUENTA


def actualizar_activos_opcode():
    try:
        estado.Iq.update_ACTIVES_OPCODE()
        print("Activos/OPCODE actualizados correctamente")

        try:
            activos_opcode = estado.Iq.get_all_ACTIVES_OPCODE()
            print("Total de activos en OPCODE:", len(activos_opcode))
        except Exception:
            pass

        return True

    except Exception as e:
        print("No se pudieron actualizar los activos/OPCODE:", e)
        return False


def conectar():
    print("Conectando a IQ Option...")

    estado.Iq = IQ_Option(EMAIL, PASSWORD)
    check, reason = estado.Iq.connect()

    if not check:
        print("Error conectando:", reason)
        sys.exit()

    print("Conectado correctamente")

    try:
        estado.Iq.change_balance(MODO_CUENTA)
        print("Cuenta seleccionada:", MODO_CUENTA)
    except Exception as e:
        print("No se pudo cambiar el balance:", e)

    # IMPORTANTE:
    # Esto actualiza los códigos internos de activos de la librería.
    # Debe ejecutarse después de conectar.
    actualizar_activos_opcode()

    try:
        perfil = estado.Iq.get_profile_ansyc()

        if perfil and "balance" in perfil:
            estado.balance_inicial = float(perfil["balance"])
        else:
            estado.balance_inicial = 0

    except Exception:
        estado.balance_inicial = 0

    print("Balance inicial:", estado.balance_inicial)


def reconectar_iq():
    try:
        print("Reconectando IQ Option...")

        estado.Iq.connect()
        time.sleep(2)

        try:
            estado.Iq.change_balance(MODO_CUENTA)
        except Exception:
            pass

        actualizar_activos_opcode()

        return True

    except Exception as e:
        print("No se pudo reconectar:", e)
        return False