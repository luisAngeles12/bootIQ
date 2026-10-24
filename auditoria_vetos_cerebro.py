"""Diagnóstico offline de vetos D7 con separación temporal.

Los resultados de señales canceladas son hipotéticos: esta herramienta no
autoriza entradas, no aprende automáticamente y no modifica el bot.
"""

import csv
import re
from collections import defaultdict
from datetime import datetime, timezone


PATRON_REGLA = re.compile(r"\b(D7\.\d+):")
SOMBRA_AUTORIZADA = {"OPERAR_SOMBRA", "OPERAR_CON_PROTOCOLO_SOMBRA"}


def auditar_vetos_temporales(filas, minimo=20):
    """Cuenta resultados hipotéticos por veto y día sin mezclar operaciones.

    La fecha es un timestamp Unix en segundos. Un registro con múltiples
    reglas se contabiliza en la combinación completa, no se duplica.
    """
    grupos = defaultdict(lambda: {"wins": 0, "losses": 0, "dias": defaultdict(lambda: {"wins": 0, "losses": 0})})
    excluidos = defaultdict(int)
    for fila in filas:
        if not isinstance(fila, dict):
            excluidos["registro_invalido"] += 1
            continue
        if str(fila.get("estado_operacion") or "").strip().upper().startswith("OPERADA"):
            excluidos["operada_no_hipotetica"] += 1
            continue
        if str(fila.get("decision_estadistica_sombra") or "").strip().upper() not in SOMBRA_AUTORIZADA:
            excluidos["sombra_no_autorizada"] += 1
            continue
        resultado = str(fila.get("resultado_hipotetico") or "").strip().upper()
        if resultado not in {"WIN", "LOSS"}:
            excluidos["sin_resultado_hipotetico"] += 1
            continue
        try:
            dia = datetime.fromtimestamp(int(fila["fecha"]), tz=timezone.utc).date().isoformat()
        except (KeyError, TypeError, ValueError, OverflowError, OSError):
            excluidos["fecha_invalida"] += 1
            continue
        reglas = tuple(sorted(set(PATRON_REGLA.findall(str(fila.get("cerebro_unico_motivos") or "")))))
        clave = "+".join(reglas) if reglas else "SIN_REGLA_D7_IDENTIFICADA"
        campo = "wins" if resultado == "WIN" else "losses"
        grupos[clave][campo] += 1
        grupos[clave]["dias"][dia][campo] += 1

    reporte = []
    for regla, datos in grupos.items():
        n = datos["wins"] + datos["losses"]
        if n < minimo:
            continue
        dias = []
        for dia, conteos in sorted(datos["dias"].items()):
            nd = conteos["wins"] + conteos["losses"]
            dias.append({"dia_utc": dia, "n": nd, "wins": conteos["wins"],
                         "losses": conteos["losses"], "wr_hipotetico": round(100 * conteos["wins"] / nd, 2)})
        reporte.append({"regla": regla, "n": n, "wins": datos["wins"],
                        "losses": datos["losses"], "wr_hipotetico": round(100 * datos["wins"] / n, 2),
                        "dias": dias, "naturaleza": "SOLO_HIPOTETICO_NO_OPERADO"})
    return sorted(reporte, key=lambda r: (-r["n"], r["regla"])), dict(excluidos)


def imprimir_vetos_temporales(ruta="auditoria_xpd_sep2026_autoridad.csv", minimo=20):
    with open(ruta, encoding="utf-8-sig", newline="") as archivo:
        filas = list(csv.DictReader(archivo))
    reporte, excluidos = auditar_vetos_temporales(filas, minimo=minimo)
    print("===== VETOS D7 POR DIA (SOLO HIPOTETICOS) =====")
    print("Exclusiones:", excluidos)
    for registro in reporte:
        print(registro["regla"], "n", registro["n"], "WR hipotetico", registro["wr_hipotetico"])
        for dia in registro["dias"]:
            print("  ", dia["dia_utc"], "n", dia["n"], "WR", dia["wr_hipotetico"])


if __name__ == "__main__":
    imprimir_vetos_temporales()
