import pygame

class Camera:
    def __init__(self, screen_width, screen_height):
        """
        初始化屏幕的宽度和高度，并设置初始偏移量。
    
        Args:
            screen_width (int): 屏幕的宽度。
            screen_height (int): 屏幕的高度。
        """
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.offset_x = 0
        self.offset_y = 0

    def update(self, player_rect):
        # 让玩家始终居中
        self.offset_x = player_rect.centerx - self.screen_width // 2
        self.offset_y = player_rect.centery - self.screen_height // 2

    def apply(self, rect):
        # 将世界坐标rect转换为屏幕坐标rect
        return rect.move(-self.offset_x, -self.offset_y)

    def apply_pos(self, pos):
        # 直接转换单个坐标点
        return (pos[0] - self.offset_x, pos[1] - self.offset_y)
