import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core.protocol import (
    MessageBuffer,
    ProtocolError,
    encode_message,
    validate_client_message,
)


class ProtocolTests(unittest.TestCase):
    def test_fragmented_and_coalesced_messages(self):
        first = encode_message({"type": "ping", "client_time": 1})
        second = encode_message({"type": "ping", "client_time": 2})
        decoder = MessageBuffer()

        self.assertEqual(decoder.feed(first[:2]), [])
        self.assertEqual(decoder.feed(first[2:9]), [])
        messages = decoder.feed(first[9:] + second)

        self.assertEqual([item["client_time"] for item in messages], [1, 2])

    def test_rejects_invalid_action(self):
        with self.assertRaises(ProtocolError):
            validate_client_message({
                "type": "action",
                "sequence": 1,
                "action": {"type": "move", "direction": "diagonal"},
            })

        with self.assertRaises(ProtocolError):
            validate_client_message({
                "type": "action",
                "sequence": True,
                "action": {"type": "attack"},
            })


if __name__ == "__main__":
    unittest.main()
