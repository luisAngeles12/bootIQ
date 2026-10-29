"""Estudio multi-sesion del ARBITRO de BootIQ PRACTICE, solo sombra.

No usa resultados aislados de estrategias como rendimiento del bot.
Separa dias cronologicos y exige evidencia independiente en holdout.
"""
from datetime import datetime, timezone
from math import ceil

from evaluar_arbitro_fresco import evaluar_arbitro
from evaluar_captura_fresca_practice import resumen_sesion
from validar_evidencia_practice import verificar_evidencia_sostenida
from evaluar_pago_practice import evaluar_viabilidad_pago


def estudiar_eventos_arbitro(sesiones, fraccion_desarrollo=0.7):
    """Sesiones evaluadas: [(activo, inicio_utc, eventos_arbitro)]."""
    if not 0.5 <= fraccion_desarrollo < 1:
        raise ValueError("FRACCION_INVALIDA")
    sesiones = list(sesiones)
    resumen = resumen_sesion([
        evento for _, _, eventos in sesiones for evento in eventos
    ])
    dias = sorted({
        datetime.fromtimestamp(inicio, tz=timezone.utc).date()
        for _, inicio, _ in sesiones
    })
    if len(dias) < 2:
        return {
            "estado": "ARBITRO_OOS_NO_VALIDADO",
            "motivos": ["DIAS_INSUFICIENTES"],
            "resumen_total": resumen, "operaciones_autorizadas": False,
        }
    n_dev = min(len(dias) - 1, max(1, ceil(len(dias) * fraccion_desarrollo)))
    dias_dev = set(dias[:n_dev])
    dias_oos = set(dias[n_dev:])
    def pertenece(sesion, conjunto):
        return datetime.fromtimestamp(
            sesion[1], tz=timezone.utc).date() in conjunto
    dev = [s for s in sesiones if pertenece(s, dias_dev)]
    oos = [s for s in sesiones if pertenece(s, dias_oos)]
    evidencia_dev = verificar_evidencia_sostenida(dev)
    evidencia_oos = verificar_evidencia_sostenida(oos)
    viabilidad_pago = evaluar_viabilidad_pago([
        e for _, _, eventos in oos for e in eventos
    ])
    motivos = []
    for nombre, grupo in (("DESARROLLO", dev), ("HOLDOUT", oos)):
        # El arbitro en sombra jamas emite ordenes. Si se recibe un
        # evento con autoridad inesperada, el estudio NO puede aprobar.
        eventos_grupo = [e for _, _, eventos in grupo for e in eventos]
        if any(e.get("operable") is not False for e in eventos_grupo):
            motivos.append("ARBITRO_" + nombre + "_AUTORIZACION_INESPERADA")
        if any(e.get("direccion") not in ("call", "put")
               for e in eventos_grupo):
            motivos.append("ARBITRO_" + nombre + "_DIRECCION_INVALIDA")
    if len(dias_dev) < 3:
        motivos.append("DESARROLLO_MENOR_TRES_DIAS")
    if len(dias_oos) < 3:
        motivos.append("HOLDOUT_MENOR_TRES_DIAS")
    if evidencia_dev["estado"] != "EVIDENCIA_PRELIMINAR_SUPERA_OBJETIVO":
        motivos.append("ARBITRO_DESARROLLO_NO_VALIDADO")
    if evidencia_oos["estado"] != "EVIDENCIA_PRELIMINAR_SUPERA_OBJETIVO":
        motivos.append("ARBITRO_HOLDOUT_NO_VALIDADO")
    return {
        "estado": ("EVIDENCIA_OOS_ARB_SOMBRA" if not motivos
                   else "ARBITRO_OOS_NO_VALIDADO"),
        "motivos": motivos,
        "resumen_total": resumen,
        "dias_desarrollo": len(dias_dev),
        "dias_holdout": len(dias_oos),
        "ultima_fecha_desarrollo": str(max(dias_dev)),
        "primera_fecha_holdout": str(min(dias_oos)),
        "desarrollo": evidencia_dev,
        "holdout": evidencia_oos,
        "viabilidad_pago_holdout": viabilidad_pago,
        "operaciones_autorizadas": False,
        "advertencia": "SOMBRA_NO_ES_EJECUCION_NI_RENTABILIDAD_DEMOSTRADA",
    }


def estudiar_capturas_arbitro(sesiones, fraccion_desarrollo=0.7):
    """Capturas: [(activo, inicio_utc, velas_1s)] sin mezclar archivos."""
    evaluadas = [
        (activo, inicio, evaluar_arbitro(velas))
        for activo, inicio, velas in sesiones
    ]
    return estudiar_eventos_arbitro(evaluadas, fraccion_desarrollo)
