import pygame
import os
import json

tile_size = 64
# 假设地图文件为 map.txt，地块类型为0:草地, 1:水, 2:墙
TILE_IMG_PATHS = {
    0: 'picture/grass.png',
    1: 'picture/water.png',
    2: 'picture/wall.png',
}

def load_map(filename):
    """从json文件加载64x64地图，返回二维数组"""
    with open(filename, 'r') as f:
        data = json.load(f)
        return data["map"] if "map" in data else data

def load_tile_images():
    """加载所有地块图片，返回字典"""
    images = {}
    for k, path in TILE_IMG_PATHS.items():
        if os.path.exists(path):
            images[k] = pygame.image.load(path).convert()
        else:
            images[k] = pygame.Surface((tile_size, tile_size))
            images[k].fill((100, 100, 100))
    return images

def draw_map(screen, map_data, tile_images, camera=None):
    """渲染地图，支持相机偏移"""
    for y, row in enumerate(map_data):
        for x, tile in enumerate(row):
            img = tile_images.get(tile)
            draw_x = x * tile_size
            draw_y = y * tile_size
            if camera is not None:
                draw_x -= camera.offset_x
                draw_y -= camera.offset_y
            screen.blit(img, (draw_x, draw_y))
