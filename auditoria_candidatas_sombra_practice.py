"""Observación prospectiva de candidatas rechazadas; NUNCA envía órdenes.

Los resultados se calculan con la apertura y el cierre de la vela POSTERIOR
a la señal. No son fills del broker, ni generan autoridad de aprendizaje.
"""
import csv
import os
from pathlib import Path
from datetime import datetime, timezone

RUTA_EVENTOS = "auditoria_candidatas_sombra_practice.csv"
COLUMNAS = (
    "id", "activo", "patron", "direccion", "vela_senal_from",
    "decision", "motivo", "tipo_mercado", "calidad_mercado",
    "accion_precio", "estado_tendencia", "vela_entrada_from",
    "precio_entrada_hipotetico", "precio_cierre_hipotetico",
    "resultado_hipotetico", "calidad_tiempo",
)

def _id(activo, patron, direccion, ts):
    import hashlib
    texto = "|".join((str(activo), str(patron), str(direccion), str(ts)))
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()[:24]

def _leer(ruta):
    p = Path(ruta)
    if not p.exists() or not p.stat().st_size:
        return []
    with p.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not set(COLUMNAS).issubset(reader.fieldnames or []):
            raise ValueError("ESQUEMA_SOMBRA_INCOMPATIBLE")
        return list(reader)

def _guardar(ruta, registros):
    p = Path(ruta)
    p.parent.mkdir(parents=True, exist_ok=True)
    temporal = p.with_name(p.name + ".tmp")
    with temporal.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNAS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(registros)
    os.replace(temporal, p)

def registrar_candidata(senal, ctx, ruta=RUTA_EVENTOS):
    """Registrar TODAS las rechazadas una sola vez sin alterar su decisión."""
    ts = int(senal.get("vela_senal_from") or ctx.get("vela_senal_from") or 0)
    activo = str(senal.get("activo") or ctx.get("activo") or "")
    patron = str(senal.get("patron") or "")
    direccion = str(senal.get("direccion") or "").lower()
    if not activo or not patron or direccion not in {"call", "put"} or ts <= 0:
        return False
    if str(senal.get("decision_unificada_accion")) != "NO_OPERAR":
        return False
    registros = _leer(ruta)
    clave = _id(activo, patron, direccion, ts)
    # La asociacion se registra incluso ante reintentos del mismo candidato,
    # para poder marcar pertenencias ambiguas, sin duplicar el CSV.
    def registrar_pertenencia():
        try:
            import estado
            from trazabilidad_rondas_sombra import registrar_evento
            registrar_evento(
                "CANDIDATA",
                getattr(estado, "sombra_run_id", ""),
                getattr(estado, "sombra_intento", 0),
                getattr(estado, "sombra_vela_ronda", 0),
                candidato_id=clave,
            )
        except Exception as error:
            print("SOMBRA PERTENENCIA NO DISPONIBLE:", type(error).__name__, flush=True)

    if any(x["id"] == clave for x in registros):
        registrar_pertenencia()
        return False
    fila = {campo: "" for campo in COLUMNAS}
    fila.update({
        "id": clave, "activo": activo, "patron": patron,
        "direccion": direccion, "vela_senal_from": str(ts),
        "decision": "NO_OPERAR",
        # Conservar íntegro el motivo oficial para diagnóstico causal.
        # No cambia la decisión ni la autorización operativa.
        "motivo": str(senal.get("motivo_decision_unificada") or
                      senal.get("razon") or ""),
        "tipo_mercado": str(ctx.get("tipo_mercado") or ""),
        "calidad_mercado": str(ctx.get("calidad_mercado") or ""),
        "accion_precio": str(senal.get("accion_precio") or ""),
        "estado_tendencia": str(ctx.get("estado_tendencia") or ""),
        "calidad_tiempo": "PENDIENTE_VELA_POSTERIOR",
    })
    registros.append(fila)
    _guardar(ruta, registros)
    registrar_pertenencia()
    return True

def resolver_candidatas(activo, ctx, ruta=RUTA_EVENTOS):
    """Solo resuelve velas cerradas presentes causalmente en el contexto."""
    registros = _leer(ruta)
    if not registros:
        return 0
    froms = [int(x) for x in ctx.get("froms", [])]
    opens = ctx.get("opens", [])
    closes = ctx.get("closes", [])
    if not (len(froms) == len(opens) == len(closes)):
        return 0
    if not froms or any(b - a != 60 for a, b in zip(froms, froms[1:])):
        # Un contexto discontinuo no sirve para declarar un resultado.
        return 0
    indices = {t: i for i, t in enumerate(froms)}
    actual = int(ctx.get("vela_senal_from") or 0)
    cambios = 0
    for fila in registros:
        if fila["activo"] != activo or fila["resultado_hipotetico"]:
            continue
        entrada_from = int(fila["vela_senal_from"]) + 60
        # La vela posterior solo se puede evaluar DESPUES de cerrar.
        if entrada_from > actual:
            continue
        if entrada_from < froms[0]:
            # Resultado irrecuperable con el buffer disponible:
            # nunca inventar WIN/LOSS ni ocultarlo entre pendientes recientes.
            if fila["calidad_tiempo"] != "SIN_VELA_POSTERIOR_EN_BUFFER":
                fila["calidad_tiempo"] = "SIN_VELA_POSTERIOR_EN_BUFFER"
                cambios += 1
            continue
        if entrada_from not in indices:
            continue
        indice = indices[entrada_from]
        if indice == 0 or froms[indice - 1] != entrada_from - 60:
            continue
        try:
            precio_entrada = float(opens[indice])
            precio_cierre = float(closes[indice])
        except (TypeError, ValueError, OverflowError):
            continue
        if not all(__import__("math").isfinite(v) for v in (precio_entrada, precio_cierre)):
            continue
        if precio_cierre == precio_entrada:
            resultado = "EMPATE"
        elif (fila["direccion"] == "call" and precio_cierre > precio_entrada) or (
            fila["direccion"] == "put" and precio_cierre < precio_entrada
        ):
            resultado = "WIN"
        else:
            resultado = "LOSS"
        fila.update({
            "vela_entrada_from": str(entrada_from),
            "precio_entrada_hipotetico": str(precio_entrada),
            "precio_cierre_hipotetico": str(precio_cierre),
            "resultado_hipotetico": resultado,
            # No se conoce fill ni payout del broker.
            "calidad_tiempo": "HIPOTETICO_VELA_COMPLETA_SIN_FILL",
        })
        cambios += 1
    if cambios:
        _guardar(ruta, registros)
    return cambios
