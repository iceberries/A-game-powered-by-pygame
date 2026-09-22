"""单机和联机共用的纯游戏规则。

本模块不依赖 Pygame 的显示、音频或事件系统，因此可以安全地在
服务器模拟线程和无界面测试中使用。
"""

import math
from core.state import GAME_CONFIG, GameConfig


BalanceConfig = GameConfig


class GameplayRules:
    def __init__(self, config=None):
        self.config = config or GAME_CONFIG

    def difficulty(self, elapsed_seconds):
        cfg = self.config
        ramp = min(1.0, elapsed_seconds / cfg.spawn_ramp_seconds)
        spawn_interval = (
            cfg.spawn_base_interval
            + (cfg.spawn_min_interval - cfg.spawn_base_interval) * ramp
        )
        steps = int(elapsed_seconds // cfg.max_alive_step_seconds)
        max_alive = min(
            cfg.max_alive_cap,
            cfg.max_alive_base + steps * cfg.max_alive_step,
        )
        if elapsed_seconds <= cfg.attack_enemy_start_seconds:
            attack_ratio = 0.0
        else:
            attack_ratio = min(
                cfg.attack_enemy_max_ratio,
                (elapsed_seconds - cfg.attack_enemy_start_seconds)
                / cfg.attack_enemy_ramp_seconds
                * cfg.attack_enemy_max_ratio,
            )
        return spawn_interval, max_alive, attack_ratio

    @staticmethod
    def shrink_rate(score):
        """返回体型宽、高每秒的变化量（负数表示衰减）。"""
        scale = math.exp(0.05 * score)
        return -0.06 * 60 * scale, -0.04 * 60 * scale

    def clamp_size(self, width, height):
        min_width, min_height = self.config.player_min_size
        return max(min_width, width), max(min_height, height)

    def score_from_size(self, width):
        base_width = self.config.player_size[0]
        return int((width + 100 - base_width) / 10)

    @staticmethod
    def movement_delta(direction, speed, dt):
        directions = {
            "left": (-1.0, 0.0),
            "right": (1.0, 0.0),
            "up": (0.0, -1.0),
            "down": (0.0, 1.0),
        }
        dx, dy = directions.get(direction, (0.0, 0.0))
        return dx * speed * dt, dy * speed * dt

    @staticmethod
    def attack_rect(pos, size, facing_left, width_scale=0.5, height_scale=1.0):
        width = max(1.0, size[0] * width_scale)
        height = max(1.0, size[1] * height_scale)
        if facing_left:
            left = pos[0] - width * 3 / 4
        else:
            left = pos[0] + size[0] - width / 4
        return left, pos[1], width, height

    @staticmethod
    def intersects(first, second):
        ax, ay, aw, ah = first
        bx, by, bw, bh = second
        return (
            ax < bx + bw
            and ax + aw > bx
            and ay < by + bh
            and ay + ah > by
        )

    @staticmethod
    def normalized_direction(start, target):
        dx = target[0] - start[0]
        dy = target[1] - start[1]
        length = math.hypot(dx, dy)
        if length <= 1e-9:
            return 0.0, 0.0
        return dx / length, dy / length

    def flocking_vector(self, subject_center, subject_speed, neighbors):
        """计算确定性的 Boids 分离、对齐、聚合向量。

        ``neighbors`` 中每项为 ``(center, velocity)``。这里仅处理数值，因而可由
        单机精灵和联机服务器权威世界共同使用。
        """
        cfg = self.config
        separation_x = separation_y = 0.0
        alignment_x = alignment_y = 0.0
        cohesion_x = cohesion_y = 0.0
        count = 0
        sx, sy = subject_center
        for center, velocity in neighbors:
            dx, dy = center[0] - sx, center[1] - sy
            distance = math.hypot(dx, dy)
            if distance <= 1e-9 or distance >= cfg.boid_neighbor_radius:
                continue
            separation_x -= dx / distance
            separation_y -= dy / distance
            alignment_x += velocity[0]
            alignment_y += velocity[1]
            cohesion_x += center[0]
            cohesion_y += center[1]
            count += 1
        if not count:
            return 0.0, 0.0
        separation_x /= count
        separation_y /= count
        alignment_x /= count
        alignment_y /= count
        cohesion_x = cohesion_x / count - sx
        cohesion_y = cohesion_y / count - sy
        result_x = (
            separation_x * cfg.boid_separation_weight
            + alignment_x * cfg.boid_alignment_weight
            + cohesion_x * cfg.boid_cohesion_weight
        )
        result_y = (
            separation_y * cfg.boid_separation_weight
            + alignment_y * cfg.boid_alignment_weight
            + cohesion_y * cfg.boid_cohesion_weight
        )
        maximum = subject_speed * 0.8
        magnitude = math.hypot(result_x, result_y)
        if magnitude > maximum and magnitude > 1e-9:
            scale = maximum / magnitude
            result_x *= scale
            result_y *= scale
        return result_x, result_y

    def green_capoo_orbit_velocity(self, capoo_center, player_center,
                                   player_size, capoo_size, speed,
                                   orbit_direction=1):
        """让绿 Capoo 靠近后沿玩家体型边缘环绕，并始终留在可攻击距离内。"""
        cfg = self.config
        offset_x = capoo_center[0] - player_center[0]
        offset_y = capoo_center[1] - player_center[1]
        distance = math.hypot(offset_x, offset_y)
        if distance <= 1e-9:
            radial_x, radial_y = 1.0, 0.0
        else:
            radial_x, radial_y = offset_x / distance, offset_y / distance

        # 自身半径 + 玩家半径 + 小间隙：不穿进身体，同时低于攻击判定能覆盖的距离。
        orbit_radius = (
            max(player_size) / 2
            + max(capoo_size) / 2
            + cfg.green_capoo_orbit_padding
        )
        radial_error = distance - orbit_radius
        radial_speed = 0.0
        if abs(radial_error) > cfg.green_capoo_orbit_tolerance:
            radial_speed = -math.copysign(
                speed * min(1.0, abs(radial_error) / max(orbit_radius, 1.0)),
                radial_error,
            )
        tangent_x = -radial_y * orbit_direction
        tangent_y = radial_x * orbit_direction
        orbit_ratio = (
            cfg.green_capoo_orbit_speed_ratio
            if abs(radial_error) <= cfg.green_capoo_orbit_tolerance * 2
            else cfg.green_capoo_approach_orbit_ratio
        )
        velocity_x = radial_x * radial_speed + tangent_x * speed * orbit_ratio
        velocity_y = radial_y * radial_speed + tangent_y * speed * orbit_ratio
        maximum = speed
        magnitude = math.hypot(velocity_x, velocity_y)
        if magnitude > maximum and magnitude > 1e-9:
            scale = maximum / magnitude
            velocity_x *= scale
            velocity_y *= scale
        return velocity_x, velocity_y, orbit_radius

    def green_capoo_batch_size_at(self, elapsed_seconds):
        """按开局阶段返回每一波绿 Capoo 数量：3、2、1。"""
        cfg = self.config
        stage = min(
            len(cfg.green_capoo_stage_batch_sizes) - 1,
            int(max(0.0, elapsed_seconds) // cfg.green_capoo_stage_seconds),
        )
        return cfg.green_capoo_stage_batch_sizes[stage]


DEFAULT_RULES = GameplayRules()
