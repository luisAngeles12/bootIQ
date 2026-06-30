import csv
import os

RUTA_APRENDIZAJE = "aprendizaje_historico_bootiq.csv"

MIN_MUESTRA = 8
UMBRAL_BUENO = 58.0
UMBRAL_MALO = 48.0


def _txt(v):
    return str(v or "").upper().strip()


def _clave(senal):
    return "|".join([
        _txt(senal.get("activo")),
        _txt(senal.get("direccion")),
        _txt(senal.get("tipo_setup")),
        _txt(senal.get("subtipo_setup")),
        _txt(senal.get("protocolo_sugerido")),
        _txt(senal.get("accion_precio")),
        _txt(senal.get("pa_tipo")),
        _txt(senal.get("tipo_mercado")),
        _txt(senal.get("estado_tendencia")),
        _txt(senal.get("nivel_consenso")),
    ])


def cargar_aprendizaje(ruta=RUTA_APRENDIZAJE):
    if not os.path.exists(ruta):
        return {}

    memoria = {}

    with open(ruta, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            clave = row.get("clave", "")
            if not clave:
                continue

            memoria[clave] = {
                "total": int(float(row.get("total", 0) or 0)),
                "wins": int(float(row.get("wins", 0) or 0)),
                "losses": int(float(row.get("losses", 0) or 0)),
                "winrate": float(row.get("winrate", 0) or 0),
                "ajuste_confianza": float(row.get("ajuste_confianza", 0) or 0),
                "decision_aprendizaje": row.get("decision_aprendizaje", "SIN_DATOS"),
            }

    return memoria


def evaluar_aprendizaje_historico(senal, memoria=None):
    if memoria is None:
        memoria = cargar_aprendizaje()

    clave = _clave(senal)
    data = memoria.get(clave)

    if not data:
        return {
            "aprendizaje_encontrado": False,
            "clave_aprendizaje": clave,
            "ajuste_confianza_aprendizaje": 0,
            "decision_aprendizaje": "SIN_DATOS",
            "motivo_aprendizaje": "Sin historial para esta combinación."
        }

    total = data.get("total", 0)
    winrate = data.get("winrate", 0)
    ajuste = data.get("ajuste_confianza", 0)
    decision = data.get("decision_aprendizaje", "NEUTRO")

    if total < MIN_MUESTRA:
        return {
            "aprendizaje_encontrado": True,
            "clave_aprendizaje": clave,
            "ajuste_confianza_aprendizaje": 0,
            "decision_aprendizaje": "MUESTRA_INSUFICIENTE",
            "motivo_aprendizaje": f"Historial insuficiente: {total} operaciones."
        }

    return {
        "aprendizaje_encontrado": True,
        "clave_aprendizaje": clave,
        "ajuste_confianza_aprendizaje": ajuste,
        "decision_aprendizaje": decision,
        "motivo_aprendizaje": f"Historial: {total} operaciones, winrate {winrate}%."
    }


def generar_aprendizaje_desde_resultados(resultados, ruta=RUTA_APRENDIZAJE):
    grupos = {}

    for r in resultados:
        clave = _clave(r)

        if clave not in grupos:
            grupos[clave] = {
                "total": 0,
                "wins": 0,
                "losses": 0,
                "ejemplo": r
            }

        grupos[clave]["total"] += 1

        if r.get("resultado") == "WIN":
            grupos[clave]["wins"] += 1
        else:
            grupos[clave]["losses"] += 1

    filas = []

    for clave, d in grupos.items():
        total = d["total"]
        wins = d["wins"]
        losses = d["losses"]
        winrate = round((wins / total) * 100, 2) if total else 0

        if total < MIN_MUESTRA:
            decision = "MUESTRA_INSUFICIENTE"
            ajuste = 0
        elif winrate >= UMBRAL_BUENO:
            decision = "FAVORABLE"
            ajuste = 8
        elif winrate <= UMBRAL_MALO:
            decision = "DEBIL"
            ajuste = -10
        else:
            decision = "NEUTRO"
            ajuste = 0

        ejemplo = d["ejemplo"]

        filas.append({
            "clave": clave,
            "total": total,
            "wins": wins,
            "losses": losses,
            "winrate": winrate,
            "ajuste_confianza": ajuste,
            "decision_aprendizaje": decision,
            "activo": ejemplo.get("activo", ""),
            "direccion": ejemplo.get("direccion", ""),
            "tipo_setup": ejemplo.get("tipo_setup", ""),
            "subtipo_setup": ejemplo.get("subtipo_setup", ""),
            "protocolo_sugerido": ejemplo.get("protocolo_sugerido", ""),
            "accion_precio": ejemplo.get("accion_precio", ""),
            "pa_tipo": ejemplo.get("pa_tipo", ""),
            "tipo_mercado": ejemplo.get("tipo_mercado", ""),
            "estado_tendencia": ejemplo.get("estado_tendencia", ""),
            "nivel_consenso": ejemplo.get("nivel_consenso", ""),
        })

    filas = sorted(
        filas,
        key=lambda x: (x["total"], x["winrate"]),
        reverse=True
    )

    campos = [
        "clave",
        "total",
        "wins",
        "losses",
        "winrate",
        "ajuste_confianza",
        "decision_aprendizaje",
        "activo",
        "direccion",
        "tipo_setup",
        "subtipo_setup",
        "protocolo_sugerido",
        "accion_precio",
        "pa_tipo",
        "tipo_mercado",
        "estado_tendencia",
        "nivel_consenso",
    ]

    with open(ruta, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=campos)
        writer.writeheader()
        writer.writerows(filas)

    print("Archivo de aprendizaje generado:", ruta)
    print("Combinaciones aprendidas:", len(filas))

    return filas