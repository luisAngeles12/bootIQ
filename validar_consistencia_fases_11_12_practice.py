"""Evaluador de consistencia PRACTICE: solo operaciones cerradas. No usa broker."""
import argparse
import csv
import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

RESULTADOS = {"WIN", "LOSS", "EMPATE"}
COLUMNAS = {"order_id", "fecha_cierre", "resultado", "neto", "familia", "tipo_cuenta"}

def _tiempo(s):
    try:
        d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        if d.tzinfo is None:
            raise ValueError("sin zona")
        return d.astimezone(timezone.utc)
    except (ValueError, TypeError) as e:
        raise ValueError("FECHA_CIERRE_INVALIDA") from e

def evaluar(filas, min_winrate=60, tamano=20):
    if tamano != 20 or min_winrate != 60:
        raise ValueError("CRITERIOS_PROYECTO_FIJOS")
    ordenes = []
    ids = set()
    for fila in filas:
        if not isinstance(fila, dict) or not COLUMNAS.issubset(fila):
            raise ValueError("COLUMNAS_INSUFICIENTES")
        if any(fila[c] in (None, "") for c in COLUMNAS):
            raise ValueError("FILA_INCOMPLETA")
        identificador = str(fila["order_id"]).strip()
        if not identificador or identificador in ids:
            raise ValueError("ORDEN_DUPLICADA_O_VACIA")
        ids.add(identificador)
        if str(fila["tipo_cuenta"]).strip().upper() != "PRACTICE":
            raise ValueError("SOLO_PRACTICE")
        resultado = str(fila["resultado"]).strip().upper()
        if resultado not in RESULTADOS:
            raise ValueError("RESULTADO_NO_CERRADO")
        try:
            neto = Decimal(str(fila["neto"]).strip())
        except (InvalidOperation, ValueError, TypeError) as e:
            raise ValueError("NETO_INVALIDO") from e
        if not neto.is_finite():
            raise ValueError("NETO_INVALIDO")
        # El ledger liquida importes monetarios a centavos. Rechazar
        # subcentavos evita aprobar una ventana cuyo neto visible es 0.00.
        if neto * 100 != (neto * 100).to_integral_value():
            raise ValueError("NETO_FRACCION_DE_CENTAVO")
        if ((resultado == "WIN" and neto <= 0)
                or (resultado == "LOSS" and neto >= 0)
                or (resultado == "EMPATE" and neto != 0)):
            raise ValueError("RESULTADO_NETO_CONTRADICTORIO")
        familia = str(fila["familia"]).strip()
        if not familia:
            raise ValueError("FAMILIA_VACIA")
        ordenes.append({"id": identificador, "fecha": _tiempo(fila["fecha_cierre"]),
                        "resultado": resultado, "neto": neto,
                        "familia": familia})
    ordenes.sort(key=lambda r: (r["fecha"], r["id"]))

    def medida(bloque):
        w = sum(o["resultado"] == "WIN" for o in bloque)
        l = sum(o["resultado"] == "LOSS" for o in bloque)
        n = sum((o["neto"] for o in bloque), Decimal("0"))
        return {"operaciones": len(bloque), "wins": w, "losses": l,
                "empates": len(bloque) - w - l,
                "acierto_pct": round(100 * w / len(bloque), 2) if bloque else None,
                "neto": float(n),
                "cumple": bool(len(bloque) == tamano and w >= 12 and n >= Decimal("0.01"))}

    ventanas = [medida(ordenes[i:i+tamano])
                for i in range(max(0, len(ordenes)-tamano+1))]
    bloques = [medida(ordenes[i:i+tamano]) for i in range(0, len(ordenes), tamano)
               if len(ordenes[i:i+tamano]) == tamano]
    familias = {}
    for nombre in sorted({o["familia"] for o in ordenes}):
        grupo = [o for o in ordenes if o["familia"] == nombre]
        fventanas = [medida(grupo[i:i+tamano])
                    for i in range(max(0, len(grupo)-tamano+1))]
        familias[nombre] = {
            "operaciones": len(grupo), "total": medida(grupo),
            "ventanas_20": len(fventanas),
            "todas_ventanas_cumplen": bool(fventanas) and all(v["cumple"] for v in fventanas),
        }
    cumple = bool(ventanas) and all(v["cumple"] for v in ventanas)
    familias_evaluables = [f for f in familias.values() if f["operaciones"] >= tamano]
    cumplen_familias = bool(familias_evaluables) and all(
        f["todas_ventanas_cumplen"] for f in familias_evaluables
    )
    return {
        "modo": "AUDITORIA_PRACTICE_SIN_BROKER",
        "operaciones": len(ordenes), "total": medida(ordenes),
        "ventanas_moviles_20": len(ventanas),
        "ventanas_bajo_objetivo": sum(not v["cumple"] for v in ventanas),
        "bloques_no_solapados_20": len(bloques),
        "bloques_bajo_objetivo": sum(not b["cumple"] for b in bloques),
        "familias": familias, "cumple_muestra_observada": cumple,
        "familias_evaluables": len(familias_evaluables),
        "cumplen_familias_evaluables": cumplen_familias,
        "cumple_conjunto_y_familias": cumple and cumplen_familias,
        "validacion_prospectiva_confirmada": False,
        "autoriza_real": False,
        "limitacion": "No demuestra ventaja futura ni independencia estadistica. "
                      "Origen PRACTICE y PnL conciliado requieren evidencia externa.",
    }

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("csv_resultados", type=Path)
    args = p.parse_args()
    with args.csv_resultados.open(encoding="utf-8-sig", newline="") as f:
        filas = list(csv.DictReader(f))
    print(json.dumps(evaluar(filas), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
