"""Diagnóstico de solo lectura del bloque PRACTICE y memoria V3.

No importa bot.py ni conecta a IQ Option. No escribe archivos.
Uso: python scripts/diagnostico_fuentes_fase9.py RUTA_REPORTE.json
"""
import argparse
import csv
import json
import os
from collections import Counter
from pathlib import Path


CLAVES_REGISTROS = (
    "operaciones", "trades", "ordenes", "resultados", "filas", "rows",
    "detalle_operaciones", "operaciones_cerradas",
)
CLAVES_AUTORIDAD = (
    "origen_autoridad", "autoridad", "fuente_autorizacion",
    "motivo_autorizacion", "origen_decision",
)
CLAVES_RESULTADO = ("resultado", "result", "estado_resultado")
CLAVES_NETO = ("resultado_neto", "neto", "pnl", "pnl_realized", "ganancia")
CLAVES_ID = ("order_id", "id_orden", "id_operacion")


def _registros_de_reporte(documento):
    """Localiza una colección de órdenes sin fabricar datos faltantes."""
    cola = [("raiz", documento)]
    while cola:
        ruta, valor = cola.pop(0)
        if isinstance(valor, list):
            if valor and all(isinstance(v, dict) for v in valor):
                campos = set().union(*(v.keys() for v in valor))
                if campos.intersection(CLAVES_ID):
                    return ruta, valor
            for i, item in enumerate(valor[:20]):
                if isinstance(item, (dict, list)):
                    cola.append((f"{ruta}[{i}]", item))
        elif isinstance(valor, dict):
            for clave, item in valor.items():
                if isinstance(item, (dict, list)):
                    cola.append((f"{ruta}.{clave}", item))
    return None, None


def analizar_reporte(documento):
    ruta, registros = _registros_de_reporte(documento)
    resultado = {
        "tipo_raiz": type(documento).__name__,
        "claves_raiz": sorted(documento) if isinstance(documento, dict) else [],
        "ruta_registros": ruta,
        "cantidad_registros": len(registros) if registros is not None else None,
        "campos_registros": sorted(set().union(*(r.keys() for r in registros)))
        if registros else [],
    }
    if registros is None:
        resultado["advertencia"] = (
            "No se encontró lista identificada por order_id; "
            "no se infieren órdenes ni autoridades."
        )
        return resultado

    def buscar(fila, opciones):
        for clave in opciones:
            if clave in fila and fila[clave] not in (None, ""):
                return fila[clave]
        return None

    total = len(registros)
    origenes = Counter()
    resultados = Counter()
    faltan_autoridad = faltan_resultado = 0
    for fila in registros:
        fuente = buscar(fila, CLAVES_AUTORIDAD)
        estado = buscar(fila, CLAVES_RESULTADO)
        if fuente is None:
            faltan_autoridad += 1
        else:
            origenes[str(fuente)] += 1
        if estado is None:
            faltan_resultado += 1
        else:
            resultados[str(estado).upper()] += 1
    resultado.update({
        "autoridades_presentes": dict(sorted(origenes.items())),
        "resultados_presentes": dict(sorted(resultados.items())),
        "sin_campo_autoridad": faltan_autoridad,
        "sin_campo_resultado": faltan_resultado,
        "sin_desglose_autoridad": faltan_autoridad == total,
    })
    return resultado


def analizar_memoria(ruta):
    salida = {"ruta": str(ruta), "existe": ruta.is_file()}
    if not ruta.is_file():
        return salida
    with ruta.open("r", newline="", encoding="utf-8-sig") as archivo:
        lector = csv.DictReader(archivo)
        campos = lector.fieldnames or []
        salida["columnas"] = campos
        filas = 0
        sin_clave = 0
        con_muestra_5 = 0
        con_muestra_12 = 0
        con_muestra_20 = 0
        errores_muestra = 0
        for fila in lector:
            filas += 1
            if not str(fila.get("clave") or "").strip():
                sin_clave += 1
            try:
                n = int(float(fila.get("total") or 0))
            except (TypeError, ValueError, OverflowError):
                errores_muestra += 1
                continue
            con_muestra_5 += n >= 5
            con_muestra_12 += n >= 12
            con_muestra_20 += n >= 20
        salida.update({
            "filas": filas,
            "sin_clave": sin_clave,
            "muestra_ge_5": con_muestra_5,
            "muestra_ge_12": con_muestra_12,
            "muestra_ge_20": con_muestra_20,
            "muestra_invalida": errores_muestra,
        })
    return salida


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reporte", type=Path)
    args = parser.parse_args()
    if not args.reporte.is_file():
        parser.error("El reporte indicado no existe")
    with args.reporte.open(encoding="utf-8-sig") as archivo:
        documento = json.load(archivo)
    memoria = Path(os.getenv(
        "BOOTIQ_RUTA_APRENDIZAJE",
        "aprendizaje_historico_bootiq_F4_CC2.csv",
    ))
    print("R9 DIAGNOSTICO REPORTE:")
    print(json.dumps(analizar_reporte(documento), ensure_ascii=False, indent=2))
    print("R9 DIAGNOSTICO MEMORIA:")
    print(json.dumps(analizar_memoria(memoria), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
