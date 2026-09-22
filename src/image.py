import pygame
import random
import ability
import math
from core.assets import ASSETS
from core.game_rules import DEFAULT_RULES
from core.state import DISPLAY_SETTINGS, GAME_CONFIG


class Image(pygame.sprite.Sprite):
    def load_image(self, pathFmt):
        """
        加载和处理图片的辅助函数
        :param pathFmt: 图片路径格式
        :return: tuple (image, original_image)
        """
        if not pathFmt.strip():  # 判断是否为空路径
            image = pygame.Surface(self.size, pygame.SRCALPHA)
            image.fill((200, 200, 200))  # 滑道基础色
            original_image = image.copy()
        else:
            if self.total_num > 1:
                path = self.path % self.Index
            else:
                path = self.path
            original_image = ASSETS.image(path, self.size)
            image = ASSETS.image(path, self.size, not self.facing_left)
        return image, original_image

    def __init__(self, pathFmt, size, pos, Index, Total_num = 1, Record = 0, facing_left = True):#Index起始位置，Total_num总张数
        self.Index = Index
        self.Record = Record
        self.total_num = Total_num
        self.path = pathFmt
        self.size = size
        self.pos = list(pos)
        self.facing_left = facing_left
        self.is_walking = False
        self.pressed = False
        self.ativate = False
        self.image, self.original_image = self.load_image(pathFmt)
        self.reloade()
        # 初始化输入处理器（仅在需要时创建）
        self.input_handler = None
        self.is_attacking = False
        self.attack_frame = 0.0
        self.attack_cooldown = GAME_CONFIG.player_attack_duration
        self.attack_interval = GAME_CONFIG.player_attack_interval
        self.attack_timer = 0.0  # 剩余冷却时间（秒）
        self.attack_paths = ['picture/Capoo/AT/AT0.png', 'picture/Capoo/AT/AT1.png', 'picture/Capoo/AT/AT2.png', 'picture/Capoo/AT/AT3.png', 'picture/Capoo/AT/AT4.png']
        if self.path.strip():
            if self.total_num > 1:
                frame_paths = [
                    self.path % index
                    for index in range(self.Index, self.total_num + 1)
                ]
            else:
                frame_paths = [self.path]
            ASSETS.animation(frame_paths, self.size)
            ASSETS.animation(frame_paths, self.size, True)
        is_capoo_animation = (
            'capoo' in self.path.casefold() and self.total_num > 1
        )
        if is_capoo_animation:
            ASSETS.animation(self.attack_paths, self.size)
            ASSETS.animation(self.attack_paths, self.size, True)
        self.attack_damage = GAME_CONFIG.player_attack_damage
        self.move_speed = GAME_CONFIG.player_speed
        self.attack_width_scale = 0.5  # 攻击判定宽度比例（可被能力提升）
        self.attack_height_scale = 1.0  # 攻击判定高度比例（可被能力提升）
        self.attack_offset_x = 0  # 攻击判定x方向偏移
        self.shrink_resist = 0.0  # 体型衰减减免比例（0~1）
        self.growth_scale = 1.0  # 击杀成长倍率
        self.attack_hit_enemies = []  # 记录本次攻击已命中的敌人
        self.bite_paths = [f'picture/bites/{i}.png' for i in range(3)]
        self.bite_images = (
            list(ASSETS.animation(self.bite_paths))
            if is_capoo_animation else []
        )
        self.bite_frame = 0
        self.bite_animating = False
        self.bite_pos = (0, 0)
        self.abilities = []  # 玩家能力列表
        self.pending_kills = []  # 能力造成的击杀，由关卡统一结算
    
    def getrect(self):
        rect = self.image.get_rect(midbottom = (self.size[0]/2,0))
        rect.topleft = self.pos
        return rect
    #取得图片

    def change_rect(self,add_wide,add_hight):
        # 体型只保底、不设上限：衰减到下限即“体型归零”，由关卡判定游戏结束
        new_w, new_h = DEFAULT_RULES.clamp_size(
            self.size[0] + add_wide, self.size[1] + add_hight,
        )
        if abs(new_w - self.size[0]) < 1e-6 and abs(new_h - self.size[1]) < 1e-6:
            return  # 已在下限，跳过缩放（也避免每帧重复生成表面）
        self.size = (new_w, new_h)  # 修改 size 属性
        self.reloade()
        self.rect = self.getrect()  # 更新 rect 的位置

    def is_min_size(self):
        """体型是否已衰减到下限（体型归零 → 关卡判定游戏结束）。"""
        min_width, min_height = GAME_CONFIG.player_min_size
        return (self.size[0] <= min_width + 1e-6 or
                self.size[1] <= min_height + 1e-6)
    
    def get_hitbox(self,wide,hight):
        hitbox = self.getrect().inflate((wide,hight))
        return hitbox

    def Player_move(self, enemy_group=None, attack_enemy_group=None, dt=GAME_CONFIG.fixed_dt):
        self.is_walking = False
        prev_facing = self.facing_left
        keys = pygame.key.get_pressed()
        direction = pygame.Vector2(0, 0)
        speed = getattr(self, 'move_speed', 600.0)
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            direction.x -= 1
            self.facing_left = True
            self.is_walking = True
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            direction.x += 1
            self.facing_left = False
            self.is_walking = True
        if (keys[pygame.K_UP] or keys[pygame.K_w]):
            direction.y -= 1
            self.is_walking = True
        if (keys[pygame.K_DOWN] or keys[pygame.K_s]):
            direction.y += 1
            self.is_walking = True
        if direction.length_squared() > 0:
            direction = direction.normalize() * speed * dt
        move_x, move_y = direction.x, direction.y
        # 软碰撞逻辑
        push_vec = pygame.Vector2(0, 0)
        if enemy_group is not None or attack_enemy_group is not None:
            new_rect = self.getrect().copy()
            new_rect.x += move_x
            new_rect.y += move_y
            new_mask = self.get_mask()
            if enemy_group is not None:
                for enemy in enemy_group:
                    enemy_rect = enemy.getrect()
                    if not new_rect.colliderect(enemy_rect):
                        continue
                    enemy_mask = enemy.get_mask()
                    offset = (enemy_rect.x - new_rect.x, enemy_rect.y - new_rect.y)
                    if new_mask.overlap(enemy_mask, offset):
                        # 计算分离向量
                        my_center = pygame.Vector2(new_rect.center)
                        enemy_center = pygame.Vector2(enemy.getrect().center)
                        vec = my_center - enemy_center
                        if vec.length() > 0:
                            push_vec += vec.normalize()
            if attack_enemy_group is not None:
                for enemy in attack_enemy_group:
                    enemy_rect = enemy.getrect()
                    if not new_rect.colliderect(enemy_rect):
                        continue
                    enemy_mask = enemy.get_mask()
                    offset = (enemy_rect.x - new_rect.x, enemy_rect.y - new_rect.y)
                    if new_mask.overlap(enemy_mask, offset):
                        my_center = pygame.Vector2(new_rect.center)
                        enemy_center = pygame.Vector2(enemy.getrect().center)
                        vec = my_center - enemy_center
                        if vec.length() > 0:
                            push_vec += vec.normalize()
        # 应用玩家输入和软碰撞推力
        self.pos[0] += move_x + push_vec.x * 300 * dt
        self.pos[1] += move_y + push_vec.y * 300 * dt
        if self.is_walking:
            self.updataRecord(self.Record + 1)
        if prev_facing != self.facing_left:
            self.image = pygame.transform.flip(self.original_image, not self.facing_left, False)
        self.reloade()

    def reloade(self):
        if not self.path.strip():  # 如果是空路径
            self.image = pygame.Surface(self.size, pygame.SRCALPHA)
            self.image.fill((200, 200, 200))  # 使用灰色填充
            self.original_image = self.image.copy()
        else:
            if self.total_num > 1:
                if self.Record <= self.total_num:
                    path = self.path % self.Record
                else:
                    self.Record = self.Index
                    path = self.path % self.Record
            else:
                path = self.path
            self.original_image = ASSETS.image(path, self.size)
            self.image = ASSETS.image(path, self.size, not self.facing_left)

    def updatasize(self,size):
        self.size=size
        self.reloade()
        
    def updataRecord(self,Record):
        self.Record=Record
        self.reloade()
    
    def updateIndex(self,Index,Total_num):
        self.Index=Index
        self.total_num=Total_num
        self.reloade()

    def draw(self, ds, camera=None):
        # 正常绘制
        if camera is not None:
            ds.blit(self.image, camera.apply(self.getrect()))
        else:
            ds.blit(self.image, self.getrect())

        # 攻击动画：始终绘制主撕咬判定区，额外判定区的表现由 draw_abilities 负责
        if self.is_attacking or self.bite_animating:
            attack_rect = self.get_attack_rect()
            bite_idx = min(self.bite_frame // 2, len(self.bite_images) - 1)
            bite_img = ASSETS.image(
                self.bite_paths[bite_idx],
                (attack_rect.width, attack_rect.height),
            )
            bite_rect = bite_img.get_rect(center=attack_rect.center)
            if camera is not None:
                ds.blit(bite_img, camera.apply(bite_rect))
            else:
                ds.blit(bite_img, bite_rect)
        # 半身穿墙效果：左边超界时右侧补绘
        if self.pos[0] < 0:
            temp_rect = self.getrect().copy()
            temp_rect.x = self.pos[0] + DISPLAY_SETTINGS.width
            if camera is not None:
                ds.blit(self.image, camera.apply(temp_rect))
            else:
                ds.blit(self.image, temp_rect)
        # 右边超界时左侧补绘
        elif self.pos[0] + self.size[0] > DISPLAY_SETTINGS.width:
            temp_rect = self.getrect().copy()
            temp_rect.x = self.pos[0] - DISPLAY_SETTINGS.width
            if camera is not None:
                ds.blit(self.image, camera.apply(temp_rect))
            else:
                ds.blit(self.image, temp_rect)

    def get_initial_position(self):
        return (
            DISPLAY_SETTINGS.width + 50,
            random.randrange(
                int(DISPLAY_SETTINGS.height / 2), DISPLAY_SETTINGS.height,
            ),
        )

    def change_path(self, new_path):
        """
        更改矩阵图片的功能
        :param new_path: 新的图片路径
        """
        self.path = new_path  # 更新路径
        self.image, self.original_image = self.load_image(new_path)
        self.reloade()

    def Switch_Button(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:  # 如果鼠标按下
            mouse_pos = pygame.mouse.get_pos() + (1,1)
            if self.getrect().colliderect(mouse_pos):#在按钮上
                self.pressed = True
        if event.type == pygame.MOUSEBUTTONUP:#鼠标松开
            mouse_pos = pygame.mouse.get_pos() + (1,1) #将pos矩阵补成4个值
            if self.pressed and self.getrect().colliderect(mouse_pos):#在按钮上
                self.pressed = False
                self.ativate = True
            elif self.pressed and not self.getrect().colliderect(mouse_pos):
                self.pressed = False #图标恢复
        
        # 状态切换和返回结果
        if self.ativate:
            self.ativate = False
            DISPLAY_SETTINGS.fullscreen = not DISPLAY_SETTINGS.fullscreen
        return DISPLAY_SETTINGS.fullscreen
    def update_attack_timer(self, dt=GAME_CONFIG.fixed_dt):
        """按经过的秒数推进攻击冷却。"""
        self.attack_timer = max(0.0, self.attack_timer - dt)

    def attack_ready(self):
        """是否可以再次出手。"""
        return self.attack_timer <= 0 and not self.is_attacking

    def attack_ready_ratio(self):
        """攻击冷却进度（0=刚出手，1=可以出手），供 HUD 画冷却环。"""
        if self.attack_interval <= 0:
            return 1.0
        return max(0.0, min(1.0, 1.0 - self.attack_timer / self.attack_interval))

    def start_attack(self):
        """开始一次攻击；冷却中或正在出手时返回 False。"""
        if self.is_attacking or self.attack_timer > 0:
            return False
        self.is_attacking = True
        self.attack_frame = 0.0
        self.attack_hit_enemies = []  # 攻击开始时清空
        self.attack_timer = self.attack_interval
        self.notify_attack_start()
        return True

    def notify_attack_start(self):
        """通知所有能力「玩家刚出手」，供旋风撕咬等需要一次性触发的效果使用。"""
        for ab in list(getattr(self, 'abilities', [])):
            ab.on_attack_start(self)

    def attack_angles(self):
        """本次攻击覆盖的角度列表：0 为主判定区方向，其余来自多重撕咬等能力。"""
        angles = [0.0]
        for ab in list(getattr(self, 'abilities', [])):
            angles.extend(ab.attack_extra_angles())
        return angles

    def play_attack_animation(self, dt=GAME_CONFIG.fixed_dt, animation_len=5):
        if self.is_attacking:
            progress = min(1.0, self.attack_frame / max(self.attack_cooldown, 1e-6))
            idx = min(int(progress * animation_len), len(self.attack_paths) - 1)
            path = self.attack_paths[idx]
            self.original_image = ASSETS.image(path, self.size)
            self.image = ASSETS.image(path, self.size, not self.facing_left)
            self.attack_frame += dt
            # 播放咬合动画
            if not self.bite_animating:
                self.bite_animating = True
                self.bite_frame = 0
            if self.bite_animating:
                self.bite_frame = min(
                    int(progress * len(self.bite_images) * 2),
                    len(self.bite_images) * 2 - 1,
                )
            # 能力动画帧同步（如多重撕咬等能力）
            for ab in getattr(self, 'abilities', []):
                if hasattr(ab, 'on_attack_animation'):
                    ab.on_attack_animation(self)
            if self.attack_frame + GAME_CONFIG.time_epsilon >= self.attack_cooldown:
                self.is_attacking = False
                self.attack_frame = 0.0
                self.attack_hit_enemies = []  # 攻击动画结束时清空
                self.bite_animating = False
        else:
            self.reloade()

    def get_attack_rect(self, width_scale=None, height_scale=None, offset_x=None, offset_y=0):
        """
        获取攻击判定区域，可自定义大小和位置偏移。
        参数为 None 时使用实例属性（可被「长臂」等能力修改）：
        width_scale: 攻击区域宽度占自身宽度比例（默认0.5）
        height_scale: 攻击区域高度占自身高度比例（默认1.0）
        offset_x: 攻击区域在x方向的偏移（默认0，正值向前方）
        offset_y: 攻击区域在y方向的偏移（默认0，正值向下）
        """
        if width_scale is None:
            width_scale = getattr(self, 'attack_width_scale', 0.5)
        if height_scale is None:
            height_scale = getattr(self, 'attack_height_scale', 1.0)
        if offset_x is None:
            offset_x = getattr(self, 'attack_offset_x', 0)
        left, top, width, height = DEFAULT_RULES.attack_rect(
            self.pos, self.size, self.facing_left,
            width_scale=width_scale,
            height_scale=height_scale,
        )
        return pygame.Rect(
            int(left + offset_x), int(top + offset_y),
            max(1, int(width)), max(1, int(height)),
        )

    def try_attack(self, target_rect=None, width_scale=0.5, height_scale=1.0, offset_x=0, offset_y=0):
        """
        通用攻击判定方法。
        target_rect: 被攻击对象的rect（如玩家rect）
        width_scale, height_scale, offset_x, offset_y: 攻击判定区域参数
        返回: 是否触发攻击
        """
        if self.is_attacking:
            return False
        attack_rect = self.get_attack_rect(width_scale, height_scale, offset_x, offset_y)
        if target_rect and attack_rect.colliderect(target_rect):
            self.start_attack()
            if hasattr(self, 'attack_finished'):
                self.attack_finished = False
            return True
        return False

    def get_mask(self):
        if getattr(self, '_mask_source', None) is not self.image:
            self._mask_source = self.image
            self._mask_cache = pygame.mask.from_surface(self.image)
        return self._mask_cache
    @staticmethod
    def draw_scene(ds, background, game_exit_font, score, capoo_surface, enemies):
        """
        游戏主绘制函数，整合自game_level.py
        ds: 屏幕surface
        background: 背景Image对象
        game_exit_font: mFont对象
        score: 当前分数
        capoo_surface: 玩家Image对象
        enemies: 敌人列表
        """
        ds.fill((255, 255, 255))
        background.draw(ds)
        game_exit_font.fdraw(ds)
        from image import mFont  # 避免静态方法引用类属性
        score_surface = mFont("score:" + str(score), 'font/BoutiqueBitmap9x9_Bold_1.9.ttf', 50, (230, 100, 150), (DISPLAY_SETTINGS.width, 160))
        score_surface.fdraw(ds)
        capoo_surface.draw(ds)
        for enemy in enemies:
            enemy.draw(ds)
        pygame.display.flip()
        pygame.time.Clock().tick(GAME_CONFIG.simulation_hz)

    # ---------------- 能力系统接口 ----------------
    def add_ability(self, ability_obj):
        """获得能力：已拥有同类能力则叠加层数并再次生效，否则加入能力列表。

        已经满层的能力不会重复生效，直接返回已有实例。
        """
        for owned in self.abilities:
            if type(owned) is type(ability_obj):
                if owned.max_stack > 0 and owned.stack >= owned.max_stack:
                    return owned  # 已满层：不叠层也不重复生效
                owned.stack += 1
                owned.apply_to_player(self)
                return owned
        ability_obj.stack = 1
        self.abilities.append(ability_obj)
        ability_obj.apply_to_player(self)
        return ability_obj

    def has_ability(self, ability_cls):
        """判断是否已拥有某个能力（含子类）。"""
        return any(isinstance(ab, ability_cls) for ab in self.abilities)

    def attack_with_abilities(self, target_group):
        """攻击时调用所有能力的on_attack，返回所有命中的敌人"""
        hit_enemies = []
        for ab in list(self.abilities):
            result = ab.on_attack(self, target_group)
            if result:
                hit_enemies.extend(result)
        return hit_enemies

    def update_abilities(self, level=None, dt=GAME_CONFIG.fixed_dt):
        """按经过的秒数更新雷霆领域等周期性能力。"""
        for ab in list(self.abilities):
            ab.on_update(self, level, dt)

    def notify_kill(self, enemy):
        """击杀敌人后通知所有能力。"""
        for ab in list(self.abilities):
            ab.on_kill(self, enemy)

    def notify_defend(self, level=None):
        """玩家受到伤害后通知所有能力。"""
        for ab in list(self.abilities):
            ab.on_defend(self, level)

    def take_pending_kills(self):
        """取出并清空能力造成的击杀，交由关卡统一结算。"""
        kills = self.pending_kills
        self.pending_kills = []
        return kills

    def grow_on_kill(self, base_w=None, base_h=None):
        """击杀成长（受「掠食本能」倍率影响）。"""
        if base_w is None or base_h is None:
            base_w, base_h = GAME_CONFIG.kill_growth
        self.change_rect(base_w * self.growth_scale, base_h * self.growth_scale)

    def shrink(self, add_w, add_h):
        """统一的体型变化入口：负向变化会被「铁壁」等能力减免。"""
        resist = getattr(self, 'shrink_resist', 0.0)
        if add_w < 0:
            add_w *= (1 - resist)
        if add_h < 0:
            add_h *= (1 - resist)
        self.change_rect(add_w, add_h)

    def draw_abilities(self, ds, camera=None):
        """绘制能力附加的视觉表现（额外判定区、领域光环等）。"""
        for ab in list(self.abilities):
            ab.draw_effect(self, ds, camera)
class mFont(pygame.sprite.Sprite):
    _instances = []
    def __init__(self,title, font_path, size, color=None,pos=(0,0)):
        self.title=title
        self.path=font_path
        self.size=size
        self.color=color
        self.mfont = ASSETS.font(self.path, self.size)
        self.text = ASSETS.text(
            self.title, self.path, self.size, self.color,
        )
        self.rect = self.text.get_rect()
        self.pos = list(pos)
        self.pos = [pos[0] - int(self.rect.width), pos[1]]
        self.pressed = False  # 按下状态标识
        self.original_pos = list(pos)  # 保存原始位置
        self.ativate = False  # 激活状态标识
    @classmethod
    def get_all_instance(cls):
        return cls._instances
    
    def update_all_pos(cls,width,hight,x_rate,y_rate):
        for instance in cls._instances:
            instance.pos = [(width - instance.getrect().width) / x_rate, hight*y_rate/5]
    #打算做一个一键更新该类所以对象的函数，未完成

    def getrect(self):
        rect = self.text.get_rect()
        rect.topleft = tuple(self.pos)
        return rect
    
    def fdraw(self,ds):
        ds.blit(self.text,self.getrect())

    def updatasize(self,size):
        self.size = size  # 更新为新的字体大小
        self.mfont = ASSETS.font(self.path, self.size)
        self.text = ASSETS.text(
            self.title, self.path, self.size, self.color,
        )
        self.rect = self.getrect()  # 更新文本的矩形
    
    def Button(self,events,target_state=None):
        if events.type == pygame.MOUSEBUTTONDOWN:  # 如果鼠标按下
            mouse_pos = pygame.mouse.get_pos() + (1,1)
            if self.getrect().colliderect(mouse_pos):#在按钮上
                self.pressed = True#图标变换
                self.pos[1] += 2
        if events.type == pygame.MOUSEBUTTONUP:#鼠标松开
            mouse_pos = pygame.mouse.get_pos() + (1,1) #将pos矩阵补成4个值
            if self.pressed and self.getrect().colliderect(mouse_pos):#在按钮上
                self.pressed = False#图标恢复
                self.pos[1] -= 2
                self.ativate = True
            elif self.pressed and not self.getrect().colliderect(mouse_pos):
                self.pressed = False #图标恢复
                self.pos[1] -= 2
        
        # 状态切换和返回结果
        if self.ativate and target_state is not None:
            self.ativate = False
            return {'state_change': True, 'new_state': target_state}
        return {'state_change': False}

    def align(self, position, mode='center'):
        alignments = {
            'topleft': self.text.get_rect(topleft=position),
            'midtop': self.text.get_rect(midtop=position),
            'center': self.text.get_rect(center=position),
            'midbottom': self.text.get_rect(midbottom=position)
        }
        self.rect = alignments.get(mode, self.text.get_rect(center=position))
        return self
    
    def get_mask(self):
        return pygame.mask.from_surface(self.text)

class Slider(Image):
    def __init__(self, handle_path, image_size, size, pos, Index, min_val=0, max_val=100, handle_radius=10, 
                Total_num=1, Record=0, facing_left=True):
        super().__init__(handle_path, size, pos, Index, Total_num, Record, facing_left)
        self.image_size = image_size  # 滑块大小
        self.handle_image = ASSETS.image(handle_path, self.image_size)
        self.handle_rect = self.handle_image.get_rect()
        # 滑块特有属性
        self.min_val = min_val
        self.max_val = max_val
        self.handle_radius = handle_radius
        self.value = DISPLAY_SETTINGS.bgm_volume
        self.dragging = False
        self.handle_color = (40, 120, 200)    # 滑块颜色
        self.font = ASSETS.system_font('Arial', 20)
        self.show_value = True
        
        # 覆盖父类属性
        self.facing_left = True  # 强制水平方向
        self.original_image = self.create_slider_bg()  # 创建纯色滑道背景
        self.image = self.original_image.copy()

    def create_slider_bg(self):
        """创建滑道背景"""
        surface = pygame.Surface(self.size, pygame.SRCALPHA)
        pygame.draw.rect(surface, (200, 200, 200), (0, 0, *self.size), border_radius=5)
        return surface

    def handle_event(self, event):
        """处理鼠标事件"""
        if event.type not in [pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION]:
            return  # 跳过无关事件
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.get_handle_rect().collidepoint(event.pos):
                self.dragging = True
        elif event.type == pygame.MOUSEBUTTONUP:
            self.dragging = False
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            self.update_value(pygame.mouse.get_pos()[0])

    def update_value(self, mouse_x):
        """根据鼠标位置更新值"""
        rect = self.getrect()
        mouse_x = max(rect.left, min(mouse_x, rect.right))
        self.value = self.min_val + (mouse_x - rect.left) / rect.width * (self.max_val - self.min_val)
        DISPLAY_SETTINGS.set_bgm_volume(self.value)


    def get_handle_rect(self):
        """获取滑块圆形区域"""
        rect = self.getrect()
        handle_x = rect.left + (self.value - self.min_val) / (self.max_val - self.min_val) * rect.width
        return pygame.Rect(handle_x - self.handle_radius,rect.centery - self.handle_radius,self.handle_radius*2, self.handle_radius*2)
    def draw(self, ds):
        """绘制滑道和滑块"""
        super().draw(ds)  # 绘制父类背景
        if self.handle_image is not None:
            handle_rect = self.get_handle_rect()
            ds.blit(self.handle_image, handle_rect)  # 使用图片渲染手柄
        else:
            pygame.draw.circle(ds, self.handle_color,self.get_handle_rect().center, self.handle_radius)
        if self.show_value:
            text = self.font.render(f"{int(self.value*100)}%", True, (0,0,0))
            ds.blit(text, (self.getrect().right + 10, self.getrect().centery - 10))

    # 禁用不需要的父类方法
    def Player_move(self): pass

class InputBox(mFont):
    """
    可输入内容的文本框类，继承自mFont类
    """
    def __init__(self, title="", font_path="font/FZBangSKJW.TTF", size=24, color=(0, 0, 0), 
                 pos=(0, 0), box_width=200, box_height=40, 
                 inactive_color=(200, 200, 200), active_color=(240, 240, 240), 
                 border_color=(100, 100, 100), max_length=20):
        """
        初始化输入框
        
        参数:
            title: 初始文本内容
            font_path: 字体路径
            size: 字体大小
            color: 文本颜色
            pos: 文本框左上角的坐标
            box_width: 文本框宽度
            box_height: 文本框高度
            inactive_color: 非激活状态的背景颜色
            active_color: 激活状态的背景颜色
            border_color: 边框颜色
            max_length: 最大文本长度
        """
        # 调用父类初始化方法
        super().__init__(title, font_path, size, color, pos)
        
        # 输入框特有属性
        self.box_width = box_width
        self.box_height = box_height
        self.inactive_color = inactive_color
        self.active_color = active_color
        self.border_color = border_color
        self.input_active = False
        self.max_length = max_length
        
        # 创建输入框矩形
        self.box_rect = pygame.Rect(pos[0], pos[1], box_width, box_height)
        
        # 调整文本位置到输入框内部
        self.pos = [pos[0] + 5, pos[1] + (box_height - self.rect.height) // 2]
    
    def handle_input(self, event):
        """
        处理输入事件
        
        参数:
            event: pygame事件
            
        返回:
            dict: 包含action和data的字典
        """
        result = {"action": None, "data": None}
        
        # 处理鼠标点击事件
        if event.type == pygame.MOUSEBUTTONDOWN:
            # 检查点击是否在输入框内
            if self.box_rect.collidepoint(event.pos):
                self.input_active = True
            else:
                self.input_active = False
        
        # 处理键盘输入事件
        if event.type == pygame.KEYDOWN and self.input_active:
            if event.key == pygame.K_RETURN:
                # 回车键提交文本
                result["action"] = "send"
                result["data"] = self.title
            elif event.key == pygame.K_BACKSPACE:
                # 退格键删除字符
                self.title = self.title[:-1]
                # 重新渲染文本
                self.text = ASSETS.text(
                    self.title, self.path, self.size, self.color,
                )
                self.rect = self.text.get_rect()
                # 调整文本位置
                self.rect.topleft = (self.pos[0], self.pos[1])
            else:
                # 添加输入的字符，但要检查长度限制
                if len(self.title) < self.max_length:
                    self.title += event.unicode
                    # 重新渲染文本
                    self.text = ASSETS.text(
                        self.title, self.path, self.size, self.color,
                    )
                    self.rect = self.text.get_rect()
                    # 调整文本位置
                    self.rect.topleft = (self.pos[0], self.pos[1])
        
        return result
    
    def draw(self, surface):
        """
        在屏幕上绘制输入框和文本
        
        参数:
            surface: pygame屏幕表面
        """
        # 根据激活状态选择背景颜色
        bg_color = self.active_color if self.input_active else self.inactive_color
        
        # 绘制输入框背景
        pygame.draw.rect(surface, bg_color, self.box_rect)
        
        # 绘制输入框边框
        pygame.draw.rect(surface, self.border_color, self.box_rect, 2)
        
        # 绘制文本
        surface.blit(self.text, (self.pos[0], self.pos[1]))
    
    def get_text(self):
        """
        获取当前文本内容
        
        返回:
            str: 文本内容
        """
        return self.title
    
    def set_text(self, text):
        """
        设置文本内容
        
        参数:
            text: 新的文本内容
        """
        self.title = text
        self.text = ASSETS.text(
            self.title, self.path, self.size, self.color,
        )
        self.rect = self.text.get_rect()
        self.rect.topleft = (self.pos[0], self.pos[1])
    
    def clear(self):
        """
        清空文本内容
        """
        self.title = ''
        self.text = ASSETS.text(
            self.title, self.path, self.size, self.color,
        )
        self.rect = self.text.get_rect()
        self.rect.topleft = (self.pos[0], self.pos[1])
    
    def update_box_size(self, width=None, height=None):
        """
        更新输入框大小
        
        参数:
            width: 新的宽度（如果为None则保持不变）
            height: 新的高度（如果为None则保持不变）
        """
        if width is not None:
            self.box_width = width
        if height is not None:
            self.box_height = height
        
        # 更新输入框矩形
        self.box_rect.width = self.box_width
        self.box_rect.height = self.box_height
        
        # 调整文本位置
        self.pos[1] = self.box_rect.y + (self.box_height - self.rect.height) // 2


