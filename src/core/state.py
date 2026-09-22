"""互不耦合的配置、显示设置和单局状态模型。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class GameConfig:
    simulation_hz: int = 60
    render_fps: int = 120
    max_frame_time: float = 0.1
    time_epsilon: float = 1e-9

    player_speed: float = 600.0
    player_attack_damage: float = 25.0
    player_attack_interval: float = 1.0
    player_attack_duration: float = 10 / 60
    player_size: tuple = (100.0, 70.0)
    player_min_size: tuple = (40.0, 28.0)
    kill_growth: tuple = (6.0, 4.0)

    enemy_hp: float = 1.0
    attack_enemy_hp: float = 100.0
    attack_chicken_size: tuple = (80.0, 80.0)
    attack_chicken_speed: float = 300.0
    attack_chicken_first_seconds: float = 12.0
    attack_chicken_interval: float = 12.0
    attack_chicken_max_alive: int = 3

    green_capoo_size: tuple = (44.0, 32.0)
    green_capoo_speed: float = 180.0
    green_capoo_hp: float = 1.0
    green_capoo_growth: tuple = (10.0, 7.0)
    green_capoo_first_seconds: float = 3.0
    green_capoo_interval: float = 6.0
    green_capoo_phase_seconds: float = 60.0
    green_capoo_stage_seconds: float = 20.0
    green_capoo_stage_batch_sizes: tuple = (3, 2, 1)
    green_capoo_max_total: int = 20
    green_capoo_max_alive: int = 9
    green_capoo_orbit_padding: float = 8.0
    green_capoo_orbit_tolerance: float = 16.0
    green_capoo_orbit_speed_ratio: float = 0.72
    green_capoo_approach_orbit_ratio: float = 0.35
    boid_neighbor_radius: float = 96.0
    boid_separation_weight: float = 0.8
    boid_alignment_weight: float = 0.6
    boid_cohesion_weight: float = 0.5
    upgrade_kill_base: int = 5
    upgrade_kill_growth: float = 2.0

    spawn_base_interval: float = 130 / 60
    spawn_min_interval: float = 45 / 60
    spawn_ramp_seconds: float = 150.0
    max_alive_base: int = 12
    max_alive_step_seconds: float = 30.0
    max_alive_step: int = 5
    max_alive_cap: int = 46
    attack_enemy_start_seconds: float = 20.0
    attack_enemy_ramp_seconds: float = 90.0
    attack_enemy_max_ratio: float = 0.4

    @property
    def fixed_dt(self):
        return 1.0 / self.simulation_hz


@dataclass
class DisplaySettings:
    width: int = 1536
    height: int = 864
    fullscreen: bool = False
    bgm_volume: float = 0.5
    sfx_volume: float = 0.5

    def resize(self, width, height):
        self.width = int(width)
        self.height = int(height)

    def set_bgm_volume(self, value):
        self.bgm_volume = max(0.0, min(1.0, float(value)))

    def set_sfx_volume(self, value):
        self.sfx_volume = max(0.0, min(1.0, float(value)))


@dataclass
class GameSession:
    score: int = 10
    max_score: int = 10
    enemies_defeated: int = 0
    upgrade_earned: int = 0
    upgrade_pending_count: int = 0

    @property
    def upgrade_pending(self):
        return self.upgrade_pending_count > 0

    def update_score(self, width, rules):
        self.score = rules.score_from_size(width)
        self.max_score = max(self.max_score, self.score)
        self.check_upgrades(rules.config)
        return self.score

    def register_kill(self, config):
        self.enemies_defeated += 1
        return self.check_upgrades(config)

    def kills_required_for_next_upgrade(self, config):
        """下一次升级单独所需的击杀数：5、10、20、40……"""
        return int(round(
            config.upgrade_kill_base
            * config.upgrade_kill_growth ** self.upgrade_earned
        ))

    def next_upgrade_threshold(self, config):
        """下一次升级的累计击杀阈值：5、15、35、75……"""
        threshold = 0
        for level in range(self.upgrade_earned + 1):
            threshold += int(round(
                config.upgrade_kill_base
                * config.upgrade_kill_growth ** level
            ))
        return threshold

    def check_upgrades(self, config):
        while self.enemies_defeated >= self.next_upgrade_threshold(config):
            self.upgrade_pending_count += 1
            self.upgrade_earned += 1
        return self.upgrade_pending_count

    def take_upgrade(self):
        if self.upgrade_pending_count <= 0:
            return False
        self.upgrade_pending_count -= 1
        return True

    def reset(self):
        self.score = 10
        self.max_score = 10
        self.enemies_defeated = 0
        self.upgrade_earned = 0
        self.upgrade_pending_count = 0


GAME_CONFIG = GameConfig()
DISPLAY_SETTINGS = DisplaySettings()
GAME_SESSION = GameSession()
