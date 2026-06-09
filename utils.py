import time
import estado


def segundo_actual():
    return int(time.localtime().tm_sec)


def esperar_inicio_vela():
    while True:
        s = segundo_actual()

        if 0 <= s <= 3:
            return True

        if s > 56:
            time.sleep(0.10)
            continue

        return False


def activo_en_cooldown(activo):
    if activo not in estado.cooldown_activos:
        return False

    if time.time() >= estado.cooldown_activos[activo]:
        del estado.cooldown_activos[activo]
        return False

    return True


def estrategia_en_cooldown(patron):
    if not hasattr(estado, "cooldown_estrategias"):
        estado.cooldown_estrategias = {}

    if patron not in estado.cooldown_estrategias:
        return False

    if time.time() >= estado.cooldown_estrategias[patron]:
        del estado.cooldown_estrategias[patron]
        return False

    return True