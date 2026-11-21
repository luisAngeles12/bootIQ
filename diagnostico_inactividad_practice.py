"""Diagnostico puro de inactividad PRACTICE; no autoriza operaciones.

Diferencia ausencia de oportunidades, rechazos del Cerebro y fallos
de ejecucion. Los contadores de la ronda son la fuente; no inferir
que el broker se desconecto solo por faltar aperturas.
"""
from datetime import datetime, timezone


def resumen_inactividad(metricas, senales_finales, aperturas, *,
                       memoria_oficial_estado="DESCONOCIDA",
                       segundos_sin_apertura=0):
    datos = metricas if isinstance(metricas, dict) else {}
    def numero(clave):
        try:
            return max(0, int(datos.get(clave, 0) or 0))
        except (TypeError, ValueError, OverflowError):
            return 0

    senales = max(0, int(senales_finales or 0))
    aperturas = max(0, int(aperturas or 0))
    rechazadas = numero("cerebro_no_operar")
    sin_permiso = numero("cerebro_sin_autorizacion")
    aptas = numero("senales_aprobadas")
    fallidas = numero("directas_no_ejecutadas")
    protocolos = numero("autorizadas_protocolo")
    if aperturas:
        razon = "APERTURAS_CONFIRMADAS"
    elif senales == 0:
        razon = "SIN_SENALES_FINALES"
    elif rechazadas + sin_permiso >= senales:
        razon = "CEREBRO_SIN_AUTORIZACION"
    elif fallidas:
        razon = "AUTORIZADAS_PERO_ENVIO_NO_EJECUTADO"
    elif protocolos:
        razon = "AUTORIZADAS_A_PROTOCOLO_SIN_APERTURA_DIRECTA"
    elif aptas:
        razon = "SENALES_APROBADAS_SIN_APERTURA_CONFIRMADA"
    else:
        razon = "SIN_APERTURAS_CAUSA_NO_DETERMINADA"
    return {
        "estado": razon,
        "senal_finales": senales,
        "aperturas_confirmadas_ronda": aperturas,
        "rechazos_cerebro": rechazadas,
        "sin_autorizacion": sin_permiso,
        "autorizadas": aptas,
        "envios_directos_no_ejecutados": fallidas,
        "autorizadas_protocolo": protocolos,
        "memoria_oficial_estado_inicio": str(memoria_oficial_estado),
        "segundos_sin_apertura_confirmada": max(0, int(segundos_sin_apertura or 0)),
        "no_modifica_decisiones": True,
        "no_autoriza_operaciones": True,
    }


def texto_inactividad(datos):
    return (
        "BOOTIQ PRACTICE INACTIVIDAD | {estado} | "
        "señales={senal_finales} | autorizadas={autorizadas} | "
        "rechazadas={rechazos_cerebro} | sin_permiso={sin_autorizacion} | "
        "fallidas={envios_directos_no_ejecutados} | "
        "protocolo={autorizadas_protocolo} | "
        "memoria_inicio={memoria_oficial_estado_inicio} | "
        "segundos_sin_apertura={segundos_sin_apertura_confirmada}"
    ).format(**datos)
