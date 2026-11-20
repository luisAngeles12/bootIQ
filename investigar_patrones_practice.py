"""Estabilidad cronologica de familias PRACTICE, diagnostico sin operabilidad.

No selecciona ni desactiva estrategias, no conecta a IQ. Los resultados de
bootstrap quedan separados; dividirlos en tercios es exploratorio, no OOS.
"""
import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

COLUMNAS = {"order_id", "fecha", "estado", "modo_cuenta_configurado",
            "resultado", "patron", "origen_autoridad"}


def _fecha(cadena):
    try:
        fecha = datetime.fromisoformat(str(cadena or "").replace("Z", "+00:00"))
        if not fecha.isoformat():
            raise ValueError("FECHA_INVALIDA")
        return fecha
    except (ValueError, TypeError) as exc:
        raise ValueError("FECHA_INVALIDA") from exc


def _resumen(registros):
    n = len(registros)
    wins = sum(f["pnl"] > 0 for f in registros)
    neto = sum((f["pnl"] for f in registros), Decimal("0"))
    return {"n": n, "wins": wins, "losses": n-wins,
            "wr_pct": round(100 * wins / n, 2) if n else None, "neto": float(neto),
            "cumple_60_y_neto": bool(n and wins / n >= .6 and neto > 0)}


def explorar(filas, minimo_familia=20):
    if type(minimo_familia) is not int or minimo_familia < 3:
        raise ValueError("MINIMO_INVALIDO")
    aceptadas, rechazadas, ids = [], Counter(), set()
    for fila in filas:
        if not isinstance(fila, dict) or not COLUMNAS.issubset(fila):
            raise ValueError("COLUMNAS_INSUFICIENTES")
        if str(fila["modo_cuenta_configurado"] or "").strip().upper() != "PRACTICE":
            rechazadas["MODO_NO_CONFIRMADO"] += 1
            continue
        if str(fila["estado"] or "").strip().upper() != "CERRADA":
            rechazadas["NO_CERRADA"] += 1
            continue
        identificador = str(fila["order_id"] or "").strip()
        if not identificador or identificador in ids:
            rechazadas["ID_AUSENTE_O_DUPLICADO"] += 1
            continue
        try:
            fecha = _fecha(fila["fecha"])
            pnl = Decimal(str(fila["resultado"]).strip())
            if not pnl.is_finite() or pnl * 100 != (pnl * 100).to_integral_value():
                raise ValueError("PNL_INVALIDO")
        except (ValueError, InvalidOperation, TypeError):
            rechazadas["FECHA_O_PNL_INVALIDO"] += 1
            continue
        ids.add(identificador)
        if pnl == 0:
            rechazadas["EMPATE"] += 1
            continue
        aceptadas.append({"fecha": fecha, "orden": len(aceptadas), "pnl": pnl,
                          "patron": str(fila["patron"] or "SIN_PATRON").strip(),
                          "origen": str(fila["origen_autoridad"] or "SIN_AUTORIDAD").strip().upper()})
    if len({x["fecha"].tzinfo is None for x in aceptadas}) > 1:
        raise ValueError("ZONAS_MIXTAS")
    aceptadas.sort(key=lambda f: (f["fecha"], f["orden"]))
    grupos = defaultdict(list)
    for x in aceptadas:
        grupos[(x["origen"], x["patron"])].append(x)
    familias = []
    for (origen, patron), datos in sorted(grupos.items()):
        n = len(datos)
        # Tres fracciones cronologicas, sin reajustar limites segun resultado.
        cortes = [0, n // 3, (2 * n) // 3, n]
        tercios = [_resumen(datos[cortes[i]:cortes[i+1]]) for i in range(3)]
        resumen = _resumen(datos)
        elegible = n >= minimo_familia
        familias.append({"origen": origen, "patron": patron, **resumen,
                         "tercios_cronologicos": tercios if elegible else None,
                         "tercios_todos_60_y_netos": (all(t["cumple_60_y_neto"] for t in tercios)
                             if elegible else None),
                         "evidencia_v3_prospectiva_certificada": False,
                         "advertencia": "Tercios historicos son exploratorios, no validacion OOS"})
    return {"modo": "INVESTIGACION_RETROSPECTIVA_PRACTICE_SOLO_LECTURA",
            "total_evaluables": len(aceptadas), "descartes": dict(sorted(rechazadas.items())),
            "global": _resumen(aceptadas), "familias": familias,
            "conclusion": "SIN_PRUEBA_DE_VENTAJA_PROSPECTIVA",
            "autoriza_real": False, "autoriza_cambiar_reglas": False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("historial_csv", type=Path)
    args = p.parse_args()
    with args.historial_csv.open(encoding="utf-8-sig", newline="") as archivo:
        lector = csv.DictReader(archivo)
        if not lector.fieldnames or len(lector.fieldnames) != len(set(lector.fieldnames)):
            raise ValueError("ENCABEZADOS_INVALIDOS")
        reporte = explorar(lector)
    print(json.dumps(reporte, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
