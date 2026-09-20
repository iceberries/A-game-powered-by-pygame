from image import Image
import random
import math
import pygame
import const
class Enemy(Image, pygame.sprite.Sprite):
    SPRITE_PATH = 'picture/Enemy/%d.png'  # 行走动画贴图（子类可覆盖）
    FRAME_NUM = 3                         # 行走动画帧数（子类可覆盖）

    def __init__(self, player, size=(50, 50), speed=120):
        pygame.sprite.Sprite.__init__(self)
        side = random.choice(['left', 'right'])
        y = random.randint(0, const.hsize - size[1])
        if side == 'left':
            x = 0
        else:
            x = const.wsize - size[0]
        super().__init__(self.SPRITE_PATH, size, (x, y), 1, self.FRAME_NUM, 1, facing_left=(side == 'left'))
        self.player = player
        self.speed = speed
        self.pos = [x, y]
        self.facing_left = side == 'left'
        self.original_image = self.image.copy() if hasattr(self.image, 'copy') else self.image
        self.runaway_timer = 0.0  # 逃跑剩余时间（秒）
        self.max_hp = const.Enemy_HP
        self.hp = self.max_hp

    def update_boids(self, enemies, separation_weight=0.8, alignment_weight=0.6, cohesion_weight=0.5, neighbor_radius=20):
        separation = pygame.Vector2(0, 0)
        alignment = pygame.Vector2(0, 0)
        cohesion = pygame.Vector2(0, 0)
        count = 0
        my_center = pygame.Vector2(self.getrect().center)
        for other in enemies:
            if other is self:
                continue
            other_center = pygame.Vector2(other.getrect().center)
            dist = my_center.distance_to(other_center)
            if dist < neighbor_radius:
                separation += (my_center - other_center) / (dist + 1e-5)
                alignment += pygame.Vector2(other.speed if hasattr(other, 'speed') else 2, 0)
                cohesion += other_center
                count += 1
        if count > 0:
            separation /= count
            alignment /= count
            cohesion = (cohesion / count - my_center)
        boid_vec = separation * separation_weight + alignment * alignment_weight + cohesion * cohesion_weight
        # 限制boid_vec最大幅度，防止横跳
        max_boid = self.speed * 0.8
        if boid_vec.length() > max_boid:
            boid_vec = boid_vec.normalize() * max_boid
        return boid_vec

    def hp_caculater(self, damage):
        self.hp -= damage
        return self.hp

    def avoid_overlap(self, enemies,sep_plus = 2):
        # 体积碰撞分离，防止重叠
        my_rect = self.getrect()
        for other in enemies:
            if other is self:
                continue
            other_rect = other.getrect()
            if my_rect.colliderect(other_rect):
                # 计算分离向量
                dx = my_rect.centerx - other_rect.centerx
                dy = my_rect.centery - other_rect.centery
                dist = max(1, (dx ** 2 + dy ** 2) ** 0.5)
                sep_vec = pygame.Vector2(dx, dy) / dist * sep_plus  # 分离强度可调
                self.pos[0] += sep_vec.x
                self.pos[1] += sep_vec.y

    def should_runaway(self, target, runaway_distance=300, runaway_duration=0.5,
                       speed_plus=1, dt=const.FIXED_DT):
        tx, ty = target.getrect().center if hasattr(target, 'getrect') else target
        ex, ey = self.getrect().center
        dx, dy = tx - ex, ty - ey
        vec = pygame.Vector2(dx, dy)
        distance = vec.length()
        if distance > 0:
            if self.runaway_timer > 0:
                self.runaway_timer = max(0.0, self.runaway_timer - dt)
                return True, (-vec).normalize() * (speed_plus*self.speed)
            elif distance < runaway_distance:
                self.runaway_timer = runaway_duration
                return True, (-vec).normalize() * (speed_plus*self.speed)
        return False, vec.normalize() * self.speed if distance > 0 else pygame.Vector2(0, 0)

    def play_animation(self, dt=const.FIXED_DT):
        self.updataRecord(self.Record + 1)
    
    def reset(self, camera=None):
        # 视野外随机生成
        cam_left = camera.offset_x
        cam_right = camera.offset_x + const.wsize
        cam_top = camera.offset_y
        cam_bottom = camera.offset_y + const.hsize
        margin = 100
        size = self.size
        side = random.choice(['left', 'right', 'top', 'bottom'])
        if side == 'left':
            x = random.randint(cam_left - margin - size[0], cam_left - size[0])
            y = random.randint(cam_top - margin, cam_bottom + margin - size[1])
            if x + size[0] > cam_left:
                x = cam_left - size[0]
        elif side == 'right':
            x = random.randint(cam_right, cam_right + margin)
            y = random.randint(cam_top - margin, cam_bottom + margin - size[1])
            if x < cam_right:
                x = cam_right
        elif side == 'top':
            x = random.randint(cam_left - margin, cam_right + margin - size[0])
            y = random.randint(cam_top - margin - size[1], cam_top - size[1])
            if y + size[1] > cam_top:
                y = cam_top - size[1]
        else:  # bottom
            x = random.randint(cam_left - margin, cam_right + margin - size[0])
            y = random.randint(cam_bottom, cam_bottom + margin)
            if y < cam_bottom:
                y = cam_bottom
        self.pos = [x, y]
        self.facing_left = side == 'left'
        self.Record = self.Index
        self.reloade()
        self.runaway_timer = 0.0  # 重置逃跑计时器
        self.hp = self.max_hp

    def draw(self, ds, camera=None):
        if camera is not None:
            ds.blit(self.image, camera.apply(self.getrect()))
        else:
            ds.blit(self.image, self.getrect())

    def move_behead_attacker(self, attack_center, player_pos, keep_distance=200,
                             runaway_duration=0.5, player_runaway_distance=200,
                             player_runaway_duration=20 / 60, enemies=None,
                             dt=const.FIXED_DT):
        my_center = pygame.Vector2(self.getrect().center)

        # 玩家与群体中心连线向量
        line_vec = attack_center - player_pos
        if line_vec.length() > 0:
            line_vec = line_vec.normalize()
        # 敌人到群体中心距离
        to_center = attack_center - my_center
        distance = to_center.length()
        # 目标点：群体中心沿玩家-群体连线方向偏移
        target_point = attack_center + line_vec * 80
        to_target = target_point - my_center
        # 玩家过于靠近时逃跑
        runaway_player, player_escape_vec = self.should_runaway(
            player_pos, player_runaway_distance, player_runaway_duration, 2, dt)
        if runaway_player:
            move_vec = player_escape_vec
        else:
            # 使用should_runaway统一逃跑判定（对群体中心）
            runaway, move_vec = self.should_runaway(
                attack_center, keep_distance, runaway_duration, 1, dt)
            if not runaway:
                move_vec = to_target.normalize() * self.speed
        # 群体智能分布
        boid_vec = pygame.Vector2(0, 0)
        final_vec = move_vec + boid_vec
        if enemies is not None:
            self.avoid_overlap(enemies,3)
            if hasattr(self, 'update_boids'):
                boid_vec = self.update_boids(enemies)
        self.pos[0] += final_vec.x * dt
        self.pos[1] += final_vec.y * dt
        prev_facing = self.facing_left
        self.facing_left = final_vec.x < 0
        if prev_facing != self.facing_left:
            self.image = pygame.transform.flip(self.original_image, not self.facing_left, False)
        self.reloade()

class AttackEnemy(Enemy):
    def __init__(self, player, size=(80, 80), speed=120):
        super().__init__(player, size, speed)
        self.max_hp = const.AttackEnemy_HP
        self.hp = self.max_hp
        self.walk_paths = ['picture/Enemy/1.PNG', 'picture/Enemy/2.PNG', 'picture/Enemy/3.PNG']
        self.attack_paths = ['picture/Enemy/AT0.PNG', 'picture/Enemy/AT1.PNG', 'picture/Enemy/AT2.PNG']
        self.is_attacking = False
        self.attack_frame = 0.0
        self.attack_cooldown = 20 / 60  # 攻击动画时长（秒）
        self.attack_finished = False
    def get_attack_rect(self):
        rect = self.getrect().copy()
        if self.facing_left:
            rect.width = rect.width // 5
            rect.left -= rect.width
        else:
            rect.width = rect.width // 5
            rect.left += rect.width * 4
        return rect

    def move_towards_player(self, enemies=None, dt=const.FIXED_DT):
        if self.is_attacking:
            return  # 攻击时不移动
        # 仅实现靠近玩家和群体智能，不包含逃跑逻辑
        boid_vec = pygame.Vector2(0, 0)
        if enemies is not None:
            if hasattr(self, 'update_boids'):
                boid_vec = self.update_boids(enemies)
            self.avoid_overlap(enemies,3)
        px, py = self.player.getrect().center
        ex, ey = self.getrect().center
        dx, dy = px - ex, py - ey
        player_vec = pygame.Vector2(dx, dy)
        if player_vec.length() > 0:
            player_vec = player_vec.normalize() * self.speed
        final_vec = player_vec + boid_vec
        self.pos[0] += final_vec.x * dt
        self.pos[1] += final_vec.y * dt
        prev_facing = self.facing_left
        self.facing_left = final_vec.x < 0
        if prev_facing != self.facing_left:
            self.image = pygame.transform.flip(self.original_image, not self.facing_left, False)
        self.reloade()

    def play_animation(self, dt=const.FIXED_DT):
        if self.is_attacking:
            # 播放攻击动画
            progress = min(1.0, self.attack_frame / max(self.attack_cooldown, 1e-6))
            idx = min(int(progress * len(self.attack_paths)), len(self.attack_paths) - 1)
            path = self.attack_paths[idx]
            self.original_image = pygame.image.load(path).convert_alpha()
            self.original_image = pygame.transform.scale(self.original_image, self.size)
            self.image = pygame.transform.flip(self.original_image, not self.facing_left, False)
            self.attack_frame += dt
            if self.attack_frame + const.TIME_EPSILON >= self.attack_cooldown:
                self.is_attacking = False
                self.attack_frame = 0.0
                self.attack_finished = True
        else:
            # 行走动画
            idx = (self.Record % 3)
            path = self.walk_paths[idx]
            self.original_image = pygame.image.load(path).convert_alpha()
            self.original_image = pygame.transform.scale(self.original_image, self.size)
            self.image = pygame.transform.flip(self.original_image, not self.facing_left, False)
            self.updataRecord(self.Record + 1)

    def try_attack(self):
        if self.is_attacking:
            return False
        attack_rect = self.get_attack_rect()
        player_rect = self.player.getrect()
        if attack_rect.colliderect(player_rect):
            self.is_attacking = True
            self.attack_frame = 0.0
            self.attack_finished = False
            return True
        return False

    def reset(self, camera=None):
        super().reset(camera)
        self.is_attacking = False
        self.attack_frame = 0.0
        self.attack_finished = False
        self.hp = self.max_hp


class RewardChick(Enemy):
    """
    绿色奖励小鸡：前期少量出现，不会攻击玩家。

    被咬到（1 点血，任何一次攻击都能吃掉）后给玩家一大口体型成长与额外分数，
    用来帮玩家度过体型衰减最快的开局阶段。
    """
    SPRITE_PATH = 'picture/Capoo/%d.PNG'   # 复用主角贴图，染成绿色
    FRAME_NUM = 8
    TINT = (110, 255, 120)                 # 绿色染色（BLEND_RGBA_MULT）
    GROWTH = (20, 14)                      # 吃掉后的体型成长（远大于普通击杀的 6/4）

    def __init__(self, player, size=(44, 32), speed=180):
        super().__init__(player, size, speed)
        self.max_hp = 1
        self.hp = self.max_hp
        self.wobble = random.uniform(0, math.tau)

    def reloade(self):
        """每次动画换帧后重新染成绿色（父类会重新加载原始贴图）。"""
        super().reloade()
        self.image = self._tinted(self.image)
        self.original_image = self._tinted(self.original_image)

    def _tinted(self, surface):
        if surface is None:
            return None
        tinted = surface.copy()
        tinted.fill((*self.TINT, 255), special_flags=pygame.BLEND_RGBA_MULT)
        return tinted

    def move_towards_player(self, enemies=None, dt=const.FIXED_DT):
        """慢悠悠地摇向玩家，方便被咬到；不参与攻击。"""
        if enemies is not None:
            self.avoid_overlap(enemies, 2)
        self.wobble += 0.12
        px, py = self.player.getrect().center
        ex, ey = self.getrect().center
        vec = pygame.Vector2(px - ex, py - ey)
        if vec.length() > 1:
            vec = vec.normalize().rotate(math.sin(self.wobble) * 14) * self.speed
        self.pos[0] += vec.x * dt
        self.pos[1] += vec.y * dt
        prev_facing = self.facing_left
        self.facing_left = vec.x < 0
        if prev_facing != self.facing_left:
            self.image = pygame.transform.flip(self.original_image, not self.facing_left, False)
        self.updataRecord(self.Record + 1)

    def draw(self, ds, camera=None):
        super().draw(ds, camera)
        gray = self.getrect()
        rect = camera.apply(gray) if camera is not None else gray
        # 头顶绿色小环，提示这是可吃掉的奖励
        pygame.draw.circle(ds, (120, 255, 140), (rect.centerx, rect.top - 6), 6, 2)

    def start_attack(self):
        if not hasattr(self, 'is_attacking'):
            self.is_attacking = False
        if not hasattr(self, 'attack_frame'):
            self.attack_frame = 0
        if not self.is_attacking:
            self.is_attacking = True
            self.attack_frame = 0

    def draw(self, ds, camera=None):
        if camera is not None:
            ds.blit(self.image, camera.apply(self.getrect()))
        else:
            ds.blit(self.image, self.getrect())
