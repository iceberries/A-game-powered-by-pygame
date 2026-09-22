import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core.game_world import GameWorld, MAX_PLAYERS
from core.spatial_hash import SpatialHash
from core.state import GameSession


class GameWorldTests(unittest.TestCase):
    def simulate_one_second(self, dt):
        world = GameWorld(["Player"], seed=1)
        steps = round(1 / dt)
        for sequence in range(1, steps + 1):
            commands = []
            if sequence == 1:
                commands.append({
                    "player": "Player",
                    "sequence": sequence,
                    "action": {"type": "move", "direction": "right"},
                })
            world.step(dt, commands)
        return world

    def test_movement_is_delta_time_independent(self):
        positions = [
            self.simulate_one_second(dt).players["Player"]["pos"][0]
            for dt in (1 / 30, 1 / 60, 1 / 120)
        ]
        self.assertEqual(positions, [700.0, 700.0, 700.0])

    def test_attack_uses_shared_growth_rules(self):
        world = GameWorld(["Player"], seed=1)
        enemy = world._new_enemy("normal")
        enemy["pos"][:] = (190, 100)
        world.enemies[enemy["id"]] = enemy

        world.step(1 / 60, [{
            "player": "Player",
            "sequence": 1,
            "action": {"type": "attack"},
        }])

        self.assertTrue(world.players["Player"]["attacking"])
        self.assertGreater(world.players["Player"]["size"][0], 105)
        self.assertEqual(enemy["hp"], enemy["max_hp"])
        self.assertIn("attack_elapsed", world.snapshot()["players"]["Player"])

    def test_opening_green_capoos_spawn_three_at_a_time(self):
        world = GameWorld(["Player"], seed=1)
        config = world.rules.config

        world.step(config.green_capoo_first_seconds)
        green_capoos = [
            enemy for enemy in world.enemies.values()
            if enemy["type"] == "green_capoo"
        ]
        self.assertEqual(
            len(green_capoos), world.rules.green_capoo_batch_size_at(3),
        )

        world.step(config.green_capoo_interval)
        green_capoos = [
            enemy for enemy in world.enemies.values()
            if enemy["type"] == "green_capoo"
        ]
        self.assertEqual(
            len(green_capoos), world.rules.green_capoo_batch_size_at(3) * 2,
        )

    def test_green_capoo_spawn_count_decreases_by_twenty_second_stage(self):
        world = GameWorld(["Player"], seed=1)

        self.assertEqual(world.rules.green_capoo_batch_size_at(0), 3)
        self.assertEqual(world.rules.green_capoo_batch_size_at(19.99), 3)
        self.assertEqual(world.rules.green_capoo_batch_size_at(20), 2)
        self.assertEqual(world.rules.green_capoo_batch_size_at(39.99), 2)
        self.assertEqual(world.rules.green_capoo_batch_size_at(40), 1)
        self.assertEqual(world.rules.green_capoo_batch_size_at(60), 1)

    def test_attack_chicken_has_its_own_spawn_schedule(self):
        world = GameWorld(["Player"], seed=1)
        config = world.rules.config
        world.elapsed = config.attack_chicken_first_seconds - 1 / 60

        world.step(1 / 60)

        chickens = [
            enemy for enemy in world.enemies.values()
            if enemy["type"] == "attack_chicken"
        ]
        self.assertEqual(len(chickens), 1)
        self.assertEqual(chickens[0]["size"], list(config.attack_chicken_size))
        snapshot_chicken = next(
            enemy for enemy in world.snapshot()["enemies"]
            if enemy["type"] == "attack_chicken"
        )
        self.assertIn("attack_elapsed", snapshot_chicken)

    def test_green_capoo_is_removed_and_grants_its_bonus_growth(self):
        world = GameWorld(["Player"], seed=1)
        enemy = world._new_enemy("green_capoo")
        enemy["pos"][:] = (190, 100)
        world.enemies[enemy["id"]] = enemy
        initial_width = world.players["Player"]["size"][0]

        world.step(1 / 60, [{
            "player": "Player",
            "sequence": 1,
            "action": {"type": "attack"},
        }])

        self.assertNotIn(enemy["id"], world.enemies)
        self.assertGreater(
            world.players["Player"]["size"][0],
            initial_width + world.rules.config.green_capoo_growth[0] - 1,
        )

    def test_boids_uses_neighbor_velocity_for_alignment(self):
        world = GameWorld(["Player"], seed=1)
        first = world._new_enemy("normal")
        second = world._new_enemy("normal")
        first["pos"][:] = (300, 300)
        second["pos"][:] = (360, 300)
        second["velocity"][:] = (0, 120)
        flock = {
            enemy["id"]: (world._enemy_center(enemy), tuple(enemy["velocity"]))
            for enemy in (first, second)
        }
        index = SpatialHash(world.rules.config.boid_neighbor_radius)
        for enemy_id, (center, _) in flock.items():
            index.add(enemy_id, (*center, 0, 0))

        flock_x, flock_y = world._flocking_vector(first, flock, index)

        self.assertNotEqual((flock_x, flock_y), (0.0, 0.0))
        self.assertGreater(flock_y, 0.0)

    def test_green_capoo_orbits_at_a_size_aware_attackable_distance(self):
        world = GameWorld(["Player"], seed=1)
        config = world.rules.config
        player_size = list(config.player_size)
        capoo_size = list(config.green_capoo_size)
        player_center = (150.0, 135.0)
        expected_radius = (
            max(player_size) / 2 + max(capoo_size) / 2
            + config.green_capoo_orbit_padding
        )

        velocity_x, velocity_y, radius = world.rules.green_capoo_orbit_velocity(
            (player_center[0] + expected_radius, player_center[1]),
            player_center, player_size, capoo_size,
            config.green_capoo_speed, 1,
        )
        _, _, larger_radius = world.rules.green_capoo_orbit_velocity(
            (player_center[0] + expected_radius, player_center[1]),
            player_center, [200.0, 140.0], capoo_size,
            config.green_capoo_speed, 1,
        )

        self.assertEqual(radius, expected_radius)
        self.assertGreater(larger_radius, radius)
        self.assertAlmostEqual(velocity_x, 0.0)
        self.assertGreater(velocity_y, 0.0)

    def test_upgrade_thresholds_grow_exponentially(self):
        world = GameWorld(["Player"], seed=1)
        config = world.rules.config
        session = GameSession()

        for _ in range(5):
            session.register_kill(config)
        self.assertEqual(session.upgrade_earned, 1)
        self.assertEqual(session.kills_required_for_next_upgrade(config), 10)
        self.assertEqual(session.next_upgrade_threshold(config), 15)

        for _ in range(10):
            session.register_kill(config)
        self.assertEqual(session.upgrade_earned, 2)
        self.assertEqual(session.kills_required_for_next_upgrade(config), 20)
        self.assertEqual(session.next_upgrade_threshold(config), 35)

    def test_snapshot_does_not_share_mutable_state(self):
        world = GameWorld(["Player"], seed=1)
        snapshot = world.snapshot()
        original_x = snapshot["players"]["Player"]["pos"][0]

        world.players["Player"]["pos"][0] += 100

        self.assertEqual(snapshot["players"]["Player"]["pos"][0], original_x)

    def test_four_player_camera_uses_character_centers(self):
        names = [f"Player_{index}" for index in range(1, MAX_PLAYERS + 1)]
        world = GameWorld(names, seed=1)

        snapshot = world.snapshot()

        self.assertEqual(snapshot["camera"]["center"], [210.0, 195.0])

    def test_rejects_more_than_four_players(self):
        with self.assertRaises(ValueError):
            GameWorld([
                f"Player_{index}" for index in range(MAX_PLAYERS + 1)
            ])


if __name__ == "__main__":
    unittest.main()
