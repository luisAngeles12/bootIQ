"""Evaluador causal en sombra sobre capturas nuevas PRACTICE de velas 1s.

No importa broker, no emite operaciones, no calibra filtros a posteriori.
"""
import argparse
import csv
from datetime import datetime, timezone
from pathlib import Path

from sondear_velas_1s_practice import evaluar_micro_rechazo_sombra


def leer_captura(ruta):
    with Path(ruta).open(newline="", encoding="utf-8") as archivo:
        lector = csv.DictReader(archivo)
        if not {"activo", "timestamp_utc", "open", "high", "low", "close", "capturado_en_utc"} <= set(lector.fieldnames or []):
            raise ValueError("FORMATO_CAPTURA_INVALIDO")
        filas = list(lector)
    if not filas:
        raise ValueError("SIN_VELAS")
    activos = {fila["activo"] for fila in filas}
    marcas_captura = {fila["capturado_en_utc"] for fila in filas}
    if len(activos) != 1 or len(marcas_captura) != 1:
        raise ValueError("SESIONES_MEZCLADAS")
    try:
        marca = datetime.fromisoformat(next(iter(marcas_captura)))
    except (ValueError, TypeError):
        raise ValueError("MARCA_CAPTURA_INVALIDA") from None
    if marca.tzinfo is None or marca.utcoffset().total_seconds() != 0:
        raise ValueError("MARCA_CAPTURA_NO_UTC")
    if marca.timestamp() > datetime.now(timezone.utc).timestamp() + 5:
        raise ValueError("MARCA_CAPTURA_EN_FUTURO")
    velas = {}
    for fila in filas:
        t = int(fila["timestamp_utc"])
        if t in velas:
            raise ValueError("TIMESTAMP_DUPLICADO")
        demora_texto = fila.get("latencia_primera_recepcion_s", "")
        demora = None if demora_texto in (None, "") else int(demora_texto)
        if demora is not None and demora < 0:
            raise ValueError("LATENCIA_INVALIDA")
        velas[t] = {
            "from": t, "open": float(fila["open"]), "close": float(fila["close"]),
            "max": float(fila["high"]), "min": float(fila["low"]),
            "_latencia_primera_recepcion_s": demora,
        }
    if max(velas) + 1 > marca.timestamp():
        raise ValueError("VELA_POSTERIOR_A_CAPTURA")
    from captura_fresca_practice import preparar_filas
    preparar_filas(next(iter(activos)), velas, min(velas), max(velas) + 1)
    return next(iter(activos)), velas


def evaluar_sesion(velas, horizonte=60):
    """Evalua cada señal una sola vez; salida siguiente al cierre de horizonte.

    La selección depende solo de velas disponibles en el instante de detección.
    No se permite abrir una segunda posición durante los próximos 'horizonte' s.
    """
    if not 1 <= horizonte <= 3600:
        raise ValueError("HORIZONTE_INVALIDO")
    marcas = sorted(velas)
    if any(b - a != 1 for a, b in zip(marcas, marcas[1:])):
        raise ValueError("HUECO_TEMPORAL")
    resultados = []
    ocupado_hasta = -1
    # 20 velas previas + 3 velas de patrón, todas cerradas al instante t+1.
    for i in range(22, len(marcas)):
        t = marcas[i]
        if t < ocupado_hasta:
            continue
        contexto = {k: velas[k] for k in marcas[i - 22:i + 1]}
        eventos = evaluar_micro_rechazo_sombra(contexto, t + 1)
        if len(eventos) != 1:
            continue  # ambigüedad de direcciones: ninguna operacion
        direccion = eventos[0]["direccion"]
        if direccion not in ("call", "put"):
            continue  # una direccion desconocida no equivale a PUT
        # La decision solo existe tras el cierre t+1. Ese cierre ya es
        # informacion conocida, NO un precio ejecutable. La primera
        # apertura hipotetica es la vela siguiente (sin orden real).
        indice_entrada = i + 1
        indice_salida = i + horizonte
        if indice_salida >= len(marcas):
            resultado = "SIN_FUTURO"
        else:
            precio_entrada = float(velas[marcas[indice_entrada]]["open"])
            precio_salida = float(velas[marcas[indice_salida]]["close"])
            if precio_salida == precio_entrada:
                resultado = "EMPATE"
            elif (precio_salida > precio_entrada) == (direccion == "call"):
                resultado = "WIN"
            else:
                resultado = "LOSS"
        # Todas las 23 velas utilizadas para decidir deben haberse recibido
        # antes de t+1; comprobar solo las tres del patron permite contexto
        # historico tardio y crea una falsa validacion causal.
        demoras = [(marcas[j], velas[marcas[j]].get("_latencia_primera_recepcion_s"))
                   for j in range(i - 22, i + 1)]
        if any(d is None for _, d in demoras):
            calidad = "LATENCIA_NO_REGISTRADA"
        elif any(type(d) is not int or d < 0 for _, d in demoras):
            calidad = "LATENCIA_INVALIDA_O_NO_REGISTRADA"
        elif any(instante + 1 + d > t + 1 for instante, d in demoras):
            calidad = "DETECCION_TARDIA"
        else:
            calidad = "TIEMPO_VERIFICADO"
        resultados.append({
            "timestamp_senal": t,
            "timestamp_entrada_hipotetica": t + 1,
            "timestamp_salida_hipotetica": marcas[indice_salida]
            if indice_salida < len(marcas) else t + horizonte,
            "modelo_entrada": "APERTURA_PRIMERA_VELA_FUTURA_NO_EJECUTADA",
            "direccion": direccion,
            "resultado": resultado,
            "calidad_tiempo": calidad,
        })
        ocupado_hasta = t + horizonte + 1
    return resultados


def resumen_sesion(eventos):
    conteos = {k: sum(e["resultado"] == k for e in eventos)
               for k in ("WIN", "LOSS", "EMPATE", "SIN_FUTURO")}
    validas = conteos["WIN"] + conteos["LOSS"]
    verificadas = [e for e in eventos if e.get("calidad_tiempo") == "TIEMPO_VERIFICADO"
                   and e["resultado"] in ("WIN", "LOSS")]
    wins_verificados = sum(e["resultado"] == "WIN" for e in verificadas)
    return {
        "senales_no_solapadas": len(eventos),
        **conteos,
        "wr_hipotetico": round(100 * conteos["WIN"] / validas, 2) if validas else None,
        "resultados_con_tiempo_verificado": len(verificadas),
        "wr_hipotetico_con_tiempo_verificado": (
            round(100 * wins_verificados / len(verificadas), 2) if verificadas else None
        ),
        "con_tiempo_verificado": sum(e.get("calidad_tiempo") == "TIEMPO_VERIFICADO"
                                     for e in eventos),
        "detecciones_tardias": sum(e.get("calidad_tiempo") == "DETECCION_TARDIA"
                                    for e in eventos),
        "sin_latencia_registrada": sum(e.get("calidad_tiempo") == "LATENCIA_NO_REGISTRADA"
                                       for e in eventos),
        "latencia_invalida": sum(e.get("calidad_tiempo") == "LATENCIA_INVALIDA_O_NO_REGISTRADA"
                                for e in eventos),
        "advertencia": "HIPOTETICO_NO_OPERACIONES_REALES_NI_RENDIMIENTO_GARANTIZADO",
    }


def diagnostico_direcciones(eventos):
    """Desglose descriptivo fijo; NO selecciona ni invierte estrategias."""
    return {
        direccion: resumen_sesion([e for e in eventos if e["direccion"] == direccion])
        for direccion in ("call", "put")
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directorio", help="Directorio de capturas nuevas PRACTICE")
    parser.add_argument("--horizonte", type=int, default=60)
    args = parser.parse_args()
    carpeta = Path(args.directorio)
    rutas = sorted(carpeta.glob("practice_1s_*.csv"))
    if not rutas:
        raise SystemExit("SIN_CAPTURAS_NUEVAS")
    totales = []
    sesiones = []
    sesiones_estrategias = []
    for ruta in rutas:
        activo, velas = leer_captura(ruta)
        eventos = evaluar_sesion(velas, args.horizonte)
        totales.extend(eventos)
        sesiones.append((activo, min(velas), eventos))
        sesiones_estrategias.append((activo, min(velas), velas))
        print(activo, ruta.name, resumen_sesion(eventos))
        print("DESGLOSE_POR_DIRECCION:", diagnostico_direcciones(eventos))
        from comparar_estrategias_frescas import resumen_comparativa
        print("COMPARATIVA_TRES_ESTRATEGIAS:", resumen_comparativa(velas))
        from evaluar_arbitro_fresco import resumen_arbitro
        print("ARBITRO_COMPLETO_SOMBRA:", resumen_arbitro(velas))
        from diagnostico_preparacion_practice import diagnosticar_preparacion
        print("DIAGNOSTICO_PREPARACION_SOMBRA:", diagnosticar_preparacion(velas))
    print("TOTAL", resumen_sesion(totales))
    print("TOTAL_POR_DIRECCION:", diagnostico_direcciones(totales))
    from validar_evidencia_practice import verificar_evidencia_sostenida
    print("EVIDENCIA_SOSTENIDA_PRACTICE:", verificar_evidencia_sostenida(sesiones))
    from estudio_multisesion_practice import estudiar_sesiones
    print("ESTUDIO_TRES_ESTRATEGIAS_MULTISESION:",
          estudiar_sesiones(sesiones_estrategias))
    from validacion_oos_practice import validar_oos_capturas
    print("VALIDACION_OOS_POR_DIAS:",
          validar_oos_capturas(sesiones_estrategias))
    from estudio_arbitro_multisesion_practice import estudiar_capturas_arbitro
    print("VALIDACION_OOS_ARB_CEREBRO_COMPLETO:",
          estudiar_capturas_arbitro(sesiones_estrategias))


if __name__ == "__main__":
    main()
