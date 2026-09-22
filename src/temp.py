
# 剪贴板以及临时处理

from image import Image
import pygame
import random
import const
from core.assets import ASSETS
class Enemy(Image):
    def __init__(self, player, size=(50, 50), speed=2):
        side = random.choice(['left', 'right'])
        y = random.randint(0, const.hsize - size[1])
        if side == 'left':
            x = 0
        else:
            x = const.wsize - size[0]
        super().__init__('picture/Enemy/%d.png', size, (x, y), 1, 3, 1, facing_left=(side == 'left'))
        self.player = player
        self.speed = speed
        self.pos = [x, y]
        self.facing_left = side == 'left'
        self.original_image = self.image.copy() if hasattr(self.image, 'copy') else self.image
        self.runaway_timer = 0  # 逃跑计时器

    def update_boids(self, enemies, separation_weight=0.5, alignment_weight=0.3, cohesion_weight=1.2, neighbor_radius=40):
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

    def avoid_overlap(self, enemies):
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
                sep_vec = pygame.Vector2(dx, dy) / dist * 2  # 分离强度可调
                self.pos[0] += sep_vec.x
                self.pos[1] += sep_vec.y

    def move_towards_player(self, enemies=None):
        boid_vec = pygame.Vector2(0, 0)
        if enemies is not None:
            if hasattr(self, 'update_boids'):
                boid_vec = self.update_boids(enemies)
            self.avoid_overlap(enemies)
        px, py = self.player.getrect().center
        ex, ey = self.getrect().center
        dx, dy = px - ex, py - ey
        player_vec = pygame.Vector2(dx, dy)
        distance = player_vec.length()
        runaway_distance = 300  # 判定距离
        runaway_duration = 30   # 逃跑帧数
        if distance > 0:
            if self.runaway_timer > 0:
                player_vec = (-player_vec).normalize() * (2*self.speed)
                self.runaway_timer -= 1
            elif distance < runaway_distance:
                self.runaway_timer = runaway_duration
                player_vec = (-player_vec).normalize() * (2*self.speed)
            else:
                player_vec = player_vec.normalize() * self.speed
        # 合成速度时主导玩家追踪方向
        final_vec = player_vec * 0.7 + boid_vec * 0.3
        # 限制最终速度幅度
        max_speed = 2*self.speed
        if final_vec.length() > max_speed:
            final_vec = final_vec.normalize() * max_speed
        self.pos[0] += final_vec.x
        self.pos[1] += final_vec.y
        prev_facing = self.facing_left
        self.facing_left = final_vec.x < 0
        if prev_facing != self.facing_left:
            self.image = pygame.transform.flip(self.original_image, not self.facing_left, False)
        self.reloade()

    def play_animation(self):
        self.updataRecord(self.Record + 1)
    
    def reset(self):
        # 重置位置为左右随机
        side = random.choice(['left', 'right'])
        y = random.randint(0, const.hsize - self.size[1])
        if side == 'left':
            x = 0
        else:
            x = const.wsize - self.size[0]
        self.pos = [x, y]
        self.facing_left = side == 'left'
        self.Record = self.Index
        self.reloade()
        self.runaway_timer = 0  # 重置逃跑计时器

class AttackEnemy(Enemy):
    def __init__(self, player, size=(80, 80), speed=2):
        super().__init__(player, size, speed)
        self.walk_paths = ['picture/Enemy/1.PNG', 'picture/Enemy/2.PNG', 'picture/Enemy/3.PNG']
        self.attack_paths = ['picture/Enemy/AT0.PNG', 'picture/Enemy/AT1.PNG', 'picture/Enemy/AT2.PNG']
        self.is_attacking = False
        self.attack_frame = 0
        self.attack_cooldown = 20  # 攻击动画帧数
        self.attack_finished = False

    def start_attack(self):
        if not self.is_attacking:
            self.is_attacking = True
            self.attack_frame = 0

    def play_attack_animation(self):
        if self.is_attacking:
            idx = min(self.attack_frame // max(1, self.attack_cooldown // 3), len(self.attack_paths) - 1)
            path = self.attack_paths[idx]
            self.original_image = ASSETS.image(path, self.size)
            self.image = ASSETS.image(path, self.size, not self.facing_left)
            self.attack_frame += 1
            if self.attack_frame >= self.attack_cooldown:
                self.is_attacking = False
                self.attack_frame = 0
                self.attack_finished = True
        else:
            self.reloade()

    def get_attack_rect(self):
        rect = self.getrect().copy()
        if self.facing_left:
            rect.width = rect.width // 5
            rect.left -= rect.width
        else:
            rect.width = rect.width // 5
            rect.left += rect.width * 4
        return rect

    def try_attack(self):
        if self.is_attacking:
            return False
        attack_rect = self.get_attack_rect()
        player_rect = self.player.getrect()
        if attack_rect.colliderect(player_rect):
            self.start_attack()
            self.attack_finished = False
            return True
        return False

    def reset(self):
        super().reset()
        self.is_attacking = False
        self.attack_frame = 0
        self.attack_finished = False
