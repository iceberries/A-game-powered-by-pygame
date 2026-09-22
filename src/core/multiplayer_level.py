import pygame
import sys
import const
import image
from core.server import ServerUI
from core.client import ClientUI
from core.base_level import BaseLevel

class MultiplayerLevel(BaseLevel):
    def __init__(self):
        super().__init__()
        self.game_state = "mul_game_state"
        loading_thread = self.start_loading()
        self.setup_ui()
        self.stop_loading(loading_thread)
        self.ServerUI = ServerUI
        self.ClientUI = ClientUI

    def setup_ui(self):
        self.mul_game_bg = image.Image('picture/bg3.jpg', (const.wsize, const.hsize), (0, 0), 0, 1, 0)
        self.mul_exit_font = image.mFont(const.exittitle, 'font/BoutiqueBitmap9x9_Bold_1.9.TTF', const.text_size, (230, 200, 150), (const.wsize, 10))
        self.mul_server_font = image.mFont(const.start_server, 'font/BoutiqueBitmap9x9_Bold_1.9.TTF', const.text_size, (230, 100, 150), (const.wsize/2+100, const.hsize*2/5))
        self.mul_client_font = image.mFont(const.start_client, 'font/BoutiqueBitmap9x9_Bold_1.9.TTF', const.text_size, (230, 100, 150), (const.wsize/2+100, const.hsize*3/5))

    def update_ui(self,event):
        new_width, new_height = self.handle_resize(event, self.mul_game_bg)
        self.mul_game_bg = image.Image('picture/bg3.jpg', (const.wsize, const.hsize), (0, 0), 0, 1, 0)
        self.mul_exit_font.pos = [(new_width - self.mul_exit_font.getrect().width - 10), 10]
        self.mul_server_font.pos = [const.wsize/2.2, new_height*2/5]
        self.mul_client_font.pos = [const.wsize/2.2, new_height*3/5]

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.VIDEORESIZE:
                self.update_ui(event)

            button_result = self.mul_exit_font.Button(event, "main_menu")
            if button_result['state_change']:
                self.game_state = button_result['new_state']
                return True

            button_result = self.mul_server_font.Button(event, "create_server")
            if button_result['state_change']:
                self.run_server()
                self.update_ui(event)
                return False

            button_result = self.mul_client_font.Button(event, "join_server")
            if button_result['state_change']:
                self.run_client()
                self.update_ui(event)
                return False

        return False

    def run_server(self):
        server_ui = self.ServerUI(self.DS)
        server_ui.run()

    def run_client(self):
        client_ui = self.ClientUI(self.DS)
        client_ui.run()

    def draw(self):
        self.DS.fill((255, 255, 255))
        self.mul_game_bg.draw(self.DS)
        self.mul_exit_font.fdraw(self.DS)
        self.mul_server_font.fdraw(self.DS)
        self.mul_client_font.fdraw(self.DS)
        pygame.display.flip()
        self.clock.tick(const.RENDER_FPS)

    def run(self):
        while self.game_state == "mul_game_state":
            if self.handle_events():
                break
            self.draw()
        return self.game_state
