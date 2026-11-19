"""F11/F12: informe reproducible de ledger PRACTICE, SOLO LECTURA.

La consistencia observada no confirma procedencia del broker, fill ni OOS.
No importa el bot, credenciales ni ejecuta ordenes.
"""
import argparse
import csv
import json
from pathlib import Path

from analizar_robustez_fase11_practice import analizar
from diagnosticar_ledger_fases11_12_practice import diagnosticar
from validar_consistencia_fases_11_12_practice import evaluar


def informe(ruta):
    ruta = Path(ruta)
    evidencia = diagnosticar(ruta)
    base = {
        "tipo": "INFORME_INTEGRAL_F11_F12_PRACTICE",
        "origen": str(ruta),
        "preflight": evidencia,
        "consistencia": None,
        "robustez": None,
        "evaluacion_posible": False,
        "certificacion_fases_5_a_12": False,
        "conciliacion_broker_confirmada": False,
        "validacion_oos_confirmada": False,
        "autoriza_real": False,
    }
    if not evidencia["apto_para_evaluar"]:
        base["estado"] = "EVIDENCIA_INSUFICIENTE"
        return base
    try:
        with ruta.open(encoding="utf-8-sig", newline="") as f:
            filas = list(csv.DictReader(f))
        # No descartar pérdidas, empates ni filas defectuosas para
        # mejorar artificialmente la tasa.
        consistencia = evaluar(filas)
        robustez = analizar(filas)
    except (ValueError, OSError, csv.Error) as exc:
        base["estado"] = "EVIDENCIA_INVALIDA"
        base["error_validacion"] = str(exc)
        return base
    base["consistencia"] = consistencia
    base["robustez"] = robustez
    base["evaluacion_posible"] = True
    base["estado"] = (
        "OBJETIVO_OBSERVADO_SIN_CERTIFICACION"
        if consistencia["cumple_conjunto_y_familias"]
        else "OBJETIVO_NO_DEMOSTRADO"
    )
    base["limitacion"] = (
        "No se verifico fill, payout, procedencia real PRACTICE, "
        "independencia, fecha de cierre ante IQ, OOS ni multi-jornada. "
        "Ninguna coincidencia con 60% prueba tasa verdadera constante."
    )
    return base


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger_csv", type=Path)
    args = parser.parse_args()
    print(json.dumps(informe(args.ledger_csv), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
