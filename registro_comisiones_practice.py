"""Registro independiente de CAMBIOS de comision observados, solo PRACTICE.

No es una cotizacion ejecutable; nunca se convierte en payout_fuente
PRACTICE_PREENTRADA ni autoriza operaciones. No importa el broker.
"""
import csv
from pathlib import Path

COLUMNAS = ("activo", "instrumento", "timestamp_fuente_utc",
            "timestamp_observacion_utc", "estado",
            "payout_estimado_conservador", "procedencia",
            "operable")


def guardar_eventos_comision(activo, inicio, fin, eventos, directorio):
    """Crea archivo exclusivo solo si existen cambios genuinos observados."""
    if not eventos:
        return None, 0
    if type(inicio) is not int or type(fin) is not int or fin <= inicio:
        raise ValueError("RANGO_INVALIDO")
    filas = []
    vistos = set()
    for evento in eventos:
        fuente = evento.get("timestamp_fuente")
        observado = evento.get("timestamp_observacion_utc")
        if (evento.get("estado") != "COMISION_RECIENTE_ESTIMACION_CONSERVADORA"
                or evento.get("activo") != activo
                or evento.get("instrumento") != "turbo-option"
                or evento.get("operable") is not False
                or type(fuente) is not int or type(observado) is not int
                or fuente > observado or observado < inicio or observado > fin
                or observado - fuente > 60):
            raise ValueError("EVENTO_COMISION_NO_VERIFICABLE")
        pago = evento.get("payout_neto")
        if type(pago) not in (int, float) or not 0 < pago < 1:
            raise ValueError("ESTIMACION_INVALIDA")
        if fuente in vistos:
            raise ValueError("EVENTO_COMISION_DUPLICADO")
        vistos.add(fuente)
        filas.append((activo, "turbo-option", fuente, observado,
                      evento["estado"], pago, "WEBSOCKET_CAMBIO_NO_EJECUTABLE",
                      False))
    destino = Path(directorio)
    destino.mkdir(parents=True, exist_ok=True)
    ruta = destino / f"practice_comisiones_observadas_{activo}_{inicio}_{fin}.csv"
    with ruta.open("x", encoding="utf-8", newline="") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(COLUMNAS)
        escritor.writerows(filas)
    return ruta, len(filas)
