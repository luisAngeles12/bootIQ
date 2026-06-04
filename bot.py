import time
import estado
from config import MOSTRAR_ESTADISTICAS_CADA_RONDAS, STOP_LOSS, STOP_WIN, MAX_OPERACIONES_ABIERTAS
from utils import segundo_actual
from conexion import conectar
from historial import asegurar_historial_csv, cargar_operaciones_pendientes
from mercado import obtener_activos
from estrategia import analizar_activo
from entrada import entrada_rapida_disponible, guardar_senal_pendiente, procesar_senales_pendientes
from operaciones import revisar_operaciones_abiertas, abrir_operacion
from estadisticas import imprimir_estadisticas

def main():
    conectar()
    asegurar_historial_csv()
    cargar_operaciones_pendientes()
    ronda_estadisticas = 0
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

        print("\nBalance actual:", balance_actual)
        print("Ganancia neta:", round(ganancia_neta, 2))
        print("Operaciones abiertas:", len(estado.operaciones_abiertas))
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

        # Torneo: analizamos casi toda la vela para no perder oportunidades.
        if not (0 <= segundo <= 24):
            time.sleep(0.25)
            continue

        if len(estado.operaciones_abiertas) >= MAX_OPERACIONES_ABIERTAS:
            revisar_operaciones_abiertas()
            time.sleep(0.25)
            continue

        print("\nAnalizando mercado para torneo...")

        activos = obtener_activos()
        print("Activos compatibles:", len(activos))

        senales = []

        for item in activos:
            try:
                activo = item["activo"]
                tipo = item["tipo"]

                if any(op["activo"] == activo for op in estado.operaciones_abiertas):
                    continue

                senal = analizar_activo(activo)

                if senal is not None:
                    senal["tipo"] = tipo
                    senales.append(senal)

            except Exception as e:
                print("Error analizando", item, e)

        print("Señales preparadas:", len(senales))

        if not senales:
            time.sleep(0.25)
            continue

        senales = sorted(
            senales,
            key=lambda x: (
                x.get("prioridad", 0),
                x["puntaje"]
            ),
            reverse=True
        )

        for s in senales[:10]:
            print(
                s["activo"],
                s["tipo"],
                s["direccion"],
                "puntaje:",
                s["puntaje"],
                "| calidad:",
                s.get("calidad", "N/A"),
                "| prioridad:",
                s.get("prioridad", 0),
                "| patrón:",
                s["patron"],
                "| RSI:",
                s["rsi"]
            )

        abiertas_ahora = 0

        for senal in senales:
            if len(estado.operaciones_abiertas) >= MAX_OPERACIONES_ABIERTAS:
                break
        
            if any(op["activo"] == senal["activo"] for op in estado.operaciones_abiertas):
                continue
        
            # Para mantener calidad: operar solo señales buenas.
            if senal.get("prioridad", 0) < 3:
                continue
        
            if entrada_rapida_disponible(senal):
                if abrir_operacion(senal):
                    abiertas_ahora += 1
            else:
                guardar_senal_pendiente(senal)
            time.sleep(0.02)

        print("Operaciones abiertas en esta ronda:", abiertas_ahora)
        time.sleep(0.25)


if __name__ == "__main__":
    main()
