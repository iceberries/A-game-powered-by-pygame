import pygame
import sys
import const
import image
from sound import *
from core.game_level import GameLevel
import random
from Enemies import Enemy
from Enemies import AttackEnemy
import camera
import threading
import json
import socket
import time

class MultiplayerGameLevel(GameLevel):
    """多人游戏关卡类，继承自GameLevel，添加网络同步功能"""
    def __init__(self, multiplayer=True):
        """初始化多人游戏关卡
        multiplayer: 是否为多人模式
        """
        # 调用父类初始化，传递multiplayer参数，避免卡在loading
        super().__init__(multiplayer=multiplayer)
        
        # 多人游戏特有属性
        self.multiplayer = multiplayer
        self.players = {}  # 存储所有玩家信息 {player_name: {pos, hp, action, ...}}
        self.player_sprites = {}  # 存储所有玩家精灵对象
        self.spawn_points = [(100, 100), (200, 100), (100, 200), (200, 200)]  # 玩家出生点
        
        # 网络同步相关
        self.last_sync_time = time.time()
        self.sync_interval = 1.0 / 30  # 30fps同步频率print("1")
    
    def get_spawn_point(self, player_index):
        """获取玩家出生点
        player_index: 玩家索引
        """
        if player_index < len(self.spawn_points):
            return self.spawn_points[player_index]
        else:
            # 如果玩家数量超过预设出生点，随机生成新的出生点
            x = random.randint(100, 500)
            y = random.randint(100, 500)
            return (x, y)
    
    def update(self, players_data):
        """更新游戏状态，供服务器调用
        players_data: 玩家数据字典 {player_name: {pos, hp, action, ...}}
        """
        # 更新玩家数据
        self.players = players_data
        
        # 处理玩家操作
        for player_name, player_data in self.players.items():
            action = player_data.get('action')
            if action:
                self.handle_player_action(player_name, action)
                # 清除已处理的操作
                player_data['action'] = None
        
        # 更新游戏逻辑（敌人、地图等）
        self.update_enemies()
        
        # 检测碰撞
        self.check_collisions()
        return not (self.game_state == "main_menu")  # 返回游戏是否继续
    
    def handle_player_action(self, player_name, action):
        """处理玩家操作
        player_name: 玩家名称
        action: 操作数据 {type, params}
        """
        if not action:
            return
            
        # 获取玩家数据
        player_data = self.players.get(player_name)
        if not player_data:
            return
            
        # 根据操作类型处理
        action_type = action.get('type')
        if action_type == 'move':
            # 移动操作
            direction = action.get('direction')
            if direction == 'left':
                player_data['pos'] = (player_data['pos'][0] - 5, player_data['pos'][1])
                player_data['facing_left'] = True
            elif direction == 'right':
                player_data['pos'] = (player_data['pos'][0] + 5, player_data['pos'][1])
                player_data['facing_left'] = False
            elif direction == 'up':
                player_data['pos'] = (player_data['pos'][0], player_data['pos'][1] - 5)
            elif direction == 'down':
                player_data['pos'] = (player_data['pos'][0], player_data['pos'][1] + 5)
        
        elif action_type == 'attack':
            # 攻击操作
            player_data['attacking'] = True
            # 检测攻击是否命中敌人
            self.check_player_attack(player_name)
    
    def update_enemies(self):
        """更新敌人状态"""
        # 敌人生成
        self.spawn_timer += 1
        if self.spawn_timer >= self.spawn_enemy_cd:
            self.spawn_enemy()
            self.spawn_timer = 0
        
        # 更新攻击型敌人
        for enemy in self.attack_enemy_group:
            if hasattr(enemy, 'try_attack'):
                if enemy.try_attack():
                    continue  # 进入攻击状态后不移动
            enemy.move_towards_player(self.attack_enemy_group)
            enemy.play_animation()
        
        # 更新普通敌人
        if len(self.attack_enemy_group) > 0:
            centers = [pygame.Vector2(e.getrect().center) for e in self.attack_enemy_group]
            attack_center = sum(centers, pygame.Vector2(0,0)) / len(centers)
        else:
            attack_center = pygame.Vector2(const.wsize//2, const.hsize//2)
            
        for enemy in self.enemy_group:
            # 普通敌人根据玩家与攻击型敌人群体中心连线移动并保持距离
            # 多人模式下，选择最近的玩家作为目标
            closest_player_pos = self.get_closest_player_pos(enemy.getrect().center)
            enemy.move_behead_attacker(attack_center, pygame.Vector2(closest_player_pos), enemies=self.enemy_group)
            enemy.play_animation()
    
    def get_closest_player_pos(self, pos):
        """获取离指定位置最近的玩家位置"""
        if not self.players:
            return (const.wsize//2, const.hsize//2)
            
        min_dist = float('inf')
        closest_pos = None
        
        for player_name, player_data in self.players.items():
            player_pos = player_data.get('pos', (0, 0))
            dist = ((player_pos[0] - pos[0])**2 + (player_pos[1] - pos[1])**2)**0.5
            if dist < min_dist:
                min_dist = dist
                closest_pos = player_pos
        return closest_pos or (const.wsize//2, const.hsize//2)
    
    def spawn_enemy(self):
        """生成敌人"""
        # 计算当前所有玩家的平均位置作为参考点
        if not self.players:
            return
            
        avg_x = sum(p['pos'][0] for p in self.players.values()) / len(self.players)
        avg_y = sum(p['pos'][1] for p in self.players.values()) / len(self.players)
        
        # 在平均位置周围生成敌人
        margin = 300  # 生成在视野外300像素区域
        pos = [0, 0]
        side = random.choice(['left', 'right', 'top', 'bottom'])
        
        if side == 'left':
            pos[0] = avg_x - margin - 80
            pos[1] = random.randint(int(avg_y - margin), int(avg_y + margin - 80))
        elif side == 'right':
            pos[0] = avg_x + margin
            pos[1] = random.randint(int(avg_y - margin), int(avg_y + margin - 80))
        elif side == 'top':
            pos[0] = random.randint(int(avg_x - margin), int(avg_x + margin - 80))
            pos[1] = avg_y - margin - 80
        else:  # bottom
            pos[0] = random.randint(int(avg_x - margin), int(avg_x + margin - 80))
            pos[1] = avg_y + margin
        
        # 随机生成攻击型或普通敌人
        if random.randint(0, 3) == 0:
            enemy = AttackEnemy(self.capoo_surface, size=(80, 80), speed=5)
            enemy.pos = pos
            self.attack_enemy_group.add(enemy)
        else:
            enemy = Enemy(self.capoo_surface, size=(50, 50), speed=5)
            enemy.pos = pos
            self.enemy_group.add(enemy)
    
    def check_player_attack(self, player_name):
        """检测玩家攻击是否命中敌人
        player_name: 玩家名称
        """
        player_data = self.players.get(player_name)
        if not player_data or not player_data.get('attacking'):
            return
            
        # 创建攻击判定区域
        player_pos = player_data.get('pos', (0, 0))
        player_size = player_data.get('size', (const.capoo_width, const.capoo_hight))
        facing_left = player_data.get('facing_left', False)
        
        # 创建攻击矩形
        attack_width = int(player_size[0] * 0.5)
        attack_height = int(player_size[1])
        attack_rect = pygame.Rect(0, 0, attack_width, attack_height)
        
        # 根据朝向设置攻击矩形的位置
        if facing_left:
            attack_rect.left = player_pos[0] - attack_width * 3 // 4
        else:
            attack_rect.left = player_pos[0] + player_size[0] - attack_width // 4
        
        attack_rect.top = player_pos[1]
        
        # 检测攻击是否命中敌人
        for enemy in self.attack_enemy_group:
            if attack_rect.colliderect(enemy.getrect()):
                if enemy.hp_caculater(player_data.get('attack_damage', 10)) <= 0:
                    enemy.reset(self.camera)
                    # 增加玩家体型
                    player_data['size'] = (
                        player_data['size'][0] + 6,
                        player_data['size'][1] + 4
                    )
                    # 更新分数
                    player_data['score'] = player_data.get('score', 0) + 1
                    break
        
        # 检测攻击是否命中普通敌人
        for enemy in self.enemy_group:
            if attack_rect.colliderect(enemy.getrect()):
                if enemy.hp_caculater(player_data.get('attack_damage', 10)) <= 0:
                    enemy.reset(self.camera)
                    # 增加玩家体型
                    player_data['size'] = (
                        player_data['size'][0] + 6,
                        player_data['size'][1] + 4
                    )
                    # 更新分数
                    player_data['score'] = player_data.get('score', 0) + 1
                    break
    
    def check_collisions(self):
        """检测碰撞"""
        # 检测敌人攻击是否命中玩家
        for player_name, player_data in self.players.items():
            player_pos = player_data.get('pos', (0, 0))
            player_size = player_data.get('size', (const.capoo_width, const.capoo_hight))
            player_rect = pygame.Rect(player_pos[0], player_pos[1], player_size[0], player_size[1])
            
            # 检测攻击型敌人的攻击
            for enemy in self.attack_enemy_group:
                if hasattr(enemy, 'attack_finished') and enemy.attack_finished:
                    attack_rect = enemy.get_attack_rect()
                    if player_rect.colliderect(attack_rect):
                        # 减小玩家体型
                        shrink_x, shrink_y = self.get_shrink_speed(player_data.get('score', 0))
                        player_data['size'] = (
                            player_data['size'][0] + shrink_x * 10,
                            player_data['size'][1] + shrink_y * 10
                        )
                        # 更新分数
                        player_data['score'] = player_data.get('score', 0) - 1
    
    def get_enemies_state(self):
        """获取敌人状态，用于网络同步"""
        enemies_state = []
        
        # 收集普通敌人状态
        for enemy in self.enemy_group:
            enemy_state = {
                'id': id(enemy),  # 使用对象ID作为唯一标识
                'type': 'normal',
                'pos': enemy.pos,
                'size': enemy.size,
                'hp': enemy.hp
            }
            enemies_state.append(enemy_state)
        
        # 收集攻击型敌人状态
        for enemy in self.attack_enemy_group:
            enemy_state = {
                'id': id(enemy),
                'type': 'attack',
                'pos': enemy.pos,
                'size': enemy.size,
                'hp': enemy.hp,
                'attacking': hasattr(enemy, 'attacking') and enemy.attacking
            }
            enemies_state.append(enemy_state)
        return enemies_state
    
    def get_map_state(self):
        """获取地图状态，用于网络同步"""
        # 简化版地图状态，实际项目中可能需要更复杂的地图数据
        print("10")
        return {
            'width': const.wsize,
            'height': const.hsize,
            'camera_offset': (self.camera.offset_x, self.camera.offset_y)
        }

    def run(self):
        """多人游戏主循环"""
        clock = pygame.time.Clock()
        while self.game_state == "mul_game_state":
            # 处理事件
            if self.handle_events():
                break
            
            # 更新游戏状态
            self.update()
            
            # 网络同步
            current_time = time.time()
            if current_time - self.last_sync_time >= self.sync_interval:
                self.last_sync_time = current_time
                self.sync_game_state()
            
            # 渲染
            self.draw()
            clock.tick(const.fps)
        return self.game_state