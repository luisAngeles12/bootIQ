"""Audita 3–4 rondas prospectivas de 20 operaciones PRACTICE (solo lectura).

No importa bot/config, no conecta al broker ni habilita trading. Un CSV con
campos declarados no constituye por si mismo conciliacion independiente.
"""
import argparse
import csv
import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

CAMPOS = {"ronda_id", "order_id", "fecha_cierre", "estado", "tipo_cuenta",
          "resultado", "neto", "familia", "origen_autoridad"}
BOOTSTRAP = "BOOTSTRAP_PRACTICE_SIN_HISTORIAL"


def _utc(valor):
    try:
        fecha = datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
        if fecha.tzinfo is None:
            raise ValueError("ZONA_HORARIA_REQUERIDA")
        return fecha.astimezone(timezone.utc)
    except (TypeError, ValueError) as exc:
        raise ValueError("FECHA_CIERRE_INVALIDA") from exc


def _neto(valor):
    try:
        importe = Decimal(str(valor).strip())
        if not importe.is_finite() or importe * 100 != (importe * 100).to_integral_value():
            raise ValueError("NETO_INVALIDO")
        return importe
    except (InvalidOperation, TypeError) as exc:
        raise ValueError("NETO_INVALIDO") from exc


def evaluar(filas, congelacion_utc, rondas_objetivo=4):
    """No selecciona rondas ganadoras; procesa el conjunto consecutivo completo."""
    if rondas_objetivo not in (3, 4):
        raise ValueError("RONDAS_OBJETIVO_INVALIDAS")
    congelacion = _utc(congelacion_utc)
    registros, ids, rondas = [], set(), {}
    for i, fila in enumerate(filas, 1):
        if not isinstance(fila, dict) or not CAMPOS.issubset(fila):
            raise ValueError("COLUMNAS_INSUFICIENTES")
        if any(not str(fila[c] or "").strip() for c in CAMPOS):
            raise ValueError("FILA_INCOMPLETA")
        if fila["estado"].strip().upper() != "CERRADA":
            raise ValueError("ORDEN_NO_CERRADA")
        if fila["tipo_cuenta"].strip().upper() != "PRACTICE":
            raise ValueError("SOLO_PRACTICE")
        origen = fila["origen_autoridad"].strip().upper()
        if origen == BOOTSTRAP:
            raise ValueError("BOOTSTRAP_NO_ES_V3_VALIDADO")
        order_id = fila["order_id"].strip()
        if order_id in ids:
            raise ValueError("ORDER_ID_DUPLICADO")
        ids.add(order_id)
        fecha = _utc(fila["fecha_cierre"])
        if fecha <= congelacion:
            raise ValueError("OPERACION_NO_PROSPECTIVA")
        neto = _neto(fila["neto"])
        resultado = fila["resultado"].strip().upper()
        if resultado not in ("WIN", "LOSS", "EMPATE"):
            raise ValueError("RESULTADO_INVALIDO")
        if ((resultado == "WIN" and neto <= 0)
                or (resultado == "LOSS" and neto >= 0)
                or (resultado == "EMPATE" and neto != 0)):
            raise ValueError("RESULTADO_NETO_CONTRADICTORIO")
        ronda = fila["ronda_id"].strip()
        if ronda not in rondas:
            rondas[ronda] = []
        # Exigir archivo cronologico, no reordenar/selectivamente filtrar datos.
        if registros and fecha <= registros[-1]["fecha"]:
            raise ValueError("CRONOLOGIA_NO_ESTRICTA")
        if registros and ronda != registros[-1]["ronda"] and ronda in {r["ronda"] for r in registros}:
            raise ValueError("RONDA_INTERCALADA")
        registro = {"ronda": ronda, "fecha": fecha, "resultado": resultado,
                    "neto": neto, "familia": fila["familia"].strip(), "orden": i}
        registros.append(registro)
        rondas[ronda].append(registro)
    if len(rondas) > rondas_objetivo:
        raise ValueError("RONDAS_EXCEDEN_OBJETIVO")
    detalle = []
    for numero, (ronda, operaciones) in enumerate(rondas.items(), 1):
        if len(operaciones) > 20:
            raise ValueError("RONDA_SUPERA_20_OPERACIONES")
        ganadas = sum(x["resultado"] == "WIN" for x in operaciones)
        perdidas = sum(x["resultado"] == "LOSS" for x in operaciones)
        neto = sum((x["neto"] for x in operaciones), Decimal("0"))
        completa = len(operaciones) == 20
        pasa = completa and ganadas >= 12 and neto > 0
        detalle.append({"ronda": numero, "ronda_id": ronda, "operaciones": len(operaciones),
                        "wins": ganadas, "losses": perdidas,
                        "empates": len(operaciones) - ganadas - perdidas,
                        "winrate_pct": round(100 * ganadas / len(operaciones), 2) if operaciones else None,
                        "neto": float(neto), "completa": completa,
                        "cumple_60_y_neto_positivo": pasa,
                        "dias_utc": len({x["fecha"].date() for x in operaciones})})
    dias = len({x["fecha"].date() for x in registros})
    todas = len(detalle) == rondas_objetivo and all(x["cumple_60_y_neto_positivo"] for x in detalle)
    # Reportar muestra limitada por jornadas: nunca equivalencia a independencia.
    return {"tipo": "RONDAS_60_PRACTICE_SOLO_LECTURA",
            "congelacion_utc": congelacion.isoformat(),
            "rondas_objetivo": rondas_objetivo,
            "rondas_completas": sum(x["completa"] for x in detalle),
            "rondas_aprobadas": sum(x["cumple_60_y_neto_positivo"] for x in detalle),
            "operaciones": len(registros), "dias_utc_distintos": dias,
            "resultado_observado_3_4_rondas": "CUMPLE" if todas and dias >= 2 else "NO_DEMOSTRADO",
            "rondas": detalle,
            "procedencia_broker_certificada": False,
            "independencia_estadistica_certificada": False,
            "rentabilidad_futura_garantizada": False,
            "autoriza_real": False,
            "advertencia": "El CSV declara resultados: verificar fills, payouts y cierres con IQ. "
                            "Ni 3-4 bloques aprobados garantizan 60% constante futuro."}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("csv_practice", type=Path)
    p.add_argument("--congelacion-utc", required=True,
                   help="Fecha UTC en que se congelaron las reglas ANTES de observar estas rondas")
    p.add_argument("--rondas", type=int, choices=(3, 4), default=4)
    args = p.parse_args()
    with args.csv_practice.open(encoding="utf-8-sig", newline="") as archivo:
        lector = csv.DictReader(archivo)
        if not lector.fieldnames or len(lector.fieldnames) != len(set(lector.fieldnames)):
            raise ValueError("ENCABEZADOS_INVALIDOS")
        resultado = evaluar(lector, args.congelacion_utc, args.rondas)
    print(json.dumps(resultado, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
