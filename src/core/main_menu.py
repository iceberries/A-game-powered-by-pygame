import pygame
import sys
import const
import image
from sound import *
from core.state import DISPLAY_SETTINGS
from core.base_level import BaseLevel

class MainMenu(BaseLevel):
    def __init__(self):
        super().__init__()
        self.new_font_size = const.title1_size
        self.setup_fonts()
        self.setup_background()
        self.setup_music()

    def setup_fonts(self):
        self.singleplayer_font = image.mFont(const.starttitle, 'font/BoutiqueBitmap9x9_Bold_1.9.TTF', const.title1_size, (230, 100, 150), (const.wsize/2.2, const.hsize*1/5))
        self.multiplayer_font = image.mFont(const.multiplayertitle, 'font/BoutiqueBitmap9x9_Bold_1.9.TTF', const.title1_size, (230, 100, 150), (const.wsize/2.2, const.hsize*2/5))
        self.config_font = image.mFont(const.configtitle, 'font/BoutiqueBitmap9x9_Bold_1.9.TTF', const.title1_size, (230, 100, 150), (const.wsize/2.2, const.hsize*3/5))
        self.exit_font = image.mFont(const.exittitle, 'font/BoutiqueBitmap9x9_Bold_1.9.TTF', const.title1_size, (230, 100, 150), (const.wsize/2.2, const.hsize*4/5))
        self.capoo_font = image.mFont(const.gametitle, 'font/FZVDLGTMCJW-M.TTF', const.title1_size, (230, 100, 150), (const.wsize, 10))
        self.update_font_positions()

    def setup_background(self):
        self.background = image.Image('picture/bg0.jpg', (const.wsize, const.hsize), (0, 0), 0, 1, 0)

    def setup_music(self):
        self.bgm = Musicm('sound/bgm.flac', DISPLAY_SETTINGS.bgm_volume)
        if not self.bgm.Mget_busy():
            self.bgm.Play_music(True)

    def update_font_positions(self):
        new_width, new_height = const.wsize, const.hsize
        self.singleplayer_font.pos = [(new_width - self.singleplayer_font.getrect().width) / 2.2, new_height*1/5]
        self.multiplayer_font.pos = [(new_width - self.multiplayer_font.getrect().width) / 2.2, new_height*2/5]
        self.config_font.pos = [(new_width - self.config_font.getrect().width) / 2.2, new_height*3/5]
        self.exit_font.pos = [(new_width - self.exit_font.getrect().width) / 2.2, new_height*4/5]
        self.capoo_font.pos = [(new_width - self.capoo_font.getrect().width - 10), 10]

    def update_font_sizes(self, new_font_size):
        self.singleplayer_font.updatasize((new_font_size))
        self.multiplayer_font.updatasize((new_font_size))
        self.config_font.updatasize((new_font_size))
        self.exit_font.updatasize((new_font_size))

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.VIDEORESIZE:
                new_width, new_height = self.handle_resize(event, self.background)
                self.new_font_size = int(const.title1_size * (new_height / const.hsize))
                self.background = image.Image('picture/bg0.jpg', (const.wsize, const.hsize), (0, 0), 0, 1, 0)
                self.update_font_positions()
                self.update_font_sizes(self.new_font_size)

            button_handlers = [
                (self.singleplayer_font, "game_state"),
                (self.config_font, "config_state"),
                (self.exit_font, "exit"),
                (self.multiplayer_font, "mul_game_state")
            ]

            for button, target in button_handlers:
                result = button.Button(event, target)
                if result['state_change']:
                    if result['new_state'] == "exit":
                        pygame.quit()
                        sys.exit()
                    else:
                        self.game_state = result['new_state']
                        return self.game_state

        return None

    def draw(self):
        self.DS.fill((255, 255, 255))
        self.background.draw(self.DS)
        self.capoo_font.fdraw(self.DS)
        self.singleplayer_font.fdraw(self.DS)
        self.multiplayer_font.fdraw(self.DS)
        self.exit_font.fdraw(self.DS)
        self.config_font.fdraw(self.DS)
        pygame.display.flip()
        self.clock.tick(const.RENDER_FPS)

    def run(self):
        while self.game_state == "main_menu":
            new_state = self.handle_events()
            if new_state:
                return new_state
            self.draw()
        return self.game_state
