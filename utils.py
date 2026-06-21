import time
import estado


def segundo_actual():
    return int(time.time() % 60)


def esperar_inicio_vela():
    while True:
        s = segundo_actual()

        if 0 <= s <= 3:
            return True

        if s > 56:
            time.sleep(0.05)
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

def registrar_bloqueo(motivo):
    import estado

    if not hasattr(estado, "metricas_ronda"):
        estado.metricas_ronda = {
            "mercados_analizados": 0,
            "senales_detectadas": 0,
            "senales_aprobadas": 0,
            "entradas_abiertas": 0,
            "bloqueos": {}
        }

    if motivo not in estado.metricas_ronda["bloqueos"]:
        estado.metricas_ronda["bloqueos"][motivo] = 0

    estado.metricas_ronda["bloqueos"][motivo] += 1


def imprimir_resumen_ronda():
    import estado

    print("\n===== RESUMEN DE RONDA =====")
    print("Mercados analizados:", estado.metricas_ronda.get("mercados_analizados", 0))
    print("Señales detectadas:", estado.metricas_ronda.get("senales_detectadas", 0))
    print("Señales aprobadas:", estado.metricas_ronda.get("senales_aprobadas", 0))
    print("Entradas abiertas:", estado.metricas_ronda.get("entradas_abiertas", 0))

    bloqueos = estado.metricas_ronda.get("bloqueos", {})

    if bloqueos:
        print("Bloqueos principales:")
        for motivo, total in sorted(bloqueos.items(), key=lambda x: x[1], reverse=True):
            print("-", motivo + ":", total)

    print("============================\n")


def reiniciar_metricas_ronda():
    import estado

    estado.metricas_ronda = {
        "mercados_analizados": 0,
        "senales_detectadas": 0,
        "senales_aprobadas": 0,
        "entradas_abiertas": 0,
        "bloqueos": {}
    }