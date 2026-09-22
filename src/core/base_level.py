import pygame
import sys
import const
import image
from core.state import DISPLAY_SETTINGS

class BaseLevel:
    def __init__(self):
        self.DS = pygame.display.get_surface()
        self.game_state = "main_menu"
        self.is_loading = False
        # 每个界面持有一个长期存活的时钟，不要在每帧重新创建 Clock。
        self.clock = pygame.time.Clock()

    def loading_pic(self):
        loading_screen = image.Image('picture/loading/loading1.png', (const.wsize, const.hsize), (0, 0), 0, 1, 0)
        self.DS.fill((255, 255, 255))
        loading_screen.draw(self.DS)
        pygame.display.flip()

    def start_loading(self):
        self.is_loading = True
        # Pygame 的 Surface/显示 API 只允许由主线程访问。
        self.loading_pic()
        return None

    def stop_loading(self, loading_thread):
        self.is_loading = False

    def handle_resize(self, event, background):
        display_info = pygame.display.Info()
        if DISPLAY_SETTINGS.fullscreen:
            new_size = (display_info.current_w, display_info.current_h)
        else:
            if hasattr(event, 'size'):
                new_size = event.size
            else:
                current_surface = pygame.display.get_surface()
                new_size = current_surface.get_size()
        mode = pygame.FULLSCREEN if DISPLAY_SETTINGS.fullscreen else pygame.RESIZABLE
        self.DS = pygame.display.set_mode(new_size, mode, 32)
        background.updatasize(new_size)
        const.set_resolution(*new_size)
        return const.wsize, const.hsize
