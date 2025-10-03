import pygame
import sys
import const
import image
import threading

class BaseLevel:
    def __init__(self):
        self.DS = pygame.display.get_surface()
        self.game_state = "main_menu"
        self.is_loading = False

    def loading_pic(self):
        loading_screen = image.Image('picture/loading/loading1.png', (const.wsize, const.hsize), (0, 0), 0, 1, 0)
        while self.is_loading:
            self.DS.fill((255, 255, 255))
            loading_screen.draw(self.DS)
            pygame.display.flip()
            pygame.time.Clock().tick(60)

    def start_loading(self):
        self.is_loading = True
        loading_thread = threading.Thread(target=self.loading_pic)
        loading_thread.start()
        return loading_thread

    def stop_loading(self, loading_thread):
        self.is_loading = False
        loading_thread.join()

    def handle_resize(self, event, background):
        display_info = pygame.display.Info()
        if const.FullSrceen_Switch:
            new_size = (display_info.current_w, display_info.current_h)
        else:
            if hasattr(event, 'size'):
                new_size = event.size
            else:
                current_surface = pygame.display.get_surface()
                new_size = current_surface.get_size()
        self.DS = pygame.display.set_mode(new_size, const.Srceen_Mode[const.FullSrceen_Switch], 32)
        background.updatasize(new_size)
        const.wsize = new_size[0]
        const.hsize = new_size[1]
        return const.wsize, const.hsize
