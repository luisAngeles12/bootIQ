"""Sondeo de velas de 1 s; SOLO PRACTICE, sin órdenes ni archivos."""

import argparse
import ast
from pathlib import Path
import time
import threading


def exigir_config_practice(ruta):
    """Validar literalmente el modo ANTES de importar módulos del bróker."""
    arbol = ast.parse(Path(ruta).read_text(encoding="utf-8"))
    modos = [
        nodo.value.value
        for nodo in arbol.body
        if isinstance(nodo, (ast.Assign, ast.AnnAssign))
        for destino in (nodo.targets if isinstance(nodo, ast.Assign) else [nodo.target])
        if isinstance(destino, ast.Name)
        and destino.id == "MODO_CUENTA"
        and isinstance(nodo.value, ast.Constant)
    ]
    if modos != ["PRACTICE"]:
        raise RuntimeError("BLOQUEADO: MODO_CUENTA no es literalmente PRACTICE")


def observar_instantanea(instantanea, ahora, desde, vistos):
    """Cuenta solamente velas cerradas, nuevas y recibidas desde el inicio."""
    if not isinstance(instantanea, dict):
        return 0
    nuevas = 0
    for clave, vela in sorted(instantanea.items(), key=lambda par: int(par[0])):
        try:
            inicio = int(vela["from"])
            if inicio != int(clave) or inicio < desde or inicio + 1 > ahora:
                continue
            apertura = float(vela["open"])
            cierre = float(vela["close"])
            minimo = float(vela["min"])
            maximo = float(vela["max"])
            if not (minimo <= apertura <= maximo and minimo <= cierre <= maximo):
                continue
        except (KeyError, ValueError, TypeError, OverflowError):
            continue
        if inicio not in vistos:
            vistos[inicio] = dict(vela)
            nuevas += 1
    return nuevas


def resumir(velas, inicio, fin):
    marcas = sorted(velas)
    saltos = [(a, b) for a, b in zip(marcas, marcas[1:]) if b - a != 1]
    ultima = marcas[-1] if marcas else None
    return {
        "segundos_observacion": fin - inicio,
        "velas_1s_nuevas": len(marcas),
        "huecos_entre_velas": len(saltos),
        "ultima_vela": ultima,
        "retraso_ultima_segundos": fin - ultima - 1 if ultima is not None else None,
        "muestra_continua": bool(marcas) and not saltos,
        "advertencia": "DIAGNOSTICO_SIN_OPERACIONES_NO_ESTIMA_WINRATE",
    }


def conectar_sondeo_practice(iq_factory, email, password, estado):
    """Arranque de solo lectura: no solicita initialization-data ni OPCODE."""
    iq = iq_factory(email, password)
    estado.Iq = iq
    conectado, motivo = iq.connect()
    if not conectado or not iq.check_connect():
        raise RuntimeError("SONDEO_CANCELADO: conexion fallida: " + str(motivo))
    iq.change_balance("PRACTICE")
    if iq.get_balance_mode() != "PRACTICE":
        raise RuntimeError("BLOQUEADO: cuenta no confirmada PRACTICE")
    time.sleep(2)
    estado.balance_inicial = float(iq.get_balance())
    print("SONDEO | conexion y balance PRACTICE confirmados", flush=True)
    return iq


def iniciar_stream_sin_precarga(iq, activo, opcodes):
    """Suscripción en memoria para un código estático conocido; sin historial."""
    codigo = opcodes.get(activo)
    if not isinstance(codigo, int) or codigo <= 0:
        raise RuntimeError(
            "SONDEO_CANCELADO: activo sin ID local verificable; "
            "se requiere OPCODE pero el broker no lo entrega"
        )
    iq.api.real_time_candles_maxdict_table[activo][1] = 60
    if iq.start_candles_one_stream(activo, 1) is not True:
        raise RuntimeError("SONDEO_CANCELADO: suscripcion 1s no confirmada")



def sondear(activo, segundos):
    exigir_config_practice(Path(__file__).with_name("config.py"))
    # Importaciones del bróker únicamente después del bloqueo anterior.
    import estado
    from config import EMAIL, PASSWORD
    from iqoptionapi.stable_api import IQ_Option
    from iqoptionapi.constants import ACTIVES

    # Nunca inferir IDs para activos recientes: el mapa local debe conocerlo.
    if activo not in ACTIVES:
        raise RuntimeError(
            "SONDEO_CANCELADO: activo no incluido en IDs locales; "
            "elige uno conocido (ejemplo USDINR-OTC)"
        )
    iq = conectar_sondeo_practice(IQ_Option, EMAIL, PASSWORD, estado)
    if not iq.check_connect() or iq.get_balance_mode() != "PRACTICE":
        raise RuntimeError("BLOQUEADO: sesion PRACTICE no confirmada")
    inicio = int(iq.get_server_timestamp())
    if inicio <= 0:
        raise RuntimeError("BLOQUEADO: reloj IQ no disponible")
    vistos = {}
    print("SONDEO SOLO LECTURA | PRACTICE | activo:", activo,
          "| segundos:", segundos, flush=True)
    try:
        iniciar_stream_sin_precarga(iq, activo, ACTIVES)
        limite = time.monotonic() + segundos
        while time.monotonic() < limite:
            if not iq.check_connect() or iq.get_balance_mode() != "PRACTICE":
                raise RuntimeError("BLOQUEADO: sesion o modo PRACTICE perdido")
            ahora = int(iq.get_server_timestamp())
            if ahora <= 0:
                raise RuntimeError("BLOQUEADO: reloj IQ no disponible")
            observar_instantanea(iq.get_realtime_candles(activo, 1),
                                 ahora, inicio, vistos)
            time.sleep(0.2)
        # Medir ANTES del cierre; desuscribir puede esperar 5 segundos.
        fin = int(iq.get_server_timestamp())
        print("RESULTADO:", resumir(vistos, inicio, fin), flush=True)
    finally:
        # stop_candles_one_stream duerme 5 s antes de comprobar el cierre.
        limpieza = threading.Thread(
            target=iq.stop_candles_stream, args=(activo, 1), daemon=True
        )
        limpieza.start()
        limpieza.join(timeout=8)
        if limpieza.is_alive():
            print("AVISO: desuscripcion excedio 8 s", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--activo", required=True,
                        help="Nombre de activo abierto en IQ Option")
    parser.add_argument("--segundos", type=int, default=30)
    args = parser.parse_args()
    if not 10 <= args.segundos <= 60:
        parser.error("--segundos debe estar entre 10 y 60")
    sondear(args.activo, args.segundos)
