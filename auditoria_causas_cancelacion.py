"""Clasificación PASIVA de las causas verificables de cancelación V3.

No calcula decisiones nuevas, no modifica autoridad ni contabiliza
WIN/LOSS hipotéticos como operaciones ejecutadas.
"""
import csv
import re
from collections import Counter, defaultdict


_VETOS = re.compile(r"\b(D7\.\d+[A-Z]?)\s*:", re.IGNORECASE)
_FAVORABLE = {"OPERAR_SOMBRA", "OPERAR_CON_PROTOCOLO_SOMBRA"}
_GENERIC = "V3_SOMBRA_FAVORABLE_SIN_AUTORIDAD_GENERICA"


def _texto(fila, *claves):
    for clave in claves:
        valor = str(fila.get(clave, "") or "").strip()
        if valor:
            return valor
    return ""


def clasificar_causa_cancelacion(fila):
    """Una causa principal auditable o SIN_CAUSA_DEMOSTRADA.

    El nivel de riesgo es telemetría, NO una prueba de veto.
    El resultado hipotético tampoco atribuye causalidad.
    """
    if not isinstance(fila, dict):
        return "FILA_INVALIDA"
    estado = _texto(fila, "estado_operacion").upper()
    decision = _texto(fila, "cerebro_unico_decision").upper()
    if not (estado.startswith("CANCELADA_") or decision == "NO_OPERAR"):
        return "NO_CANCELADA"
    motivo = _texto(fila, "fase4_motivo", "cerebro_unico_motivos")
    sombra = _texto(fila, "decision_sombra_origen", "decision_estadistica_sombra").upper()
    if _GENERIC in motivo:
        return "AUTORIDAD_GENERICA_DESHABILITADA"
    vetos = sorted(set(_VETOS.findall(motivo)), key=lambda x: (int(x.split(".")[1].rstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ")), x))
    if vetos:
        return "VETO_EXPRESO_" + "+".join(vetos)
    if sombra == "SIN_DATOS_ESTADISTICOS":
        return "FUENTE_ESTADISTICA_INSUFICIENTE"
    if sombra.startswith("NO_OPERAR_SOMBRA_MUESTRA"):
        return "MUESTRA_ESTADISTICA_INSUFICIENTE"
    if sombra == "NO_OPERAR_SOMBRA":
        return "PROBABILIDAD_NO_AUTORIZADA"
    if sombra in _FAVORABLE:
        return "SOMBRA_FAVORABLE_SIN_MOTIVO_ESPECIFICO"
    return "SIN_CAUSA_DEMOSTRADA"


def resumir_causas_cancelacion(filas):
    resumen = defaultdict(lambda: Counter())
    for fila in filas:
        causa = clasificar_causa_cancelacion(fila)
        resumen[causa]["n"] += 1
        if causa in {"NO_CANCELADA", "FILA_INVALIDA"}:
            continue
        hipotetico = _texto(fila, "resultado_hipotetico").upper()
        if hipotetico in {"WIN", "LOSS"}:
            resumen[causa]["hipotetico_" + hipotetico] += 1
        else:
            resumen[causa]["sin_resultado_hipotetico"] += 1
    return {causa: dict(conteos) for causa, conteos in sorted(resumen.items())}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Auditoría de cancelaciones; lectura solamente")
    parser.add_argument("csv")
    args = parser.parse_args()
    with open(args.csv, encoding="utf-8-sig", newline="") as archivo:
        for causa, conteos in resumir_causas_cancelacion(csv.DictReader(archivo)).items():
            print(causa, conteos)


if __name__ == "__main__":
    main()
