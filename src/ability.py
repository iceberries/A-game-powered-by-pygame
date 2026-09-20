import pygame
import math

# 品质配色：普通 / 稀有 / 史诗 / 传说
QUALITY_COLORS = {
    "普通": (205, 205, 205),
    "稀有": (95, 175, 255),
    "史诗": (195, 120, 255),
    "传说": (255, 195, 70),
}

# 品质抽取权重：品质越高越稀有（会被 Ability.weight 再乘一次）
QUALITY_WEIGHTS = {
    "普通": 1.0,
    "稀有": 0.75,
    "史诗": 0.5,
    "传说": 0.3,
}


def rotate_vector(vec, angle):
    """把向量按 angle 度旋转（与 rotate_rect 同一套方向约定）。"""
    offset = pygame.Vector2(vec)
    rad = math.radians(angle)
    return pygame.Vector2(
        offset.x * math.cos(rad) - offset.y * math.sin(rad),
        offset.x * math.sin(rad) + offset.y * math.cos(rad),
    )


def rotate_rect(rect, center, angle):
    """以 center 为中心把 rect 旋转 angle 度（顺时针为正），返回旋转后的新 rect。"""
    rot = rotate_vector(pygame.Vector2(rect.center) - pygame.Vector2(center), angle)
    return pygame.Rect(
        int(center[0] + rot.x) - rect.width // 2,
        int(center[1] + rot.y) - rect.height // 2,
        rect.width,
        rect.height,
    )


class Ability:
    """
    游戏能力类：用于为player添加新的攻击/防御/运营方式。

    子类可覆盖的钩子：
        apply_to_player(player)          获得（或叠加）该能力时立即生效
        remove_from_player(player)       移除能力时恢复属性
        on_attack(player, group)         攻击时对敌人组做额外判定，返回额外命中的敌人列表
        on_update(player, level, dt)     按秒更新（level 提供 enemy_group / camera 等）
        on_kill(player, enemy)           击杀敌人时调用
        on_defend(player, level)         玩家受到伤害时调用
        draw_effect(player, ds, camera)  绘制该能力的附加视觉表现
    """

    max_stack = 1    # 最大叠加层数（<=0 表示不限制）
    weight = 1.0     # 抽取权重基础值（子类可覆盖，实例上还会乘以品质权重）

    def __init__(self, ability_name, ability_quality, ability_description, ability_image=None):
        self.ability_name = ability_name
        self.ability_quality = ability_quality           # 如普通/稀有/史诗等
        self.ability_description = ability_description   # 注意：不要写成 "x", 否则会变成元组
        self.ability_image = ability_image
        # 实际抽取权重 = 类权重 × 品质稀有度
        self.weight = type(self).weight * QUALITY_WEIGHTS.get(ability_quality, 1.0)
        self.stack = 0            # 当前已叠加层数
        self._icon = None
        self._icon_loaded = False

    # ---------------- 展示相关 ----------------
    @property
    def quality_color(self):
        return QUALITY_COLORS.get(self.ability_quality, (205, 205, 205))

    def get_icon(self):
        """懒加载图标；缺图时返回 None，由 UpgradeUI 生成占位图标。"""
        if not self._icon_loaded:
            self._icon_loaded = True
            if self.ability_image:
                try:
                    self._icon = pygame.image.load(self.ability_image).convert_alpha()
                except (pygame.error, FileNotFoundError):
                    self._icon = None
        return self._icon

    def get_stack_text(self):
        """用于在卡片上展示叠加进度，如 2/3；不可叠加时返回空串。"""
        if self.max_stack <= 1:
            return ""
        return f"{self.stack}/{self.max_stack}"

    # ---------------- 效果钩子 ----------------
    def apply_to_player(self, player):
        """将能力效果应用到player对象（需在player类中实现对应接口）"""
        pass  # 具体实现由子类或外部调用扩展

    def remove_from_player(self, player):
        """移除能力效果（如有需要）"""
        pass

    def on_attack(self, player, target):
        """攻击时触发的能力效果（可选），返回额外命中的敌人列表"""
        return []

    def on_attack_start(self, player):
        """玩家刚开始一次攻击时触发一次（不是每帧），适合放旋风等一次性效果"""
        pass

    def attack_extra_angles(self):
        """本次攻击在主判定区之外额外产生的角度（供多重撕咬、旋风撕咬共用）"""
        return []

    def on_defend(self, player, level=None):
        """防御时触发的能力效果（可选）"""
        pass

    def on_update(self, player, level=None, dt=1 / 60):
        """按经过的秒数更新能力效果（可选）。"""
        pass

    def on_kill(self, player, enemy):
        """击杀敌人时触发的能力效果（可选）"""
        pass

    def draw_effect(self, player, ds, camera=None):
        """绘制该能力的附加视觉表现（可选）"""
        pass


class SharpClawAbility(Ability):
    """利爪：直接提升攻击伤害。"""
    max_stack = 5

    def __init__(self):
        super().__init__(
            ability_name="利爪",
            ability_quality="普通",
            ability_description="攻击伤害 +10。",
        )

    def apply_to_player(self, player):
        player.attack_damage += 10


class SwiftBiteAbility(Ability):
    """迅捷撕咬：缩短攻击冷却，出手更快。"""
    max_stack = 4

    def __init__(self):
        super().__init__(
            ability_name="迅捷撕咬",
            ability_quality="普通",
            ability_description="攻击冷却 -15%，出手更快。",
        )

    def apply_to_player(self, player):
        # 冷却按比例缩短，但不短于攻击动画本身
        player.attack_interval = max(player.attack_cooldown + 2 / 60, player.attack_interval * 0.85)


class SwiftFeetAbility(Ability):
    """疾风步：提升移动速度。"""
    max_stack = 4

    def __init__(self):
        super().__init__(
            ability_name="疾风步",
            ability_quality="普通",
            ability_description="移动速度 +3。",
        )

    def apply_to_player(self, player):
        player.move_speed += 3 * 60


class LongReachAbility(Ability):
    """长臂：扩大攻击判定范围。"""
    max_stack = 3

    def __init__(self):
        super().__init__(
            ability_name="长臂",
            ability_quality="稀有",
            ability_description="攻击判定范围 +20%。",
        )

    def apply_to_player(self, player):
        player.attack_width_scale *= 1.2
        player.attack_height_scale *= 1.2


class IronSkinAbility(Ability):
    """铁壁：减免体型（血量）衰减。"""
    max_stack = 3

    def __init__(self):
        super().__init__(
            ability_name="铁壁",
            ability_quality="稀有",
            ability_description="受到的体型衰减减少 30%。",
        )

    def apply_to_player(self, player):
        player.shrink_resist = min(0.85, player.shrink_resist + 0.3)


class PredatorAbility(Ability):
    """掠食本能：击杀获得的成长翻倍。"""
    max_stack = 2

    def __init__(self):
        super().__init__(
            ability_name="掠食本能",
            ability_quality="史诗",
            ability_description="击杀敌人时获得的体型成长 +100%。",
        )

    def apply_to_player(self, player):
        player.growth_scale += 1.0


class ThunderFieldAbility(Ability):
    """雷霆领域：周期性对身边敌人造成伤害。"""
    max_stack = 3

    def __init__(self):
        super().__init__(
            ability_name="雷霆领域",
            ability_quality="史诗",
            ability_description="每 2 秒对周围敌人造成 30 点伤害。",
        )
        self.interval = 2.0   # 触发间隔（秒）
        self.radius = 180     # 作用半径
        self.damage = 0       # 单次伤害（由 apply_to_player 逐层叠加，首层即 30）
        self.timer = 0.0
        self.flash = 0.0      # 视觉反馈剩余时间（秒）
        self.flash_duration = 12 / 60

    def apply_to_player(self, player):
        self.damage += 30
        self.radius += 40

    def on_update(self, player, level=None, dt=1 / 60):
        if self.flash > 0:
            self.flash = max(0.0, self.flash - dt)
        self.timer += dt
        if level is None or self.timer + 1e-9 < self.interval:
            return
        self.timer = max(0.0, self.timer - self.interval)
        self.flash = self.flash_duration
        center = pygame.Vector2(player.getrect().center)
        for group in (getattr(level, 'enemy_group', None), getattr(level, 'attack_enemy_group', None)):
            if not group:
                continue
            for enemy in list(group):
                enemy_center = pygame.Vector2(enemy.getrect().center)
                if (enemy_center - center).length() <= self.radius:
                    if enemy.hp_caculater(self.damage) <= 0:
                        # 交由关卡统一结算（音效、刷新、成长、分数）
                        player.pending_kills.append(enemy)

    def draw_effect(self, player, ds, camera=None):
        if self.flash <= 0:
            return
        center = player.getrect().center
        pos = camera.apply_pos(center) if camera is not None else center
        alpha = max(0, int(150 * self.flash / self.flash_duration))
        ring = pygame.Surface((self.radius * 2, self.radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(ring, (130, 210, 255, alpha // 3), (self.radius, self.radius), self.radius)
        pygame.draw.circle(ring, (200, 240, 255, alpha), (self.radius, self.radius), self.radius, 4)
        ds.blit(ring, (pos[0] - self.radius, pos[1] - self.radius))


class MultiBiteAbility(Ability):
    """
    多重撕咬能力：攻击时以主角中心为圆心，额外生成若干个旋转过的撕咬判定区。

    每叠加一层额外 +2 个判定区（±60° → ±120°），最多额外 +4 个。
    """
    max_stack = 2
    # 每层新增的角度（每层 2 个，合计最多 4 个）
    ANGLES_PER_STACK = ((60, -60), (120, -120))

    def __init__(self):
        super().__init__(
            ability_name="多重撕咬",
            ability_quality="稀有",
            ability_description="每次选择额外 +2 个撕咬判定区，最多 +4 个。",
            ability_image="picture/ability/MultiBite.png"
        )

    def attack_extra_angles(self):
        """按叠加层数返回额外判定区的旋转角度（每层 2 个，最多 4 个）。"""
        layers = max(0, min(self.stack, len(self.ANGLES_PER_STACK)))
        angles = []
        for layer in self.ANGLES_PER_STACK[:layers]:
            angles.extend(layer)
        return angles

    def bite_count(self):
        """额外判定区数量（不含正前方的主判定区）。"""
        return len(self.attack_extra_angles())

    def on_attack(self, player, target_group):
        """
        player: 玩家对象（需有get_attack_rect、facing_left等属性）
        target_group: 敌人组
        """
        # 原攻击rect与旋转中心
        main_rect = player.get_attack_rect()
        center = pygame.Vector2(player.getrect().center)
        angle_list = self.attack_extra_angles()
        hit_enemies = []
        for angle in angle_list:
            bite_rect = rotate_rect(main_rect, center, angle)
            # 检查碰撞
            for enemy in target_group:
                if bite_rect.colliderect(enemy.getrect()) and enemy not in hit_enemies:
                    hit_enemies.append(enemy)
        return hit_enemies

    def draw_effect(self, player, ds, camera=None):
        """绘制额外撕咬判定区的咬合动画。"""
        if not (player.is_attacking or player.bite_animating):
            return
        main_rect = player.get_attack_rect()
        bite_idx = min(player.bite_frame // 2, len(player.bite_images) - 1)
        bite_img = pygame.transform.scale(player.bite_images[bite_idx], (main_rect.width, main_rect.height))
        center = pygame.Vector2(player.getrect().center)
        for angle in self.attack_extra_angles():
            bite_rect = rotate_rect(main_rect, center, angle)
            blit_rect = bite_img.get_rect(center=bite_rect.center)
            ds.blit(bite_img, camera.apply(blit_rect) if camera is not None else blit_rect)


class Whirlwind:
    """一个向前飞行的旋风。

    速度按反比例函数衰减：v(t) = v0 / (1 + k*t)，所以刚出手时飞快，越飞越慢，
    飞行距离 = (v0/k) * ln(1 + k*T)，不会无限制跑下去。
    """

    def __init__(self, pos, direction, speed0, decay, lifetime, damage, radius, color):
        self.pos = pygame.Vector2(pos)
        self.dir = pygame.Vector2(direction)
        if self.dir.length_squared() > 0:
            self.dir = self.dir.normalize()
        self.speed0 = speed0
        self.decay = decay
        self.lifetime = lifetime
        self.damage = damage
        self.radius = radius
        self.color = color
        self.t = 0.0
        self.hit = []  # 已命中过的敌人（防止同一个旋风反复扣血）

    def speed(self):
        """当前速度（像素/帧），随时间反比例衰减。"""
        return self.speed0 / (1.0 + self.decay * self.t)

    def update(self, dt=1 / 60):
        """推进一步，返回自身是否已耗尽。"""
        self.pos += self.dir * self.speed() * dt
        self.t += dt
        return self.t + 1e-9 >= self.lifetime

    @property
    def fade(self):
        """剩余生命比例（1 → 0），用于淡出。"""
        return max(0.0, 1.0 - self.t / max(1.0, self.lifetime))

    def get_rect(self):
        r = max(6, int(self.radius * (0.65 + 0.35 * self.fade)))
        return pygame.Rect(int(self.pos.x) - r, int(self.pos.y) - r, r * 2, r * 2)


class WhirlwindBiteAbility(Ability):
    """
    旋风撕咬：每次攻击时，当前每个攻击判定区都会向前放出一个小旋风。

    旋风速度按反比例函数衰减（v = v0/(1+k t)），越飞越慢，命中敌人扣血。
    若同时拥有多重撕咬，每个额外判定区也会各放一个旋风（方向与判定区一致）。
    """
    max_stack = 3
    MAX_WHIRLWINDS = 24        # 同时存在的旋风上限（防止叠加层数过高时爆量）
    BASE_SPEED = 8.0 * 60      # 首层初始速度（像素/秒）
    BASE_DECAY = 0.05 * 60     # 速度衰减系数 k（每秒）
    BASE_LIFETIME = 90 / 60    # 首层存活时间（秒）
    BASE_DAMAGE = 25           # 首层单个旋风的伤害
    BASE_RADIUS = 44           # 首层判定/绘制半径
    PER_STACK_SPEED = 2.0 * 60 # 每多一层：速度（像素/秒）
    PER_STACK_LIFETIME = 15 / 60  # 每多一层：存活时间（秒）
    PER_STACK_DAMAGE = 15      # 每多一层：伤害
    PER_STACK_RADIUS = 6       # 每多一层：半径

    def __init__(self):
        super().__init__(
            ability_name="旋风撕咬",
            ability_quality="史诗",
            ability_description="攻击时每个判定区向前放出旋风，速度逐渐衰减；每层 +15 伤害。",
        )
        self.whirlwinds = []
        self.decay = self.BASE_DECAY
        self.speed0 = self.BASE_SPEED
        self.lifetime = self.BASE_LIFETIME
        self.damage = self.BASE_DAMAGE
        self.radius = self.BASE_RADIUS
        self._visuals = {}        # 旋风贴图缓存：(半径, 颜色) -> Surface

    def refresh_stats(self):
        """按当前层数重算属性：首层就是基础值，之后每层线性递增。"""
        extra = max(0, self.stack - 1)
        self.speed0 = self.BASE_SPEED + self.PER_STACK_SPEED * extra
        self.lifetime = self.BASE_LIFETIME + self.PER_STACK_LIFETIME * extra
        self.damage = self.BASE_DAMAGE + self.PER_STACK_DAMAGE * extra
        self.radius = self.BASE_RADIUS + self.PER_STACK_RADIUS * extra

    def apply_to_player(self, player):
        self.refresh_stats()

    # ---------------- 释放 ----------------
    def on_attack_start(self, player):
        """每次出手，当前每个攻击判定区向前放出一个旋风。"""
        main_rect = player.get_attack_rect()
        center = pygame.Vector2(player.getrect().center)
        base_dir = pygame.Vector2(-1 if player.facing_left else 1, 0)
        for angle in player.attack_angles():
            rect = main_rect if angle == 0 else rotate_rect(main_rect, center, angle)
            direction = rotate_vector(base_dir, angle)
            self.whirlwinds.append(Whirlwind(
                pos=pygame.Vector2(rect.center),
                direction=direction,
                speed0=self.speed0,
                decay=self.decay,
                lifetime=self.lifetime,
                damage=self.damage,
                radius=self.radius,
                color=self.quality_color,
            ))
        # 超出上限时丢掉最旧的
        if len(self.whirlwinds) > self.MAX_WHIRLWINDS:
            del self.whirlwinds[:len(self.whirlwinds) - self.MAX_WHIRLWINDS]

    # ---------------- 每帧推进与伤害 ----------------
    def on_update(self, player, level=None, dt=1 / 60):
        if not self.whirlwinds:
            return
        for whirl in list(self.whirlwinds):
            expired = whirl.update(dt)
            rect = whirl.get_rect()
            if level is not None:
                for group in (getattr(level, 'enemy_group', None),
                              getattr(level, 'attack_enemy_group', None)):
                    if not group:
                        continue
                    for enemy in list(group):
                        if enemy in whirl.hit:
                            continue
                        if rect.colliderect(enemy.getrect()):
                            whirl.hit.append(enemy)
                            if enemy.hp_caculater(self.damage) <= 0:
                                # 交由关卡统一结算（音效、刷新、成长、分数）
                                player.pending_kills.append(enemy)
            if expired:
                self.whirlwinds.remove(whirl)

    # ---------------- 绘制 ----------------
    def _visual(self, radius, color):
        """按半径与颜色缓存螺旋贴图，避免每帧重建表面。"""
        key = (int(radius), tuple(color))
        surf = self._visuals.get(key)
        if surf is None:
            r = int(radius)
            d = r * 2 + 8
            surf = pygame.Surface((d, d), pygame.SRCALPHA)
            center = (d // 2, d // 2)
            # 淡淡的涡心 + 三圈旋转弧，读起来像一个转动的旋风
            pygame.draw.circle(surf, (*color, 40), center, max(2, int(r * 0.3)))
            pygame.draw.circle(surf, (255, 255, 255, 45), center, max(2, int(r * 0.14)))
            outer = pygame.Rect(0, 0, r * 2, r * 2)
            outer.center = center
            width = max(3, int(r * 0.18))
            for i in range(3):
                start = i * (math.tau / 3)
                pygame.draw.arc(surf, (*color, 250), outer, start, start + 1.6, width)
            inner = outer.inflate(-int(r * 0.85), -int(r * 0.85))
            for i in range(3):
                start = i * (math.tau / 3) + 0.7
                pygame.draw.arc(surf, (255, 255, 255, 200), inner, start, start + 1.0, max(2, width - 2))
            self._visuals[key] = surf
        return surf

    def draw_effect(self, player, ds, camera=None):
        for whirl in self.whirlwinds:
            visual = self._visual(whirl.radius, whirl.color)
            img = pygame.transform.rotate(visual, whirl.t * 60 * 9.0)
            img.set_alpha(int(60 + 195 * whirl.fade))
            pos = camera.apply_pos(whirl.pos) if camera is not None else whirl.pos
            ds.blit(img, img.get_rect(center=(int(pos[0]), int(pos[1]))))


def all_ability_classes():
    """返回本模块中所有可抽取的能力类（供 UpgradeUI 使用）。"""
    classes = []
    for value in globals().values():
        if isinstance(value, type) and issubclass(value, Ability) and value is not Ability and value not in classes:
            classes.append(value)
    return classes
