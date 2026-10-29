"""Sondeo de velas de 1 s; SOLO PRACTICE, sin órdenes."""

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


def observar_instantanea(instantanea, ahora, desde, vistos, latencias=None):
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
            if latencias is not None:
                # Primer instante del reloj IQ en que vimos el cierre.
                latencias[inicio] = max(0, ahora - (inicio + 1))
            nuevas += 1
    return nuevas


def resumir(velas, inicio, fin, latencias=None):
    marcas = sorted(velas)
    saltos = [(a, b) for a, b in zip(marcas, marcas[1:]) if b - a != 1]
    ultima = marcas[-1] if marcas else None
    retrasos = sorted(latencias.values()) if latencias is not None else []
    p95 = retrasos[max(0, (len(retrasos) * 95 + 99) // 100 - 1)] if retrasos else None
    mediana = retrasos[(len(retrasos) - 1) // 2] if retrasos else None
    return {
        "segundos_observacion": fin - inicio,
        "velas_1s_nuevas": len(marcas),
        "huecos_entre_velas": len(saltos),
        "ultima_vela": ultima,
        "retraso_ultima_segundos": fin - ultima - 1 if ultima is not None else None,
        "muestra_continua": bool(marcas) and not saltos,
        "latencia_mediana_segundos": mediana,
        "latencia_p95_segundos": p95,
        "latencia_maxima_segundos": max(retrasos) if retrasos else None,
        "velas_con_demora_2s_o_mas": sum(n >= 2 for n in retrasos),
        "advertencia_latencia": "RESOLUCION_1S_NO_SUBSEGUNDO",
        "advertencia": "DIAGNOSTICO_SIN_OPERACIONES_NO_ESTIMA_WINRATE",
    }



def evaluar_micro_rechazo_sombra(velas, ahora):
    """Nivel calculado de 20 velas anteriores; patrón solo en las 3 posteriores.

    Diagnóstico sin autorización operativa ni comparación con resultados futuros.
    """
    from price_action import diagnosticar_micro_rechazo_1s

    secuencia = [velas[t] for t in sorted(velas)]
    if len(secuencia) < 23:
        return []
    ultimas = secuencia[-23:]
    marcas = [int(v["from"]) for v in ultimas]
    if any(b - a != 1 for a, b in zip(marcas, marcas[1:])):
        return []
    contexto, evento = ultimas[:20], ultimas[20:]
    soporte = min(float(v["min"]) for v in contexto)
    resistencia = max(float(v["max"]) for v in contexto)
    eventos = []
    for direccion, nivel in (("call", soporte), ("put", resistencia)):
        r = diagnosticar_micro_rechazo_1s(evento, nivel, direccion, ahora)
        if r["estado"] == "MICRO_RECHAZO_CONFIRMADO":
            eventos.append({
                "timestamp": marcas[-1],
                "direccion": direccion,
                "nivel_previo": nivel,
                "operable": False,
            })
    return eventos


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



def evaluar_captura_finalizada(velas, horizonte=60):
    """Evaluacion hipotetica independiente al finalizar una captura continua."""
    from evaluar_captura_fresca_practice import evaluar_sesion, resumen_sesion
    return resumen_sesion(evaluar_sesion(velas, horizonte=horizonte))


def sondear(activo, segundos, guardar_nuevas=False):
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
    latencias = {}
    ultimos_evaluados = set()
    eventos_sombra = []
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
            nuevas = observar_instantanea(iq.get_realtime_candles(activo, 1),
                                           ahora, inicio, vistos, latencias)
            if nuevas and vistos:
                ultimo_timestamp = max(vistos)
                if ultimo_timestamp not in ultimos_evaluados:
                    ultimos_evaluados.add(ultimo_timestamp)
                    for evento in evaluar_micro_rechazo_sombra(vistos, ahora):
                        eventos_sombra.append(evento)
                        print("MICRORECHAZO_SOMBRA:", evento, flush=True)
            time.sleep(0.2)
        # Medir ANTES del cierre; desuscribir puede esperar 5 segundos.
        fin = int(iq.get_server_timestamp())
        print("RESULTADO:", resumir(vistos, inicio, fin, latencias), flush=True)
        if guardar_nuevas:
            from captura_fresca_practice import guardar_captura_fresca
            ruta, total = guardar_captura_fresca(
                activo, vistos, inicio, fin,
                Path(__file__).with_name("data_actual_practice"),
                latencias=latencias,
            )
            print("CAPTURA_NUEVA_VALIDADA:", ruta, "| velas:", total, flush=True)
            from contexto_mercado_fresco import consolidar_minutos, diagnosticar_contexto
            minutos = consolidar_minutos(vistos)
            contexto = diagnosticar_contexto(minutos)
            print("CONTEXTO_MERCADO_1M:", contexto, flush=True)
            from estrategias_contexto_fresco import diagnosticar_estrategias
            print("ESTRATEGIAS_CONTEXTO_SOMBRA:",
                  diagnosticar_estrategias(minutos, contexto["estado"]), flush=True)
            print("EVALUACION_AUTOMATICA_SOMBRA_60S:",
                  evaluar_captura_finalizada({
                      t: {**vela, "_latencia_primera_recepcion_s": latencias.get(t)}
                      for t, vela in vistos.items()
                  }), flush=True)
        print("MICRORECHAZOS_SOMBRA:", {
            "total": len(eventos_sombra),
            "call": sum(e["direccion"] == "call" for e in eventos_sombra),
            "put": sum(e["direccion"] == "put" for e in eventos_sombra),
            "operaciones": 0,
            "advertencia": "NO_ES_SENAL_NI_WINRATE",
        }, flush=True)
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
    parser.add_argument("--guardar-nuevas", action="store_true",
                        help="Guarda solo velas nuevas validas de la sesion; no importa historial")
    args = parser.parse_args()
    if not 10 <= args.segundos <= 3600:
        parser.error("--segundos debe estar entre 10 y 3600")
    sondear(args.activo, args.segundos, args.guardar_nuevas)
