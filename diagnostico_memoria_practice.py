"""Diagnostico de memoria al iniciar BootIQ; nunca autoriza operaciones.

La memoria experimental se menciona solo como evidencia de investigacion.
No se sustituye ni se promueve automaticamente como archivo productivo.
"""
from pathlib import Path


def diagnosticar_memoria(ruta_oficial, ruta_candidata=None, cargador=None):
    """Devuelve hechos observables sin modificar memoria ni autoridad."""
    ruta = Path(ruta_oficial)
    candidata = Path(ruta_candidata) if ruta_candidata is not None else None
    resultado = {
        "ruta_oficial": str(ruta),
        "estado": "AUSENTE",
        "claves": 0,
        "candidata_experimental_presente": (
            candidata.is_file() if candidata is not None else False
        ),
        "autoriza_operaciones": False,
    }
    if not ruta.is_file():
        return resultado
    if cargador is None:
        from motor_aprendizaje_historico import cargar_aprendizaje
        cargador = cargar_aprendizaje
    try:
        memoria = cargador(str(ruta))
    except (OSError, ValueError, TypeError) as exc:
        resultado["estado"] = "ERROR_CARGA"
        resultado["error"] = type(exc).__name__
        return resultado
    if not isinstance(memoria, dict):
        resultado["estado"] = "ERROR_FORMATO"
        return resultado
    resultado["claves"] = len(memoria)
    resultado["estado"] = "DISPONIBLE" if memoria else "VACIA"
    return resultado


def lineas_diagnostico_memoria(resultado):
    """Lineas estables para consola; no contienen datos privados."""
    salida = [
        "BOOTIQ MEMORIA V3 | estado: {} | claves: {} | ruta: {}".format(
            resultado["estado"], resultado["claves"], resultado["ruta_oficial"]
        )
    ]
    if resultado["estado"] != "DISPONIBLE":
        salida.append(
            "BOOTIQ MEMORIA V3 | SIN FUENTES OFICIALES UTILIZABLES; "
            "el Cerebro puede rechazar candidatas por SIN_DATOS_ESTADISTICOS"
        )
    if resultado["candidata_experimental_presente"]:
        salida.append(
            "BOOTIQ MEMORIA V3 | candidata TRAIN presente; "
            "NO se carga ni autoriza automaticamente"
        )
    salida.append(
        "BOOTIQ MEMORIA V3 | diagnostico informativo; "
        "sin cambios de estrategia ni permisos de operacion"
    )
    return salida
