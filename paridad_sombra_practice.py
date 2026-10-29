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


def reproducir_cierres(velas_1s):
    """Referencia por timestamp, sin utilizar ninguna barra futura al decidir."""
    minutos = consolidar_minutos(velas_1s)
    resultados = []
    for i, minuto in enumerate(minutos):
        if i and minuto["from"] - minutos[i - 1]["from"] != 60:
            # Los historiales separados no deben transferir contexto.
            inicio = i
            while inicio and minutos[inicio - 1]["from"] == minutos[inicio]["from"] - 60:
                inicio -= 1
            historia = minutos[inicio:i + 1]
        else:
            historia = minutos[:i + 1]
            if historia and len(historia) > 1:
                # Aislar cualquier segmento anterior desconectado.
                j = len(historia) - 1
                while j and historia[j]["from"] - historia[j - 1]["from"] == 60:
                    j -= 1
                historia = historia[j:]
        resultados.append((minuto["end"], diagnosticar_cierre(historia)))
    return resultados


def evaluar_flujo(llegadas):
    """Cada llegada: (segundo_de_recepcion, vela_1s). Orden temporal obligatorio.

    Usa el segundo de RECEPCION, no el timestamp de la vela, para determinar
    si pudo ser conocida al cierre. No reinterpreta datos tardios como oportunos.
    """
    vistos = {}
    resultados = []
    recepcion_anterior = None
    minuto_vigente = None

    def cerrar(hasta):
        nonlocal minuto_vigente
        if minuto_vigente is None:
            return
        fin = minuto_vigente + 60
        if hasta < fin:
            return
        # Solo observaciones recibidas como maximo en el instante de cierre.
        historia = {t: v for t, v in vistos.items() if t < fin}
        minutos = consolidar_minutos(historia)
        if minutos and minutos[-1]["end"] == fin:
            j = len(minutos) - 1
            while j and minutos[j]["from"] - minutos[j - 1]["from"] == 60:
                j -= 1
            resultados.append((fin, diagnosticar_cierre(minutos[j:])))
        minuto_vigente = None

    for recibido, vela in llegadas:
        recibido = int(recibido)
        if recepcion_anterior is not None and recibido < recepcion_anterior:
            raise ValueError("RECEPCIONES_DESORDENADAS")
        recepcion_anterior = recibido
        t = int(vela["from"])
        if t + 1 > recibido:
            raise ValueError("VELA_AUN_ABIERTA")
        if minuto_vigente is None:
            minuto_vigente = (recibido // 60) * 60
        if recibido >= minuto_vigente + 60:
            cerrar(recibido)
            minuto_vigente = (recibido // 60) * 60
        # Rechazar timestamps anteriores: llegaron tarde y no pueden corregir pasado.
        if t // 60 == recibido // 60 and t not in vistos:
            vistos[t] = dict(vela)
    cerrar(recepcion_anterior or 0)
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
