"""Preflight observacional de memoria V3 para PRACTICE.

No importa backtest_bot_real ni ejecuta entrenamiento, escribe memoria,
cambia el modo experimental ni establece permisos operativos.
"""
import argparse
import ast
import csv
import json
import os
from pathlib import Path


def _asignaciones_constantes(path):
    arbol = ast.parse(Path(path).read_text(encoding="utf-8"))
    valores = {}
    for nodo in arbol.body:
        if not isinstance(nodo, (ast.Assign, ast.AnnAssign)):
            continue
        destinos = nodo.targets if isinstance(nodo, ast.Assign) else [nodo.target]
        if len(destinos) != 1 or not isinstance(destinos[0], ast.Name):
            continue
        try:
            valores[destinos[0].id] = ast.literal_eval(nodo.value)
        except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
            pass
    return valores


def auditar_memoria(
    raiz=".", ruta_memoria=None, ruta_backtest="backtest_bot_real.py",
):
    base = Path(raiz)
    ruta = Path(ruta_memoria or os.getenv(
        "BOOTIQ_RUTA_APRENDIZAJE", "aprendizaje_historico_bootiq_F4_CC2.csv"
    ))
    if not ruta.is_absolute():
        ruta = base / ruta
    backtest = base / ruta_backtest
    controles = _asignaciones_constantes(backtest) if backtest.is_file() else {}
    modo = controles.get("MODO_EXPERIMENTO")
    general = controles.get("ACTUALIZAR_APRENDIZAJE")
    protocolo = controles.get("ACTUALIZAR_APRENDIZAJE_PROTOCOLO")

    estado = "MEMORIA_AUSENTE"
    totales = {"filas": 0, "claves_validas": 0, "muestras_ge_5": 0,
               "muestras_ge_12": 0, "filas_protocolo": 0}
    problemas = []
    if ruta.is_file():
        try:
            with ruta.open(encoding="utf-8-sig", newline="") as archivo:
                lector = csv.DictReader(archivo)
                columnas = set(lector.fieldnames or [])
                if not {"nivel", "clave", "total"}.issubset(columnas):
                    estado = "ESQUEMA_NO_COMPATIBLE"
                    problemas.append("FALTAN_COLUMNAS_NIVEL_CLAVE_TOTAL")
                else:
                    for fila in lector:
                        totales["filas"] += 1
                        clave = str(fila.get("clave") or "").strip()
                        nivel = str(fila.get("nivel") or "").strip()
                        if not clave:
                            problemas.append("CLAVE_VACIA")
                            continue
                        totales["claves_validas"] += 1
                        if nivel.startswith("PROTOCOLO") or clave.startswith("PROTOCOLO"):
                            totales["filas_protocolo"] += 1
                        try:
                            n = int(fila.get("total") or "0")
                        except ValueError:
                            problemas.append("TOTAL_NO_ENTERO")
                            continue
                        if n < 0:
                            problemas.append("TOTAL_NEGATIVO")
                            continue
                        if n >= 5:
                            totales["muestras_ge_5"] += 1
                        if n >= 12:
                            totales["muestras_ge_12"] += 1
                    if estado != "ESQUEMA_NO_COMPATIBLE":
                        estado = (
                            "MEMORIA_SIN_FUENTES_CON_MUESTRA"
                            if totales["muestras_ge_5"] == 0 else
                            "MEMORIA_CON_FILAS_POTENCIALMENTE_UTILIZABLES"
                        )
        except (OSError, UnicodeError, csv.Error) as exc:
            estado = "MEMORIA_ILEGIBLE"
            problemas.append(type(exc).__name__)

    if not backtest.is_file():
        problemas.append("BACKTEST_NO_ENCONTRADO")
    # No basta la presencia de memoria para afirmar que una senal concreta
    # encuentra una clave jerarquica compatible ni que su origen es seguro.
    return {
        "modo": "AUDITORIA_MEMORIA_SOLO_LECTURA",
        "ruta_memoria": str(ruta),
        "estado_memoria": estado,
        "conteos": totales,
        "config_backtest_estatica": {
            "modo_experimento": modo,
            "actualizar_aprendizaje_general": general,
            "actualizar_aprendizaje_protocolo": protocolo,
        },
        "actualizacion_estatica_desactivada": general is False and protocolo is False,
        "problemas": sorted(set(problemas)),
        "compatibilidad_por_senal_verificada": False,
        "memoria_generada": False,
        "entrenamiento_ejecutado": False,
        "cambios_operativos_autorizados": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raiz", default=".")
    parser.add_argument("--memoria", default=None)
    args = parser.parse_args()
    print(json.dumps(
        auditar_memoria(raiz=args.raiz, ruta_memoria=args.memoria),
        indent=2, ensure_ascii=False,
    ))


if __name__ == "__main__":
    main()
