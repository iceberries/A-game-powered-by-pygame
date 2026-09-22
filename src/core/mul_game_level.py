"""旧联机关卡名称的兼容入口。

联机规则不再继承带 Pygame/UI 副作用的 ``GameLevel``。服务端与无界面测试统一
使用纯状态 ``GameWorld``；客户端只渲染它的快照。
"""

from core.game_world import GameWorld


class MultiplayerGameLevel(GameWorld):
    """兼容旧代码的名称，不再维护第二套移动、攻击与碰撞实现。"""

    def __init__(self, player_names=(), world_size=(1536, 864), **kwargs):
        super().__init__(player_names, world_size=world_size, **kwargs)
