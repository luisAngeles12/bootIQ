"""Evaluar una memoria TRAIN candidata contra VALIDACION, sin ordenes.

Recrea la memoria esperada con TRAIN en archivo temporal y compara bytes:
impide evaluar una memoria de procedencia no verificable como si fuese TRAIN.
El OOS solo se consulta; no realimenta la memoria ni habilita operaciones.
"""
import argparse
import csv
import hashlib
import json
import tempfile
from collections import defaultdict
from pathlib import Path

from verificar_particion_train_valid_practice import verificar_particion


def _leer_csv(ruta):
    with Path(ruta).open(encoding="utf-8-sig", newline="") as archivo:
        return list(csv.DictReader(archivo))


def _hash_archivo(ruta):
    digest = hashlib.sha256()
    with Path(ruta).open("rb") as archivo:
        for bloque in iter(lambda: archivo.read(65536), b""):
            digest.update(bloque)
    return digest.hexdigest()


def evaluar_candidata_oos(train, validacion, ruta_candidata):
    train = list(train)
    validacion = list(validacion)
    check = verificar_particion(train, validacion)
    if not check["apta_para_experimento_cronologico"]:
        raise ValueError("PARTICION_TEMPORAL_NO_APTA")
    if len(train) < 20 or len(validacion) < 20:
        raise ValueError("MUESTRA_INSUFICIENTE_20_POR_GRUPO")
    for row in train + validacion:
        if str(row.get("resultado_hipotetico") or "").strip().upper() not in {"WIN", "LOSS"}:
            raise ValueError("ETIQUETA_HIPOTETICA_AUSENTE_O_INVALIDA")

    # Solo se admite como candidata la memoria reproducible a partir de TRAIN.
    from motor_aprendizaje_historico import (
        generar_aprendizaje_desde_resultados,
        cargar_aprendizaje,
        evaluar_aprendizaje_historico,
    )
    with tempfile.TemporaryDirectory(prefix="bootiq_oos_") as temporal:
        esperado = Path(temporal) / "memoria_esperada.csv"
        generar_aprendizaje_desde_resultados(
            train, ruta=str(esperado), incluir_hipoteticos=True,
        )
        if _hash_archivo(esperado) != _hash_archivo(ruta_candidata):
            raise ValueError("CANDIDATA_NO_COINCIDE_CON_TRAIN")
    memoria = cargar_aprendizaje(ruta=str(ruta_candidata))
    if not memoria:
        raise ValueError("MEMORIA_CANDIDATA_VACIA")

    grupos = defaultdict(lambda: {"n": 0, "wins": 0, "losses": 0})
    fuentes = defaultdict(int)
    con_fuentes = 0
    sin_fuentes = 0
    for row in validacion:
        respuesta = evaluar_aprendizaje_historico(row, memoria=memoria)
        usa_fuentes = bool(respuesta.get("aprendizaje_encontrado"))
        con_fuentes += int(usa_fuentes)
        sin_fuentes += int(not usa_fuentes)
        if not usa_fuentes:
            banda = "SIN_FUENTE"
        else:
            try:
                prob = float(respuesta.get("probabilidad_estimada"))
            except (ValueError, TypeError):
                banda = "PROBABILIDAD_INVALIDA"
            else:
                if prob < 40:
                    banda = "MENOR_40"
                elif prob < 50:
                    banda = "40_A_49"
                elif prob < 60:
                    banda = "50_A_59"
                elif prob < 70:
                    banda = "60_A_69"
                else:
                    banda = "70_O_MAS"
            principal = respuesta.get("fuente_probabilidad_principal") or {}
            if isinstance(principal, dict):
                nivel = str(principal.get("nivel") or "SIN_NIVEL")
                fuentes[nivel] += 1
        grupo = grupos[banda]
        grupo["n"] += 1
        if str(row["resultado_hipotetico"]).strip().upper() == "WIN":
            grupo["wins"] += 1
        else:
            grupo["losses"] += 1
    bandas = {}
    for banda, grupo in sorted(grupos.items()):
        n = grupo["n"]
        bandas[banda] = {
            **grupo,
            "winrate_observado_pct": round(100 * grupo["wins"] / n, 2),
        }
    return {
        "modo": "EVALUACION_MEMORIA_OOS_NO_AUTORIZANTE",
        "train_registros": len(train),
        "validacion_registros": len(validacion),
        "separacion_temporal_verificada": True,
        "huella_memoria_coincide_con_train": True,
        "huella_sha256_memoria": _hash_archivo(ruta_candidata),
        "senales_con_fuente": con_fuentes,
        "senales_sin_fuente": sin_fuentes,
        "cobertura_pct": round(100 * con_fuentes / len(validacion), 2),
        "por_banda_probabilidad": bandas,
        "fuente_principal_por_nivel": dict(sorted(fuentes.items())),
        "limitaciones": [
            "Los resultados hipoteticos no equivalen a ejecucion real.",
            "Cobertura y bandas no prueban rentabilidad ni causalidad.",
            "Se requiere validacion posterior independiente para cambios productivos.",
        ],
        "cambios_operativos_autorizados": False,
        "memoria_productiva_modificada": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("train")
    parser.add_argument("validacion")
    parser.add_argument("candidata")
    args = parser.parse_args()
    reporte = evaluar_candidata_oos(
        _leer_csv(args.train), _leer_csv(args.validacion), args.candidata
    )
    print(json.dumps(reporte, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
