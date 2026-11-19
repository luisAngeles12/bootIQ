"""R9-07: auditoría de procedencia del historial, estrictamente de solo lectura.

No llama IQ, no genera memoria y no cambia etiquetas. Cuenta estados, modos,
IDs y cronología antes de considerar entrenamiento TRAIN/OOS.
"""
import csv
import json
import math
from datetime import datetime, timezone
from collections import Counter, defaultdict
from pathlib import Path


ESTADOS_NO_EJECUTADOS = {
    "HIPOTETICA", "HIPOTETICO", "ABIERTA", "PENDIENTE",
    "CANCELADA", "CANCELADO", "CANCELADA_CEREBRO",
    "CANCELADA_PROTOCOLO",
}


def _txt(valor):
    return str(valor or "").strip().upper()


def _fecha_finita(valor):
    try:
        numero = float(valor)
    except (ValueError, TypeError, OverflowError):
        return None
    return numero if math.isfinite(numero) and numero > 0 else None



def _fecha_iso(valor):
    """Reconoce ISO 8601 solo como diagnóstico (sin inventar zona horaria)."""
    texto = str(valor or "").strip()
    if not texto:
        return None
    try:
        fecha = datetime.fromisoformat(
            texto[:-1] + "+00:00" if texto.endswith("Z") else texto
        )
    except (TypeError, ValueError, OverflowError):
        return None
    return fecha.isoformat()


def _resultado_monetario(valor):
    """Clasifica PNL, sin convertirlo en una etiqueta de entrenamiento."""
    try:
        pnl = float(valor)
    except (TypeError, ValueError, OverflowError):
        return "NO_NUMERICO"
    if not math.isfinite(pnl):
        return "NO_FINITO"
    return "GANANCIA" if pnl > 0 else ("PERDIDA" if pnl < 0 else "EMPATE")


def _cierre_explicito(estado):
    return estado in {"CERRADA", "CERRADO"}



def analizar_historial(ruta):
    ruta = Path(ruta)
    modos = Counter()
    estados = Counter()
    etiquetas = Counter()
    origenes = Counter()
    id_filas = defaultdict(list)
    falta_id = 0
    fechadas = 0
    posibles_candidatas = 0
    fechas_candidatas = []
    filas = 0
    marcas_candidatas = set()
    estados_cierre = Counter()
    resultados_numericos = Counter()
    modos_cierre_numerico = Counter()
    fechas_iso = 0
    fechas_iso_cierre_practice = 0
    cierre_practice_numerico_ids = set()
    fechas_cierre_practice = []
    zonas_fecha_cierre = Counter()
    motivos_exclusion = Counter()
    candidatas_temporales = 0

    with ruta.open(encoding="utf-8-sig", newline="") as archivo:
        lector = csv.DictReader(archivo)
        columnas = lector.fieldnames or []
        requeridas = {"order_id", "resultado", "estado_operacion", "fecha"}
        for registro in lector:
            filas += 1
            modo = _txt(registro.get("modo_cuenta_configurado")) or "SIN_MODO"
            estado = _txt(registro.get("estado_operacion")) or "SIN_ESTADO"
            etiqueta = _txt(registro.get("resultado")) or "SIN_RESULTADO"
            origen = _txt(registro.get("origen_autoridad")) or "SIN_AUTORIDAD"
            orden = str(registro.get("order_id") or "").strip()
            fecha = _fecha_finita(registro.get("fecha"))
            fecha_iso = _fecha_iso(registro.get("fecha"))
            fechas_iso += fecha_iso is not None
            pnl_tipo = _resultado_monetario(registro.get("resultado"))
            resultados_numericos[pnl_tipo] += 1
            # R9-09: candidato de auditoría estricta; no es entrenamiento.
            # No aceptar modo vacío, estado de cierre inferido ni fechas
            # sin huso horario: TRAIN/OOS exige orden cronológico inequívoco.
            marca_cierre = _cierre_explicito(_txt(registro.get("estado")))
            if modo == "PRACTICE":
                if not orden:
                    motivos_exclusion["SIN_ORDER_ID"] += 1
                elif not marca_cierre:
                    motivos_exclusion["SIN_CIERRE_EXPLICITO"] += 1
                elif pnl_tipo not in {"GANANCIA", "PERDIDA"}:
                    motivos_exclusion["PNL_SIN_WIN_LOSS"] += 1
                elif fecha_iso is None:
                    motivos_exclusion["SIN_FECHA_ISO"] += 1
                else:
                    dt = datetime.fromisoformat(fecha_iso)
                    if dt.tzinfo is None or dt.utcoffset() is None:
                        motivos_exclusion["FECHA_SIN_ZONA_HORARIA"] += 1
                    else:
                        candidatas_temporales += 1
                        fechas_cierre_practice.append(dt.astimezone(timezone.utc))
                        zonas_fecha_cierre["CON_OFFSET"] += 1
            if _cierre_explicito(_txt(registro.get("estado"))):
                estados_cierre[modo] += 1
                if pnl_tipo in {"GANANCIA", "PERDIDA", "EMPATE"}:
                    modos_cierre_numerico[modo] += 1
                    if modo == "PRACTICE" and orden:
                        cierre_practice_numerico_ids.add(orden)
                        fechas_iso_cierre_practice += fecha_iso is not None
            modos[modo] += 1
            estados[estado] += 1
            etiquetas[etiqueta] += 1
            origenes[origen] += 1
            fechadas += fecha is not None
            if orden:
                id_filas[orden].append((modo, estado, etiqueta))
            else:
                falta_id += 1
            if (
                orden and modo == "PRACTICE"
                and estado not in ESTADOS_NO_EJECUTADOS
                and estado not in {"", "SIN_ESTADO"}
                and etiqueta in {"WIN", "LOSS"}
            ):
                posibles_candidatas += 1
                marcas_candidatas.add(orden)
                if fecha is not None:
                    fechas_candidatas.append(fecha)

    repetidos = sum(len(grupo) > 1 for grupo in id_filas.values())
    conflictivos = sum(
        len(set(grupo)) > 1 for grupo in id_filas.values() if len(grupo) > 1
    )
    return {
        "archivo": str(ruta),
        "filas": filas,
        "columnas_requeridas_presentes": sorted(requeridas.intersection(columnas)),
        "columnas_requeridas_ausentes": sorted(requeridas.difference(columnas)),
        "modos": dict(sorted(modos.items())),
        "estados_operacion": dict(sorted(estados.items())),
        "resultados": dict(sorted(etiquetas.items())),
        "autoridades": dict(sorted(origenes.items())),
        "filas_sin_order_id": falta_id,
        "order_ids_distintos": len(id_filas),
        "order_ids_repetidos": repetidos,
        "order_ids_con_metadatos_distintos": conflictivos,
        "filas_con_fecha_numerica": fechadas,
        "filas_con_fecha_iso": fechas_iso,
        "filas_cierre_explicito_por_modo": dict(sorted(estados_cierre.items())),
        "tipos_resultado_monetario": dict(sorted(resultados_numericos.items())),
        "filas_cierre_con_pnl_finito_por_modo": dict(
            sorted(modos_cierre_numerico.items())
        ),
        "ids_practice_cierre_con_pnl_finito": len(cierre_practice_numerico_ids),
        "cierre_practice_con_fecha_iso": fechas_iso_cierre_practice,
        "candidatas_temporales_practice_preliminares": candidatas_temporales,
        "exclusiones_practice_para_train_oos": dict(sorted(motivos_exclusion.items())),
        "candidatas_train_oos_con_zona": dict(sorted(zonas_fecha_cierre.items())),
        "primera_fecha_utc_preliminar": (
            min(fechas_cierre_practice).isoformat() if fechas_cierre_practice else None
        ),
        "ultima_fecha_utc_preliminar": (
            max(fechas_cierre_practice).isoformat() if fechas_cierre_practice else None
        ),
        "filas_candidatas_preliminares_practice": posibles_candidatas,
        "ids_candidatos_distintos": len(marcas_candidatas),
        "candidatas_fechadas": len(fechas_candidatas),
        "min_fecha_candidata": min(fechas_candidatas) if fechas_candidatas else None,
        "max_fecha_candidata": max(fechas_candidatas) if fechas_candidatas else None,
        "advertencia": (
            "CANDIDATAS PRELIMINARES, NO MEMORIA: falta verificar contra IQ "
            "las órdenes y resultados, duplicados y partición temporal TRAIN/OOS. "
            "Los PNL numéricos no son etiquetas WIN/LOSS del motor."
        ),
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("historial", nargs="?", default="historial_bot.csv")
    argumentos = parser.parse_args()
    print(json.dumps(analizar_historial(argumentos.historial),
                     indent=2, ensure_ascii=False))
