"""Diagnostico OFFLINE y exclusivamente informativo de BootIQ sin operaciones.

No conecta con broker, no escribe memoria ni archivos, no coloca ordenes.
La memoria CC2 vacia no se reemplaza por resultados hipoteticos.
"""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from auditoria_candidatas_sombra_practice import _leer
from reporte_candidatas_sombra_practice import resumen_oportunidades_independientes
from trazabilidad_rondas_sombra import auditar_intentos


def diagnosticar(raiz=".", *, archivo_sombra="auditoria_candidatas_sombra_practice.csv",
                archivo_historial="historial_bot.csv",
                archivo_memoria="aprendizaje_historico_bootiq_F4_CC2.csv",
                archivo_ledger="trazabilidad_rondas_sombra.jsonl"):
    base = Path(raiz)
    memoria = base / archivo_memoria
    historial = base / archivo_historial
    sombra = base / archivo_sombra
    ledger = base / archivo_ledger

    def contar_csv(ruta):
        if not ruta.is_file():
            return None
        with ruta.open("r", newline="", encoding="utf-8-sig") as archivo:
            return sum(1 for _ in csv.DictReader(archivo))

    n_memoria = contar_csv(memoria)
    n_historial = contar_csv(historial)
    filas = _leer(sombra)
    resultados = Counter(f.get("resultado_hipotetico") or "SIN_RESULTADO"
                         for f in filas)
    tiempos = Counter(f.get("calidad_tiempo") or "SIN_CALIDAD"
                      for f in filas)
    decisiones = Counter(f.get("decision") or "SIN_DECISION" for f in filas)
    ids = [f.get("id") or "" for f in filas]
    duplicados = len(ids) - len(set(ids))
    if ledger.is_file():
        try:
            auditoria = auditar_intentos(ledger)
            trazabilidad = {
                "intentos": auditoria["intentos"],
                "estados": auditoria["estados"],
                "candidatas_con_pertenencia": len(auditoria["ids_por_estado"]),
            }
        except (ValueError, KeyError, json.JSONDecodeError, OSError) as exc:
            trazabilidad = {"estado": "LEDGER_INVALIDO", "detalle": type(exc).__name__}
    else:
        trazabilidad = {"estado": "LEDGER_AUSENTE"}
    oportunidades = resumen_oportunidades_independientes(filas)
    estado_memoria = ("AUSENTE" if n_memoria is None else
                      "SIN_FILAS" if n_memoria == 0 else "PRESENTE_POR_AUDITAR")
    razones = []
    if n_historial is None or n_historial == 0:
        razones.append("SIN_OPERACIONES_HISTORICAS_REGISTRADAS")
    if n_memoria is None or n_memoria == 0:
        razones.append("SIN_MEMORIA_CC2")
    if not filas:
        razones.append("SIN_CANDIDATAS_SOMBRA")
    if duplicados:
        razones.append("IDS_SOMBRA_DUPLICADOS")
    return {
        "modo": "SOLO_PRUEBAS_OFFLINE",
        "broker_conectado": False,
        "operaciones_autorizadas": False,
        "modifica_memoria": False,
        "memoria_cc2": {"estado": estado_memoria, "filas": n_memoria},
        "historial_operaciones": {"filas": n_historial},
        "sombra": {
            "filas": len(filas),
            "ids_duplicados": duplicados,
            "resultados_hipoteticos": dict(sorted(resultados.items())),
            "calidades_tiempo": dict(sorted(tiempos.items())),
            "decisiones": dict(sorted(decisiones.items())),
            "oportunidades_independientes_proxy":
                oportunidades["oportunidades_independientes"],
            "resultado": oportunidades["resultado"],
        },
        "trazabilidad_rondas": trazabilidad,
        "razones_sin_autorizacion": razones,
        "diagnostico": (
            "La memoria de ejecuciones esta ausente o vacia; "
            "la observacion sombra es una prueba hipotetica, no evidencia de fills."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description="Auditoria sin conexion ni operaciones")
    parser.add_argument("--raiz", default=".")
    args = parser.parse_args()
    print(json.dumps(diagnosticar(args.raiz), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
