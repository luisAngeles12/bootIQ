"""Comparacion causal de tres estrategias en capturas nuevas, solo PRACTICE.

Cada estrategia se evalua por separado; no se suman sus muestras como
operaciones independientes. No conecta al broker ni envia ordenes.
"""
from contexto_mercado_fresco import consolidar_minutos, diagnosticar_contexto
from estrategias_contexto_fresco import diagnosticar_estrategias


def comparar_estrategias(velas_1s, horizonte_minutos=1):
    if not 1 <= horizonte_minutos <= 10:
        raise ValueError("HORIZONTE_INVALIDO")
    minutos = consolidar_minutos(velas_1s)
    nombres = ("RUPTURA_RETEST", "RECHAZO_ZONA", "CONTINUACION_TENDENCIA")
    resultados = {nombre: [] for nombre in nombres}
    ocupados = {nombre: -1 for nombre in nombres}
    for i in range(23, len(minutos)):
        actuales = minutos[:i + 1]
        contexto = diagnosticar_contexto(actuales)
        # Nunca usar una barra futura para decidir el candidato.
        candidatos = diagnosticar_estrategias(actuales, contexto["estado"])
        for candidato in candidatos:
            nombre = candidato["estrategia"]
            if candidato["estado"] != "CANDIDATO_SOMBRA" or i < ocupados[nombre]:
                continue
            salida = i + horizonte_minutos
            if salida >= len(minutos):
                resultado = "SIN_FUTURO"
            elif minutos[salida]["from"] != minutos[i]["from"] + horizonte_minutos * 60:
                resultado = "SIN_FUTURO"
            else:
                entrada = float(minutos[i]["close"])
                cierre = float(minutos[salida]["close"])
                if cierre == entrada:
                    resultado = "EMPATE"
                elif (cierre > entrada) == (candidato["direccion"] == "call"):
                    resultado = "WIN"
                else:
                    resultado = "LOSS"
            # Retraso del ultimo segundo de la barra de confirmacion.
            ultimo_segundo = minutos[i]["end"] - 1
            latencia = velas_1s[ultimo_segundo].get("_latencia_primera_recepcion_s")
            if latencia is None:
                calidad = "LATENCIA_NO_REGISTRADA"
            elif latencia > 1:
                calidad = "DETECCION_TARDIA"
            else:
                calidad = "TIEMPO_VERIFICADO"
            resultados[nombre].append({
                "timestamp_senal": ultimo_segundo,
                "direccion": candidato["direccion"],
                "resultado": resultado,
                "calidad_tiempo": calidad,
            })
            ocupados[nombre] = salida + 1
    return resultados


def resumen_comparativa(velas_1s, horizonte_minutos=1):
    from evaluar_captura_fresca_practice import resumen_sesion
    eventos = comparar_estrategias(velas_1s, horizonte_minutos)
    return {
        nombre: resumen_sesion(filas)
        for nombre, filas in eventos.items()
    }
