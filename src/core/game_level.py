import pygame
import sys
import const
import image
from sound import *
from core.base_level import BaseLevel
import random
from Enemies import Enemy
import random
from Enemies import AttackEnemy
import camera

class GameLevel(BaseLevel):
    def __init__(self, multiplayer=False):
        super().__init__()
        self.game_state = "game_state"
        self.multiplayer = multiplayer
        if not self.multiplayer:
            loading_thread = self.start_loading()
            self.setup_ui()
            self.stop_loading(loading_thread)
        else:
            self.setup_ui()
        self.circulating_times = 0
        self.enemy_group = pygame.sprite.Group()  # 普通敌人
        self.attack_enemy_group = pygame.sprite.Group()  # 攻击型敌人
        self.camera = camera.Camera(const.wsize, const.hsize)

    def setup_ui(self):
        self.game_exit_font = image.mFont(const.exittitle, 'font/BoutiqueBitmap9x9_Bold_1.9.TTF', const.text_size, (230, 100, 150), (const.wsize, 10))
        self.background = image.Image('picture/bg0.jpg', (const.wsize, const.hsize), (0, 0), 0, 1, 0)
        self.grass_img = pygame.image.load('picture/grass.png').convert()
        self.capoo_surface = image.Image('picture/Capoo/%d.png', (const.capoo_width, const.capoo_hight), (const.capoo_x, const.capoo_y), 1, 8, 1)
        self.capoo_jiao = Soundm('sound/capoo.wav', const.sfx_vol)
        self.spawn_enemy_cd = 120
        self.spawn_timer = 0

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.VIDEORESIZE:
                new_width, new_height = self.handle_resize(event, self.background)
                new_font_size = int(const.title1_size * (new_height / const.hsize))
                self.background = image.Image('picture/bg0.jpg', (const.wsize, const.hsize), (0, 0), 0, 1, 0)
                self.game_exit_font.pos = [(new_width - self.game_exit_font.getrect().width - 10), 10]
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_j:
                    self.capoo_surface.start_attack()
            elif event.type == pygame.KEYDOWN or event.type == pygame.KEYUP:
                pass

            button_result = self.game_exit_font.Button(event, "main_menu")
            if button_result['state_change']:
                const.Reset_Game_Const()
                self.game_state = button_result['new_state']
                return True
        return False

    def get_shrink_speed(self, score):
        # 体型衰减速度 = 基础速度 * exp(得分 * 系数)
        # 系数可调，建议0.01~0.05，基础速度为负数
        import math
        base_speed_x = -0.06
        base_speed_y = -0.04
        k = 0.08
        speed_x = base_speed_x * math.exp(k * score)
        speed_y = base_speed_y * math.exp(k * score)
        return speed_x, speed_y

    def update_game(self):
        self.capoo_surface.Player_move(self.enemy_group, self.attack_enemy_group)
        self.capoo_surface.play_attack_animation()
        # 敌人生成（1:3比例生成攻击型和普通型）
        self.spawn_timer += 1
        if self.spawn_timer >= self.spawn_enemy_cd:
            # 计算当前camera视野范围
            cam_left = self.camera.offset_x
            cam_right = self.camera.offset_x + const.wsize
            cam_top = self.camera.offset_y
            cam_bottom = self.camera.offset_y + const.hsize
            margin = 100  # 生成在视野外100像素区域
            pos = [0,0]
            side = random.choice(['left', 'right','top','bottom'])
            if side == 'left':
                pos[0] = random.randint(cam_left - margin - 80, cam_left - 80)
                pos[1] = random.randint(cam_top - margin, cam_bottom + margin - 80)
            elif side == 'right':
                pos[0] = random.randint(cam_right, cam_right + margin)
                pos[1] = random.randint(cam_top - margin, cam_bottom + margin - 80)
            elif side == 'top':
                pos[0] = random.randint(cam_left - margin, cam_right + margin - 80)
                pos[1] = random.randint(cam_top - margin - 80, cam_top - 80)
                if pos[1] + 80 > cam_top:
                    pos[1] = cam_top - 80
            else:  # bottom
                pos[0] = random.randint(cam_left - margin, cam_right + margin - 80)
                pos[1] = random.randint(cam_bottom, cam_bottom + margin)
            if pos[1] < cam_bottom:
                pos[1] = cam_bottom
            if random.randint(0, 3) == 0:
                enemy = AttackEnemy(self.capoo_surface, size=(80, 80), speed=5)
                enemy.pos = pos
                self.attack_enemy_group.add(enemy)
            else:
                enemy = Enemy(self.capoo_surface, size=(50, 50), speed=5)
                enemy.pos = pos
                self.enemy_group.add(enemy)
            self.spawn_timer = 0
        # 攻击型敌人移动和动画
        for enemy in self.attack_enemy_group:
            if hasattr(enemy, 'try_attack'):
                if enemy.try_attack():
                    continue  # 进入攻击状态后不移动
            enemy.move_towards_player(self.attack_enemy_group)
            enemy.play_animation()
        # 普通敌人移动和动画，聚合中心为攻击型敌人群体
        # 计算攻击型敌人群体中心
        if len(self.attack_enemy_group) > 0:
            centers = [pygame.Vector2(e.getrect().center) for e in self.attack_enemy_group]
            attack_center = sum(centers, pygame.Vector2(0,0)) / len(centers)
        else:
            attack_center = pygame.Vector2(const.wsize//2, const.hsize//2)
        for enemy in self.enemy_group:
            # 普通敌人根据玩家与攻击型敌人群体中心连线移动并保持距离
            enemy.move_behead_attacker(attack_center, pygame.Vector2(self.capoo_surface.getrect().center),enemies = self.enemy_group)
            enemy.play_animation()
        # 体型随分数指数衰减
        shrink_x, shrink_y = self.get_shrink_speed(const.player_score)
        self.capoo_surface.change_rect(shrink_x, shrink_y)
        self.circulating_times += 1
        if self.circulating_times == 10:
            self.circulating_times = 0
            const.update_score(self.capoo_surface.size[0])
        # 玩家攻击判定
        if self.capoo_surface.is_attacking:
            attack_rect = self.capoo_surface.get_attack_rect()
            for enemy in self.attack_enemy_group:
                if attack_rect.colliderect(enemy.getrect()) and enemy not in self.capoo_surface.attack_hit_enemies:
                    self.capoo_surface.attack_hit_enemies.append(enemy)
                    if enemy.hp_caculater(self.capoo_surface.attack_damage) <= 0:
                        self.capoo_jiao.Play_sound(False)
                        enemy.reset(self.camera)
                        self.capoo_surface.change_rect(6, 4)
                        const.update_score(self.capoo_surface.size[0])
                        break
            # 玩家攻击判定（普通敌人）
            for enemy in self.enemy_group:
                if attack_rect.colliderect(enemy.getrect()) and enemy not in self.capoo_surface.attack_hit_enemies:
                    self.capoo_surface.attack_hit_enemies.append(enemy)
                    if enemy.hp_caculater(self.capoo_surface.attack_damage) <= 0:
                        self.capoo_jiao.Play_sound(False)
                        enemy.reset(self.camera)
                        self.capoo_surface.change_rect(6, 4)
                        const.update_score(self.capoo_surface.size[0])
                        break
        capoo_rect = self.capoo_surface.getrect()
        capoo_mask = self.capoo_surface.get_mask()
        # 攻击型敌人攻击完成后再次检测攻击rect是否与玩家rect碰撞，若碰撞则扣分
        for enemy in self.attack_enemy_group:
            if hasattr(enemy, 'attack_finished') and enemy.attack_finished:
                attack_rect = enemy.get_attack_rect()
                attack_offset = (attack_rect.x - capoo_rect.x, attack_rect.y - capoo_rect.y)
                attack_mask = pygame.mask.Mask((attack_rect.width, attack_rect.height), True)
                if capoo_mask.overlap(attack_mask, attack_offset):
                    self.capoo_surface.change_rect(shrink_x*10, shrink_y*10)
                    const.update_score(self.capoo_surface.size[0])
                enemy.attack_finished = False
        if const.player_score <= -8:
            Game_over_Font = image.mFont("GAME OVER", 'font/BoutiqueBitmap9x9_Bold_1.9.ttf', 100, (230, 100, 150), (const.wsize/2, const.hsize/2))
            Game_over_Font.fdraw(self.DS)
            pygame.display.flip()
            pygame.time.delay(1000)
            const.Reset_Game_Const()
            self.game_state = "main_menu"
            return True
        return False

    def draw(self):
        self.camera.update(self.capoo_surface.getrect())
        # 平铺grass.png作为背景
        grass_w, grass_h = self.grass_img.get_width(), self.grass_img.get_height()
        offset_x = self.camera.offset_x % grass_w
        offset_y = self.camera.offset_y % grass_h
        for x in range(-grass_w, const.wsize + grass_w, grass_w):
            for y in range(-grass_h, const.hsize + grass_h, grass_h):
                screen_x = x - offset_x
                screen_y = y - offset_y
                self.DS.blit(self.grass_img, (screen_x, screen_y))
        self.game_exit_font.fdraw(self.DS)  # UI元素一般不跟随相机
        image.mFont("score:" + str(const.player_score), 'font/BoutiqueBitmap9x9_Bold_1.9.ttf', 50, (230, 100, 150), (const.wsize, 160)).fdraw(self.DS)
        self.capoo_surface.draw(self.DS, self.camera)
        for enemy in self.enemy_group:
            enemy.draw(self.DS, self.camera)
        for enemy in self.attack_enemy_group:
            enemy.draw(self.DS, self.camera)
        pygame.display.flip()

    def run(self):
        while True:
            if self.handle_events():
                break
            if self.update_game():
                break
            self.draw()
        return self.game_state
