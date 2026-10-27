"""Captura aislada de velas para Fase 3, PRACTICE y sin órdenes.

No cambia la selección oficial TOP, no elimina datasets ni edita estrategia.
La captura cruda NO es todavía un replay de señales A/B ni evidencia de PNL.
"""

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


MAX_MERCADOS = 20
CORTE_F3_UTC = datetime(2026, 10, 26, tzinfo=timezone.utc).timestamp()


def validar_top_oficial(activos):
    """Acepta el TOP oficial íntegro; nunca inventa ni completa activos."""
    if not isinstance(activos, list) or not 1 <= len(activos) <= MAX_MERCADOS:
        raise ValueError("TOP oficial vacío, inválido o superior a 20")
    if any(not isinstance(x, dict) or not x.get("activo")
           or x.get("tipo") != "turbo" for x in activos):
        raise ValueError("Elemento TOP sin activo/tipo turbo válido")
    claves = [(str(x["tipo"]), str(x["activo"])) for x in activos]
    if len(set(claves)) != len(claves):
        raise ValueError("TOP oficial con activos duplicados")
    return list(activos)


def capturar(raiz=None):
    # Los imports de conexión solo ocurren al ejecutar expresamente el script.
    from config import MODO_CUENTA
    if MODO_CUENTA != "PRACTICE":
        raise RuntimeError("CAPTURA BLOQUEADA: configuración distinta de PRACTICE")

    from conexion import conectar
    from mercado import obtener_activos
    import backtest_data
    import estado

    conectar()
    if estado.Iq is None or estado.Iq.get_balance_mode() != "PRACTICE":
        raise RuntimeError("CAPTURA BLOQUEADA: balance PRACTICE no confirmado")

    top = validar_top_oficial(obtener_activos())
    ahora = datetime.now(timezone.utc)
    raiz = Path(raiz) if raiz is not None else Path.home() / "bootIQ_fase3_capturas"
    destino = raiz / ahora.strftime("%Y%m%dT%H%M%S_%fZ")
    destino.mkdir(parents=True, exist_ok=False)

    # Única redirección de ruta; se omite deliberadamente limpiar_data_backtest().
    backtest_data.CARPETA_DATA = str(destino)
    guardados = []
    for item in top:
        if not backtest_data.descargar_velas_activo(item["tipo"], item["activo"]):
            raise RuntimeError(
                "Captura incompleta: revisar directorio conservado " + str(destino)
            )
        nombre = (
            item["tipo"] + "_" +
            item["activo"].replace("/", "_").replace(":", "_") + ".csv"
        )
        ruta = destino / nombre
        with ruta.open(newline="", encoding="utf-8") as entrada:
            filas = list(csv.DictReader(entrada))
        if not filas:
            raise RuntimeError("CSV sin velas: " + str(ruta))
        inicio = int(float(filas[0]["from"]))
        fin = int(float(filas[-1]["from"]))
        if inicio < CORTE_F3_UTC or fin < CORTE_F3_UTC:
            raise RuntimeError(
                "Captura no es totalmente posterior al corte F3: " + str(ruta)
            )
        guardados.append({
            "activo": item["activo"], "tipo": item["tipo"],
            "archivo": nombre, "velas": len(filas),
            "desde": inicio, "hasta": fin,
            "sha256": hashlib.sha256(ruta.read_bytes()).hexdigest(),
        })

    manifiesto = {
        "modo": "PRACTICE", "tipo": "VELAS_CRUDAS_SIN_OPERACIONES",
        "capturado_utc": ahora.isoformat(),
        "corte_prospectivo_utc": CORTE_F3_UTC,
        "total_activos": len(top), "datasets": guardados,
        "es_evidencia_de_trades": False,
        "autoriza_operaciones": False,
    }
    with (destino / "manifest.json").open("x", encoding="utf-8") as salida:
        json.dump(manifiesto, salida, indent=2, ensure_ascii=False)
    return destino, manifiesto


if __name__ == "__main__":
    directorio, resultado = capturar()
    print("CAPTURA_COMPLETA:", directorio)
    print("ACTIVOS:", resultado["total_activos"])
    print("VELAS CRUDAS, NO SEÑALES NI OPERACIONES")
