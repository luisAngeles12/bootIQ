import tempfile
import unittest
from pathlib import Path
from diagnostico_memoria_practice import diagnosticar_memoria, lineas_diagnostico_memoria


class DiagnosticoMemoriaPracticeTests(unittest.TestCase):
    def test_ausente_con_candidata_no_promueve(self):
        with tempfile.TemporaryDirectory() as tmp:
            candidata = Path(tmp) / 'train.csv'
            candidata.write_text('clave,total\nA,10\n', encoding='utf-8')
            r = diagnosticar_memoria(Path(tmp) / 'oficial.csv', candidata,
                                    cargador=lambda _: self.fail('No debe cargar'))
            self.assertEqual(r['estado'], 'AUSENTE')
            self.assertTrue(r['candidata_experimental_presente'])
            self.assertFalse(r['autoriza_operaciones'])
            self.assertIn('NO se carga', ' '.join(lineas_diagnostico_memoria(r)))

    def test_presente_vacia(self):
        with tempfile.TemporaryDirectory() as tmp:
            archivo = Path(tmp) / 'oficial.csv'
            archivo.touch()
            r = diagnosticar_memoria(archivo, cargador=lambda _: {})
            self.assertEqual(r['estado'], 'VACIA')
            self.assertEqual(r['claves'], 0)

    def test_presente_usable_solo_informativo(self):
        with tempfile.TemporaryDirectory() as tmp:
            archivo = Path(tmp) / 'oficial.csv'
            archivo.touch()
            r = diagnosticar_memoria(archivo, cargador=lambda _: {'A': {}})
            self.assertEqual(r['estado'], 'DISPONIBLE')
            self.assertEqual(r['claves'], 1)
            self.assertFalse(r['autoriza_operaciones'])

    def test_falla_carga_explicita(self):
        with tempfile.TemporaryDirectory() as tmp:
            archivo = Path(tmp) / 'oficial.csv'
            archivo.touch()
            def falla(_):
                raise OSError('prueba')
            r = diagnosticar_memoria(archivo, cargador=falla)
            self.assertEqual(r['estado'], 'ERROR_CARGA')
            self.assertEqual(r['error'], 'OSError')


if __name__ == '__main__':
    unittest.main()
