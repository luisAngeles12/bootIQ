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



def seleccionar_velas_cerradas_vigentes(filas, timestamp_referencia, minimo=200):
    """Rechaza velas abiertas y segmentos antiguos; nunca rellena huecos."""
    if not filas:
        raise ValueError("SIN_VELAS")
    inicio_actual = (int(timestamp_referencia) // 60) * 60
    cerradas = sorted(
        (fila for fila in filas if int(float(fila["from"])) < inicio_actual),
        key=lambda fila: int(float(fila["from"])),
    )
    if len(cerradas) < minimo:
        raise ValueError("VELAS_CERRADAS_INSUFICIENTES")
    tiempos = [int(float(fila["from"])) for fila in cerradas]
    if any(b-a != 60 for a, b in zip(tiempos, tiempos[1:])):
        raise ValueError("HUECO_TEMPORAL_EN_VELAS_CERRADAS")
    if tiempos[0] < CORTE_F3_UTC:
        raise ValueError("VENTANA_ANTERIOR_AL_CORTE_F3")
    esperada = inicio_actual - 60
    if tiempos[-1] != esperada:
        raise ValueError(
            "ULTIMA_VELA_CERRADA_DESACTUALIZADA: "
            + str(tiempos[-1]) + " != " + str(esperada)
        )
    return cerradas


def capturar(raiz=None):
    # Los imports de conexión solo ocurren al ejecutar expresamente el script.
    from config import MODO_CUENTA
    if MODO_CUENTA != "PRACTICE":
        raise RuntimeError("CAPTURA BLOQUEADA: configuración distinta de PRACTICE")

    from conexion import conectar
    from mercado import obtener_activos, _timestamp_servidor_iq
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
    destino_cerradas = destino / "cerradas"
    destino_cerradas.mkdir()

    # Única redirección de ruta; se omite deliberadamente limpiar_data_backtest().
    backtest_data.CARPETA_DATA = str(destino)
    guardados = []
    fallos = []
    for item in top:
        if not backtest_data.descargar_velas_activo(item["tipo"], item["activo"]):
            fallos.append({"activo": item["activo"], "motivo": "DESCARGA_INCOMPLETA"})
            continue
        nombre = (
            item["tipo"] + "_" +
            item["activo"].replace("/", "_").replace(":", "_") + ".csv"
        )
        ruta = destino / nombre
        with ruta.open(newline="", encoding="utf-8") as entrada:
            filas = list(csv.DictReader(entrada))
        referencia_servidor = _timestamp_servidor_iq()
        try:
            cerradas = seleccionar_velas_cerradas_vigentes(
                filas, referencia_servidor,
            )
        except ValueError as error:
            fallos.append({"activo": item["activo"], "motivo": str(error)})
            continue

        archivo_cerrado = destino_cerradas / nombre
        with archivo_cerrado.open("x", newline="", encoding="utf-8") as salida:
            escritor = csv.DictWriter(salida, fieldnames=list(filas[0]))
            escritor.writeheader()
            escritor.writerows(cerradas)
        guardados.append({
            "activo": item["activo"], "tipo": item["tipo"],
            "archivo": "cerradas/" + nombre,
            "archivo_bruto": nombre, "velas": len(cerradas),
            "desde": int(float(cerradas[0]["from"])),
            "hasta": int(float(cerradas[-1]["from"])),
            "referencia_servidor": referencia_servidor,
            "sha256": hashlib.sha256(archivo_cerrado.read_bytes()).hexdigest(),
            "sha256_bruto": hashlib.sha256(ruta.read_bytes()).hexdigest(),
        })

    if fallos:
        diagnostico = {
            "tipo": "TOP_OFICIAL_NO_VALIDADO",
            "total_activos_top": len(top),
            "activos_cerrados_validos": len(guardados),
            "fallos": fallos,
            "autoriza_replay": False,
            "autoriza_operaciones": False,
        }
        with (destino / "diagnostico_no_validado.json").open("x", encoding="utf-8") as salida:
            json.dump(diagnostico, salida, indent=2, ensure_ascii=False)
        resumen = "; ".join(x["activo"] + ": " + x["motivo"] for x in fallos)
        raise RuntimeError(
            "Captura NO validada para TOP oficial (" + str(len(fallos))
            + "/" + str(len(top)) + "): " + resumen
            + " | diagnóstico y archivos conservados en " + str(destino)
        )

    manifiesto = {
        "modo": "PRACTICE", "tipo": "VELAS_CERRADAS_VALIDADAS_SIN_OPERACIONES",
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
