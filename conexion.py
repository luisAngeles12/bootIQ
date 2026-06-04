import time
import sys
from iqoptionapi.stable_api import IQ_Option
import estado
from config import EMAIL, PASSWORD, MODO_CUENTA

def conectar():

    print("Conectando a IQ Option...")

    estado.Iq = IQ_Option(EMAIL, PASSWORD)

    check, reason = estado.Iq.connect()

    if not check:
        print("Error conectando:", reason)
        sys.exit()

    print("Conectado correctamente")

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
        return True

    except Exception as e:
        print("No se pudo reconectar:", e)
        return False
