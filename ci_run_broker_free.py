"""Ejecutor CI broker-free: importa pruebas solo despues de aislar credenciales.

Nunca conecta el broker ni utiliza secretos privados. La logica de negocio
no se altera: exclusivamente el orden de importacion del runner unittest.
"""
import sys
import types
import unittest


def main():
    falso = types.ModuleType("credenciales_local")
    falso.EMAIL = ""
    falso.PASSWORD = ""
    sys.modules["credenciales_local"] = falso

    import config
    if config.MODO_CUENTA != "PRACTICE":
        raise RuntimeError("CI OOS BLOQUEADO: cuenta distinta de PRACTICE")

    if len(sys.argv) < 2:
        raise SystemExit("Indicar modulos de pruebas")
    suite = unittest.defaultTestLoader.loadTestsFromNames(sys.argv[1:])
    resultado = unittest.TextTestRunner(verbosity=1).run(suite)
    raise SystemExit(0 if resultado.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
