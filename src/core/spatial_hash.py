"""轻量空间哈希：以常数数量的网格查询附近实体，避免全量两两遍历。"""

import math


class SpatialHash:
    def __init__(self, cell_size):
        if cell_size <= 0:
            raise ValueError("cell_size must be positive")
        self.cell_size = float(cell_size)
        self._cells = {}

    def add(self, key, bounds):
        x, y, width, height = bounds
        left = math.floor(x / self.cell_size)
        top = math.floor(y / self.cell_size)
        right = math.floor((x + max(0, width)) / self.cell_size)
        bottom = math.floor((y + max(0, height)) / self.cell_size)
        for cell_x in range(left, right + 1):
            for cell_y in range(top, bottom + 1):
                self._cells.setdefault((cell_x, cell_y), set()).add(key)

    def query(self, bounds):
        x, y, width, height = bounds
        left = math.floor(x / self.cell_size)
        top = math.floor(y / self.cell_size)
        right = math.floor((x + max(0, width)) / self.cell_size)
        bottom = math.floor((y + max(0, height)) / self.cell_size)
        results = set()
        for cell_x in range(left, right + 1):
            for cell_y in range(top, bottom + 1):
                results.update(self._cells.get((cell_x, cell_y), ()))
        return results
