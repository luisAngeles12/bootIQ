import time
import estado
from config import (
    MOSTRAR_ESTADISTICAS_CADA_RONDAS,
    STOP_LOSS,
    STOP_WIN,
    MAX_OPERACIONES_ABIERTAS,
    VENTANA_ENTRADA_INICIO,
    VENTANA_ENTRADA_FIN,
    MIN_PRIORIDAD_OPERAR
)
from utils import segundo_actual,registrar_bloqueo, imprimir_resumen_ronda, reiniciar_metricas_ronda
from conexion import conectar
from historial import asegurar_historial_csv, cargar_operaciones_pendientes
from mercado import obtener_activos
from estrategia import analizar_activo
from entrada import (
    entrada_rapida_disponible,
    guardar_senal_pendiente,
    procesar_senales_pendientes,
    motivo_pendiente_por_accion_precio
)
from operaciones import revisar_operaciones_abiertas, abrir_operacion
from estadisticas import imprimir_estadisticas

def main():
    
    conectar()
    asegurar_historial_csv()
    cargar_operaciones_pendientes()

    ronda_estadisticas = 0
    operaciones_desde_resumen_mercado = 0
    ultima_impresion_estado = 0
    ultima_impresion_resumen = 0

    # Nuevo: reporte general de mercados cada 5 minutos.
    if not hasattr(estado, "ultimo_reporte_mercados"):
        estado.ultimo_reporte_mercados = 0

    if not hasattr(estado, "snapshot_mercados"):
        estado.snapshot_mercados = {}

    while True:
        revisar_operaciones_abiertas()
        procesar_senales_pendientes(abrir_operacion)

        if not estado.Iq.check_connect():
            print("Reconectando...")
            try:
                estado.Iq.connect()
            except Exception:
                pass
            time.sleep(3)
            continue

        balance_actual = estado.Iq.get_balance()
        ganancia_neta = balance_actual - estado.balance_inicial

        ahora = time.time()

        # ==========================================
        # REPORTE GENERAL DE MERCADOS CADA 5 MIN
        # ==========================================
        if ahora - estado.ultimo_reporte_mercados >= 300:
            if estado.snapshot_mercados:
                print("\n" + "=" * 80)
                print("REPORTE GENERAL DE MERCADOS")
                print("=" * 80)

                for activo, info in sorted(estado.snapshot_mercados.items()):
                    print(
                        activo,
                        "|",
                        info.get("tipo", "INDEFINIDO"),
                        "|",
                        info.get("calidad", "SIN_DATOS"),
                        "| score:",
                        info.get("score", 0),
                        "|",
                        info.get("tendencia", "INDEFINIDA"),
                        "| fuerza:",
                        round(info.get("fuerza", 0), 2)
                    )

                print("=" * 80 + "\n")

            estado.ultimo_reporte_mercados = ahora

        # Imprime balance solo cada 20 segundos para no llenar la terminal.
        if ahora - ultima_impresion_estado >= 20:
            print(
                "\nBalance:",
                round(balance_actual, 2),
                "| Neto:",
                round(ganancia_neta, 2),
                "| Abiertas:",
                len(estado.operaciones_abiertas)
            )
            ultima_impresion_estado = ahora

        ronda_estadisticas += 1

        if ronda_estadisticas >= MOSTRAR_ESTADISTICAS_CADA_RONDAS:
            imprimir_estadisticas()
            ronda_estadisticas = 0

        if ganancia_neta <= STOP_LOSS:
            print("Stop loss alcanzado. Bot detenido.")
            break

        if ganancia_neta >= STOP_WIN:
            print("Stop win alcanzado. Bot detenido.")
            break

        segundo = segundo_actual()

        # Ventana de búsqueda de entrada.
        if not (VENTANA_ENTRADA_INICIO <= segundo <= VENTANA_ENTRADA_FIN):

            if time.time() - ultima_impresion_resumen >= 60:
                if (
                    estado.metricas_ronda.get("mercados_analizados", 0) > 0
                    or estado.metricas_ronda.get("senales_detectadas", 0) > 0
                    or estado.metricas_ronda.get("entradas_abiertas", 0) > 0
                ):
                    imprimir_resumen_ronda()
            
                ultima_impresion_resumen = time.time()
                time.sleep(0.25)
                continue
            
            if len(estado.operaciones_abiertas) >= MAX_OPERACIONES_ABIERTAS:
                revisar_operaciones_abiertas()
                if time.time() - ultima_impresion_resumen >= 60:
                    if (
                        estado.metricas_ronda.get("mercados_analizados", 0) > 0
                        or estado.metricas_ronda.get("senales_detectadas", 0) > 0
                        or estado.metricas_ronda.get("entradas_abiertas", 0) > 0
                    ):
                        imprimir_resumen_ronda()
                
                    ultima_impresion_resumen = time.time()
            time.sleep(0.25)
            continue

        activos = obtener_activos()
        reiniciar_metricas_ronda()
        estado.metricas_ronda["mercados_analizados"] = len(activos)
        # Limpiar snapshot para que el reporte solo muestre
        # los mercados reales analizados en esta ronda.
        estado.snapshot_mercados = {}
        
        senales = []
        bloqueos_importantes = []

        resumen_mercado = {
            "TENDENCIA_ALCISTA": 0,
            "TENDENCIA_BAJISTA": 0,
            "RANGO": 0,
            "COMPRESION": 0,
            "EXPANSION": 0,
            "INDEFINIDO": 0,
            "LIMPIO": 0,
            "NORMAL": 0,
            "SUCIO": 0,
            "CAOTICO": 0
        }

        for item in activos:
            try:
                activo = item["activo"]
                tipo = item["tipo"]

                if any(op["activo"] == activo for op in estado.operaciones_abiertas):
                    continue

                senal = analizar_activo(activo)

                if senal is not None:
                    estado.metricas_ronda["senales_detectadas"] += 1
                    senal["tipo"] = tipo
                    senales.append(senal)
                    estado.metricas_ronda["senales_aprobadas"] += 1
                    tipo_m = senal.get("tipo_mercado")
                    calidad_m = senal.get("calidad_mercado")

                    if tipo_m in resumen_mercado:
                        resumen_mercado[tipo_m] += 1

                    if calidad_m in resumen_mercado:
                        resumen_mercado[calidad_m] += 1

            except Exception as e:
                bloqueos_importantes.append(
                    "Error analizando " + str(item) + ": " + str(e)
                )

        if senales:
            print("\nSeñales preparadas:", len(senales))

            senales = sorted(
                senales,
                key=lambda x: (
                    x.get("prioridad", 0),
                    x["puntaje"]
                ),
                reverse=True
            )

            for s in senales[:5]:
                print(
                    s["activo"],
                    s["tipo"],
                    s["direccion"],
                    "| puntaje:",
                    s["puntaje"],
                    "| calidad:",
                    s.get("calidad", "N/A"),
                    "| patrón:",
                    s["patron"],
                    "| RSI:",
                    s["rsi"],
                    "| mercado:",
                    s.get("tipo_mercado", "N/A"),
                    "| calidad mercado:",
                    s.get("calidad_mercado", "N/A")
                )

        abiertas_ahora = 0

        for senal in senales:
            if len(estado.operaciones_abiertas) >= MAX_OPERACIONES_ABIERTAS:
                break

            if any(op["activo"] == senal["activo"] for op in estado.operaciones_abiertas):
                continue

            if senal.get("prioridad", 0) < MIN_PRIORIDAD_OPERAR:
               continue

            if entrada_rapida_disponible(senal):
                if abrir_operacion(senal):
                    estado.metricas_ronda["entradas_abiertas"] += 1
                    abiertas_ahora += 1
                    operaciones_desde_resumen_mercado += 1
            else:
                motivo = motivo_pendiente_por_accion_precio(senal)
            
                if motivo in [
                    "ESPERANDO_RUPTURA_RESISTENCIA",
                    "ESPERANDO_RUPTURA_SOPORTE",
                    "ESPERANDO_CONFIRMACION_RECHAZO"
                ]:
                    if senal.get("soporte") is None or senal.get("resistencia") is None:
                        print(
                            "PENDIENTE NO GUARDADA:",
                            senal["activo"],
                            "sin soporte/resistencia"
                        )
                        continue
            
                guardar_senal_pendiente(senal, motivo)

            time.sleep(0.02)

        if abiertas_ahora > 0:
            print("Operaciones abiertas en esta ronda:", abiertas_ahora)

        # Resumen de mercado cada 5 operaciones abiertas por el bot.
        if operaciones_desde_resumen_mercado >= 5:
            print("\n===== RESUMEN DE MERCADO CADA 5 OPERACIONES =====")
            print(
                "Tendencias:",
                "ALCISTA", resumen_mercado["TENDENCIA_ALCISTA"],
                "| BAJISTA", resumen_mercado["TENDENCIA_BAJISTA"],
                "| RANGO", resumen_mercado["RANGO"]
            )
            print(
                "Calidad:",
                "LIMPIO", resumen_mercado["LIMPIO"],
                "| NORMAL", resumen_mercado["NORMAL"],
                "| SUCIO", resumen_mercado["SUCIO"],
                "| CAOTICO", resumen_mercado["CAOTICO"]
            )
            operaciones_desde_resumen_mercado = 0
            if time.time() - ultima_impresion_resumen >= 60:
                if (
                    estado.metricas_ronda.get("mercados_analizados", 0) > 0
                    or estado.metricas_ronda.get("senales_detectadas", 0) > 0
                    or estado.metricas_ronda.get("entradas_abiertas", 0) > 0
                ):
                    imprimir_resumen_ronda()
            
                ultima_impresion_resumen = time.time()
        time.sleep(0.25)
if __name__ == "__main__":
    main()
