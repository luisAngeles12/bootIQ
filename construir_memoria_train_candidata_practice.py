"""Construccion OPCIONAL de memoria experimental, aislada del cerebro V3.

Solo crea un CSV candidato en experimentos_fase5/ si TRAIN y VALIDACION
son temporalmente disjuntos. No cambia bot.py, memoria productiva ni REAL.
"""
import argparse
import csv
import json
import os
import tempfile
from pathlib import Path

from verificar_particion_train_valid_practice import verificar_particion

NOMBRE_CANDIDATA = "memoria_train_candidata.csv"
SUBDIRECTORIO = "experimentos_fase5"


def construir_memoria_candidata(train, validacion, raiz="."):
    registros_train = list(train)
    registros_valid = list(validacion)
    precheck = verificar_particion(registros_train, registros_valid)
    if not precheck["apta_para_experimento_cronologico"]:
        raise ValueError(
            "PARTICION_CRONOLOGICA_NO_APTA: no se generara memoria"
        )
    if len(registros_train) < 20:
        raise ValueError("MUESTRA_TRAIN_INSUFICIENTE_MINIMO_20")
    # La memoria general del backtest usa exclusivamente la etiqueta
    # hipotetica; nunca sustituirla silenciosamente por el resultado
    # de una operacion ya filtrada.
    for registro in registros_train:
        if str(registro.get("resultado_hipotetico") or "").strip().upper() not in (
            "WIN", "LOSS"
        ):
            raise ValueError("TRAIN_SIN_ETIQUETA_HIPOTETICA_VALIDA")

    base = Path(raiz).resolve()
    carpeta = base / SUBDIRECTORIO
    destino = carpeta / NOMBRE_CANDIDATA

    memoria_productiva = Path(os.getenv(
        "BOOTIQ_RUTA_APRENDIZAJE",
        "aprendizaje_historico_bootiq_F4_CC2.csv",
    ))
    if not memoria_productiva.is_absolute():
        memoria_productiva = base / memoria_productiva
    if destino.resolve() == memoria_productiva.resolve():
        raise ValueError("RUTA_CANDIDATA_EQUIVALE_A_MEMORIA_PRODUCTIVA")
    # No permitir sustituir una candidata existente sin inspeccion.
    if destino.exists():
        raise FileExistsError("CANDIDATA_YA_EXISTE_NO_SOBRESCRIBIR")

    # Importar solo tras validar todos los registros: se evita el
    # costo del generador cuando el split debe rechazarse.
    from motor_aprendizaje_historico import generar_aprendizaje_desde_resultados

    carpeta.mkdir(parents=True, exist_ok=True)
    temporal = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=".train_candidato_", suffix=".csv",
            dir=str(carpeta), delete=False,
        ) as archivo:
            temporal = Path(archivo.name)
        filas_memoria = generar_aprendizaje_desde_resultados(
            registros_train, ruta=str(temporal), incluir_hipoteticos=True
        )
        if not filas_memoria:
            raise ValueError("GENERADOR_NO_PRODUJO_MEMORIA")
        # Sin comprobacion o reemplazo de la memoria del bot.
        if destino.exists():
            raise FileExistsError("CANDIDATA_YA_EXISTE_NO_SOBRESCRIBIR")
        os.link(str(temporal), str(destino))
    finally:
        if temporal is not None:
            temporal.unlink(missing_ok=True)

    return {
        "estado": "CANDIDATA_EXPERIMENTAL_CREADA",
        "ruta": str(destino),
        "registros_train": len(registros_train),
        "registros_validacion_reservados": len(registros_valid),
        "claves_generadas": len(filas_memoria),
        "verificacion_particion": precheck,
        "memoria_productiva_modificada": False,
        "operaciones_autorizadas": False,
        "requiere_validacion_independiente": True,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("train", help="CSV backtest TRAIN")
    parser.add_argument("validacion", help="CSV backtest VALIDACION")
    parser.add_argument("--raiz", default=".")
    args = parser.parse_args()
    with Path(args.train).open(encoding="utf-8-sig", newline="") as f:
        train = list(csv.DictReader(f))
    with Path(args.validacion).open(encoding="utf-8-sig", newline="") as f:
        validacion = list(csv.DictReader(f))
    reporte = construir_memoria_candidata(train, validacion, raiz=args.raiz)
    print(json.dumps(reporte, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
