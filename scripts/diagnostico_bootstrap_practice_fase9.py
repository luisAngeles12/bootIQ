"""R9-25.14: desgloses historicos PRACTICE, exclusivamente DESCRIPTIVOS.

No autentica origen IQ, no asume zona horaria, no hace TRAIN/OOS,
no modifica historial/estrategia/memoria ni identifica grupos como ganadores.
"""
import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from scripts.auditar_historial_fase9 import _cierre_explicito, _txt, _fecha_iso
from scripts.conciliar_exportacion_iq_fase9 import _monto

REQUERIDAS = {
    "order_id", "modo_cuenta_configurado", "estado", "resultado", "fecha",
    "familia_setup", "regimen_mercado", "direccion", "origen_autoridad",
}


def diagnosticar(ruta):
    base = {
        "estado": "NO_APTO",
        "solo_descriptivo_no_certificado": True,
        "procedencia_iq_verificada": False,
        "validacion_oos": False,
        "permite_reconfigurar_estrategia": False,
        "habilita_trading": False,
        "memoria_generada": False,
    }
    try:
        with Path(ruta).open(encoding="utf-8-sig", newline="") as archivo:
            lector = csv.DictReader(archivo)
            columnas = lector.fieldnames or []
            if len(columnas) != len(set(columnas)):
                return {**base, "causa": "COLUMNAS_DUPLICADAS"}
            if not REQUERIDAS.issubset(columnas):
                return {**base, "causa": "COLUMNAS_FALTANTES",
                        "columnas_faltantes": sorted(REQUERIDAS - set(columnas))}
            filas = list(lector)
    except (OSError, UnicodeError, csv.Error):
        return {**base, "causa": "ARCHIVO_ILEGIBLE"}
    if any(None in fila for fila in filas):
        return {**base, "causa": "CSV_MALFORMADO"}

    frecuencias = Counter(str(f.get("order_id") or "").strip() for f in filas)
    excluidas = Counter()
    grupos = {
        "dias": defaultdict(list),
        "familias": defaultdict(list),
        "regimen_y_direccion": defaultdict(list),
        "familia_regimen_direccion": defaultdict(list),
        "autoridades": defaultdict(list),
    }
    importes = []
    for f in filas:
        modo = _txt(f.get("modo_cuenta_configurado"))
        oid = str(f.get("order_id") or "").strip()
        if not modo:
            excluidas["CUENTA_DESCONOCIDA"] += 1
            continue
        if modo != "PRACTICE":
            excluidas["NO_PRACTICE"] += 1
            continue
        if not oid or frecuencias[oid] != 1:
            excluidas["PRACTICE_ID_AUSENTE_O_DUPLICADO"] += 1
            continue
        if not _cierre_explicito(_txt(f.get("estado"))):
            excluidas["PRACTICE_NO_CERRADA"] += 1
            continue
        pnl = _monto(f.get("resultado"))
        if pnl is None:
            excluidas["PRACTICE_PNL_INVALIDO"] += 1
            continue
        if pnl == 0:
            excluidas["PRACTICE_EMPATE"] += 1
            continue
        fecha = str(f.get("fecha") or "").strip()
        if _fecha_iso(fecha) is None:
            excluidas["PRACTICE_FECHA_INVALIDA"] += 1
            continue
        # Dia local declarado: no convertir ni imputar una zona.
        dia = fecha[:10]
        familia = _txt(f.get("familia_setup")) or "SIN_FAMILIA"
        regimen = _txt(f.get("regimen_mercado")) or "SIN_REGIMEN"
        direccion = _txt(f.get("direccion")) or "SIN_DIRECCION"
        autoridad = _txt(f.get("origen_autoridad")) or "SIN_AUTORIDAD"
        importes.append(pnl)
        for nombre, clave in (
            ("dias", dia),
            ("familias", familia),
            ("regimen_y_direccion", (regimen, direccion)),
            ("familia_regimen_direccion", (familia, regimen, direccion)),
            ("autoridades", autoridad),
        ):
            grupos[nombre][clave].append(pnl)

    def metricas(valores):
        ganadas = sum(v > 0 for v in valores)
        perdidas = sum(v < 0 for v in valores)
        neto = sum(valores)
        return {
            "n": len(valores), "wins": ganadas, "losses": perdidas,
            "winrate_pct": round(100 * ganadas / len(valores), 2) if valores else None,
            "neto": str(neto),
            "muestra_menor_20": len(valores) < 20,
        }

    tablas = {}
    for nombre, agrupacion in grupos.items():
        tablas[nombre] = [
            {"clave": list(clave) if isinstance(clave, tuple) else clave,
             **metricas(valores)}
            for clave, valores in sorted(agrupacion.items(),
                                        key=lambda par: str(par[0]))
        ]
    return {
        **base,
        "estado": "DESCRIPTIVO_NO_VERIFICADO_BROKER" if importes else "SIN_MUESTRA_PRACTICE_APTA",
        "filas_totales": len(filas),
        "filas_practice_descriptivas": len(importes),
        "filas_excluidas": sum(excluidas.values()),
        "motivos_exclusion": dict(sorted(excluidas.items())),
        "conteo_conservado": len(importes) + sum(excluidas.values()) == len(filas),
        "resumen": metricas(importes),
        "desgloses": tablas,
        "nota": (
            "Los dias son etiquetas del CSV sin zona confirmada. "
            "Los grupos fueron elegidos tras observar los resultados; "
            "ningun subgrupo demuestra ventaja OOS ni acredita broker."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("historial", nargs="?", default="historial_bot.csv")
    args = parser.parse_args()
    print(json.dumps(diagnosticar(args.historial), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
