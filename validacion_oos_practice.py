"""Validacion prospectiva OOS: seleccionar en desarrollo y evaluar en dias posteriores.

La comparacion de tres estrategias no justifica elegir la ganadora segun
resultados del holdout. Este modulo jamas autoriza operaciones.
"""
from datetime import datetime, timezone
from math import ceil

from estudio_multisesion_practice import ESTRATEGIAS
from validar_evidencia_practice import verificar_evidencia_sostenida


def _dia(timestamp):
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).date()


def validar_oos_por_dias(eventos_por_estrategia, fraccion_desarrollo=0.7):
    """Entrada por estrategia: [(activo, inicio_utc, eventos), ...].

    Regla fija: primeros 70% de dias para desarrollo, resto holdout; minimo
    de tres dias posteriores para aceptar evidencia sostenida.
    No importa nunca resultados futuros para elegir estrategia.
    """
    if not 0.5 <= fraccion_desarrollo < 1.0:
        raise ValueError("FRACCION_INVALIDA")
    if set(eventos_por_estrategia) != set(ESTRATEGIAS):
        raise ValueError("CATALOGO_ESTRATEGIAS_INCOMPLETO")
    dias = sorted({
        _dia(inicio)
        for sesiones in eventos_por_estrategia.values()
        for _, inicio, _ in sesiones
    })
    if not dias:
        return {
            "estado": "OOS_NO_VALIDADO", "motivos": ["SIN_SESIONES"],
            "estrategia_fijada": None, "operaciones_autorizadas": False,
        }
    if len(dias) < 2:
        return {
            "estado": "OOS_NO_VALIDADO", "motivos": ["MENOS_DE_DOS_DIAS"],
            "estrategia_fijada": None, "operaciones_autorizadas": False,
        }
    # ceil evita mover un dia del futuro al conjunto de entrenamiento.
    n_desarrollo = min(len(dias) - 1, max(1, ceil(len(dias) * fraccion_desarrollo)))
    dias_desarrollo = set(dias[:n_desarrollo])
    dias_holdout = set(dias[n_desarrollo:])
    desarrollo = {}
    holdout = {}
    for nombre in ESTRATEGIAS:
        sesiones = list(eventos_por_estrategia[nombre])
        desarrollo[nombre] = verificar_evidencia_sostenida([
            sesion for sesion in sesiones if _dia(sesion[1]) in dias_desarrollo
        ])
        holdout[nombre] = [
            sesion for sesion in sesiones if _dia(sesion[1]) in dias_holdout
        ]
    # Seleccion solo con resultados de desarrollo. No se mira holdout.
    candidatos = [
        (desarrollo[nombre]["limite_inferior_95_pct"], nombre)
        for nombre in ESTRATEGIAS
        if desarrollo[nombre]["estado"] == "EVIDENCIA_PRELIMINAR_SUPERA_OBJETIVO"
    ]
    elegido = sorted(candidatos, key=lambda item: (-item[0], item[1]))[0][1] if candidatos else None
    motivos = []
    if len(dias_desarrollo) < 3:
        motivos.append("DESARROLLO_MENOR_TRES_DIAS")
    if len(dias_holdout) < 3:
        motivos.append("HOLDOUT_MENOR_TRES_DIAS")
    if elegido is None:
        motivos.append("NINGUNA_ESTRATEGIA_VALIDADA_EN_DESARROLLO")
    evidencia_holdout = (
        verificar_evidencia_sostenida(holdout[elegido])
        if elegido is not None else None
    )
    if evidencia_holdout is not None and evidencia_holdout["estado"] != "EVIDENCIA_PRELIMINAR_SUPERA_OBJETIVO":
        motivos.append("HOLDOUT_BAJO_CRITERIOS")
    return {
        "estado": ("EVIDENCIA_OOS_PRELIMINAR" if not motivos
                   else "OOS_NO_VALIDADO"),
        "estrategia_fijada": elegido,
        "dias_desarrollo": len(dias_desarrollo),
        "dias_holdout": len(dias_holdout),
        "ultimo_dia_desarrollo": str(max(dias_desarrollo)),
        "primer_dia_holdout": str(min(dias_holdout)) if dias_holdout else None,
        "desarrollo": desarrollo,
        "holdout_estrategia_fijada": evidencia_holdout,
        "motivos": motivos,
        "operaciones_autorizadas": False,
        "advertencia": "SIN_VALIDACION_DE_EJECUCION_PRACTICE_NO_HABILITAR_TRADING",
    }


def validar_oos_capturas(sesiones, fraccion_desarrollo=0.7):
    """Aplica el protocolo OOS a capturas nuevas sin seleccionar por holdout."""
    from comparar_estrategias_frescas import comparar_estrategias
    eventos = {nombre: [] for nombre in ESTRATEGIAS}
    for activo, inicio, velas in sesiones:
        comparados = comparar_estrategias(velas)
        for nombre in ESTRATEGIAS:
            eventos[nombre].append((activo, inicio, comparados[nombre]))
    return validar_oos_por_dias(eventos, fraccion_desarrollo)
