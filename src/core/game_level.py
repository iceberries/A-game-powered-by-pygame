import pygame
import sys
import math
import const
import image
from sound import *
from core.base_level import BaseLevel
import random
from Enemies import Enemy
import random
from Enemies import AttackChicken, GreenCapoo
import camera
from upgrade_ui import UpgradeUI
from core.game_rules import DEFAULT_RULES
from core.assets import ASSETS
from core.spatial_hash import SpatialHash
from core.state import DISPLAY_SETTINGS, GAME_SESSION

class GameLevel(BaseLevel):
    RULES = DEFAULT_RULES

    def __init__(self, session=None, rules=None):
        super().__init__()
        self.session = session or GAME_SESSION
        self.rules = rules or self.RULES
        self.game_state = "game_state"
        loading_token = self.start_loading()
        self.setup_ui()
        self.stop_loading(loading_token)
        self.score_update_timer = 0.0
        self.enemy_group = pygame.sprite.Group()  # 普通敌人
        self.attack_enemy_group = pygame.sprite.Group()  # 攻击型敌人
        self.green_capoo_group = pygame.sprite.Group()
        self.camera = camera.Camera(const.wsize, const.hsize)

    def setup_ui(self):
        self.game_exit_font = image.mFont(const.exittitle, 'font/BoutiqueBitmap9x9_Bold_1.9.TTF', const.text_size, (230, 100, 150), (const.wsize, 10))
        self.background = image.Image('picture/bg0.jpg', (const.wsize, const.hsize), (0, 0), 0, 1, 0)
        self.grass_img = ASSETS.image('picture/grass.png')
        self.capoo_surface = image.Image('picture/Capoo/%d.png', (const.capoo_width, const.capoo_hight), (const.capoo_x, const.capoo_y), 1, 8, 1)
        self.capoo_jiao = Soundm(
            'sound/capoo.wav', DISPLAY_SETTINGS.sfx_volume,
        )
        # 刷怪、绿 Capoo 与攻击大鸡进度。
        self.elapsed = 0.0           # 关卡已经历时间（秒）
        self.spawn_timer = 0.0
        self.green_capoos_spawned = 0
        self.green_capoos_eaten = 0
        self.floating_texts = []     # [(文字, 世界坐标, 剩余帧数, 颜色)]
        self.reset_progress()

    def reset_progress(self):
        """重置一局内的进度计时（进入关卡时调用）。"""
        self.elapsed = 0.0
        self.spawn_timer = 0.0
        self.green_capoos_spawned = 0
        self.green_capoos_eaten = 0
        self.next_green_capoo_spawn = (
            self.rules.config.green_capoo_first_seconds
        )
        self.next_attack_chicken_spawn = (
            self.rules.config.attack_chicken_first_seconds
        )
        self.floating_texts = []

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.VIDEORESIZE:
                new_width, new_height = self.handle_resize(event, self.background)
                new_font_size = int(const.title1_size * (new_height / const.hsize))
                self.background = image.Image('picture/bg0.jpg', (const.wsize, const.hsize), (0, 0), 0, 1, 0)
                self.grass_img = ASSETS.image('picture/grass.png')
                self.game_exit_font.pos = [(new_width - self.game_exit_font.getrect().width - 10), 10]
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_j:
                    # 单次按下立即尝试出手（冷却中会自动忽略）；长按自动连击见 update_game
                    self.capoo_surface.start_attack()
            elif event.type == pygame.KEYDOWN or event.type == pygame.KEYUP:
                pass

            button_result = self.game_exit_font.Button(event, "main_menu")
            if button_result['state_change']:
                self.session.reset()
                self.game_state = button_result['new_state']
                return True
        return False

    def get_shrink_speed(self, score):
        return self.rules.shrink_rate(score)

    def on_enemy_defeated(self, enemy):
        """统一的击杀结算：音效、敌人重生、玩家成长、分数/击杀进度与能力回调。"""
        self.capoo_jiao.Play_sound(False)
        if isinstance(enemy, GreenCapoo):
            self.on_green_capoo_eaten(enemy)
            return
        enemy.reset(self.camera)
        self.capoo_surface.grow_on_kill()
        self.session.update_score(self.capoo_surface.size[0], self.rules)
        self.session.register_kill(self.rules.config)
        self.capoo_surface.notify_kill(enemy)

    def on_green_capoo_eaten(self, enemy):
        """吃掉绿 Capoo：额外体型成长 + 计入击杀进度，不再重生。"""
        grown = enemy.GROWTH
        self.green_capoo_group.remove(enemy)
        self.green_capoos_eaten += 1
        self.capoo_surface.change_rect(grown[0] * self.capoo_surface.growth_scale,
                                       grown[1] * self.capoo_surface.growth_scale)
        self.session.update_score(self.capoo_surface.size[0], self.rules)
        self.session.register_kill(self.rules.config)
        self.capoo_surface.notify_kill(enemy)
        self.add_floating_text(f"+{int(grown[0] * self.capoo_surface.growth_scale)} 体型",
                               enemy.getrect().center, (130, 255, 140))

    def add_floating_text(self, text, world_pos, color=(255, 255, 255), life=50 / 60):
        """在世界坐标处加一条向上飘的提示文字。"""
        self.floating_texts.append([text, [world_pos[0], world_pos[1]], life, color])

    def update_floating_texts(self, dt):
        for item in list(self.floating_texts):
            item[1][1] -= 66 * dt      # 向上飘（像素/秒）
            item[2] -= dt
            if item[2] <= 0:
                self.floating_texts.remove(item)

    def draw_floating_texts(self):
        for text, world_pos, life, color in self.floating_texts:
            alpha = max(0, min(255, int(255 * life / (50 / 60))))
            surf = ASSETS.font(
                'font/BoutiqueBitmap9x9_Bold_1.9.ttf', 30,
            ).render(text, True, color)
            surf.set_alpha(alpha)
            screen_pos = self.camera.apply_pos(world_pos) if hasattr(self.camera, 'apply_pos') else world_pos
            self.DS.blit(surf, surf.get_rect(center=(int(screen_pos[0]), int(screen_pos[1]))))

    def handle_upgrades(self):
        """处理所有待处理的升级：逐个弹出能力三选一界面。"""
        while self.session.take_upgrade():
            try:
                upgrade_ui = UpgradeUI(self.capoo_surface)
                if not upgrade_ui.has_options:
                    continue  # 所有能力都已满层，本次升级作废
                chosen = upgrade_ui.show(self.DS, redraw_callback=self.draw)
                # 升级界面中可能触发窗口缩放，需要重新获取显示表面
                self.DS = pygame.display.get_surface() or self.DS
                if chosen is not None:
                    self.capoo_surface.add_ability(chosen)
            except Exception as e:
                print("升级UI弹出异常：", e)
        # 升级界面会阻塞主循环，丢弃暂停期间累积的真实时间。
        self.clock.tick()

    # ---------------- 攻击结算 ----------------
    def resolve_attack_hits(self, attack_rect, group):
        """结算一组目标：先算能力附加判定区，再算主判定区，同一敌人只命中一次。"""
        player = self.capoo_surface
        targets = []
        for enemy in player.attack_with_abilities(group):
            if enemy not in targets:
                targets.append(enemy)
        for enemy in group:
            if enemy not in targets and attack_rect.colliderect(enemy.getrect()):
                targets.append(enemy)
        for enemy in targets:
            if enemy in player.attack_hit_enemies:
                continue
            player.attack_hit_enemies.append(enemy)
            if enemy.hp_caculater(player.attack_damage) <= 0:
                self.on_enemy_defeated(enemy)
                break

    # ---------------- 刷怪系统 ----------------
    def difficulty(self):
        """当前难度：返回 (生成间隔秒数, 同屏敌人上限, 攻击型敌人占比)。"""
        return self.rules.difficulty(self.elapsed)

    def alive_enemy_count(self):
        return len(self.enemy_group) + len(self.attack_enemy_group)

    def build_sprite_index(self, sprites):
        index = SpatialHash(self.rules.config.boid_neighbor_radius)
        for sprite in sprites:
            rect = sprite.getrect()
            index.add(sprite, (rect.x, rect.y, rect.width, rect.height))
        return index

    @staticmethod
    def nearby_sprites(index, rect, padding):
        return index.query((
            rect.x - padding, rect.y - padding,
            rect.width + padding * 2, rect.height + padding * 2,
        ))

    def spawn_off_screen(self, size, margin=90):
        """在摄像机视野之外取一个生成点：以视野外接圆半径保证必定在画面外。"""
        center = pygame.Vector2(self.camera.offset_x + const.wsize / 2,
                                self.camera.offset_y + const.hsize / 2)
        radius = math.hypot(const.wsize, const.hsize) / 2 + margin
        angle = random.uniform(0, math.tau)
        pos = center + pygame.Vector2(math.cos(angle), math.sin(angle)) * radius
        return [pos.x - size[0] / 2, pos.y - size[1] / 2]

    def spawn_system(self, dt):
        """按难度曲线刷新普通敌人：间隔递减、同屏有上限。"""
        self.spawn_timer += dt
        spawn_cd, max_alive, _ = self.difficulty()
        if (self.spawn_timer + const.TIME_EPSILON < spawn_cd
                or len(self.enemy_group) >= max_alive):
            return
        self.spawn_timer = 0.0
        size = (50, 50)
        enemy = Enemy(self.capoo_surface, size=size, speed=300)
        enemy.pos = self.spawn_off_screen(size)
        self.enemy_group.add(enemy)

    def spawn_attack_chickens(self):
        """按固定节奏生成会攻击的大鸡，避免概率过低而整局不出现。"""
        cfg = self.rules.config
        if (self.elapsed + const.TIME_EPSILON < self.next_attack_chicken_spawn
                or len(self.attack_enemy_group) >= cfg.attack_chicken_max_alive):
            return
        chicken = AttackChicken(
            self.capoo_surface,
            size=cfg.attack_chicken_size,
            speed=cfg.attack_chicken_speed,
        )
        chicken.pos = self.spawn_off_screen(chicken.size)
        self.attack_enemy_group.add(chicken)
        self.next_attack_chicken_spawn += cfg.attack_chicken_interval

    # ---------------- 绿 Capoo ----------------
    def update_green_capoos(self, dt):
        """前 60 秒每 6 秒一波，三个阶段分别生成 3、2、1 只绿 Capoo。"""
        cfg = self.rules.config
        batch_size = self.rules.green_capoo_batch_size_at(self.elapsed)
        can_spawn = (
            self.elapsed <= cfg.green_capoo_phase_seconds
            and self.green_capoos_spawned < cfg.green_capoo_max_total
            and self.elapsed + const.TIME_EPSILON >= self.next_green_capoo_spawn
            and len(self.green_capoo_group) <= (
                cfg.green_capoo_max_alive - batch_size
            )
        )
        if can_spawn:
            amount = min(
                batch_size,
                cfg.green_capoo_max_total - self.green_capoos_spawned,
            )
            for _ in range(amount):
                capoo = GreenCapoo(self.capoo_surface)
                capoo.pos = self.spawn_off_screen(capoo.size, margin=60)
                self.green_capoo_group.add(capoo)
            self.green_capoos_spawned += amount
            self.next_green_capoo_spawn += cfg.green_capoo_interval
        for capoo in list(self.green_capoo_group):
            capoo.move_towards_player(self.green_capoo_group, dt)

    def update_game(self, dt=const.FIXED_DT):
        self.elapsed += dt
        # 攻击冷却与长按 J 自动攻击
        self.capoo_surface.update_attack_timer(dt)
        if pygame.key.get_pressed()[pygame.K_j]:
            self.capoo_surface.start_attack()
        normal_index = self.build_sprite_index(self.enemy_group)
        attack_index = self.build_sprite_index(self.attack_enemy_group)
        movement_padding = self.capoo_surface.move_speed * dt + 4
        player_rect = self.capoo_surface.getrect()
        self.capoo_surface.Player_move(
            self.nearby_sprites(normal_index, player_rect, movement_padding),
            self.nearby_sprites(attack_index, player_rect, movement_padding),
            dt,
        )
        self.capoo_surface.play_attack_animation(dt)
        # 能力系统：每帧更新（如雷霆领域、旋风），并结算能力造成的击杀
        self.capoo_surface.update_abilities(self, dt)
        for enemy in self.capoo_surface.take_pending_kills():
            self.on_enemy_defeated(enemy)
        # 绿 Capoo 在开局阶段成批出现；大鸡则独立按固定节奏刷新。
        self.update_green_capoos(dt)
        self.spawn_system(dt)
        self.spawn_attack_chickens()
        self.update_floating_texts(dt)
        # 攻击型敌人移动和动画
        for enemy in self.attack_enemy_group:
            if hasattr(enemy, 'try_attack'):
                if enemy.try_attack():
                    continue  # 进入攻击状态后不移动
            enemy.move_towards_player(self.attack_enemy_group, dt)
            enemy.play_animation(dt)
        # 普通敌人移动和动画，聚合中心为攻击型敌人群体
        # 计算攻击型敌人群体中心
        if len(self.attack_enemy_group) > 0:
            centers = [pygame.Vector2(e.getrect().center) for e in self.attack_enemy_group]
            attack_center = sum(centers, pygame.Vector2(0,0)) / len(centers)
        else:
            attack_center = pygame.Vector2(const.wsize//2, const.hsize//2)
        for enemy in self.enemy_group:
            # 普通敌人根据玩家与攻击型敌人群体中心连线移动并保持距离
            enemy_rect = enemy.getrect()
            neighbor_radius = self.rules.config.boid_neighbor_radius
            neighbors = self.nearby_sprites(
                normal_index, enemy_rect, neighbor_radius,
            )
            enemy.move_behead_attacker(
                attack_center,
                pygame.Vector2(self.capoo_surface.getrect().center),
                enemies=neighbors,
                dt=dt,
            )
            enemy.play_animation(dt)
        # 体型随分数指数衰减（「铁壁」可减免）
        shrink_x, shrink_y = self.get_shrink_speed(self.session.score)
        self.capoo_surface.shrink(shrink_x * dt, shrink_y * dt)
        self.score_update_timer += dt
        if self.score_update_timer + const.TIME_EPSILON >= 10 / 60:
            self.score_update_timer -= 10 / 60
            self.session.update_score(self.capoo_surface.size[0], self.rules)
        # 玩家攻击判定：主判定区 + 能力附加判定区（含可吃掉的奖励小鸡）
        if self.capoo_surface.is_attacking:
            attack_rect = self.capoo_surface.get_attack_rect()
            self.resolve_attack_hits(attack_rect, self.attack_enemy_group)
            self.resolve_attack_hits(attack_rect, self.enemy_group)
            self.resolve_attack_hits(attack_rect, self.green_capoo_group)
        capoo_rect = self.capoo_surface.getrect()
        capoo_mask = self.capoo_surface.get_mask()
        # 攻击型敌人攻击完成后再次检测攻击rect是否与玩家rect碰撞，若碰撞则扣分
        for enemy in self.attack_enemy_group:
            if hasattr(enemy, 'attack_finished') and enemy.attack_finished:
                attack_rect = enemy.get_attack_rect()
                attack_offset = (attack_rect.x - capoo_rect.x, attack_rect.y - capoo_rect.y)
                attack_mask = pygame.mask.Mask((attack_rect.width, attack_rect.height), True)
                if capoo_mask.overlap(attack_mask, attack_offset):
                    # 原效果是 60 FPS 下 10 帧的衰减量；这里是一次性伤害，不乘本帧 dt。
                    self.capoo_surface.shrink(
                        shrink_x * (10 / 60),
                        shrink_y * (10 / 60),
                    )
                    self.session.update_score(self.capoo_surface.size[0], self.rules)
                    self.capoo_surface.notify_defend(self)
                enemy.attack_finished = False
        if self.session.score <= 0 or self.capoo_surface.is_min_size():
            # 体型归零（衰减到下限）或分数归零即游戏结束
            Game_over_Font = image.mFont("GAME OVER", 'font/BoutiqueBitmap9x9_Bold_1.9.ttf', 100, (230, 100, 150), (const.wsize/2, const.hsize/2))
            Game_over_Font.fdraw(self.DS)
            pygame.display.flip()
            pygame.time.delay(1000)
            self.session.reset()
            self.game_state = "main_menu"
            return True
        #升级UI弹出逻辑（可能一次积攒多次升级）
        if self.session.upgrade_pending:
            self.handle_upgrades()
        return False

    # 衰减强度条满格参考值（每秒衰减的宽度像素）：越大表示衰减越猛
    DECAY_BAR_FULL = 30.0

    def current_decay_per_sec(self):
        """当前每秒的体型衰减量（正数，单位为宽度像素/秒）。"""
        shrink_x, _ = self.get_shrink_speed(self.session.score)
        return -shrink_x

    def draw_size_hud(self):
        """HUD：显示当前体型与体型衰减速度（体型越大衰减越快）。"""
        width = self.capoo_surface.size[0]
        decay = self.current_decay_per_sec()
        ratio = max(0.0, min(1.0, decay / self.DECAY_BAR_FULL))
        # 绿 → 红：衰减越快越危险
        fill = (int(120 + 110 * ratio), int(220 - 130 * ratio), int(160 - 70 * ratio))
        bar_w, bar_h = 220, 18
        x, y = const.wsize - bar_w - 20, 244
        image.mFont(f"size:{int(width)}", 'font/BoutiqueBitmap9x9_Bold_1.9.ttf', 28,
                    (230, 100, 150), (const.wsize - 20, y - 40)).fdraw(self.DS)
        # 衰减标签（右对齐在进度条左侧）
        image.mFont(f"decay:-{decay:.1f}/s", 'font/BoutiqueBitmap9x9_Bold_1.9.ttf', 26,
                    fill, (x - 12, y - 5)).fdraw(self.DS)
        pygame.draw.rect(self.DS, (40, 40, 55), (x, y, bar_w, bar_h), border_radius=9)
        if ratio > 0:
            pygame.draw.rect(self.DS, fill, (x, y, int(bar_w * ratio), bar_h), border_radius=9)
        pygame.draw.rect(self.DS, (235, 235, 245), (x, y, bar_w, bar_h), 2, border_radius=9)

    def draw(self):
        # 升级界面等流程中可能触发窗口缩放，这里重新获取显示表面
        self.DS = pygame.display.get_surface() or self.DS
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
        image.mFont("score:" + str(self.session.score), 'font/BoutiqueBitmap9x9_Bold_1.9.ttf', 50, (230, 100, 150), (const.wsize, 160)).fdraw(self.DS)
        self.draw_size_hud()
        self.draw_green_capoo_hud()
        self.capoo_surface.draw(self.DS, self.camera)
        self.draw_attack_ready_ring()
        # 能力判定区域可视化渲染（如多重撕咬等能力）
        if hasattr(self.capoo_surface, 'draw_abilities'):
            self.capoo_surface.draw_abilities(self.DS, self.camera)
        visible_world = pygame.Rect(
            self.camera.offset_x - 120, self.camera.offset_y - 120,
            const.wsize + 240, const.hsize + 240,
        )
        for enemy in self.enemy_group:
            if visible_world.colliderect(enemy.getrect()):
                enemy.draw(self.DS, self.camera)
        for enemy in self.attack_enemy_group:
            if visible_world.colliderect(enemy.getrect()):
                enemy.draw(self.DS, self.camera)
        for capoo in self.green_capoo_group:
            if visible_world.colliderect(capoo.getrect()):
                capoo.draw(self.DS, self.camera)
        self.draw_floating_texts()
        pygame.display.flip()

    def draw_green_capoo_hud(self):
        """提示开局阶段绿 Capoo 的收集进度。"""
        if self.elapsed > self.rules.config.green_capoo_phase_seconds:
            return
        image.mFont(
                    f"绿Capoo {self.green_capoos_eaten}/{self.green_capoos_spawned}（吃掉快速长大）",
                    'font/BoutiqueBitmap9x9_Bold_1.9.ttf', 24, (130, 255, 140),
                    (const.wsize - 20, 274)).fdraw(self.DS)

    def draw_attack_ready_ring(self):
        """在玩家周围画一个冷却环：未充满时不能再次出手。"""
        player = self.capoo_surface
        if player.attack_ready():
            return
        rect = self.camera.apply(player.getrect()) if self.camera is not None else player.getrect()
        center = rect.center
        radius = max(rect.width, rect.height) // 2 + 10
        box = pygame.Rect(0, 0, radius * 2, radius * 2)
        box.center = center
        ratio = player.attack_ready_ratio()
        pygame.draw.arc(self.DS, (255, 235, 150), box, 0, math.tau * ratio, 4)

    def run(self):
        accumulator = 0.0
        finished = False
        # 丢弃构造和资源加载所花的时间。
        self.clock.tick()
        while not finished:
            frame_dt = min(
                self.clock.tick(const.RENDER_FPS) / 1000.0,
                const.MAX_FRAME_TIME,
            )
            if self.handle_events():
                break
            accumulator += frame_dt
            while accumulator >= const.FIXED_DT:
                if self.update_game(const.FIXED_DT):
                    finished = True
                    break
                accumulator -= const.FIXED_DT
            if not finished:
                self.draw()
        return self.game_state
