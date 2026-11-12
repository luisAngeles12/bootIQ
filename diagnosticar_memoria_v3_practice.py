"""Diagnostico solo lectura de la memoria V3 oficial de BootIQ.

No fabrica, reemplaza, ni activa ninguna memoria; no toca el broker.
"""
import argparse
import csv
import json
import os
from pathlib import Path

RUTA_OFICIAL = "aprendizaje_historico_bootiq_F4_CC2.csv"


def diagnosticar_memoria(ruta=None):
    elegida = ruta if ruta is not None else os.getenv(
        "BOOTIQ_RUTA_APRENDIZAJE", RUTA_OFICIAL
    )
    destino = Path(elegida)
    reporte = {
        "modo": "DIAGNOSTICO_MEMORIA_SOLO_LECTURA",
        "ruta_configurada": str(destino),
        "ruta_absoluta": str(destino.resolve()),
        "variable_entorno_personalizada": bool(os.getenv("BOOTIQ_RUTA_APRENDIZAJE")),
        "existe": destino.is_file(),
        "filas_csv": 0,
        "claves_no_vacias": 0,
        "claves_distintas": 0,
        "estado": None,
        "operaciones_autorizadas": False,
        "memoria_modificada": False,
    }
    if not destino.is_file():
        reporte["estado"] = "ARCHIVO_OFICIAL_AUSENTE"
        return reporte
    try:
        with destino.open("r", encoding="utf-8-sig", newline="") as archivo:
            lector = csv.DictReader(archivo)
            if not lector.fieldnames or "clave" not in lector.fieldnames:
                reporte["estado"] = "CABECERA_INCOMPATIBLE_SIN_CLAVE"
                return reporte
            claves = set()
            for fila in lector:
                reporte["filas_csv"] += 1
                clave = str(fila.get("clave") or "").strip()
                if clave:
                    reporte["claves_no_vacias"] += 1
                    claves.add(clave)
            reporte["claves_distintas"] = len(claves)
            reporte["estado"] = (
                "MEMORIA_CON_CLAVES"
                if claves else "MEMORIA_SIN_CLAVES_USABLES"
            )
    except (OSError, UnicodeError, csv.Error) as e:
        reporte["estado"] = "ERROR_DE_LECTURA"
        reporte["tipo_error"] = type(e).__name__
    return reporte


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ruta", default=None)
    args = parser.parse_args()
    print(json.dumps(diagnosticar_memoria(args.ruta), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
