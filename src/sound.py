import pygame
class Soundm(pygame.sprite.Sprite):
    def __init__(self,load,set_volume,):
        self.music = pygame.mixer.Sound(load)
        self.music.set_volume(set_volume)
    
    def Play_sound(self,is_loop):
        if is_loop:
            self.music.play(-1)
        else:
            self.music.play()
 
    def Stop_sound(self):
        self.music.stop()

    def Pause_sound(self):
        self.music.Pause()

    def set_volume(self, volume):
        self.music.set_volume(volume)

class Musicm():
    def __init__(self,load,set_volume,):
        pygame.mixer.music.load(load)
        pygame.mixer.music.set_volume(set_volume)

    def Play_music(self,is_loop):
        if is_loop:
            pygame.mixer.music.play(-1)
        else:
            pygame.mixer.music.play()
 
    def Stop_music(self):
        pygame.mixer.music.stop()

    def Pause_music(self):
        pygame.mixer.music.Pause()

    def Unpause_music(self):
        pygame.mixer.music.unpause()
    
    def Mget_busy(self):
        return pygame.mixer.music.get_busy()
    
    def set_volume(self, volume):
        pygame.mixer.music.set_volume(volume)