import pygame
import sys
import const
import image
from sound import *
from core.base_level import BaseLevel

class ConfigLevel(BaseLevel):
    def __init__(self):
        super().__init__()
        self.game_state = "config_state"
        loading_thread = self.start_loading()
        self.setup_ui()
        self.stop_loading(loading_thread)

    def setup_ui(self):
        self.switch_fullscreen = image.Image('picture/component/Switch_Off.png', (20, 20), (const.wsize*1/8, 400), 0, 1, 0)
        self.Setting_bg = image.Image('picture/bg1.jpg', (const.wsize, const.hsize), (0, 0), 0, 1, 0)
        self.config_exit_font = image.mFont(const.exittitle, 'font/BoutiqueBitmap9x9_Bold_1.9.TTF', const.text_size, (230, 100, 150), (const.wsize, 10))
        self.volume_slider = image.Slider(
            handle_path='picture/component/Button.png',
            image_size=(20, 20),
            size=(const.wsize*3/4, 8),
            pos=(const.wsize*1/8, 300),
            Index=0,
            min_val=0,
            max_val=1,
            handle_radius=10
        )
        self.volume_slider.value = pygame.mixer.music.get_volume()

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.VIDEORESIZE:
                new_width, new_height = self.handle_resize(event, self.Setting_bg)
                self.Setting_bg = image.Image('picture/bg1.jpg', (const.wsize, const.hsize), (0, 0), 0, 1, 0)
                self.config_exit_font.pos = [(new_width - self.config_exit_font.getrect().width - 10), 10]

            button_result = self.config_exit_font.Button(event, "main_menu")
            if button_result['state_change']:
                self.game_state = button_result['new_state']
                return True
            
            Flag = const.FullSrceen_Switch
            if Flag != self.switch_fullscreen.Switch_Button(event):
                Flag = const.FullSrceen_Switch
                self.switch_fullscreen.change_path(const.SWITCH_PATHS[Flag])
                self.handle_resize(event, self.Setting_bg)
            self.volume_slider.handle_event(event)
            pygame.mixer.music.set_volume(const.bgm_vol)
        return False

    def draw(self):
        self.DS.fill((255, 255, 255))
        self.Setting_bg.draw(self.DS)
        self.config_exit_font.fdraw(self.DS)
        self.volume_slider.draw(self.DS)
        self.switch_fullscreen.draw(self.DS)
        pygame.display.flip()
        pygame.time.Clock().tick(const.fps)

    def run(self):
        while self.game_state == "config_state":
            if self.handle_events():
                break
            self.draw()
        return self.game_state
