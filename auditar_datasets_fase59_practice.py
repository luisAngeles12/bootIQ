"""F5.9: inventario de velas locales, SOLO LECTURA y SIN BROKER."""
import argparse
import csv
import hashlib
import json
import math
import os
from decimal import Decimal, InvalidOperation
from pathlib import Path

COLUMNAS = {"from", "open", "close", "max", "min"}
MIN_VELAS_CARGA = 200
SEGUNDOS_VELA = 60  # config.py: CANDLE_TIME; no importar credenciales locales


def inspeccionar_archivo(ruta):
    huella = hashlib.sha256()
    huella_velas = hashlib.sha256()
    tiempos = []
    error = None
    identidad = None
    velas_completas = False
    try:
        with ruta.open("rb") as archivo:
            for bloque in iter(lambda: archivo.read(65536), b""):
                huella.update(bloque)
        with ruta.open(encoding="utf-8-sig", newline="") as archivo:
            lector = csv.DictReader(archivo)
            if not lector.fieldnames or not COLUMNAS.issubset(lector.fieldnames):
                raise ValueError("COLUMNAS_VELAS_INSUFICIENTES")
            velas_completas = True
            for fila in lector:
                if None in fila or any(fila[k] in (None, "") for k in COLUMNAS):
                    raise ValueError("FILA_INCOMPLETA")
                timestamp = float(fila["from"])
                if not math.isfinite(timestamp) or not timestamp.is_integer():
                    raise ValueError("TIMESTAMP_NO_FINITO_O_FRACCIONARIO")
                tiempos.append(int(timestamp))
                precios = {}
                for k in ("open", "close", "max", "min"):
                    valor = float(fila[k])
                    if not math.isfinite(valor):
                        raise ValueError("PRECIO_NO_FINITO")
                    precios[k] = valor
                if (precios["min"] > precios["max"]
                        or not precios["min"] <= precios["open"] <= precios["max"]
                        or not precios["min"] <= precios["close"] <= precios["max"]):
                    raise ValueError("OHLC_INCONSISTENTE")
                # Huella canonica: mismo contenido OHLC y activo, aunque
                # difieran orden de columnas, saltos de linea o formato decimal.
                activo = str(fila.get("activo") or "").strip().upper()
                tipo = str(fila.get("tipo") or "").strip().upper()
                if identidad is None:
                    identidad = (activo, tipo)
                elif identidad != (activo, tipo):
                    raise ValueError("IDENTIDAD_ACTIVO_VARIABLE")
                try:
                    valores = tuple(
                        str(Decimal(fila[k]).normalize())
                        for k in ("open", "close", "max", "min")
                    )
                except InvalidOperation as exc:
                    raise ValueError("PRECIO_DECIMAL_INVALIDO") from exc
                huella_velas.update(repr((int(timestamp), identidad, valores)).encode("utf-8"))
                huella_velas.update(b"\\n")
        if any(b <= a for a, b in zip(tiempos, tiempos[1:])):
            error = "ORDEN_O_TIMESTAMP_DUPLICADO"
    except (ValueError, KeyError, UnicodeError, OSError, csv.Error) as exc:
        error = type(exc).__name__ + ":" + str(exc)
    gaps = sum(b - a != SEGUNDOS_VELA for a, b in zip(tiempos, tiempos[1:]))
    return {
        "archivo": ruta.name,
        "velas": len(tiempos),
        "inicio_epoch": min(tiempos) if tiempos else None,
        "fin_epoch": max(tiempos) if tiempos else None,
        # Este conteo es diagnostico: el cargador oficial solo exige >=200
        # filas parseables; los errores se informan por separado.
        "supera_minimo_200": len(tiempos) >= MIN_VELAS_CARGA,
        "carga_minima_200": len(tiempos) >= MIN_VELAS_CARGA and error is None,
        "saltos_temporales": gaps,
        "continuidad_completa": bool(tiempos) and gaps == 0 and error is None,
        "error": error,
        "sha256": huella.hexdigest(),
        "sha256_velas": (huella_velas.hexdigest()
                          if velas_completas and tiempos and error is None else None),
    }


def inventariar(carpeta):
    ruta = Path(carpeta)
    if not ruta.is_dir():
        return {"estado": "SIN_DATOS_ACTUALES", "carpeta": str(ruta),
                "total_csv": 0, "archivos": [], "duplicados_identicos": [],
                "duplicados_velas": [],
                "cargables_minimo": 0, "superan_minimo_200": 0,
                "con_continuidad_completa": 0}
    # El backtest oficial lee solo .csv en el primer nivel, no recursivamente.
    archivos = [inspeccionar_archivo(p) for p in sorted(ruta.iterdir())
                if p.is_file() and p.name.endswith(".csv")]
    por_hash = {}
    por_velas = {}
    duplicados = []
    duplicados_velas = []
    for f in archivos:
        if f["sha256"] in por_hash:
            duplicados.append({"archivo": f["archivo"],
                               "identico_a": por_hash[f["sha256"]]})
        else:
            por_hash[f["sha256"]] = f["archivo"]
        huella_canonica = f["sha256_velas"]
        if huella_canonica is not None:
            if huella_canonica in por_velas:
                duplicados_velas.append({"archivo": f["archivo"],
                                         "identico_a": por_velas[huella_canonica]})
            else:
                por_velas[huella_canonica] = f["archivo"]
    return {
        "estado": "INVENTARIO_NO_VALIDACION_RENTABILIDAD",
        "carpeta": str(ruta),
        "total_csv": len(archivos),
        "superan_minimo_200": sum(f["supera_minimo_200"] for f in archivos),
        "cargables_minimo": sum(f["carga_minima_200"] for f in archivos),
        "con_continuidad_completa": sum(f["continuidad_completa"] for f in archivos),
        "duplicados_identicos": duplicados,
        "duplicados_velas": duplicados_velas,
        "archivos": archivos,
        "advertencia": "superan_minimo_200 solo cuenta filas examinadas, no garantiza "
                       "compatibilidad con el cargador oficial ni validez causal. "
                       "cargables_minimo incorpora controles extra del auditor. "
                       "duplicados_velas detecta series identicas, no solapamientos parciales. "
                       "No hay operaciones, fill ni PnL verificado.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default=os.getenv("BOOTIQ_DATASET_DIR", "data_backtest_actual"))
    args = parser.parse_args()
    print(json.dumps(inventariar(args.data_dir), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
