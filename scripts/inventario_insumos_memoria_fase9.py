"""Inventario R9 de archivos locales de aprendizaje, sin modificar datos.

Se ejecuta desde la raiz del repositorio. No importa bot.py ni accede a IQ.
No lee credenciales ni imprime filas de operaciones; solo esquema y tamaño.
"""
import csv
import json
import os
from fnmatch import fnmatch
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
    # Podar directorios antes del recorrido: evita caminar el venv.
    for carpeta, subdirectorios, archivos in os.walk(raiz):
        subdirectorios[:] = sorted(
            d for d in subdirectorios if d not in OMITIR
        )
        for nombre in sorted(archivos):
            if len(resultado) >= MAX_ARCHIVOS:
                break
            if not any(fnmatch(nombre, patron) for patron in PATRONES):
                continue
            ruta = Path(carpeta) / nombre
            if not ruta.is_file():
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
            except (OSError, UnicodeError, csv.Error):
                detalle["esquema_error"] = "LECTURA_CSV_FALLIDA"
            resultado.append(detalle)
        if len(resultado) >= MAX_ARCHIVOS:
            break
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
