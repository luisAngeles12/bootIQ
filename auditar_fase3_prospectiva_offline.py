"""Runner prospectivo F3.2, exclusivamente offline y sin autorización.

Reutiliza hipótesis A/B congeladas. Valida nombres, fechas y separación
temporal de los nuevos bloques antes de llamar al evaluador estadístico.
No importa config, estrategia, credenciales ni código del broker.
"""

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from auditoria_economia_fase32 import evaluar_rentabilidad
from auditoria_calidad_frecuencia_cerebro import resumir_frecuencia_cerebro
from auditoria_hipotesis_fase32 import (
    CORTE_PROSPECTIVO_UTC,
    _timestamp_senal,
    resumir_hipotesis_ventanas,
)


def evaluar_ventanas_prospectivas(ventanas, prospectivas, payout_neto=None):
    """ventanas: (nombre, iterable de filas). Nunca activa operaciones."""
    bloques = [(str(nombre), list(filas)) for nombre, filas in ventanas]
    nombres = [nombre for nombre, _ in bloques]
    declaradas = set(prospectivas)

    if not bloques or not declaradas:
        raise ValueError("Se requieren ventanas y nombres prospectivos explícitos")
    if len(nombres) != len(set(nombres)) or any(not n.strip() for n in nombres):
        raise ValueError("Nombres de ventanas repetidos o vacíos")
    if not declaradas.issubset(set(nombres)):
        raise ValueError("Ventana prospectiva sin archivo correspondiente")

    periodos = []
    dias_asignados = {}
    for nombre, filas in bloques:
        if nombre not in declaradas:
            continue
        if not filas:
            raise ValueError("Ventana prospectiva vacía: " + nombre)
        marcas = [_timestamp_senal(f) if isinstance(f, dict) else None for f in filas]
        if any(m is None for m in marcas):
            raise ValueError("Fecha ausente/inválida en ventana prospectiva: " + nombre)
        if min(marcas) < CORTE_PROSPECTIVO_UTC:
            raise ValueError("Datos anteriores al corte prospectivo: " + nombre)
        periodos.append((min(marcas), max(marcas), nombre))

    periodos.sort()
    for anterior, siguiente in zip(periodos, periodos[1:]):
        if siguiente[0] <= anterior[1]:
            raise ValueError(
                "Ventanas prospectivas solapadas: " + anterior[2] + " / " + siguiente[2]
            )

    # Comprobar primero el solapamiento temporal exacto; después exigir
    # días UTC independientes incluso cuando los intervalos no se cruzan.
    for nombre, filas in bloques:
        if nombre not in declaradas:
            continue
        for fila in filas:
            marca = _timestamp_senal(fila)
            dia = datetime.fromtimestamp(marca, timezone.utc).date().isoformat()
            if dia in dias_asignados and dias_asignados[dia] != nombre:
                raise ValueError(
                    "Ventanas prospectivas comparten día UTC: "
                    + dias_asignados[dia] + " / " + nombre + " (" + dia + ")"
                )
            dias_asignados[dia] = nombre

    hipotesis = resumir_hipotesis_ventanas(
        bloques, ventanas_prospectivas=declaradas
    )
    filas_futuras = [
        fila for nombre, filas in bloques if nombre in declaradas for fila in filas
    ]
    economia = evaluar_rentabilidad(filas_futuras, payout_neto=payout_neto)
    frecuencia = resumir_frecuencia_cerebro(filas_futuras)
    return {
        "corte_prospectivo_utc": CORTE_PROSPECTIVO_UTC,
        "ventanas_declaradas": sorted(declaradas),
        "periodos_prospectivos": [
            {"nombre": nombre, "inicio": inicio, "fin": fin}
            for inicio, fin, nombre in periodos
        ],
        "hipotesis": hipotesis,
        "economia_observada": economia,
        "frecuencia_backtest_por_dia": frecuencia,
        "nota": "Frecuencia retrospectiva y PNL solo cuando hay cierre monetario explícito",
        "autoriza_operaciones": False,
    }


def evaluar_archivos(archivos, prospectivas, payout_neto=None):
    bloques = []
    for nombre, ruta in archivos:
        with Path(ruta).open(newline="", encoding="utf-8-sig") as stream:
            lector = csv.DictReader(stream)
            if not lector.fieldnames or not {
                "resultado_hipotetico", "activo", "patron",
                "direccion", "pa_fuerza",
            }.issubset(set(lector.fieldnames)):
                raise ValueError("CSV sin columnas esenciales: " + str(ruta))
            if not ({"fecha_senal", "fecha"} & set(lector.fieldnames)):
                raise ValueError("CSV sin fecha de señal: " + str(ruta))
            bloques.append((nombre, list(lector)))
    return evaluar_ventanas_prospectivas(bloques, prospectivas, payout_neto=payout_neto)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ventana", action="append", nargs=2, required=True,
        metavar=("NOMBRE", "CSV"),
    )
    parser.add_argument(
        "--prospectiva", action="append", required=True, metavar="NOMBRE",
    )
    parser.add_argument(
        "--payout-neto", type=float, default=None,
        help="Ratio neto real por victoria, si se conoce; no infiere PNL",
    )
    args = parser.parse_args()
    print(json.dumps(
        evaluar_archivos(args.ventana, args.prospectiva, payout_neto=args.payout_neto),
        ensure_ascii=False, indent=2, sort_keys=True,
    ))
