import os
import json
import csv
import math
import tempfile
import pandas as pd
import estado
from config import HISTORIAL_CSV, OPERACIONES_PENDIENTES_JSON

def columnas_historial():
    return [
        "fecha",
        "estado",
        "order_id",
        "activo",
        "tipo",
        "direccion",
        "puntaje",
        "patron",
        "rsi",
        "ema9", "ema21", "bb_superior", "bb_media", "bb_inferior",
        "precio_cierre_indicadores",
        "resultado",
        "razon",

        # PASO 5.5C — PARIDAD DE EJECUCIÓN
        "paridad_live_estado",
        "paridad_live_resultado_actual",
        "paridad_live_razon_actual",
        "paridad_live_estado_sombra",
        "paridad_live_motivo_sombra",
        "segundo_antes",
        "segundo_entrada",
        "demora_envio",
        "tiempo_envio_inicio",
        "tiempo_respuesta_iq",
        "tiempo_expiracion",

        # D8-E5 — VELA EXACTA QUE ORIGINO LA SENAL
        "vela_senal_from",
        "precio_senal_open",
        "precio_senal_close",
        "precio_senal_high",
        "precio_senal_low",

        "vela_confirmacion_from",
        "precio_confirmacion_open",
        "precio_confirmacion_close",
        "precio_confirmacion_high",
        "precio_confirmacion_low",

        "auditoria_orden_iq_json",
    ]

COLUMNAS_HISTORIAL = [
    "fecha",
    "estado",
    "order_id",
    "modo_cuenta_configurado",
    "estado_operacion",
    "activo",
    "tipo",
    "direccion",
    "puntaje",
    "patron",
    "rsi",
    # F5: fotografia previa al resultado, sin recalculo a posteriori.
    "ema9", "ema21", "bb_superior", "bb_media", "bb_inferior",
    "precio_cierre_indicadores",
    "resultado",
    "razon",

    # D8-E8 — CONTEXTO PRE-ENTRADA
    "prioridad",
    "score_final",
    "consenso",
    "nivel_consenso",
    "calidad",
    "tipo_mercado",
    "calidad_mercado",
    "score_mercado",
    # Solo auditoria prospectiva; no interviene en autorizaciones.
    "regimen_mercado",
    "razon_regimen",
    "estado_tendencia",
    "fuerza_tendencia",
    "direccion_tendencia",
    "accion_precio",
    "pa_tipo",
    "pa_direccion",
    "pa_fuerza",
    "tipo_setup",
    "calidad_setup",
    "modo_entrada_setup",
    "familia_setup",
    "subtipo_setup",
    "nivel_setup",

    # D7.7C — TRAZABILIDAD DE AUTORIDAD
    "origen_autoridad",
    "decision_sombra_origen",
    "core4_rescate",
    "core4_reglas",
    "directa_ruta_validada",
    "validacion_mercado_ok",
    "razon_validacion_mercado",
    # Fase 4.9: auditoria prospectiva de validacion PA; historicos quedan vacios.
    "validacion_accion_precio_ok",
    "razon_validacion_accion_precio",
    "riesgos_base",
    # Fase 4.10: riesgo compuesto original, solo auditoria prospectiva.
    "auditoria_riesgo_compuesto_json",

    # D8-E6 — TRAZABILIDAD REAL DEL PROTOCOLO LIVE
    # Solo auditoría. No modifica decisión ni ejecución.
    "protocolo_sugerido",
    "protocolo_live_tipo",
    "protocolo_live_estado",
    "accion_confirmacion_ia",
    "protocolo_espera_velas",
    "protocolo_espera_timestamp",
    "motivo_confirmacion_protocolo_live",
    "decision_post_protocolo",
    "probabilidad_post_protocolo",
    "muestra_post_protocolo",
    "confiabilidad_post_protocolo",

    # C-C2 LIVE — identidad exacta producida por motor_protocolos.
    # Solo persistencia/auditoría.
    "auditoria_protocolo_tipo",
    "auditoria_protocolo_subtipo",
    "auditoria_protocolo_familia",
    "auditoria_protocolo_operada",
    "auditoria_protocolo_idx_senal",
    "auditoria_protocolo_idx_entrada",
    "auditoria_protocolo_espera_velas",
    "auditoria_protocolo_motivo",
    "auditoria_protocolo_riesgo",
    "auditoria_protocolo_nivel_riesgo",
    "auditoria_protocolo_indice_confirmacion",
    "auditoria_protocolo_nivel_confirmacion",
    "auditoria_protocolo_accion_confirmacion",
    "auditoria_protocolo_tipo_mercado",
    "auditoria_protocolo_tendencia",
    "auditoria_protocolo_pa_tipo",
    "auditoria_protocolo_probabilidad",

    # D8-R6C — TRAZABILIDAD V3
    "probabilidad_v3",
    "muestra_probabilidad",
    "wins_probabilidad",
    "losses_probabilidad",
    "confiabilidad_probabilidad",
    "nivel_probabilidad_principal",
    "clave_probabilidad_principal",
    "fuente_probabilidad_principal_json",
    "fuente_probabilidad_respaldo_json",

    # D8-R8B — SALUD PROSPECTIVA SOMBRA
    "salud_fuente_n",
    "salud_fuente_wins",
    "salud_fuente_losses",
    "salud_fuente_wr",
    "salud_fuente_prob_historica",
    "salud_fuente_delta_pp",
    "salud_fuente_ultimas5_wr",
    "salud_fuente_ultimas10_wr",

    # PASO 5.5C — PARIDAD DE EJECUCIÓN
    "paridad_live_estado",
    "paridad_live_resultado_actual",
    "paridad_live_razon_actual",
    "paridad_live_estado_sombra",
    "paridad_live_motivo_sombra",
    "segundo_antes",
    "segundo_entrada",
    "demora_envio",
    "tiempo_envio_inicio",
    "tiempo_respuesta_iq",
    "tiempo_expiracion",
    # D8-E5 — VELA EXACTA QUE ORIGINO LA SENAL
    "vela_senal_from",
    "precio_senal_open",
    "precio_senal_close",
    "precio_senal_high",
    "precio_senal_low",
    "vela_confirmacion_from",
    "precio_confirmacion_open",
    "precio_confirmacion_close",
    "precio_confirmacion_high",
    "precio_confirmacion_low",

    "auditoria_orden_iq_json",
    # R9-12: instante local UTC en que se confirma el resultado
    # y se prepara su persistencia atomica; NO es cierre timestamp IQ.
    "fecha_conciliacion_local_utc",
    # R9-14: UTC del registro de apertura; no es el fill del broker.
    "fecha_apertura_registro_local_utc",
]

def guardar_historial(data):
    # El esquema se valida al arrancar bot.py. En la ruta crítica
    # de una apertura evitamos releer y reescribir todo el CSV en
    # cada append. Conservamos protección si el archivo desaparece
    # o queda vacío durante la sesión.
    if (
        not os.path.exists(HISTORIAL_CSV)
        or os.path.getsize(HISTORIAL_CSV) == 0
    ):
        asegurar_historial_csv()

    ruta = os.path.abspath(HISTORIAL_CSV)
    print("Guardando historial en:", ruta)

    cols = COLUMNAS_HISTORIAL
    fila = {col: data.get(col, "") for col in cols}

    try:
        df = pd.DataFrame([fila], columns=cols)
        df.to_csv(
            HISTORIAL_CSV,
            mode="a",
            header=False,
            index=False,
            encoding="utf-8-sig"
        )
    except Exception as e:
        print("Error guardando historial:", e)


def asegurar_historial_csv():
    if not os.path.exists(HISTORIAL_CSV):
        df = pd.DataFrame(columns=COLUMNAS_HISTORIAL)
        df.to_csv(HISTORIAL_CSV, index=False, encoding="utf-8-sig")
        return

    if os.path.getsize(HISTORIAL_CSV) == 0:
        df = pd.DataFrame(columns=COLUMNAS_HISTORIAL)
        df.to_csv(HISTORIAL_CSV, index=False, encoding="utf-8-sig")
        return

    try:
        # Una migracion de esquema no debe convertir order_id
        # en entero: "00123" y "123" no son la misma identidad.
        df = pd.read_csv(
            HISTORIAL_CSV, encoding="utf-8-sig",
            dtype={"order_id": "string"}, keep_default_na=False,
        )

        if df.empty:
            df = pd.DataFrame(columns=COLUMNAS_HISTORIAL)
            df.to_csv(HISTORIAL_CSV, index=False, encoding="utf-8-sig")
            return

        columnas_actuales = list(df.columns)

        if "order_id" not in columnas_actuales:
            # Un historial sin identidad verificable NO se puede migrar
            # reescribiendolo a cero: conservar bytes para recuperacion.
            raise ValueError("HISTORIAL_SIN_ORDER_ID_NO_MIGRAR")

        # Reconstruir las columnas una sola vez sin DataFrame.reindex:
        # algunas combinaciones NumPy/pandas fallan al migrar CSV legacy
        # con muchas columnas ausentes (_NoValueType). Se conserva el
        # order_id textual y los valores de todas las columnas existentes.
        df = pd.DataFrame(
            {
                columna: df[columna] if columna in df.columns else ""
                for columna in COLUMNAS_HISTORIAL
            },
            index=df.index,
        )
        df.to_csv(HISTORIAL_CSV, index=False, encoding="utf-8-sig")

    except Exception as e:
        # Fallar preservando el CSV; el reinicio vacio destruia ordenes
        # historicas cuando faltaban campos o existian filas mal formadas.
        print("Historial no migrado: archivo original conservado:", e)
        raise


def actualizar_historial_cierre(order_id, resultado, auditoria_orden_iq_json=""):
    # Import dentro de la funcion para conservar pruebas AST aisladas.
    from datetime import datetime, timezone
    if (
        not os.path.exists(HISTORIAL_CSV)
        or os.path.getsize(HISTORIAL_CSV) == 0
    ):
        asegurar_historial_csv()

    # La conciliacion de cierres no necesita operaciones vectorizadas.
    # Evita un fallo reproducido con NumPy/pandas en Windows y conserva
    # order_id como texto exacto, incluidos ceros iniciales.
    ruta_temporal = None
    try:
        resultado_num = float(resultado)
        if not math.isfinite(resultado_num):
            raise ValueError("RESULTADO_CIERRE_NO_FINITO")
        resultado_num = round(resultado_num, 2)
        order_id = str(order_id)

        with open(HISTORIAL_CSV, "r", encoding="utf-8-sig", newline="") as archivo:
            lector = csv.DictReader(archivo)
            columnas = lector.fieldnames
            if not columnas or "order_id" not in columnas:
                print("Historial sin order_id. No se puede actualizar cierre.")
                return False
            if len(columnas) != len(set(columnas)):
                raise ValueError("COLUMNAS_HISTORIAL_DUPLICADAS")

            filas = list(lector)
            if any(None in fila for fila in filas):
                raise ValueError("FILA_HISTORIAL_CON_COLUMNAS_EXTRA")

        # Capturar una sola marca UTC justo antes de la escritura.
        # Solo aparece en el CSV si el reemplazo atomico culmina.
        fecha_conciliacion = datetime.now(timezone.utc).isoformat()
        encontradas = 0
        for fila in filas:
            if fila["order_id"] == order_id:
                fila["estado"] = "CERRADA"
                fila["resultado"] = resultado_num
                if "fecha_conciliacion_local_utc" in columnas:
                    # En reintentos no sobreescribir una marca ya persistida.
                    if not str(fila.get("fecha_conciliacion_local_utc") or "").strip():
                        fila["fecha_conciliacion_local_utc"] = fecha_conciliacion
                # Telemetria de precio SOLO si la cache devolvio evidencia
                # validada y la columna ya existe. Sin datos no se inventa.
                if (
                    auditoria_orden_iq_json
                    and "auditoria_orden_iq_json" in columnas
                ):
                    fila["auditoria_orden_iq_json"] = auditoria_orden_iq_json
                encontradas += 1

        if encontradas == 0:
            print("No existe historial para actualizar:", order_id)
            return False

        # Escribir y cerrar el archivo temporal antes del reemplazo.
        # Una excepcion deja intacto el CSV existente.
        carpeta = os.path.dirname(os.path.abspath(HISTORIAL_CSV))
        with tempfile.NamedTemporaryFile(
            mode="w", newline="", encoding="utf-8-sig",
            dir=carpeta, prefix=".historial_cierre_", suffix=".csv",
            delete=False,
        ) as temporal:
            ruta_temporal = temporal.name
            escritor = csv.DictWriter(temporal, fieldnames=columnas)
            escritor.writeheader()
            escritor.writerows(filas)

        os.replace(ruta_temporal, HISTORIAL_CSV)
        ruta_temporal = None
        print("Historial actualizado:", order_id, resultado_num)
        return True

    except Exception as e:
        print("Error actualizando historial:", e)
        return False
    finally:
        if ruta_temporal and os.path.exists(ruta_temporal):
            os.unlink(ruta_temporal)


def cargar_historial():
    if not os.path.exists(HISTORIAL_CSV):
        return None

    if os.path.getsize(HISTORIAL_CSV) == 0:
        return None

    try:
        df = pd.read_csv(HISTORIAL_CSV, encoding="utf-8-sig")

        if df.empty:
            return None

        if "estado" not in df.columns or "resultado" not in df.columns:
            return None

        df = df[df["estado"] == "CERRADA"]
        df["resultado"] = pd.to_numeric(df["resultado"], errors="coerce")
        df = df.dropna(subset=["resultado"])

        if df.empty:
            return None

        return df

    except Exception:
        return None


def guardar_operaciones_pendientes():
    try:
        with open(OPERACIONES_PENDIENTES_JSON, "w", encoding="utf-8") as f:
            json.dump(estado.operaciones_abiertas, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("Error guardando operaciones pendientes:", e)


def cargar_operaciones_pendientes():
    if not os.path.exists(OPERACIONES_PENDIENTES_JSON):
        return
    try:
        with open(OPERACIONES_PENDIENTES_JSON, "r", encoding="utf-8") as f:
            estado.operaciones_abiertas = json.load(f)
        if not isinstance(estado.operaciones_abiertas, list):
            estado.operaciones_abiertas = []
        print("Operaciones pendientes recuperadas:", len(estado.operaciones_abiertas))
    except Exception as e:
        print("Error cargando operaciones pendientes:", e)
        estado.operaciones_abiertas = []


def winrate_activo(activo):
    df = cargar_historial()
    if df is None:
        return 0.5
    df = df[df["activo"] == activo]
    if len(df) < 5:
        return 0.5
    return len(df[df["resultado"] > 0]) / len(df)


def winrate_patron(patron):
    df = cargar_historial()
    if df is None:
        return 0.5
    df = df[df["patron"] == patron]
    if len(df) < 5:
        return 0.5
    return len(df[df["resultado"] > 0]) / len(df)


def perdidas_recientes_activo(activo, cantidad=2):
    df = cargar_historial()
    if df is None:
        return False
    df = df[df["activo"] == activo]
    if len(df) < cantidad:
        return False
    return all(df.tail(cantidad)["resultado"] < 0)


def ajustar_por_memoria(activo, patron, puntaje):
    wr_activo = winrate_activo(activo)
    wr_patron = winrate_patron(patron)
    if wr_activo >= 0.65:
        puntaje += 1
    if wr_activo <= 0.35:
        puntaje -= 2
    if wr_patron >= 0.65:
        puntaje += 1
    if wr_patron <= 0.35:
        puntaje -= 1
    if perdidas_recientes_activo(activo, 2):
        puntaje -= 2
    return puntaje
def perdidas_consecutivas_activo(activo, cantidad=3):
    df = cargar_historial()

    if df is None:
        return False

    df = df[df["activo"] == activo]

    if len(df) < cantidad:
        return False

    ultimas = df.tail(cantidad)

    return all(ultimas["resultado"] < 0)


def perdidas_consecutivas_patron(patron, cantidad=3):
    df = cargar_historial()

    if df is None:
        return False

    df = df[df["patron"] == patron]

    if len(df) < cantidad:
        return False

    ultimas = df.tail(cantidad)

    return all(ultimas["resultado"] < 0)