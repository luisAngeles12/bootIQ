"""Auditoria de consistencia PRACTICE: solo lectura, sin autorizacion de trading.

Calcula bloques de 20 y ventanas moviles de 20 operaciones ordenadas por
fecha de senal. Nunca genera aprendizaje ni propone cambios automaticos.
"""
import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

TAMANO_VENTANA = 20
OBJETIVO = 0.60


def _instante(fecha):
    valor = str(fecha or "").strip()
    if not valor:
        raise ValueError("FECHA_VACIA")
    try:
        return datetime.fromisoformat(valor.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("FECHA_INVALIDA") from exc


def evaluar_filas(filas, tamano=TAMANO_VENTANA, objetivo=OBJETIVO):
    if tamano < 1 or not 0 < objetivo <= 1:
        raise ValueError("PARAMETROS_INVALIDOS")
    aceptadas = []
    rechazadas = defaultdict(int)
    ids = set()
    for fila in filas:
        if str(fila.get("modo_cuenta_configurado") or "").strip().upper() != "PRACTICE":
            rechazadas["MODO_NO_VERIFICADO_PRACTICE"] += 1
            continue
        if str(fila.get("estado", "")).strip().upper() != "CERRADA":
            rechazadas["NO_CERRADA"] += 1
            continue
        identificador = str(fila.get("order_id", "")).strip()
        if not identificador:
            rechazadas["SIN_ORDER_ID"] += 1
            continue
        if identificador in ids:
            rechazadas["ORDER_ID_DUPLICADO"] += 1
            continue
        try:
            instante = _instante(fila.get("fecha"))
        except ValueError as exc:
            rechazadas[str(exc)] += 1
            continue
        try:
            pnl = Decimal(str(fila.get("resultado", "")).strip())
        except (InvalidOperation, ValueError, TypeError):
            rechazadas["RESULTADO_INVALIDO"] += 1
            continue
        if not pnl.is_finite() or pnl * 100 != (pnl * 100).to_integral_value():
            rechazadas["RESULTADO_INVALIDO"] += 1
            continue
        # El empate no equivale ni a WIN ni a LOSS y no completa ventanas.
        ids.add(identificador)
        if pnl == 0:
            rechazadas["EMPATE"] += 1
            continue
        aceptadas.append({
            "order_id": identificador,
            "fecha": instante,
            "dia": instante.date().isoformat(),
            "patron": str(fila.get("patron") or "SIN_PATRON").strip(),
            "pnl": pnl,
            "win": pnl > 0,
        })
    # Ordenar por fecha de manera estable: ante timestamps identicos,
    # conservar la secuencia de registro CSV. Los order_id son etiquetas,
    # no una clave cronologica (su orden lexicografico altera ventanas).
    # Fechas sin zona deben provenir de la misma zona de registro.
    zonas = {x["fecha"].tzinfo is None for x in aceptadas}
    if len(zonas) > 1:
        raise ValueError("MEZCLA_FECHAS_CON_Y_SIN_ZONA")
    aceptadas.sort(key=lambda r: r["fecha"])

    def resumen(bloque):
        n = len(bloque)
        wins = sum(r["win"] for r in bloque)
        neto = sum((r["pnl"] for r in bloque), Decimal("0"))
        cumple_60 = wins / n >= objetivo if n == tamano else None
        cumple_economico = bool(cumple_60) and neto > 0 if n == tamano else None
        return {
            "n": n,
            "wins": wins,
            "losses": n - wins,
            "winrate_pct": round(100 * wins / n, 2) if n else None,
            "neto": float(neto),
            "cumple_60": cumple_60,
            "cumple_objetivo_economico": cumple_economico,
        }

    bloques = [resumen(aceptadas[i:i + tamano])
               for i in range(0, len(aceptadas), tamano)]
    completos = bloques[:len(aceptadas) // tamano]
    moviles = [resumen(aceptadas[i:i + tamano])
               for i in range(len(aceptadas) - tamano + 1)]
    dias = defaultdict(list)
    patrones = defaultdict(list)
    for r in aceptadas:
        dias[r["dia"]].append(r)
        patrones[r["patron"]].append(r)
    # Fase 5/12: la meta de 60% en cada ventana de 20 se mide
    # por familia ademas del conjunto. Una familia sin 20 cierres
    # permanece SIN_EVIDENCIA, no se considera ganadora.
    por_estrategia_20 = {}
    for patron, registros in sorted(patrones.items()):
        ventanas_patron = [
            resumen(registros[i:i + tamano])
            for i in range(max(0, len(registros) - tamano + 1))
        ]
        bajo_objetivo = sum(
            ventana["cumple_objetivo_economico"] is False for ventana in ventanas_patron
        )
        por_estrategia_20[patron] = {
            "total_evaluables": len(registros),
            "ventanas_moviles": len(ventanas_patron),
            "ventanas_bajo_objetivo": bajo_objetivo,
            "consistencia_observada": bool(ventanas_patron) and bajo_objetivo == 0,
            "evidencia_prospectiva_suficiente": False,
        }
    return {
        "modo": "AUDITORIA_SOLO_LECTURA_PRACTICE_DECLARADO",
        "procedencia_broker_certificada": False,
        "validacion_oos": False,
        "criterio_economico": "WINRATE_MINIMO_Y_NETO_ESTRICTAMENTE_POSITIVO",
        "objetivo_pct": round(objetivo * 100, 2),
        "ventana": tamano,
        "total_filas_validas_win_loss": len(aceptadas),
        "descartes": dict(sorted(rechazadas.items())),
        "global": resumen(aceptadas),
        "dias": {k: resumen(v) for k, v in sorted(dias.items())},
        "estrategias": {k: resumen(v) for k, v in sorted(patrones.items())},
        "consistencia_20_por_estrategia": por_estrategia_20,
        "bloques_no_solapados": bloques,
        "bloques_completos": len(completos),
        "bloques_completos_bajo_objetivo": sum(
            x["cumple_objetivo_economico"] is False for x in completos
        ),
        "ventanas_moviles": len(moviles),
        "ventanas_moviles_bajo_objetivo": sum(
            x["cumple_objetivo_economico"] is False for x in moviles
        ),
        "consistencia_20_observada": bool(moviles) and all(
            x["cumple_objetivo_economico"] for x in moviles
        ),
        "evidencia_prospectiva_suficiente": False,
        "operaciones_autorizadas": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("historial", nargs="?", default="historial_bot.csv")
    args = parser.parse_args()
    with Path(args.historial).open(encoding="utf-8-sig", newline="") as archivo:
        reporte = evaluar_filas(csv.DictReader(archivo))
    print(json.dumps(reporte, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
