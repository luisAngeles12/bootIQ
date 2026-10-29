"""Replay causal del ARBITRO completo sobre capturas PRACTICE nuevas.

No suma ganancias hipoteticas de estrategias que el cerebro habria
bloqueado. Ni esta funcion ni sus resultados autorizan operaciones.
"""
from contexto_mercado_fresco import consolidar_minutos
from paridad_sombra_practice import (diagnosticar_cierre, _segmento_actual,
                                    calidad_recepcion_cierre)


def evaluar_arbitro(velas_1s, horizonte_minutos=1):
    if not 1 <= horizonte_minutos <= 10:
        raise ValueError("HORIZONTE_INVALIDO")
    minutos = consolidar_minutos(velas_1s)
    eventos = []
    ocupado_hasta = -1
    for i in range(23, len(minutos)):
        actuales = _segmento_actual(minutos[:i + 1])
        diagnostico = diagnosticar_cierre(actuales)
        arbitraje = diagnostico["arbitraje"]
        if arbitraje["estado"] != "CANDIDATO_SOMBRA_NO_OPERABLE":
            continue
        if arbitraje["operable"] is not False:
            raise RuntimeError("ARBITRO_AUTORIZO_OPERACION")
        if i < ocupado_hasta:
            continue
        direccion = arbitraje["direccion"]
        if direccion not in ("call", "put"):
            raise RuntimeError("DIRECCION_ARBITRO_INVALIDA")
        entrada_ts = minutos[i]["end"]
        salida_ts = entrada_ts + horizonte_minutos * 60 - 1
        indice_salida = i + horizonte_minutos
        entrada = velas_1s.get(entrada_ts)
        salida = velas_1s.get(salida_ts)
        # Todo el horizonte debe ser continuo: verificar solo el minuto
        # final ocultaria huecos intermedios en capturas incompletas.
        futuro_continuo = (
            indice_salida < len(minutos)
            and all(
                minutos[j]["from"] == entrada_ts + (j - i - 1) * 60
                for j in range(i + 1, indice_salida + 1)
            )
        )
        if not futuro_continuo or entrada is None or salida is None:
            resultado = "SIN_FUTURO"
        else:
            precio_entrada = float(entrada["open"])
            precio_salida = float(salida["close"])
            if precio_entrada == precio_salida:
                resultado = "EMPATE"
            elif (precio_salida > precio_entrada) == (direccion == "call"):
                resultado = "WIN"
            else:
                resultado = "LOSS"
        ultima_senal = entrada_ts - 1
        calidad = calidad_recepcion_cierre(velas_1s, entrada_ts)
        if calidad == "TIEMPO_VERIFICADO" and entrada is None:
            calidad = "ENTRADA_NO_OBSERVADA"
        eventos.append({
            "timestamp_senal": ultima_senal,
            "timestamp_entrada_hipotetica": entrada_ts,
            "timestamp_salida_hipotetica": salida_ts,
            "direccion": direccion,
            "estrategias_que_coinciden": list(arbitraje["estrategias"]),
            "resultado": resultado,
            "calidad_tiempo": calidad,
            "modelo_entrada": "APERTURA_PRIMERA_VELA_FUTURA_NO_EJECUTADA",
            "operable": False,
        })
        ocupado_hasta = indice_salida + 1
    return eventos


def resumen_arbitro(velas_1s, horizonte_minutos=1):
    from evaluar_captura_fresca_practice import resumen_sesion
    return resumen_sesion(evaluar_arbitro(velas_1s, horizonte_minutos))
