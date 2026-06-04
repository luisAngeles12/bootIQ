import unittest
import time
from iqoptionapi.stable_api import IQ_Option

# 🔥 pon tus datos directo para probar (IMPORTANTE para debug)
email = "luisangelestejada@gmail.com"
password = "R@putim120799"

class TestLogin(unittest.TestCase):

    def test_login(self):
        print("🔌 Iniciando conexión a IQ Option...")

        I_want_money = IQ_Option(email, password)

        I_want_money.connect()

        # ⏳ esperar conexión real
        time.sleep(5)

        connected = I_want_money.check_connect()

        print("📡 Estado conexión:", connected)

        if not connected:
            print("❌ No se pudo conectar")
            self.fail("Login fallido en IQ Option")

        print("✅ Conectado correctamente")

        I_want_money.change_balance("PRACTICE")
        print("💰 Cambiado a cuenta DEMO")

        I_want_money.reset_practice_balance()
        print("🔄 Balance reseteado")

        print("🎯 LOGIN OK - TODO FUNCIONA")