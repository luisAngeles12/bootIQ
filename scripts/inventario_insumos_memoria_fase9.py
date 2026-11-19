"""Inventario R9 de archivos locales de aprendizaje, sin modificar datos.

Se ejecuta desde la raiz del repositorio. No importa bot.py ni accede a IQ.
No lee credenciales ni imprime filas de operaciones; solo esquema y tamaño.
"""
import csv
import json
import os
from pathlib import Path

PATRONES = (
    "*aprendizaje*.csv",
    "*historial*.csv",
    "*resultado*.csv",
    "*ledger*.csv",
)
OMITIR = {"venv", ".venv", ".git", "__pycache__", "node_modules", "site-packages"}
MAX_ARCHIVOS = 200


def inventariar_archivos(raiz):
    raiz = Path(raiz).resolve()
    vistos = set()
    resultado = []
    for patron in PATRONES:
        for ruta in raiz.rglob(patron):
            if len(resultado) >= MAX_ARCHIVOS:
                break
            if not ruta.is_file() or any(parte in OMITIR for parte in ruta.relative_to(raiz).parts):
                continue
            ruta_relativa = str(ruta.relative_to(raiz)).replace("\\", "/")
            if ruta_relativa in vistos:
                continue
            vistos.add(ruta_relativa)
            detalle = {
                "archivo": ruta_relativa,
                "bytes": ruta.stat().st_size,
            }
            try:
                with ruta.open(encoding="utf-8-sig", newline="") as archivo:
                    detalle["columnas"] = csv.DictReader(archivo).fieldnames or []
            except (OSError, UnicodeError, csv.Error) as exc:
                detalle["esquema_error"] = type(exc).__name__
            resultado.append(detalle)
    return sorted(resultado, key=lambda r: r["archivo"])


def diagnostico_insumos(raiz):
    configurada = os.getenv(
        "BOOTIQ_RUTA_APRENDIZAJE", "aprendizaje_historico_bootiq_F4_CC2.csv"
    )
    ruta = Path(configurada)
    if not ruta.is_absolute():
        ruta = Path(raiz) / ruta
    return {
        "memoria_configurada": configurada,
        "memoria_configurada_existe": ruta.is_file(),
        "inventario": inventariar_archivos(raiz),
        "nota": (
            "Los CSV de resultados o historial no se convierten en memoria "
            "ni acreditan WIN/LOSS ejecutados sin auditoria de procedencia."
        ),
    }


if __name__ == "__main__":
    print(json.dumps(diagnostico_insumos(Path.cwd()), indent=2, ensure_ascii=False))
