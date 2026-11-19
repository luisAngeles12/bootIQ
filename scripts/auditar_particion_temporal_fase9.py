"""R9-10: partición temporal de auditoría sin crear memoria ni operar.

Acepta únicamente cierres PRACTICE explícitos con PNL no cero, fechas ISO
con zona horaria y order_id único en todo el CSV. No verifica con broker.
Si el conjunto es pequeño, inválido o tiene un corte temporal compartido,
reporta NO_APTO y no ofrece un TRAIN/OOS engañoso.
"""
import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

from scripts.auditar_historial_fase9 import _cierre_explicito, _fecha_iso, _resultado_monetario, _txt


def auditar_particion(
    ruta, proporcion_train=0.70, minimo_train=20, minimo_oos=20,
    offset_origen_minutos=None,
):
    if not (0 < proporcion_train < 1):
        raise ValueError("proporcion_train debe estar entre 0 y 1")
    if minimo_train < 1 or minimo_oos < 1:
        raise ValueError("los minimos deben ser positivos")
    if offset_origen_minutos is not None:
        if (type(offset_origen_minutos) is not int or
                not -1439 <= offset_origen_minutos <= 1439):
            raise ValueError("offset_origen_minutos debe ser entero UTC válido")

    with Path(ruta).open(encoding="utf-8-sig", newline="") as archivo:
        reader = csv.DictReader(archivo)
        campos = set(reader.fieldnames or ())
        requeridos = {"order_id", "modo_cuenta_configurado", "estado",
                      "resultado", "fecha"}
        if not requeridos.issubset(campos):
            return {
                "estado": "NO_APTO", "causa": "COLUMNAS_FALTANTES",
                "columnas_faltantes": sorted(requeridos - campos),
                "train": 0, "oos": 0,
            }
        filas = list(reader)
    frecuencia_ids = Counter(
        str(f.get("order_id") or "").strip() for f in filas
        if str(f.get("order_id") or "").strip()
    )
    excluidas = Counter()
    admisibles = []
    marcas_con_offset_asumido = 0
    aperturas_utc_explicitas = 0
    aperturas_legacy = 0
    cierres_faltantes = 0
    cierres_invalidos = 0
    cierres_anteriores_a_apertura = 0
    for f in filas:
        oid = str(f.get("order_id") or "").strip()
        if not oid:
            excluidas["SIN_ORDER_ID"] += 1
            continue
        if frecuencia_ids[oid] != 1:
            excluidas["ORDER_ID_REPETIDO"] += 1
            continue
        if _txt(f.get("modo_cuenta_configurado")) != "PRACTICE":
            excluidas["MODO_NO_VERIFICADO_PRACTICE"] += 1
            continue
        if not _cierre_explicito(_txt(f.get("estado"))):
            excluidas["SIN_CIERRE_EXPLICITO"] += 1
            continue
        pnl_tipo = _resultado_monetario(f.get("resultado"))
        if pnl_tipo not in {"GANANCIA", "PERDIDA"}:
            excluidas["RESULTADO_NO_VALIDO_TRAIN"] += 1
            continue
        # Un registro nuevo con marca UTC explícita tiene prioridad.
        # Si está presente pero es inválida, NO recuperar con fecha legacy.
        marca_utc = str(f.get("fecha_apertura_registro_local_utc") or "").strip()
        iso = _fecha_iso(marca_utc if marca_utc else f.get("fecha"))
        if iso is None:
            excluidas["APERTURA_UTC_INVALIDA" if marca_utc else "SIN_FECHA_ISO"] += 1
            continue
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None or dt.utcoffset() is None:
            if marca_utc:
                excluidas["APERTURA_UTC_SIN_ZONA"] += 1
                continue
            if offset_origen_minutos is None:
                excluidas["FECHA_SIN_ZONA"] += 1
                continue
            # Hipótesis de auditoría elegida EXPLÍCITAMENTE. Nunca se
            # presenta como zona original confirmada ni como OOS válido.
            dt = dt.replace(tzinfo=timezone(timedelta(
                minutes=offset_origen_minutos
            )))
            marcas_con_offset_asumido += 1
        if marca_utc:
            aperturas_utc_explicitas += 1
        else:
            aperturas_legacy += 1
        apertura_utc = dt.astimezone(timezone.utc)
        cierre_iso = _fecha_iso(f.get("fecha_conciliacion_local_utc"))
        cierre_utc = None
        if cierre_iso is None:
            cierres_faltantes += 1
        else:
            marca = datetime.fromisoformat(cierre_iso)
            if marca.tzinfo is None or marca.utcoffset() is None:
                cierres_invalidos += 1
            else:
                cierre_utc = marca.astimezone(timezone.utc)
                if cierre_utc < apertura_utc:
                    cierres_anteriores_a_apertura += 1
                    cierre_utc = None
        admisibles.append((apertura_utc, oid, pnl_tipo, cierre_utc))

    admisibles.sort(key=lambda x: (x[0], x[1]))
    marcas = sorted(set(f[0] for f in admisibles))
    base = {
        "filas_totales": len(filas),
        "candidatas_tras_filtros": len(admisibles),
        "fechas_utc_distintas": len(marcas),
        "exclusiones": dict(sorted(excluidas.items())),
        "train": 0, "oos": 0,
        "fechas_con_offset_asumido": marcas_con_offset_asumido,
        "aperturas_con_registro_utc_explicito": aperturas_utc_explicitas,
        "aperturas_con_fecha_legacy": aperturas_legacy,
        "aperturas_utc_100pct": (
            aperturas_utc_explicitas == len(admisibles) and bool(admisibles)
        ),
        "cierres_conciliacion_utc_faltantes": cierres_faltantes,
        "cierres_conciliacion_utc_invalidos": cierres_invalidos,
        "cierres_anteriores_a_apertura": cierres_anteriores_a_apertura,
        "cierres_observados_localmente": sum(f[3] is not None for f in admisibles),
        "cierre_columna_semantica": "RESULTADO_PERSISTIDO_LOCAL_NO_LIQUIDACION_IQ",
        "offset_origen_supuesto_minutos": offset_origen_minutos,
        "fecha_columna_semantica": (
            "UTC_REGISTRO_APERTURA_SI_PRESENTE; "
            "LEGACY_FECHA_LOCAL_SIN_ZONA_SI_AUSENTE"
        ),
        "cierre_temporal_verificado": False,
        "apto_para_memoria_productiva": False,
        "nota": (
            "Solo auditoría: fecha es apertura, no cierre conciliado; "
            "el corte de aperturas NO prueba independencia de los resultados "
            "cuando operaciones cruzan la frontera TRAIN/OOS."
        ),
    }
    if len(admisibles) < minimo_train + minimo_oos:
        return {**base, "estado": "NO_APTO", "causa": "MUESTRA_INSUFICIENTE"}
    if len(marcas) < 2:
        return {**base, "estado": "NO_APTO", "causa": "SIN_CORTE_TEMPORAL"}

    # Prohibido dividir dos órdenes del mismo instante UTC entre TRAIN y OOS.
    cortes = []
    for corte in marcas[:-1]:
        n_train = sum(f[0] <= corte for f in admisibles)
        n_oos = len(admisibles) - n_train
        if n_train >= minimo_train and n_oos >= minimo_oos:
            cortes.append((abs(n_train / len(admisibles) - proporcion_train),
                           corte, n_train, n_oos))
    if not cortes:
        return {**base, "estado": "NO_APTO", "causa": "NO_HAY_CORTE_CON_MINIMOS"}
    _, corte, n_train, n_oos = min(cortes)
    primer_oos = next(f[0] for f in admisibles if f[0] > corte)
    assert corte < primer_oos and n_train + n_oos == len(admisibles)
    train_filas = [f for f in admisibles if f[0] <= corte]
    train_sin_cierre = sum(f[3] is None for f in train_filas)
    ultimo_cierre_train = max(
        (f[3] for f in train_filas if f[3] is not None), default=None
    )
    cruces_train_oos = sum(
        f[3] is not None and f[3] >= primer_oos for f in train_filas
    )
    # La etiqueta TRAIN solo era conocida antes de OOS si TODAS las
    # conciliaciones TRAIN preceden estrictamente a la primera apertura OOS.
    separacion_local = (
        train_sin_cierre == 0 and ultimo_cierre_train is not None
        and ultimo_cierre_train < primer_oos
        and marcas_con_offset_asumido == 0
    )
    return {
        **base, "estado": "PRELIMINAR_NO_VERIFICADO_IQ",
        "separacion_local_sin_fuga": separacion_local,
        "train_sin_conciliacion_utc": train_sin_cierre,
        "train_con_resultado_conocido_tarde": cruces_train_oos,
        "ultimo_cierre_train_local_utc": (
            ultimo_cierre_train.isoformat() if ultimo_cierre_train else None
        ),
        "train": n_train, "oos": n_oos,
        "fin_train_utc": corte.isoformat(),
        "inicio_oos_utc": primer_oos.isoformat(),
        "solapamiento_ids": 0,
        "corte_estricto": True,
        "observacion": (
            "Corte de aperturas SOLAMENTE: no se ha demostrado que todas "
            "las órdenes TRAIN hayan cerrado antes de la primera apertura "
            "OOS. La comparación local de conciliación identifica resultados "
            "que se conocieron tarde, pero no comprueba liquidación IQ. "
            "Nunca usar directamente en producción."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("historial", nargs="?", default="historial_bot.csv")
    parser.add_argument(
        "--offset-origen-minutos", type=int, default=None,
        help=("Hipótesis explícita de offset de la máquina al registrar "
              "aperturas sin zona; NO verifica la zona histórica ni autoriza OOS"),
    )
    a = parser.parse_args()
    print(json.dumps(
        auditar_particion(a.historial, offset_origen_minutos=a.offset_origen_minutos),
        ensure_ascii=False, indent=2
    ))


if __name__ == "__main__":
    main()
