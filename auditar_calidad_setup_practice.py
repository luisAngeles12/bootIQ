"""Auditoria de calibracion del setup; SOLO LECTURA, nunca autoriza trading.

Distingue PRACTICE marcado de legado declarado y reserva TEST por fechas.
Investiga especificamente la etiqueta PREMIUM y los patrones de reaccion
que pueden omitir espera de confirmacion en entrada.py.
"""
import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
import unicodedata

from construir_memoria_ejecutadas_train_practice import _limpiar


CALIDADES = ("PREMIUM", "BUENA", "MEDIA", "DEBIL")
# Reportar la brecha historica (antes del fix de normalizacion),
# diferenciada de la ruta LIVE corregida.
TIPOS_REACCION = {"RECHAZO_ALCISTA", "RECHAZO_BAJISTA"}


def _metricas(registros):
    n = len(registros)
    wins = sum(pnl > 0 for _, _, pnl, _ in registros)
    pnl = round(sum(pnl for _, _, pnl, _ in registros), 2)
    return {
        "n": n, "wins": wins, "losses": n - wins,
        "winrate_pct": round(100 * wins / n, 2) if n else None,
        "pnl": pnl,
        "dias": len({fecha.date().isoformat() for fecha, *_ in registros}),
    }


def _calidad(fila):
    return str(fila.get("calidad_setup") or "").strip().upper() or "SIN_DATO"


def _rama_reaccion(fila):
    patron = unicodedata.normalize("NFKD", str(fila.get("patron") or "").lower())
    patron = "".join(c for c in patron if not unicodedata.combining(c))
    tipo = str(fila.get("tipo_setup") or "").upper().strip()
    return "reaccion" in patron or tipo in TIPOS_REACCION


def _rama_reaccion_literal_legacy(fila):
    """Reproduce la condicion anterior, que ignoraba patron con tilde."""
    patron = str(fila.get("patron") or "").lower()
    tipo = str(fila.get("tipo_setup") or "").upper().strip()
    return "reaccion" in patron or tipo in TIPOS_REACCION


def analizar(filas, corte_train="2026-11-16"):
    registros, descartes = _limpiar(filas)
    procedencia = dict(Counter(
        fila["_procedencia_practice_auditoria"]
        for _, _, _, fila in registros
    ))
    segmentos = defaultdict(list)
    for registro in registros:
        fecha, oid, pnl, fila = registro
        periodo = "TRAIN" if fecha.date().isoformat() <= corte_train else "TEST"
        calidad = _calidad(fila)
        segmentos[(periodo, "TOTAL")].append(registro)
        segmentos[(periodo, "CALIDAD", calidad)].append(registro)
        if calidad == "PREMIUM":
            segmentos[(periodo, "PREMIUM_PATRON", str(fila.get("patron") or "SIN_DATO").strip().upper())].append(registro)
        if _rama_reaccion(fila):
            segmentos[(periodo, "RAMA_REACCION", calidad)].append(registro)
            if not _rama_reaccion_literal_legacy(fila):
                segmentos[(periodo, "REACCION_NO_RECONOCIDA_LITERAL", calidad)].append(registro)

    def par(clave):
        return {p: _metricas(segmentos[(p, *clave)]) for p in ("TRAIN", "TEST")}

    # Conservar la comparacion completa para detectar deriva de PREMIUM
    # frente a BUENA, sin convertir el resultado en autoridad operativa.
    premium_test = _metricas(segmentos[("TEST", "CALIDAD", "PREMIUM")])
    buena_test = _metricas(segmentos[("TEST", "CALIDAD", "BUENA")])
    brecha_pp = (
        round(premium_test["winrate_pct"] - buena_test["winrate_pct"], 2)
        if premium_test["winrate_pct"] is not None
        and buena_test["winrate_pct"] is not None
        else None
    )
    alerta_calibracion = (
        "PREMIUM_INFERIOR_A_BUENA_EN_TEST"
        if premium_test["n"] >= 20
        and buena_test["n"] >= 20
        and brecha_pp is not None and brecha_pp < 0
        else "SIN_EVIDENCIA_SUFICIENTE_DE_INVERSION"
    )

    calidades = sorted({_calidad(f) for _, _, _, f in registros})
    patrones = sorted({str(f.get("patron") or "SIN_DATO").strip().upper()
                      for _, _, _, f in registros if _calidad(f) == "PREMIUM"})
    return {
        "estado": "AUDITORIA_NO_OPERABLE",
        "corte_train": corte_train,
        "total": len(registros),
        "procedencia": procedencia,
        "descartes": descartes,
        "baseline": {p: _metricas(segmentos[(p, "TOTAL")]) for p in ("TRAIN", "TEST")},
        "calidades": {c: par(("CALIDAD", c)) for c in calidades},
        "alerta_calibracion_premium": {
            "estado": alerta_calibracion,
            "brecha_winrate_test_vs_buena_pp": brecha_pp,
            "premium_test": premium_test,
            "buena_test": buena_test,
            "accion": "INVESTIGAR_SIN_AUTORIZAR_NI_BLOQUEAR_OPERACIONES",
        },
        "premium_por_patron": {pat: par(("PREMIUM_PATRON", pat)) for pat in patrones},
        "rama_reaccion_por_calidad": {c: par(("RAMA_REACCION", c)) for c in calidades},
        "reacciones_omitidas_por_condicion_legacy_antes_de_fix": {
            c: par(("REACCION_NO_RECONOCIDA_LITERAL", c)) for c in calidades
        },
        "nota": (
            "RAMA_REACCION identifica patrones semanticamente; el campo "
            "OMITIDAS identifica la condicion legacy anterior al fix. "
            "Ninguna cohorte prueba que la condicion haya autorizado una orden. "
            "TRAIN/TEST solo describe operaciones ejecutadas, no descartadas. "
            "Calidad PREMIUM no equivale a ventaja estadistica validada."
        ),
        "autoriza_operaciones": False,
        "modifica_estrategia": False,
        "autoriza_real": False,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("historial", nargs="?", default="historial_bot.csv")
    ap.add_argument("--corte-train", default="2026-11-16")
    args = ap.parse_args()
    with Path(args.historial).open(encoding="utf-8-sig", newline="") as f:
        informe = analizar(csv.DictReader(f), corte_train=args.corte_train)
    print(json.dumps(informe, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
