import os
import shutil

import backtest_bot_real
import auditoria_estadistica
import base_conocimiento

from config_backtest import (
    PORCENTAJE_ENTRENAMIENTO,
    GENERAR_BASE_CONOCIMIENTO
)


ARCHIVO_RESULTADOS = "backtest_bot_real_resultados.csv"
ARCHIVO_TRAIN = "data/backtest_train_resultados.csv"
ARCHIVO_VALIDACION = "data/backtest_validacion_resultados.csv"


def dividir_datasets(datasets):
    total = len(datasets)

    if total < 2:
        return datasets, []

    corte = int(total * (PORCENTAJE_ENTRENAMIENTO / 100))

    train = datasets[:corte]
    validacion = datasets[corte:]

    return train, validacion


def mover_resultado(origen, destino):
    if not os.path.exists(origen):
        print("No existe archivo resultado:", origen)
        return

    os.makedirs(os.path.dirname(destino), exist_ok=True)
    shutil.copy(origen, destino)


def ejecutar_entrenamiento(datasets_train):
    print("\n===== ENTRENAMIENTO FASE 4 =====")
    print("Datasets entrenamiento:", len(datasets_train))

    backtest_bot_real.reset_estado()
    resultados_train = backtest_bot_real.ejecutar_backtest(datasets_train)
    backtest_bot_real.guardar_resultados(resultados_train)
    backtest_bot_real.imprimir_resumen(resultados_train)

    mover_resultado(ARCHIVO_RESULTADOS, ARCHIVO_TRAIN)

    print("\nGenerando auditoría estadística...")
    auditoria_estadistica.main()

    if GENERAR_BASE_CONOCIMIENTO:
        print("\nGenerando base de conocimiento...")
        base_conocimiento.main()

    return resultados_train


def ejecutar_validacion(datasets_validacion):
    print("\n===== VALIDACIÓN FASE 4 =====")
    print("Datasets validación:", len(datasets_validacion))

    backtest_bot_real.reset_estado()
    resultados_validacion = backtest_bot_real.ejecutar_backtest(datasets_validacion)
    backtest_bot_real.guardar_resultados(resultados_validacion)
    backtest_bot_real.imprimir_resumen(resultados_validacion)

    mover_resultado(ARCHIVO_RESULTADOS, ARCHIVO_VALIDACION)

    return resultados_validacion


def comparar_resultados(resultados_train, resultados_validacion):
    def calcular(filas):
        total = len(filas)
        wins = sum(1 for r in filas if r.get("resultado") == "WIN")
        losses = total - wins
        wr = round((wins / total) * 100, 2) if total else 0
        return total, wins, losses, wr

    total_train, wins_train, losses_train, wr_train = calcular(resultados_train)
    total_val, wins_val, losses_val, wr_val = calcular(resultados_validacion)

    print("\n===== COMPARACIÓN TRAIN / VALIDACIÓN =====")
    print("TRAIN | total:", total_train, "| win:", wins_train, "| loss:", losses_train, "| winrate:", str(wr_train) + "%")
    print("VALID | total:", total_val, "| win:", wins_val, "| loss:", losses_val, "| winrate:", str(wr_val) + "%")
    print("Diferencia validación - entrenamiento:", str(round(wr_val - wr_train, 2)) + "%")
    print("=========================================\n")


def main():
    print("\n===== BACKTEST MANAGER BOOTIQ =====")

    datasets = backtest_bot_real.cargar_datasets()
    print("Datasets totales:", len(datasets))

    datasets_train, datasets_validacion = dividir_datasets(datasets)

    print("Train:", len(datasets_train))
    print("Validación:", len(datasets_validacion))

    resultados_train = ejecutar_entrenamiento(datasets_train)
    resultados_validacion = ejecutar_validacion(datasets_validacion)

    comparar_resultados(resultados_train, resultados_validacion)

    print("Archivos generados:")
    print("-", ARCHIVO_TRAIN)
    print("-", ARCHIVO_VALIDACION)


if __name__ == "__main__":
    main()