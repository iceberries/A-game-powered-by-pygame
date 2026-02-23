import pygame
import math

class Ability:
    """
    游戏能力类：用于为player添加新的攻击/防御/运营方式
    """
    def __init__(self, ability_name, ability_quality, ability_description,ability_image):
        self.ability_name = ability_name
        self.ability_quality = ability_quality  # 如普通/稀有/史诗等
        self.ability_description = ability_description,
        self.ability_image=ability_image
    def apply_to_player(self, player):
        """将能力效果应用到player对象（需在player类中实现对应接口）"""
        pass  # 具体实现由子类或外部调用扩展

    def remove_from_player(self, player):
        """移除能力效果（如有需要）"""
        pass

    def on_attack(self, player, target):
        """攻击时触发的能力效果（可选）"""
        pass

    def on_defend(self, player, attacker):
        """防御时触发的能力效果（可选）"""
        pass

    def on_update(self, player, dt):
        """每一段时间触发的能力效果（可选）"""
        pass

class MultiBiteAbility(Ability):
    """
    多重撕咬能力：攻击时在中心顺/逆时针60度各生成一个攻击判定rect
    """
    def __init__(self):
        super().__init__(
            ability_name="多重撕咬",
            ability_quality="稀有",
            ability_description="攻击时在中心顺/逆时针60度各生成一个额外攻击判定区。",
            ability_image="picture/ability/MultiBite.png"
        )

    def on_attack(self, player, target_group):
        """
        player: 玩家对象（需有get_attack_rect、facing_left等属性）
        target_group: 敌人组
        """
        # 原攻击rect
        main_rect = player.get_attack_rect()
        # 计算中心
        center = pygame.Vector2(player.getrect().center)
        # 生成两个旋转后的rect
        angle_list = [60, -60]
        hit_enemies = []
        for angle in angle_list:
            # 以玩家中心为原点，旋转攻击rect
            offset = pygame.Vector2(main_rect.center) - center
            rad = math.radians(angle)
            rot_offset = pygame.Vector2(
                offset.x * math.cos(rad) - offset.y * math.sin(rad),
                offset.x * math.sin(rad) + offset.y * math.cos(rad)
            )
            new_center = center + rot_offset
            bite_rect = main_rect.copy()
            bite_rect.center = (int(new_center.x), int(new_center.y))
            # 检查碰撞
            for enemy in target_group:
                if bite_rect.colliderect(enemy.getrect()) and enemy not in hit_enemies:
                    hit_enemies.append(enemy)
        return hit_enemies
