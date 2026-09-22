"""服务器权威的纯联机游戏模拟。

此模块不创建 Surface、不读取图片、不操作 Pygame 事件队列，可以在
服务器工作线程中安全运行。
"""

import math
import random

from core.game_rules import DEFAULT_RULES
from core.spatial_hash import SpatialHash


MAX_PLAYERS = 4


class GameWorld:
    NORMAL_SIZE = (50.0, 50.0)
    ENEMY_SPEED = 300.0
    ENEMY_ATTACK_DURATION = 20 / 60
    ENEMY_ATTACK_INTERVAL = 0.75

    def __init__(self, player_names, world_size=(1536, 864), rules=None, seed=None):
        if len(player_names) > MAX_PLAYERS:
            raise ValueError(f"multiplayer supports at most {MAX_PLAYERS} players")
        self.rules = rules or DEFAULT_RULES
        self.world_size = tuple(world_size)
        self.random = random.Random(seed)
        self.players = {}
        self.enemies = {}
        self.elapsed = 0.0
        self.spawn_timer = 0.0
        self.green_capoos_spawned = 0
        self.next_green_capoo_spawn = self.rules.config.green_capoo_first_seconds
        self.next_attack_chicken_spawn = self.rules.config.attack_chicken_first_seconds
        self.tick = 0
        self._next_enemy_id = 1
        for index, name in enumerate(player_names):
            self.add_player(name, index)

    def add_player(self, name, index=None):
        if name in self.players:
            return self.players[name]
        if len(self.players) >= MAX_PLAYERS:
            raise ValueError(f"multiplayer supports at most {MAX_PLAYERS} players")
        if index is None:
            index = len(self.players)
        spawn_points = ((100, 100), (220, 100), (100, 220), (220, 220))
        if index < len(spawn_points):
            pos = list(spawn_points[index])
        else:
            pos = [
                self.random.randint(100, max(100, self.world_size[0] - 100)),
                self.random.randint(100, max(100, self.world_size[1] - 100)),
            ]
        size = list(self.rules.config.player_size)
        player = {
            "pos": pos,
            "hp": 100,
            "size": size,
            "score": self.rules.score_from_size(size[0]),
            "move_dir": None,
            "facing_left": False,
            "attacking": False,
            "attack_timer": 0.0,
            "attack_elapsed": 0.0,
            "attack_damage": self.rules.config.player_attack_damage,
            "last_sequence": -1,
            "alive": True,
        }
        self.players[name] = player
        return player

    def remove_player(self, name):
        self.players.pop(name, None)

    def apply_command(self, command):
        player_name = command.get("player")
        player = self.players.get(player_name)
        if player is None:
            return
        sequence = command.get("sequence", -1)
        if sequence <= player["last_sequence"]:
            return
        player["last_sequence"] = sequence
        action = command.get("action", {})
        action_type = action.get("type")
        if action_type == "move":
            player["move_dir"] = action.get("direction")
        elif action_type == "stop_move":
            player["move_dir"] = None
        elif action_type == "attack":
            self._start_player_attack(player_name, player)
        elif action_type == "quit_game":
            self.remove_player(player_name)

    def step(self, dt, commands=()):
        for command in commands:
            self.apply_command(command)
        self.elapsed += dt
        self.tick += 1
        self._update_players(dt)
        self._spawn_normal_enemies(dt)
        self._spawn_attack_chickens()
        self._spawn_green_capoos()
        self._update_enemies(dt)
        return any(player["alive"] for player in self.players.values())

    def _update_players(self, dt):
        for player in self.players.values():
            if not player["alive"]:
                continue
            dx, dy = self.rules.movement_delta(
                player["move_dir"],
                self.rules.config.player_speed,
                dt,
            )
            player["pos"][0] += dx
            player["pos"][1] += dy
            if dx < 0:
                player["facing_left"] = True
            elif dx > 0:
                player["facing_left"] = False

            player["attack_timer"] = max(0.0, player["attack_timer"] - dt)
            if player["attacking"]:
                player["attack_elapsed"] += dt
                if (player["attack_elapsed"] + 1e-9
                        >= self.rules.config.player_attack_duration):
                    player["attacking"] = False
                    player["attack_elapsed"] = 0.0

            shrink_x, shrink_y = self.rules.shrink_rate(player["score"])
            width, height = self.rules.clamp_size(
                player["size"][0] + shrink_x * dt,
                player["size"][1] + shrink_y * dt,
            )
            player["size"][:] = (width, height)
            player["score"] = self.rules.score_from_size(width)
            min_width, min_height = self.rules.config.player_min_size
            if width <= min_width + 1e-9 or height <= min_height + 1e-9:
                player["alive"] = False
                player["move_dir"] = None

    def _start_player_attack(self, name, player):
        if not player["alive"] or player["attack_timer"] > 0:
            return
        player["attacking"] = True
        player["attack_elapsed"] = 0.0
        player["attack_timer"] = self.rules.config.player_attack_interval
        attack_rect = self.rules.attack_rect(
            player["pos"], player["size"], player["facing_left"])
        for enemy in list(self.enemies.values()):
            enemy_rect = (*enemy["pos"], *enemy["size"])
            if not self.rules.intersects(attack_rect, enemy_rect):
                continue
            enemy["hp"] -= player["attack_damage"]
            if enemy["hp"] <= 0:
                self._defeat_enemy(enemy, player)

    def _defeat_enemy(self, enemy, player):
        if enemy["type"] == "green_capoo":
            self._reward_green_capoo(player)
            del self.enemies[enemy["id"]]
            return
        self._reward_kill(player)
        self._respawn_enemy(enemy)

    def _reward_kill(self, player):
        growth_width, growth_height = self.rules.config.kill_growth
        width, height = self.rules.clamp_size(
            player["size"][0] + growth_width,
            player["size"][1] + growth_height,
        )
        player["size"][:] = (width, height)
        player["score"] = self.rules.score_from_size(width)

    def _reward_green_capoo(self, player):
        growth_width, growth_height = self.rules.config.green_capoo_growth
        width, height = self.rules.clamp_size(
            player["size"][0] + growth_width,
            player["size"][1] + growth_height,
        )
        player["size"][:] = (width, height)
        player["score"] = self.rules.score_from_size(width)

    def _spawn_normal_enemies(self, dt):
        if not self.players:
            return
        self.spawn_timer += dt
        interval, max_alive, _ = self.rules.difficulty(self.elapsed)
        normal_count = sum(
            enemy["type"] == "normal" for enemy in self.enemies.values())
        if self.spawn_timer + 1e-9 < interval or normal_count >= max_alive:
            return
        self.spawn_timer = max(0.0, self.spawn_timer - interval)
        enemy = self._new_enemy("normal")
        self.enemies[enemy["id"]] = enemy

    def _spawn_attack_chickens(self):
        config = self.rules.config
        alive = sum(
            enemy["type"] == "attack_chicken"
            for enemy in self.enemies.values())
        if (self.elapsed + 1e-9 < self.next_attack_chicken_spawn
                or alive >= config.attack_chicken_max_alive):
            return
        chicken = self._new_enemy("attack_chicken")
        self.enemies[chicken["id"]] = chicken
        self.next_attack_chicken_spawn += config.attack_chicken_interval

    def _spawn_green_capoos(self):
        config = self.rules.config
        batch_size = self.rules.green_capoo_batch_size_at(self.elapsed)
        alive = sum(
            enemy["type"] == "green_capoo" for enemy in self.enemies.values())
        if (self.elapsed > config.green_capoo_phase_seconds
                or self.green_capoos_spawned >= config.green_capoo_max_total
                or self.elapsed + 1e-9 < self.next_green_capoo_spawn
                or alive > config.green_capoo_max_alive - batch_size):
            return
        amount = min(
            batch_size,
            config.green_capoo_max_total - self.green_capoos_spawned,
        )
        for _ in range(amount):
            capoo = self._new_enemy("green_capoo")
            self.enemies[capoo["id"]] = capoo
        self.green_capoos_spawned += amount
        self.next_green_capoo_spawn += config.green_capoo_interval

    def _new_enemy(self, enemy_type):
        enemy_id = self._next_enemy_id
        self._next_enemy_id += 1
        config = self.rules.config
        if enemy_type in {"attack", "attack_chicken"}:
            size, hp, speed = (
                config.attack_chicken_size,
                config.attack_enemy_hp,
                config.attack_chicken_speed,
            )
        elif enemy_type == "green_capoo":
            size, hp, speed = (
                config.green_capoo_size,
                config.green_capoo_hp,
                config.green_capoo_speed,
            )
        else:
            size, hp, speed = self.NORMAL_SIZE, config.enemy_hp, self.ENEMY_SPEED
        enemy = {
            "id": enemy_id,
            "type": enemy_type,
            "pos": [0.0, 0.0],
            "size": list(size),
            "hp": hp,
            "max_hp": hp,
            "speed": speed,
            "velocity": [0.0, 0.0],
            "orbit_direction": self.random.choice((-1, 1)),
            "facing_left": True,
            "attacking": False,
            "attack_elapsed": 0.0,
            "attack_timer": 0.0,
        }
        self._respawn_enemy(enemy)
        return enemy

    def _respawn_enemy(self, enemy):
        center = self._players_center()
        radius = math.hypot(*self.world_size) / 2 + 90
        angle = self.random.uniform(0, math.tau)
        enemy["pos"][:] = (
            center[0] + math.cos(angle) * radius - enemy["size"][0] / 2,
            center[1] + math.sin(angle) * radius - enemy["size"][1] / 2,
        )
        enemy["hp"] = enemy["max_hp"]
        enemy["attacking"] = False
        enemy["attack_elapsed"] = 0.0
        enemy["attack_timer"] = 0.0
        enemy["velocity"][:] = (0.0, 0.0)

    def camera_center(self):
        """返回所有存活玩家角色中心点的几何中心。"""
        active = [p for p in self.players.values() if p["alive"]]
        if not active:
            return self.world_size[0] / 2, self.world_size[1] / 2
        return (
            sum(p["pos"][0] + p["size"][0] / 2 for p in active)
            / len(active),
            sum(p["pos"][1] + p["size"][1] / 2 for p in active)
            / len(active),
        )

    def _players_center(self):
        return self.camera_center()

    def _closest_player(self, enemy):
        active = [
            (name, player)
            for name, player in self.players.items()
            if player["alive"]
        ]
        if not active:
            return None, None
        ex = enemy["pos"][0] + enemy["size"][0] / 2
        ey = enemy["pos"][1] + enemy["size"][1] / 2
        return min(
            active,
            key=lambda item: (
                item[1]["pos"][0] + item[1]["size"][0] / 2 - ex
            ) ** 2 + (
                item[1]["pos"][1] + item[1]["size"][1] / 2 - ey
            ) ** 2,
        )

    @staticmethod
    def _enemy_center(enemy):
        return (
            enemy["pos"][0] + enemy["size"][0] / 2,
            enemy["pos"][1] + enemy["size"][1] / 2,
        )

    def _flocking_vector(self, enemy, flock_states, flock_index):
        """计算当前敌人在其同类群体中的 Boids 修正速度。"""
        center = self._enemy_center(enemy)
        radius = self.rules.config.boid_neighbor_radius
        nearby_ids = flock_index.query((
            center[0] - radius, center[1] - radius, radius * 2, radius * 2,
        ))
        neighbors = [
            flock_states[enemy_id]
            for enemy_id in sorted(nearby_ids)
            if enemy_id != enemy["id"]
        ]
        return self.rules.flocking_vector(
            center, enemy["speed"], neighbors,
        )

    def _update_enemies(self, dt):
        # 先冻结本 tick 的群体状态，避免遍历顺序改变 Boids 结果。
        flock_states = {}
        flock_indices = {}
        for candidate in self.enemies.values():
            enemy_type = candidate["type"]
            center = self._enemy_center(candidate)
            flock_states.setdefault(enemy_type, {})[candidate["id"]] = (
                center, tuple(candidate["velocity"]),
            )
            index = flock_indices.setdefault(
                enemy_type,
                SpatialHash(self.rules.config.boid_neighbor_radius),
            )
            index.add(candidate["id"], (*center, 0, 0))
        for enemy in self.enemies.values():
            _, player = self._closest_player(enemy)
            if player is None:
                return
            enemy["attack_timer"] = max(0.0, enemy["attack_timer"] - dt)
            if enemy["attacking"]:
                enemy["velocity"][:] = (0.0, 0.0)
                enemy["attack_elapsed"] += dt
                if enemy["attack_elapsed"] + 1e-9 >= self.ENEMY_ATTACK_DURATION:
                    self._resolve_enemy_attack(enemy)
                    enemy["attacking"] = False
                    enemy["attack_elapsed"] = 0.0
                    enemy["attack_timer"] = self.ENEMY_ATTACK_INTERVAL
                continue

            enemy_center = self._enemy_center(enemy)
            player_center = (
                player["pos"][0] + player["size"][0] / 2,
                player["pos"][1] + player["size"][1] / 2,
            )
            if enemy["type"] == "green_capoo":
                velocity_x, velocity_y, _ = (
                    self.rules.green_capoo_orbit_velocity(
                        enemy_center, player_center, player["size"],
                        enemy["size"], enemy["speed"],
                        enemy["orbit_direction"],
                    )
                )
            else:
                dx, dy = self.rules.normalized_direction(
                    enemy_center, player_center,
                )
                distance = math.dist(enemy_center, player_center)
                if enemy["type"] == "normal" and distance < 200:
                    dx, dy = -dx, -dy
                flock_x, flock_y = self._flocking_vector(
                    enemy, flock_states[enemy["type"]],
                    flock_indices[enemy["type"]],
                )
                velocity_x = dx * enemy["speed"] + flock_x
                velocity_y = dy * enemy["speed"] + flock_y
            enemy["velocity"][:] = (velocity_x, velocity_y)
            enemy["pos"][0] += velocity_x * dt
            enemy["pos"][1] += velocity_y * dt
            if velocity_x < 0:
                enemy["facing_left"] = True
            elif velocity_x > 0:
                enemy["facing_left"] = False

            if (enemy["type"] in {"attack", "attack_chicken"}
                    and enemy["attack_timer"] <= 0):
                attack_rect = self._enemy_attack_rect(enemy)
                player_rect = (*player["pos"], *player["size"])
                if self.rules.intersects(attack_rect, player_rect):
                    enemy["attacking"] = True
                    enemy["attack_elapsed"] = 0.0

    @staticmethod
    def _enemy_attack_rect(enemy):
        width = enemy["size"][0] / 5
        if enemy["facing_left"]:
            left = enemy["pos"][0] - width
        else:
            left = enemy["pos"][0] + enemy["size"][0]
        return left, enemy["pos"][1], width, enemy["size"][1]

    def _resolve_enemy_attack(self, enemy):
        attack_rect = self._enemy_attack_rect(enemy)
        for player in self.players.values():
            if not player["alive"]:
                continue
            player_rect = (*player["pos"], *player["size"])
            if not self.rules.intersects(attack_rect, player_rect):
                continue
            shrink_x, shrink_y = self.rules.shrink_rate(player["score"])
            width, height = self.rules.clamp_size(
                player["size"][0] + shrink_x * (10 / 60),
                player["size"][1] + shrink_y * (10 / 60),
            )
            player["size"][:] = (width, height)
            player["score"] = self.rules.score_from_size(width)

    def snapshot(self):
        players = {}
        for name, player in self.players.items():
            players[name] = {
                "pos": list(player["pos"]),
                "hp": player["hp"],
                "size": list(player["size"]),
                "score": player["score"],
                "move_dir": player["move_dir"],
                "facing_left": player["facing_left"],
                "attacking": player["attacking"],
                "attack_elapsed": player["attack_elapsed"],
                "attack_timer": player["attack_timer"],
                "attack_damage": player["attack_damage"],
                "alive": player["alive"],
            }
        enemies = []
        for enemy in self.enemies.values():
            enemies.append({
                "id": enemy["id"],
                "type": enemy["type"],
                "pos": list(enemy["pos"]),
                "size": list(enemy["size"]),
                "hp": enemy["hp"],
                "facing_left": enemy["facing_left"],
                "attacking": enemy["attacking"],
                "attack_elapsed": enemy["attack_elapsed"],
            })
        return {
            "tick": self.tick,
            "elapsed": self.elapsed,
            "players": players,
            "enemies": enemies,
            "map": {
                "width": self.world_size[0],
                "height": self.world_size[1],
            },
            "camera": {
                "center": list(self.camera_center()),
            },
        }


class MultiplayerSimulation(GameWorld):
    """兼容旧导入；新代码应直接依赖 GameWorld。"""
