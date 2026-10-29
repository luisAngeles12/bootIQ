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
        recibido = int(recibido)
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
