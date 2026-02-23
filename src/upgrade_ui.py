import pygame
import const
import pygame.surfarray
import numpy as np
from scipy.ndimage import gaussian_filter
import random
import importlib
import ability

class UpgradeOption:
    def __init__(self, ability_obj):
        self.ability = ability_obj
        self.title = ability_obj.ability_name
        self.desc = ability_obj.ability_description
        icon_path = getattr(ability_obj, 'ability_image', None)
        self.icon = pygame.image.load(icon_path).convert_alpha() if icon_path else None
        self.rect = pygame.Rect(0, 0, 220, 320)
        self.base_y = 0  # 记录原始y坐标

class UpgradeUI:
    """
    升级界面：横向三选一rect，含标题、描述、图标，鼠标悬停高亮描边和抬升。
    """
    def __init__(self):
        # 动态收集ability.py中所有Ability子类
        ability_classes = [cls for name, cls in ability.__dict__.items()
                          if isinstance(cls, type) and issubclass(cls, ability.Ability) and cls is not ability.Ability]
        # 随机抽取3个不同能力
        selected = random.sample(ability_classes, 3) if len(ability_classes) >= 3 else ability_classes * 3
        self.options = [
            UpgradeOption(cls()) for cls in selected
        ]
        self.selected = 0
        self.active = True

    def draw_text_in_rect(self, surface, text, font, color, rect, top_offset):
        # 自动换行文本绘制
        words = text.split(' ')
        lines = []
        line = ''
        for word in words:
            test_line = line + word + ' '
            if font.size(test_line)[0] > rect.width - 20:
                lines.append(line)
                line = word + ' '
            else:
                line = test_line
        if line:
            lines.append(line)
        y = rect.y + top_offset
        for l in lines:
            txt_surf = font.render(l.strip(), True, color)
            surface.blit(txt_surf, (rect.centerx - txt_surf.get_width()//2, y))
            y += font.get_height() + 2

    def show(self, screen, redraw_callback=None):
        # 截屏并高斯模糊
        def get_blur_bg():
            snap = screen.copy()
            arr = pygame.surfarray.array3d(snap).astype(np.float32)
            arr = np.transpose(arr, (1, 0, 2))
            blurred = gaussian_filter(arr, sigma=(8, 8, 0))
            blurred = np.clip(blurred, 0, 255).astype(np.uint8)
            blurred = np.transpose(blurred, (1, 0, 2))
            blur_surf = pygame.surfarray.make_surface(blurred)
            return pygame.transform.scale(blur_surf, (const.wsize, const.hsize))
        if redraw_callback:
            redraw_callback()
        blur_surf = get_blur_bg()
        overlay = pygame.Surface((const.wsize, const.hsize), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 120))
        clock = pygame.time.Clock()
        font_title = pygame.font.Font("font/BoutiqueBitmap9x9_Bold_1.9.ttf", 36)
        font_desc = pygame.font.Font("font/BoutiqueBitmap9x9_Bold_1.9.ttf", 22)
        def layout_rects():
            total_w = 3 * 220 + 2 * 60
            start_x = (const.wsize - total_w) // 2
            y = const.hsize // 2 - 160
            for i, opt in enumerate(self.options):
                opt.rect.x = start_x + i * (220 + 60)
                opt.rect.y = y
                opt.base_y = y
        layout_rects()
        while self.active:
            mouse_pos = pygame.mouse.get_pos()
            hover_idx = -1
            for i, opt in enumerate(self.options):
                if opt.rect.collidepoint(mouse_pos):
                    hover_idx = i
            for i, opt in enumerate(self.options):
                if i == hover_idx:
                    opt.rect.y = opt.base_y - 5
                else:
                    opt.rect.y = opt.base_y
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    exit()
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.active = False
                        return None
                if event.type == pygame.VIDEORESIZE:
                    const.wsize, const.hsize = event.w, event.h
                    screen = pygame.display.set_mode((const.wsize, const.hsize), pygame.RESIZABLE)
                    if redraw_callback:
                        redraw_callback()  # 先让主游戏重绘一帧
                    blur_surf = get_blur_bg()
                    overlay = pygame.Surface((const.wsize, const.hsize), pygame.SRCALPHA)
                    overlay.fill((0, 0, 0, 120))
                    layout_rects()
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    for i, opt in enumerate(self.options):
                        if opt.rect.collidepoint(mouse_pos):
                            self.active = False
                            return opt.title
            # 绘制高斯模糊背景+半透明遮罩
            screen.blit(blur_surf, (0, 0))
            screen.blit(overlay, (0, 0))
            # 标题
            title = font_title.render("选择一个能力升级", True, (255, 255, 0))
            screen.blit(title, (const.wsize//2 - title.get_width()//2, 100))
            # 绘制三个rect
            for i, opt in enumerate(self.options):
                # rect底色
                pygame.draw.rect(screen, (60, 60, 80, 220), opt.rect, border_radius=18)
                # 高亮描边
                if i == hover_idx:
                    pygame.draw.rect(screen, (0, 255, 0), opt.rect, 6, border_radius=18)
                else:
                    pygame.draw.rect(screen, (180, 180, 180), opt.rect, 2, border_radius=18)
                # 图标
                if opt.icon:
                    icon_rect = opt.icon.get_rect(center=(opt.rect.centerx, opt.rect.y + 60))
                    screen.blit(opt.icon, icon_rect)
                # 标题自动换行
                self.draw_text_in_rect(screen, opt.title, font_title, (255,255,255), opt.rect, 120)
                # 描述自动换行
                self.draw_text_in_rect(screen, opt.desc, font_desc, (200,200,200), opt.rect, 180)
            pygame.display.flip()
            clock.tick(30)
        return None
