"""R9-21: reporte integral offline de salud histórica y OOS, solo lectura.

No ejecuta bot.py, no conecta IQ, no escribe memoria y no certifica
rentabilidad aun cuando los CSV proporcionados coincidan completamente.
"""
import argparse
import hashlib
import json
from pathlib import Path

from scripts.clasificar_historial_fase9 import clasificar_historial
from scripts.auditar_particion_temporal_fase9 import auditar_particion
from scripts.evaluar_oos_descriptivo_fase9 import evaluar_oos


def _huella(ruta):
    """SHA256 del contenido; no modifica el archivo ni confia en mtime."""
    if ruta is None:
        return None
    hash_ = hashlib.sha256()
    with Path(ruta).open("rb") as archivo:
        for bloque in iter(lambda: archivo.read(1024 * 1024), b""):
            hash_.update(bloque)
    return hash_.hexdigest()


def reporte_integral(historial, exportacion_iq=None):
    # El reporte hace varias lecturas independientes. Sin instantanea,
    # mezclaria filas de distintas versiones si el bot escribe al mismo
    # tiempo. Fallar cerrado ANTES de publicar estadisticas compuestas.
    rutas = {"historial": historial}
    if exportacion_iq is not None:
        rutas["exportacion_iq"] = exportacion_iq
    def huellas():
        return {nombre: _huella(ruta) for nombre, ruta in rutas.items()}
    def fallo(causa):
        return {
            "estado": "NO_APTO_PARA_VALIDACION",
            "causa": causa,
            "motivos_no_certificacion": [causa],
            "evidencia_rentabilidad_sostenida": False,
            "memoria_generada": False,
            "habilita_trading": False,
            "modo_operativo": "NINGUNO_SOLO_LECTURA",
        }
    try:
        inicial = huellas()
        clasificacion = clasificar_historial(historial)
        if huellas() != inicial:
            return fallo("FUENTE_MODIFICADA_DURANTE_AUDITORIA")
        particion = auditar_particion(historial)
        if huellas() != inicial:
            return fallo("FUENTE_MODIFICADA_DURANTE_AUDITORIA")
        evaluacion = evaluar_oos(historial, exportacion_iq=exportacion_iq)
        if huellas() != inicial:
            return fallo("FUENTE_MODIFICADA_DURANTE_AUDITORIA")
    except OSError:
        return fallo("FUENTE_NO_DISPONIBLE")
    integridad = (
        clasificacion.get("estado") == "DIAGNOSTICO_NO_CERTIFICADO"
        and clasificacion.get("integridad_conteo") is True
        and particion.get("universo_practice_completo") is True
        and particion.get("separacion_local_sin_fuga") is True
    )
    # Este reporte no decide si hubo ventaja estadistica; solo describe
    # elegibilidad del conjunto para investigaciones posteriores.
    motivos = []
    if not clasificacion.get("integridad_conteo"):
        motivos.append("CLASIFICACION_INCOMPLETA")
    if not particion.get("universo_practice_completo"):
        motivos.append("UNIVERSO_PRACTICE_INCOMPLETO")
    if not particion.get("separacion_local_sin_fuga"):
        motivos.append("TRAIN_OOS_NO_VERIFICADO_LOCALMENTE")
    if evaluacion.get("estado") != "DESCRIPTIVO_NO_VERIFICADO_BROKER":
        motivos.append("OOS_SIN_METRICAS_DESCRIPTIVAS_APTAS")
    if exportacion_iq is None:
        motivos.append("SIN_EXPORTACION_BROKER")
    else:
        cotejo = evaluacion.get("cotejo_offline") or {}
        if not cotejo.get("objetivo_oos_conciliado_completo"):
            motivos.append("COTEJO_OOS_OFFLINE_INCOMPLETO")
    motivos.append("PROCEDENCIA_INDEPENDIENTE_BROKER_NO_CERTIFICADA")
    motivos.append("EFICACIA_CEREBRO_V3_NO_VALIDADA_PROSPECTIVAMENTE")
    return {
        "estado": "DIAGNOSTICO_COMPLETO_SIN_CERTIFICACION"
        if integridad and evaluacion.get("estado") == "DESCRIPTIVO_NO_VERIFICADO_BROKER"
        else "NO_APTO_PARA_VALIDACION",
        "motivos_no_certificacion": motivos,
        "clasificacion": clasificacion,
        "particion": particion,
        "evaluacion_descriptiva": evaluacion,
        "evidencia_rentabilidad_sostenida": False,
        "memoria_generada": False,
        "habilita_trading": False,
        "modo_operativo": "NINGUNO_SOLO_LECTURA",
        "huellas_fuentes_sha256": inicial,
        "integridad_fuentes_estable": True,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("historial", nargs="?", default="historial_bot.csv")
    p.add_argument("--exportacion-iq", default=None)
    args = p.parse_args()
    print(json.dumps(reporte_integral(args.historial, args.exportacion_iq),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
