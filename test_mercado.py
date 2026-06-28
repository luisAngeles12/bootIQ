import time
import estado
from conexion import conectar

conectar()

print("Conectado. Probando get_all_open_time...", flush=True)

inicio = time.time()

try:
    abiertos = estado.Iq.get_all_open_time()
    print("Respuesta recibida en:", round(time.time() - inicio, 2), "segundos", flush=True)

    if not abiertos:
        print("open_time vacío", flush=True)
    else:
        print("Claves:", abiertos.keys(), flush=True)

        for tipo in ["binary", "digital", "turbo"]:
            mercados = abiertos.get(tipo, {})
            abiertos_tipo = [
                activo for activo, info in mercados.items()
                if info.get("open", False)
            ]

            print(tipo, "total:", len(mercados), "| abiertos:", len(abiertos_tipo), flush=True)
            print("Primeros:", abiertos_tipo[:10], flush=True)

except Exception as e:
    print("Error:", e, flush=True)