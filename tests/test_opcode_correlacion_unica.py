import unittest
from unittest.mock import Mock, patch

from iqoptionapi import constants as opcodes
from iqoptionapi.stable_api import IQ_Option


class OpcodeSolicitudUnicaTests(unittest.TestCase):
    def setUp(self):
        self.iq = IQ_Option.__new__(IQ_Option)
        self.original = dict(opcodes.ACTIVES)

    def tearDown(self):
        opcodes.ACTIVES.clear()
        opcodes.ACTIVES.update(self.original)

    def test_una_solicitud_v2_aceptada_sin_fallback(self):
        respuesta = {
            "binary": {"actives": {"123456": {"name": "binary.ACTIVO_TEST"}}},
            "turbo": {"actives": {"123456": {"name": "turbo.ACTIVO_TEST"}}},
        }
        self.iq.get_all_init_v2 = Mock(return_value=respuesta)
        self.iq._get_all_init_legacy_bounded = Mock()
        self.iq.get_ALL_Binary_ACTIVES_OPCODE()
        self.iq.get_all_init_v2.assert_called_once_with(
            timeout=45.0, avisar_timeout=True
        )
        self.iq._get_all_init_legacy_bounded.assert_not_called()
        self.assertEqual(opcodes.ACTIVES["ACTIVO_TEST"], 123456)
        self.assertIs(self.iq._bootiq_init_v2_bootstrap, respuesta)

    def test_fallo_v2_usa_un_fallback_acotado(self):
        respuesta = {
            "binary": {"actives": {"123456": {"name": "binary.ACTIVO_TEST"}}},
            "turbo": {"actives": {"123456": {"name": "turbo.ACTIVO_TEST"}}},
        }
        self.iq.get_all_init_v2 = Mock(return_value=None)
        self.iq._get_all_init_legacy_bounded = Mock(return_value=respuesta)
        self.iq.get_ALL_Binary_ACTIVES_OPCODE()
        self.iq.get_all_init_v2.assert_called_once()
        self.iq._get_all_init_legacy_bounded.assert_called_once_with(
            timeout=10.0
        )

    def test_sin_respuesta_no_publica_opcodes(self):
        self.iq.get_all_init_v2 = Mock(return_value=None)
        self.iq._get_all_init_legacy_bounded = Mock(return_value=None)
        with self.assertRaisesRegex(RuntimeError, "OPCODE"):
            self.iq.get_ALL_Binary_ACTIVES_OPCODE(timeout=1)
        self.iq.get_all_init_v2.assert_called_once_with(
            timeout=1, avisar_timeout=True
        )
        self.iq._get_all_init_legacy_bounded.assert_called_once_with(
            timeout=1
        )
        self.assertEqual(opcodes.ACTIVES, self.original)


if __name__ == "__main__":
    unittest.main()
