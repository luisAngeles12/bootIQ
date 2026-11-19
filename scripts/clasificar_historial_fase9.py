"""R9-20: triage de filas históricas BootIQ, solo lectura, sin atribuir modos.

Categorías excluyentes por fila; NO se generan memoria ni labels de training.
No se reporta winrate para registros de cuenta desconocida, REAL o incompletos.
"""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from scripts.auditar_historial_fase9 import (
    _txt, _cierre_explicito, _fecha_iso, _resultado_monetario,
)
from scripts.auditar_particion_temporal_fase9 import auditar_particion


def _identidad(row, frecuencia):
    oid = str(row.get("order_id") or "").strip()
    return oid and frecuencia.get(oid, 0) == 1


def clasificar_historial(ruta):
    ruta = Path(ruta)
    with ruta.open(encoding="utf-8-sig", newline="") as archivo:
        lector = csv.DictReader(archivo)
        columnas = lector.fieldnames or []
        if len(columnas) != len(set(columnas)):
            return {"estado": "NO_APTO", "causa": "COLUMNAS_DUPLICADAS",
                    "memoria_generada": False, "habilita_trading": False}
        rows = list(lector)
    requeridas = {"order_id", "modo_cuenta_configurado", "estado",
                  "resultado", "fecha"}
    if not requeridas.issubset(set(columnas)) or any(None in row for row in rows):
        return {"estado": "NO_APTO", "causa": "ESQUEMA_INCOMPLETO_O_MALFORMADO",
                "memoria_generada": False, "habilita_trading": False}
    frecuencia = Counter(
        str(row.get("order_id") or "").strip() for row in rows
        if str(row.get("order_id") or "").strip()
    )
    grupos = Counter()
    razones = Counter()
    por_modo = Counter()
    for row in rows:
        modo = _txt(row.get("modo_cuenta_configurado"))
        por_modo[modo or "SIN_MODO"] += 1
        if not modo:
            grupo = "CUENTA_DESCONOCIDA"
            causa = "FALTA_MODO_EXPLICITO"
        elif modo != "PRACTICE":
            grupo = "NO_PRACTICE"
            causa = "MODO_NO_PRACTICE"
        elif not _identidad(row, frecuencia):
            grupo = "PRACTICE_NO_APTO"
            causa = "ORDER_ID_AUSENTE_O_REPETIDO"
        elif not _cierre_explicito(_txt(row.get("estado"))):
            grupo = "PRACTICE_NO_APTO"
            causa = "SIN_CIERRE_EXPLICITO"
        elif _resultado_monetario(row.get("resultado")) not in ("GANANCIA", "PERDIDA"):
            grupo = "PRACTICE_NO_APTO"
            causa = "PNL_NO_SIGNIFICATIVO_O_INVALIDO"
        else:
            marca = str(row.get("fecha_apertura_registro_local_utc") or "").strip()
            iso = _fecha_iso(marca if marca else row.get("fecha"))
            if iso is None or not (
                iso.endswith("Z") or "+" in iso[10:] or "-" in iso[10:]
            ):
                grupo = "PRACTICE_NO_APTO"
                causa = "APERTURA_SIN_ZONA_CONFIRMADA"
            else:
                cierre = _fecha_iso(row.get("fecha_conciliacion_local_utc"))
                if cierre is None or not (
                    cierre.endswith("Z") or "+" in cierre[10:] or "-" in cierre[10:]
                ):
                    grupo = "PRACTICE_SOLO_DESCRIPTIVO"
                    causa = "FALTA_CONCILIACION_UTC"
                else:
                    from datetime import datetime, timezone
                    apertura = datetime.fromisoformat(iso).astimezone(timezone.utc)
                    registrado = datetime.fromisoformat(cierre).astimezone(timezone.utc)
                    if registrado < apertura:
                        grupo = "PRACTICE_NO_APTO"
                        causa = "CONCILIACION_ANTERIOR_APERTURA"
                    else:
                        grupo = "PRACTICE_CANDIDATA_NO_CERTIFICADA"
                        causa = "REQUIERE_COTEJO_BROKER"
        grupos[grupo] += 1
        razones[causa] += 1

    total = len(rows)
    return {
        "estado": "DIAGNOSTICO_NO_CERTIFICADO",
        "filas": total,
        "grupos_excluyentes": dict(sorted(grupos.items())),
        "razones_excluyentes": dict(sorted(razones.items())),
        "modos_declarados": dict(sorted(por_modo.items())),
        "integridad_conteo": sum(grupos.values()) == total,
        "memoria_generada": False,
        "habilita_trading": False,
        "nota": (
            "Candidata no es orden confirmada por IQ ni apta para entrenar. "
            "Sin modo o fechas originales, no se inventa procedencia."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("historial", nargs="?", default="historial_bot.csv")
    args = parser.parse_args()
    print(json.dumps(clasificar_historial(args.historial),
                     indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
