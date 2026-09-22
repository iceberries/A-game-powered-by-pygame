import os
from pathlib import Path
import socket
import sys
import time
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core.protocol import MessageBuffer, encode_message
from core.server import GameServer


class ServerIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.server = GameServer("127.0.0.1", 0)
        self.assertTrue(self.server.start())
        self.sock = socket.create_connection(
            ("127.0.0.1", self.server.port), timeout=2,
        )
        self.sock.settimeout(2)
        self.decoder = MessageBuffer()
        self.pending = []
        self.extra_sockets = []

    def tearDown(self):
        try:
            self.sock.close()
            for sock in self.extra_sockets:
                sock.close()
        finally:
            self.server.stop()

    def receive(self, message_type, timeout=2):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for index, message in enumerate(self.pending):
                if message.get("type") == message_type:
                    return self.pending.pop(index)
            data = self.sock.recv(65536)
            self.pending.extend(self.decoder.feed(data))
        self.fail(f"did not receive {message_type}")

    @staticmethod
    def receive_from(sock, message_type, timeout=2):
        decoder = MessageBuffer()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for message in decoder.feed(sock.recv(65536)):
                if message.get("type") == message_type:
                    return message
        raise AssertionError(f"did not receive {message_type}")

    def test_fragmented_chat_and_authoritative_movement(self):
        welcome = self.receive("welcome")
        name = welcome["player_name"]

        chat = encode_message({"type": "chat", "message": "hello"})
        self.sock.sendall(chat[:3])
        self.sock.sendall(chat[3:])
        self.assertEqual(self.receive("chat")["message"], "hello")

        self.assertTrue(self.server.start_game())
        start = self.receive("game_start")
        self.assertEqual(start["you"], name)
        initial_x = start["players"][name]["pos"][0]

        self.sock.sendall(encode_message({
            "type": "action",
            "sequence": 1,
            "action": {"type": "move", "direction": "right"},
        }))
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            sync = self.receive("sync")
            if sync["players"][name]["pos"][0] > initial_x:
                break
        else:
            self.fail("server did not apply movement")

    def test_room_accepts_four_players_and_rejects_fifth(self):
        first = self.receive("welcome")
        self.assertEqual(first["max_players"], 4)

        for _ in range(3):
            sock = socket.create_connection(
                ("127.0.0.1", self.server.port), timeout=2,
            )
            sock.settimeout(2)
            self.extra_sockets.append(sock)
            welcome = self.receive_from(sock, "welcome")
            self.assertLessEqual(welcome["player_count"], 4)

        overflow = socket.create_connection(
            ("127.0.0.1", self.server.port), timeout=2,
        )
        overflow.settimeout(2)
        self.extra_sockets.append(overflow)
        error = self.receive_from(overflow, "error")

        self.assertEqual(error["code"], "room_full")
        self.assertEqual(self.server.client_count, 4)


if __name__ == "__main__":
    unittest.main()
