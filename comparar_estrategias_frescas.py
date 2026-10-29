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
            # La señal solo se conoce al CIERRE de este minuto.
            # El precio de ese cierre no puede asumirse ejecutable.
            cierre_senal_utc = minutos[i]["end"]
            segundo_entrada = cierre_senal_utc
            segundo_salida = cierre_senal_utc + horizonte_minutos * 60 - 1
            entrada_1s = velas_1s.get(segundo_entrada)
            salida_1s = velas_1s.get(segundo_salida)
            if (salida >= len(minutos)
                    or minutos[salida]["from"] != segundo_entrada
                    + (horizonte_minutos - 1) * 60
                    or entrada_1s is None or salida_1s is None):
                resultado = "SIN_FUTURO"
            else:
                # Simulacion hipotetica: apertura de la primera vela futura,
                # no el cierre ya observado de la vela de confirmacion.
                entrada = float(entrada_1s["open"])
                cierre = float(salida_1s["close"])
                if cierre == entrada:
                    resultado = "EMPATE"
                elif (cierre > entrada) == (candidato["direccion"] == "call"):
                    resultado = "WIN"
                else:
                    resultado = "LOSS"
            ultimo_segundo = cierre_senal_utc - 1
            latencia = velas_1s[ultimo_segundo].get("_latencia_primera_recepcion_s")
            # Para asumir la siguiente apertura, el cierre debe haberse
            # visto dentro del mismo segundo de su disponibilidad.
            if latencia is None:
                calidad = "LATENCIA_NO_REGISTRADA"
            elif latencia > 0:
                calidad = "DETECCION_TARDIA"
            elif entrada_1s is None:
                calidad = "ENTRADA_NO_OBSERVADA"
            else:
                calidad = "TIEMPO_VERIFICADO"
            resultados[nombre].append({
                "timestamp_senal": ultimo_segundo,
                "timestamp_entrada_hipotetica": segundo_entrada,
                "timestamp_salida_hipotetica": segundo_salida,
                "modelo_entrada": "APERTURA_PRIMERA_VELA_FUTURA_NO_EJECUTADA",
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
