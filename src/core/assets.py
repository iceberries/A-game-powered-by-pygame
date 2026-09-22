"""集中管理 Pygame 资源，保证游戏更新阶段不访问磁盘。"""

from pathlib import Path
import threading

import pygame


class AssetManager:
    """线程安全的图片、变换结果和字体缓存。"""

    def __init__(self):
        self._images = {}
        self._transformed = {}
        self._fonts = {}
        self._texts = {}
        self._lock = threading.RLock()

    @staticmethod
    def _path_key(path):
        return str(Path(path).resolve()).casefold()

    @staticmethod
    def _size_key(size):
        if size is None:
            return None
        return max(1, int(size[0])), max(1, int(size[1]))

    def image(self, path, size=None, flip_x=False):
        """返回 `(path, size, flip_x)` 对应的共享 Surface。"""
        path_key = self._path_key(path)
        size_key = self._size_key(size)
        transformed_key = (path_key, size_key, bool(flip_x))
        with self._lock:
            cached = self._transformed.get(transformed_key)
            if cached is not None:
                return cached

            source = self._images.get(path_key)
            if source is None:
                source = pygame.image.load(path)
                try:
                    source = source.convert_alpha()
                except pygame.error:
                    # 无显示表面的测试/服务端环境仍可预加载资源。
                    pass
                self._images[path_key] = source

            result = source
            if size_key is not None and result.get_size() != size_key:
                result = pygame.transform.scale(result, size_key)
            if flip_x:
                result = pygame.transform.flip(result, True, False)
            self._transformed[transformed_key] = result
            return result

    def animation(self, paths, size=None, flip_x=False):
        """一次预热整组动画帧，之后仅返回帧引用。"""
        return tuple(self.image(path, size, flip_x) for path in paths)

    def font(self, path, size):
        key = (self._path_key(path), int(size))
        with self._lock:
            cached = self._fonts.get(key)
            if cached is None:
                cached = pygame.font.Font(path, int(size))
                self._fonts[key] = cached
            return cached

    def system_font(self, name, size):
        key = (f"system:{name.casefold()}", int(size))
        with self._lock:
            cached = self._fonts.get(key)
            if cached is None:
                cached = pygame.font.SysFont(name, int(size))
                self._fonts[key] = cached
            return cached

    def text(self, text, path, size, color, antialias=True):
        color_key = None if color is None else tuple(color)
        key = (
            str(text), self._path_key(path), int(size), color_key,
            bool(antialias),
        )
        with self._lock:
            cached = self._texts.get(key)
            if cached is None:
                cached = self.font(path, size).render(
                    str(text), antialias, color,
                )
                self._texts[key] = cached
            return cached

    def clear(self):
        """显示设备重建且像素格式变化时可显式清空缓存。"""
        with self._lock:
            self._images.clear()
            self._transformed.clear()
            self._fonts.clear()
            self._texts.clear()


ASSETS = AssetManager()
