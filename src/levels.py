import pygame
import sys
import const
import image
from sound import *
from core.server import *
from core.client import *
from core.base_level import BaseLevel
from core.main_menu import MainMenu
from core.config_level import ConfigLevel
from core.game_level import GameLevel
from core.multiplayer_level import MultiplayerLevel

# 兼容旧接口，保留空壳或入口（如有需要可补充）