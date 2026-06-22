import csv
import os

CARPETA_DATA = "data_backtest"
SALIDA = "backtest_resultados.csv"


def leer_csv_velas(ruta):
    velas = []

    with open(ruta, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            velas.append({
                "from": int(float(row["from"])),
                "open": float(row["open"]),
                "close": float(row["close"]),
                "max": float(row["max"]),
                "min": float(row["min"]),
                "volume": float(row.get("volume", 0) or 0),
            })

    return sorted(velas, key=lambda x: x["from"])


def resultado_binario(velas, index_entrada, direccion):
    entrada = velas[index_entrada]["close"]
    cierre = velas[index_entrada + 1]["close"]

    if direccion == "call":
        return "WIN" if cierre > entrada else "LOSS"

    if direccion == "put":
        return "WIN" if cierre < entrada else "LOSS"

    return "LOSS"


def detectar_senal_simple(ventana):
    ultima = ventana[-1]
    anterior = ventana[-2]

    o = ultima["open"]
    c = ultima["close"]
    h = ultima["max"]
    l = ultima["min"]

    rango = h - l
    cuerpo = abs(c - o)

    if rango <= 0:
        return None

    fuerza = cuerpo / rango
    mecha_sup = h - max(o, c)
    mecha_inf = min(o, c) - l

    # CALL: rechazo comprador
    if c > o and mecha_inf >= cuerpo * 1.2 and fuerza >= 0.18:
        return {
            "direccion": "call",
            "patron": "reaccion compradora simple",
            "puntaje": 18,
        }

    # PUT: rechazo vendedor
    if c < o and mecha_sup >= cuerpo * 1.2 and fuerza >= 0.18:
        return {
            "direccion": "put",
            "patron": "reaccion vendedora simple",
            "puntaje": 18,
        }

    # Continuación alcista
    if c > anterior["close"] and c > o and fuerza >= 0.28:
        return {
            "direccion": "call",
            "patron": "continuacion alcista simple",
            "puntaje": 14,
        }

    # Continuación bajista
    if c < anterior["close"] and c < o and fuerza >= 0.28:
        return {
            "direccion": "put",
            "patron": "continuacion bajista simple",
            "puntaje": 14,
        }

    return None


def ejecutar_backtest_activo(activo, velas):
    resultados = []

    for i in range(50, len(velas) - 2):
        ventana = velas[i - 50:i + 1]

        senal = detectar_senal_simple(ventana)

        if senal is None:
            continue

        resultado = resultado_binario(
            velas,
            i,
            senal["direccion"]
        )

        resultados.append({
            "activo": activo,
            "fecha": velas[i]["from"],
            "direccion": senal["direccion"],
            "patron": senal["patron"],
            "puntaje": senal["puntaje"],
            "resultado": resultado,
            "precio_entrada": velas[i]["close"],
            "precio_cierre": velas[i + 1]["close"],
        })

    return resultados


def guardar_resultados(resultados):
    with open(SALIDA, "w", newline="", encoding="utf-8") as f:
        campos = [
            "activo",
            "fecha",
            "direccion",
            "patron",
            "puntaje",
            "resultado",
            "precio_entrada",
            "precio_cierre",
        ]

        writer = csv.DictWriter(f, fieldnames=campos)
        writer.writeheader()

        for r in resultados:
            writer.writerow(r)


def resumen(resultados):
    total = len(resultados)
    ganadas = sum(1 for r in resultados if r["resultado"] == "WIN")
    perdidas = total - ganadas
    winrate = round((ganadas / total) * 100, 2) if total else 0

    print("\n===== RESUMEN BACKTEST =====")
    print("Total operaciones:", total)
    print("Ganadas:", ganadas)
    print("Perdidas:", perdidas)
    print("Winrate:", winrate, "%")
    print("============================\n")

    por_patron = {}

    for r in resultados:
        p = r["patron"]

        if p not in por_patron:
            por_patron[p] = {"total": 0, "win": 0}

        por_patron[p]["total"] += 1

        if r["resultado"] == "WIN":
            por_patron[p]["win"] += 1

    print("===== POR PATRÓN =====")
    for patron, data in sorted(por_patron.items()):
        total_p = data["total"]
        win_p = data["win"]
        wr = round((win_p / total_p) * 100, 2) if total_p else 0
        print(patron, "| total:", total_p, "| winrate:", wr, "%")


def main():
    todos = []

    for archivo in os.listdir(CARPETA_DATA):
        if not archivo.endswith(".csv"):
            continue

        activo = archivo.replace(".csv", "")
        ruta = os.path.join(CARPETA_DATA, archivo)

        velas = leer_csv_velas(ruta)
        resultados = ejecutar_backtest_activo(activo, velas)

        todos.extend(resultados)

    guardar_resultados(todos)
    resumen(todos)

    print("Archivo generado:", SALIDA)


if __name__ == "__main__":
    main()