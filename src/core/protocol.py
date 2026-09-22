"""TCP 长度分帧 JSON 协议。"""

import json
import struct
import threading


PROTOCOL_VERSION = 1
HEADER = struct.Struct("!I")
MAX_MESSAGE_SIZE = 1024 * 1024
MAX_CHAT_LENGTH = 500


class ProtocolError(ValueError):
    pass


def encode_message(message):
    if not isinstance(message, dict):
        raise ProtocolError("message must be a dictionary")
    envelope = dict(message)
    envelope.setdefault("protocol_version", PROTOCOL_VERSION)
    payload = json.dumps(
        envelope,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    if len(payload) > MAX_MESSAGE_SIZE:
        raise ProtocolError("message is too large")
    return HEADER.pack(len(payload)) + payload


class MessageBuffer:
    """可同时处理 TCP 拆包和粘包的增量解码器。"""

    def __init__(self):
        self._buffer = bytearray()
        self._expected_size = None

    def feed(self, data):
        if not isinstance(data, (bytes, bytearray)):
            raise ProtocolError("received data must be bytes")
        self._buffer.extend(data)
        messages = []

        while True:
            if self._expected_size is None:
                if len(self._buffer) < HEADER.size:
                    break
                self._expected_size = HEADER.unpack(
                    self._buffer[:HEADER.size]
                )[0]
                del self._buffer[:HEADER.size]
                if not 0 < self._expected_size <= MAX_MESSAGE_SIZE:
                    raise ProtocolError("invalid message size")

            if len(self._buffer) < self._expected_size:
                break

            payload = bytes(self._buffer[:self._expected_size])
            del self._buffer[:self._expected_size]
            self._expected_size = None
            try:
                message = json.loads(payload.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ProtocolError("invalid JSON payload") from exc
            if not isinstance(message, dict):
                raise ProtocolError("message payload must be an object")
            if message.get("protocol_version") != PROTOCOL_VERSION:
                raise ProtocolError("unsupported protocol version")
            messages.append(message)

        return messages


def send_message(sock, message, lock=None):
    data = encode_message(message)
    if lock is None:
        sock.sendall(data)
        return
    with lock:
        sock.sendall(data)


def validate_client_message(message):
    message_type = message.get("type")
    if message_type == "chat":
        text = message.get("message")
        if not isinstance(text, str) or not text.strip():
            raise ProtocolError("chat message must not be empty")
        if len(text) > MAX_CHAT_LENGTH:
            raise ProtocolError("chat message is too long")
        return

    if message_type == "action":
        action = message.get("action")
        sequence = message.get("sequence")
        if not isinstance(action, dict):
            raise ProtocolError("action payload is missing")
        if type(sequence) is not int or sequence < 0:
            raise ProtocolError("invalid action sequence")
        action_type = action.get("type")
        if action_type == "move":
            if action.get("direction") not in {"left", "right", "up", "down"}:
                raise ProtocolError("invalid movement direction")
        elif action_type not in {"stop_move", "attack", "quit_game"}:
            raise ProtocolError("unknown action type")
        return

    if message_type == "ping":
        return
    raise ProtocolError("unknown message type")


class Sequence:
    def __init__(self):
        self._value = 0
        self._lock = threading.Lock()

    def next(self):
        with self._lock:
            self._value += 1
            return self._value
