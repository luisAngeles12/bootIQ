"""Analisis automatico de evidencia al arrancar PRACTICE, solo observacional.

Usa los CSV existentes EN LA MAQUINA del bot; jamas carga memoria TRAIN
como productiva ni habilita bootstrap. Un resultado favorable en sombra
no representa fill/payout ni autoriza una entrada.
"""
import csv
from pathlib import Path

from analizar_oportunidades_integrales_practice import analizar
from validar_hipotesis_sombra_oos_practice import validar

RUTA_CIERRES = "historial_bot.csv"
RUTA_RECHAZADAS = "auditoria_candidatas_sombra_practice.csv"


def _leer(ruta):
    path = Path(ruta)
    if not path.is_file():
        return None
    with path.open(encoding="utf-8-sig", newline="") as archivo:
        return list(csv.DictReader(archivo))


def evaluar_fuentes(ruta_cierres=RUTA_CIERRES, ruta_rechazadas=RUTA_RECHAZADAS):
    informe = {
        "tipo": "EVIDENCIA_PRACTICE_AUTOMATICA_NO_OPERATIVA",
        "autorizacion": False,
        "memoria_productiva_modificada": False,
        "bootstrap_modificado": False,
        "cierres": {"estado": "SIN_ARCHIVO", "candidato": None},
        "rechazadas": {"estado": "SIN_ARCHIVO", "candidato": None},
    }
    try:
        filas = _leer(ruta_cierres)
        if filas is not None:
            resultado = analizar(filas)
            candidato = resultado.get("candidato") or {}
            informe["cierres"] = {
                "estado": resultado.get("estado"),
                "operaciones_validas": resultado.get("operaciones_validas", 0),
                "candidatos_train": resultado.get("candidatos_train_comparados", 0),
                "candidato_train": (
                    [candidato.get("variable"), candidato.get("valor")]
                    if candidato else None
                ),
                "test_n": (candidato.get("test_oos") or {}).get("n", 0),
                "test_wr": (candidato.get("test_oos") or {}).get("winrate_pct"),
                "test_neto": (candidato.get("test_oos") or {}).get("neto"),
                "dias_oos": candidato.get("dias_oos_candidato", 0),
                "jornadas_oos_estables": candidato.get("jornadas_oos_estables", False),
                "dias_oos_fallidos": [
                    dia for dia, m in (candidato.get("test_por_dia") or {}).items()
                    if (
                        m.get("minutos_distintos", 0) < 10
                        or (m.get("winrate_por_minuto_pct") or 0) < 60
                        or m.get("neto", 0) <= 0
                    )
                ],
                "cumple_oos": candidato.get("supera_objetivo_oos", False),
                "autoriza_operaciones": False,
            }
    except (OSError, UnicodeError, ValueError, KeyError, TypeError) as exc:
        informe["cierres"] = {"estado": "ERROR_ANALISIS", "error": type(exc).__name__}

    try:
        filas = _leer(ruta_rechazadas)
        if filas is not None:
            resultado = validar(filas)
            candidato = resultado.get("candidato") or {}
            informe["rechazadas"] = {
                "estado": resultado.get("estado"),
                "resueltas": resultado.get("resueltos", 0),
                "candidatos_train": resultado.get("candidatos_train", 0),
                "candidato_train": (
                    [candidato.get("campo"), candidato.get("valor")]
                    if candidato else None
                ),
                "test_n": (candidato.get("test") or {}).get("n", 0),
                "test_wr": (candidato.get("test") or {}).get("wr_pct"),
                "constancia_hipotetica": candidato.get("constancia_hipotetica", False),
                "tabla_candidatos_train_con_test": resultado.get(
                    "tabla_candidatos_train_con_test", []
                ),
                "autoriza_operaciones": False,
            }
    except (OSError, UnicodeError, ValueError, KeyError, TypeError) as exc:
        informe["rechazadas"] = {"estado": "ERROR_ANALISIS", "error": type(exc).__name__}
    return informe


def lineas(resumen):
    cierres = resumen["cierres"]
    sombra = resumen["rechazadas"]
    return [
        "EVIDENCIA PRACTICE | cierres: {estado} | validas: {operaciones_validas} | "
        "TRAIN candidatos: {candidatos_train} | candidato: {candidato_train} | "
        "TEST: n={test_n}, WR={test_wr}, PnL={test_neto} | "
        "dias={dias_oos}, constantes={jornadas_oos_estables}, "
        "dias_fallidos={dias_oos_fallidos} | cumple OOS: {cumple_oos}".format(
            operaciones_validas=cierres.get("operaciones_validas", 0),
            candidatos_train=cierres.get("candidatos_train", 0),
            candidato_train=cierres.get("candidato_train"),
            test_n=cierres.get("test_n", 0),
            test_wr=cierres.get("test_wr"),
            test_neto=cierres.get("test_neto"),
            dias_oos=cierres.get("dias_oos", 0),
            jornadas_oos_estables=cierres.get("jornadas_oos_estables", False),
            dias_oos_fallidos=cierres.get("dias_oos_fallidos", []),
            cumple_oos=cierres.get("cumple_oos", False),
            estado=cierres.get("estado"),
        ),
        "EVIDENCIA PRACTICE | rechazadas: {estado} | resueltas: {resueltas} | "
        "TRAIN candidatos: {candidatos_train} | candidato: {candidato_train} | "
        "TEST: n={test_n}, WR hipotetico={test_wr} | constancia: {constancia_hipotetica}".format(
            resueltas=sombra.get("resueltas", 0),
            candidatos_train=sombra.get("candidatos_train", 0),
            candidato_train=sombra.get("candidato_train"),
            test_n=sombra.get("test_n", 0),
            test_wr=sombra.get("test_wr"),
            constancia_hipotetica=sombra.get("constancia_hipotetica", False),
            estado=sombra.get("estado"),
        ),
        "EVIDENCIA PRACTICE | TOP TRAIN sombra (orden congelado; "
        "no escoger mejor TEST): {}".format(
            "; ".join(
                "{campo}={valor}: TRAIN {train_wr}%/{train_n}min, "
                "TEST {test_wr}%/{test_n}min, delta_base {delta}pp".format(
                    campo=x["campo"], valor=x["valor"],
                    train_wr=x["train"].get("winrate_por_minuto_pct"),
                    train_n=x["train"].get("minutos_distintos"),
                    test_wr=x["test"].get("winrate_por_minuto_pct"),
                    test_n=x["test"].get("minutos_distintos"),
                    delta=x.get("diferencia_wr_test_vs_baseline_pct"),
                )
                for x in sombra.get("tabla_candidatos_train_con_test", [])
            ) or "SIN_CANDIDATOS_CON_MUESTRA_SUFICIENTE"
        ),
        "EVIDENCIA PRACTICE | SOLO DIAGNOSTICO; no concede permisos IQ "
        "ni copia datos TRAIN a la memoria oficial",
    ]
