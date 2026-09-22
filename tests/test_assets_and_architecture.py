import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pygame

from core.assets import ASSETS, AssetManager
from core.game_world import GameWorld
from core.mul_game_level import MultiplayerGameLevel
from core.spatial_hash import SpatialHash
from core.state import GameSession
from image import Image


class AssetManagerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        if pygame.display.get_surface() is None:
            pygame.display.set_mode((1, 1))

    def test_image_transform_and_font_are_cached(self):
        manager = AssetManager()
        source = pygame.Surface((4, 4), pygame.SRCALPHA)
        font_object = object()

        with patch("pygame.image.load", return_value=source) as image_load:
            first = manager.image("sprite.png", (8, 8), True)
            second = manager.image("sprite.png", (8, 8), True)
        with patch("pygame.font.Font", return_value=font_object) as font_load:
            first_font = manager.font("font.ttf", 20)
            second_font = manager.font("font.ttf", 20)

        self.assertIs(first, second)
        self.assertEqual(image_load.call_count, 1)
        self.assertIs(first_font, second_font)
        self.assertEqual(font_load.call_count, 1)

    def test_animation_reload_does_not_touch_disk(self):
        ASSETS.clear()
        original_load = pygame.image.load
        with patch("pygame.image.load", wraps=original_load) as image_load:
            sprite = Image(
                "picture/Enemy/%d.png", (50, 50), (0, 0), 1, 3, 1,
            )
            initial_loads = image_load.call_count
            for index in range(30):
                sprite.Record = index % 3 + 1
                sprite.reloade()

        self.assertEqual(initial_loads, 3)
        self.assertEqual(image_load.call_count, initial_loads)

    def test_masks_are_cached_until_the_sprite_frame_changes(self):
        sprite = Image(
            "picture/Enemy/%d.png", (50, 50), (0, 0), 1, 3, 1,
        )
        with patch("pygame.mask.from_surface", wraps=pygame.mask.from_surface) as masks:
            sprite.get_mask()
            sprite.get_mask()
            sprite.Record = 2
            sprite.reloade()
            sprite.get_mask()
        self.assertEqual(masks.call_count, 2)


class SpatialHashTests(unittest.TestCase):
    def test_query_returns_only_nearby_cells(self):
        index = SpatialHash(100)
        index.add("near", (20, 20, 10, 10))
        index.add("far", (400, 400, 10, 10))

        self.assertEqual(index.query((0, 0, 99, 99)), {"near"})


class ArchitectureTests(unittest.TestCase):
    def test_legacy_multiplayer_level_uses_game_world(self):
        self.assertTrue(issubclass(MultiplayerGameLevel, GameWorld))

    def test_game_sessions_are_isolated(self):
        first = GameSession()
        second = GameSession()
        first.enemies_defeated = 12

        self.assertEqual(second.enemies_defeated, 0)


if __name__ == "__main__":
    unittest.main()
