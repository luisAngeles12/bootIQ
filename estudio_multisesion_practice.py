"""Estudio multisesion por estrategia; solo evidencia, nunca ordenes."""
from comparar_estrategias_frescas import comparar_estrategias
from evaluar_captura_fresca_practice import resumen_sesion
from validar_evidencia_practice import verificar_evidencia_sostenida

ESTRATEGIAS = ("RUPTURA_RETEST", "RECHAZO_ZONA", "CONTINUACION_TENDENCIA")


def estudiar_sesiones(sesiones, horizonte_minutos=1):
    """Cada entrada: (activo, timestamp_inicio, velas_1s).

    Mantiene separados los resultados de cada estrategia, activo y sesion.
    No elige el mejor resultado a posteriori ni modifica parametros.
    """
    datos = {nombre: [] for nombre in ESTRATEGIAS}
    for activo, inicio, velas in sesiones:
        evaluados = comparar_estrategias(velas, horizonte_minutos)
        for nombre in ESTRATEGIAS:
            datos[nombre].append((activo, inicio, evaluados[nombre]))
    return {
        nombre: {
            "resumen": resumen_sesion([e for _, _, eventos in datos[nombre]
                                      for e in eventos]),
            "evidencia": verificar_evidencia_sostenida(datos[nombre]),
        }
        for nombre in ESTRATEGIAS
    }
