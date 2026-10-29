"""Evaluador causal en sombra sobre capturas nuevas PRACTICE de velas 1s.

No importa broker, no emite operaciones, no calibra filtros a posteriori.
"""
import argparse
import csv
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
        cierre_senal = float(velas[t]["close"])
        # Después del cierre en t+1, vencimiento al cierre de t+horizonte.
        indice_salida = i + horizonte
        if indice_salida >= len(marcas):
            resultado = "SIN_FUTURO"
        else:
            cierre_salida = float(velas[marcas[indice_salida]]["close"])
            if cierre_salida == cierre_senal:
                resultado = "EMPATE"
            elif (cierre_salida > cierre_senal) == (direccion == "call"):
                resultado = "WIN"
            else:
                resultado = "LOSS"
        demoras = [velas[marcas[j]].get("_latencia_primera_recepcion_s")
                   for j in range(i - 2, i + 1)]
        if any(d is None for d in demoras):
            calidad = "LATENCIA_NO_REGISTRADA"
        elif any(d > 1 for d in demoras):
            calidad = "DETECCION_TARDIA"
        else:
            calidad = "TIEMPO_VERIFICADO"
        resultados.append({"timestamp_senal": t, "direccion": direccion,
                           "resultado": resultado, "calidad_tiempo": calidad})
        ocupado_hasta = t + horizonte + 1
    return resultados


def resumen_sesion(eventos):
    conteos = {k: sum(e["resultado"] == k for e in eventos)
               for k in ("WIN", "LOSS", "EMPATE", "SIN_FUTURO")}
    validas = conteos["WIN"] + conteos["LOSS"]
    return {
        "senales_no_solapadas": len(eventos),
        **conteos,
        "wr_hipotetico": round(100 * conteos["WIN"] / validas, 2) if validas else None,
        "con_tiempo_verificado": sum(e.get("calidad_tiempo") == "TIEMPO_VERIFICADO"
                                     for e in eventos),
        "detecciones_tardias": sum(e.get("calidad_tiempo") == "DETECCION_TARDIA"
                                    for e in eventos),
        "sin_latencia_registrada": sum(e.get("calidad_tiempo") == "LATENCIA_NO_REGISTRADA"
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
        from diagnostico_preparacion_practice import diagnosticar_preparacion
        print("DIAGNOSTICO_PREPARACION_SOMBRA:", diagnosticar_preparacion(velas))
    print("TOTAL", resumen_sesion(totales))
    print("TOTAL_POR_DIRECCION:", diagnostico_direcciones(totales))
    from validar_evidencia_practice import verificar_evidencia_sostenida
    print("EVIDENCIA_SOSTENIDA_PRACTICE:", verificar_evidencia_sostenida(sesiones))
    from estudio_multisesion_practice import estudiar_sesiones
    print("ESTUDIO_TRES_ESTRATEGIAS_MULTISESION:",
          estudiar_sesiones(sesiones_estrategias))


if __name__ == "__main__":
    main()
