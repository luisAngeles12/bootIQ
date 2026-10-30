"""Paridad causal de decisiones en sombra: reproduccion frente a flujo 1s.

No conecta con IQ Option, no importa credenciales y nunca ejecuta ordenes.
Una decision solo existe cuando llegaron las 60 velas cerradas del minuto;
si una vela llega despues del cierre, ese minuto no se evalua en tiempo real.
"""
from contexto_mercado_fresco import consolidar_minutos, diagnosticar_contexto
from estrategias_contexto_fresco import diagnosticar_estrategias
from arbitro_estrategias_frescas import arbitrar_candidatos


def diagnosticar_cierre(minutos):
    """Nucleo compartido por replay y flujo; incluye siempre operable=False."""
    contexto = diagnosticar_contexto(minutos)
    candidatos = diagnosticar_estrategias(minutos, contexto["estado"])
    arbitraje = arbitrar_candidatos(candidatos, contexto["estado"])
    if arbitraje["operable"] is not False:
        raise RuntimeError("AUTORIZACION_SOMBRA_INESPERADA")
    return {"contexto": contexto, "candidatos": candidatos, "arbitraje": arbitraje}


def _segmento_actual(minutos):
    """No mezclar los contextos a traves de un hueco de minutos."""
    j = len(minutos) - 1
    while j and minutos[j]["from"] - minutos[j - 1]["from"] == 60:
        j -= 1
    return minutos[j:]


def calidad_recepcion_cierre(velas_1s, fin_minuto):
    """Valida las 60 primeras recepciones antes de declarar señal causal.

    Una vela intermedia recibida tras el cierre impide que el minuto
    hubiese estado completo en el flujo al decidir. Resolucion: 1 segundo.
    """
    inicio = fin_minuto - 60
    for t in range(inicio, fin_minuto):
        vela = velas_1s.get(t)
        if vela is None:
            return "MINUTO_INCOMPLETO"
        latencia = vela.get("_latencia_primera_recepcion_s")
        if latencia is None:
            return "LATENCIA_NO_REGISTRADA"
        if type(latencia) is not int or latencia < 0:
            return "LATENCIA_INVALIDA_O_NO_REGISTRADA"
        if t + 1 + latencia > fin_minuto:
            return "DETECCION_TARDIA"
    return "TIEMPO_VERIFICADO"


def calidad_contexto_historico(velas_1s, minutos, profundidad=24):
    """Comprueba disponibilidad real de las barras que alimentan una senal.

    El ultimo minuto se evalua por separado para conservar el motivo preciso
    de latencia del disparador. Solo usa barras previas al disparador.
    """
    if len(minutos) < profundidad:
        return "CONTEXTO_INSUFICIENTE"
    recientes = minutos[-profundidad:]
    if any(b["from"] - a["from"] != 60
           for a, b in zip(recientes, recientes[1:])):
        return "CONTEXTO_CON_HUECOS"
    for minuto in recientes[:-1]:
        if calidad_recepcion_cierre(velas_1s, minuto["end"]) != "TIEMPO_VERIFICADO":
            return "CONTEXTO_NO_DISPONIBLE_EN_TIEMPO_REAL"
    return "TIEMPO_VERIFICADO"


def reproducir_cierres(velas_1s):
    """Referencia por timestamp, sin utilizar barras futuras al decidir."""
    minutos = consolidar_minutos(velas_1s)
    return [
        (minuto["end"], diagnosticar_cierre(_segmento_actual(minutos[:i + 1])))
        for i, minuto in enumerate(minutos)
    ]


def evaluar_flujo(llegadas):
    """Llegadas (segundo_de_recepcion, vela_1s), monotonicamente ordenadas.

    Un cierre se publica una sola vez al recibir la vela 59 del minuto o
    al avanzar el reloj. Las velas posteriores al cierre no reescriben pasado.
    """
    vistos = {}
    resultados = []
    cerrados = set()
    recepcion_anterior = None

    def finalizar_hasta(recepcion):
        # Los cierres sin 60 velas completas se descartan, no se reconstruyen.
        pendientes = sorted({t // 60 * 60 + 60 for t in vistos
                             if t // 60 * 60 + 60 <= recepcion
                             and t // 60 * 60 + 60 not in cerrados})
        for fin in pendientes:
            cerrados.add(fin)
            minutos = consolidar_minutos({t: v for t, v in vistos.items() if t < fin})
            if minutos and minutos[-1]["end"] == fin:
                resultados.append((fin, diagnosticar_cierre(_segmento_actual(minutos))))

    for recibido, vela in llegadas:
        if type(recibido) is not int or recibido < 0:
            raise ValueError("RECEPCION_INVALIDA")
        if recepcion_anterior is not None and recibido < recepcion_anterior:
            raise ValueError("RECEPCIONES_DESORDENADAS")
        recepcion_anterior = recibido
        t = int(vela["from"])
        fin = (t // 60 + 1) * 60
        if recibido < t + 1:
            raise ValueError("VELA_AUN_ABIERTA")
        # Si la ultima vela del minuto llega justo a su cierre, se acepta.
        # Las velas anteriores recibidas tras el cierre NO corrigen decisiones.
        if recibido <= fin and fin not in cerrados and t not in vistos:
            vistos[t] = dict(vela)
        finalizar_hasta(recibido)
    return resultados


def comprobar_paridad(velas_1s, llegadas):
    """Exige la misma secuencia exacta de cierres y diagnosticos."""
    referencia = reproducir_cierres(velas_1s)
    flujo = evaluar_flujo(llegadas)
    return {
        "paridad": referencia == flujo,
        "cierres_replay": len(referencia),
        "cierres_flujo": len(flujo),
        "operable": False,
        "advertencia": "PARIDAD_TECNICA_NO_DEMUESTRA_WINRATE",
    }


def comprobar_paridad_recepcion_1s(velas_1s, latencias):
    """Diagnostico por primera recepcion observada, resolucion 1 segundo.

    Requiere latencia de CADA vela; no inventa tiempos de capturas antiguas.
    El resultado no equivale a latencia de ejecucion ni autoriza operaciones.
    """
    if not velas_1s or any(t not in latencias for t in velas_1s):
        return {
            "paridad": None, "motivo": "LATENCIAS_INCOMPLETAS",
            "operable": False,
        }
    if any(type(latencias[t]) is not int or latencias[t] < 0
           for t in velas_1s):
        return {
            "paridad": None, "motivo": "LATENCIAS_INVALIDAS",
            "operable": False,
        }
    llegadas = sorted(
        ((t + 1 + latencias[t], dict(vela)) for t, vela in velas_1s.items()),
        key=lambda par: (par[0], int(par[1]["from"])),
    )
    resultado = comprobar_paridad(velas_1s, llegadas)
    # Cobertura causal: distingue replay historico de cierres recibidos a tiempo.
    # No equivale a paridad de decisiones (puede diferir el contexto anterior).
    minutos = consolidar_minutos(velas_1s)
    elegibles = set()
    tardios = set()
    for minuto in minutos:
        fin = minuto["end"]
        if all(t + 1 + latencias[t] <= fin
               for t in range(fin - 60, fin)):
            elegibles.add(fin)
        else:
            tardios.add(fin)
    cierres_flujo = {fin for fin, _ in evaluar_flujo(llegadas)}
    resultado["cierres_replay_disponibles_a_tiempo"] = len(elegibles)
    resultado["cierres_replay_con_recepcion_tardia"] = len(tardios)
    resultado["coincidencia_cierres_elegibles"] = (cierres_flujo == elegibles)
    resultado["advertencia_cobertura"] = (
        "COINCIDENCIA_DE_TIMESTAMPS_NO_ES_PARIDAD_DE_DECISIONES"
    )
    resultado["resolucion_recepcion"] = "SEGUNDO_IQ_NO_SUBSEGUNDO"
    resultado["velas_con_retraso"] = sum(latencias[t] > 0 for t in velas_1s)
    return resultado
