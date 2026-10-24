import unittest
from unittest.mock import Mock

from iqoptionapi.ws.chanels.heartbeat import Heartbeat


class HeartbeatForwardingTests(unittest.TestCase):
    def test_heartbeat_forwards_no_force_send(self):
        api = Mock()
        api.timesync.server_timestamp = 1234567890

        Heartbeat(api)(1234567890)

        api.send_websocket_request.assert_called_once_with(
            "heartbeat",
            {
                "msg": {
                    "heartbeatTime": 1234567890,
                    "userTime": 1234567890000,
                }
            },
            unittest.mock.ANY,
            no_force_send=False,
        )


if __name__ == "__main__":
    unittest.main()
