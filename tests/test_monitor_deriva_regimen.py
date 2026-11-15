"""Aislamiento causal por regimen de mercado, exclusivamente SHADOW."""
import csv
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import monitor_deriva_estrategias as modulo
from monitor_deriva_estrategias import MonitorDerivaSombra


class DerivaPorRegimenTest(unittest.TestCase):
    def test_deterioro_general_no_implica_deterioro_de_regimen(self):
        m = MonitorDerivaSombra()
        for i in range(8):
            m.registrar_cierre("CHOCH", 20.75, str(i), "TENDENCIA_LIMPIA")
        for i in range(8, 16):
            dato = m.registrar_cierre(
                "CHOCH", -25, str(i), "MERCADO_RANGO"
            )
        self.assertEqual(dato["estado"], "DETERIORO_CANDIDATO")
        self.assertEqual(dato["estado_regimen"], "MUESTRA_INSUFICIENTE")
        self.assertEqual(dato["observaciones_regimen"], 8)
        self.assertFalse(dato["cooldown_activado"])

    def test_deterioro_dentro_del_mismo_regimen(self):
        m = MonitorDerivaSombra()
        for i in range(16):
            dato = m.registrar_cierre(
                "pullback", 20.75 if i < 8 else -25,
                str(i), "TENDENCIA_LIMPIA",
            )
        self.assertEqual(dato["estado_regimen"], "DETERIORO_CANDIDATO")
        self.assertEqual(dato["regimen_expectativa_reciente"], -25)
        self.assertFalse(dato["cooldown_activado"])

    def test_sin_regimen_no_inventa_contexto(self):
        m = MonitorDerivaSombra()
        for i in range(16):
            dato = m.registrar_cierre(
                "sweep", 20.75 if i < 8 else -25, str(i)
            )
        self.assertEqual(dato["estado"], "DETERIORO_CANDIDATO")
        self.assertEqual(dato["estado_regimen"], "SIN_DATOS_REGIMEN")
        self.assertEqual(dato["observaciones_regimen"], 0)

    def test_reconstruccion_con_regimen_usa_datos_de_entrada(self):
        previo = modulo._MONITOR
        try:
            with TemporaryDirectory() as directorio:
                ruta = Path(directorio) / "prueba.csv"
                with ruta.open("w", encoding="utf-8", newline="") as archivo:
                    escritor = csv.DictWriter(
                        archivo, fieldnames=[
                            "order_id", "patron", "resultado",
                            "estado", "regimen_mercado",
                        ]
                    )
                    escritor.writeheader()
                    for i in range(16):
                        escritor.writerow({
                            "order_id": str(i),
                            "patron": "CHOCH",
                            "resultado": "20.75" if i < 8 else "-25",
                            "estado": "CERRADA",
                            "regimen_mercado": "TENDENCIA_LIMPIA",
                        })
                self.assertEqual(
                    modulo.reconstruir_monitor_desde_historial(ruta), 16
                )
                self.assertEqual(
                    len(modulo._MONITOR._resultados_regimen[
                        ("CHOCH", "TENDENCIA_LIMPIA")
                    ]), 16
                )
                self.assertIsNone(
                    modulo.observar_cierre_sombra(
                        "CHOCH", -25, "15", "TENDENCIA_LIMPIA"
                    )
                )
        finally:
            modulo._MONITOR = previo


if __name__ == "__main__":
    unittest.main()
