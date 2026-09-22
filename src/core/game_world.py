"""纯游戏世界的公共入口。

这里不依赖 Pygame、Surface、音频或输入设备，可供服务端、无界面测试和其它游戏
模式共同使用。
"""

from core.multiplayer_simulation import GameWorld, MAX_PLAYERS

__all__ = ["GameWorld", "MAX_PLAYERS"]
