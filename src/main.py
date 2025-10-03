import pygame
import sys
import const
from levels import MainMenu, ConfigLevel, GameLevel, MultiplayerLevel

def main():
    pygame.init()
    pygame.mixer.init()
    pygame.display.set_caption("Capoo")
    pygame.display.set_mode((const.wsize, const.hsize), const.Srceen_Mode[const.FullSrceen_Switch], 32)
    pygame.display.set_icon(pygame.image.load('picture/Capoo/1.PNG'))

    game_state = "main_menu"
    while True:
        if game_state == "main_menu":
            menu = MainMenu()
            game_state = menu.run()
        elif game_state == "config_state":
            config = ConfigLevel()
            game_state = config.run()
        elif game_state == "mul_game_state":
            multiplayer = MultiplayerLevel()
            game_state = multiplayer.run()
        elif game_state == "game_state":
            game = GameLevel()
            game_state = game.run()
        elif game_state == "exit":
            pygame.quit()
            sys.exit()
if __name__ == "__main__":
    main()