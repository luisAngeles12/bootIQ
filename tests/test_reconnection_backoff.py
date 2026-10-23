import unittest
from unittest.mock import patch

import conexion
import estado


class FakeFailedIQ:
    def __init__(self, reason):
        self.reason = reason
        self.attempts = 0

    def check_connect(self):
        return False

    def connect(self):
        self.attempts += 1
        return False, self.reason


class ReconnectionBackoffTests(unittest.TestCase):
    def setUp(self):
        self.original_iq = estado.Iq

    def tearDown(self):
        estado.Iq = self.original_iq

    def test_dns_failure_uses_progressive_wait_without_false_success(self):
        fake = FakeFailedIQ("[Errno 11001] getaddrinfo failed")
        estado.Iq = fake
        with patch.object(conexion.time, "sleep") as sleep:
            self.assertFalse(conexion.reconectar_iq(intentos=3))
        self.assertEqual(fake.attempts, 3)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [2, 4])

    def test_other_failure_keeps_bounded_standard_wait(self):
        fake = FakeFailedIQ("SSID_PROFILE_TIMEOUT")
        estado.Iq = fake
        with patch.object(conexion.time, "sleep") as sleep:
            self.assertFalse(conexion.reconectar_iq(intentos=3))
        self.assertEqual(fake.attempts, 3)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [2, 2])


if __name__ == "__main__":
    unittest.main()
