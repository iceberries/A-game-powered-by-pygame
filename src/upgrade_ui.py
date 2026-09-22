import sys
import random
import pygame
import pygame.surfarray
import numpy as np
from scipy.ndimage import gaussian_filter
import const
import ability
from core.assets import ASSETS


class UpgradeOption:
    """一张升级卡片所需的数据。"""

    def __init__(self, ability_obj):
        self.ability = ability_obj
        self.title = ability_obj.ability_name
        self.desc = ability_obj.ability_description
        self.quality = ability_obj.ability_quality
        self.color = ability_obj.quality_color
        self.stack_text = ability_obj.get_stack_text()
        self.icon = ability_obj.get_icon()
        self.rect = pygame.Rect(0, 0, 220, 320)
        self.base_y = 0     # 记录的基准y坐标
        self.lift = 0.0     # 当前抬升量（平滑过渡）
        self.target_lift = 0.0

class UpgradeUI:
    """
    升级三选一界面。

    - 从 ability 模块随机抽取 3 个能力作为候选
    - 已满层的能力不再出现，尚未拥有的能力更容易被抽到
    - 鼠标悬停 / ←→ 切换高亮，点击卡片或 Enter/空格/1-2-3 确认
    - 卡片描边颜色由品质决定，缺少图标时自动生成占位图标
    """

    CARD_W = 220
    CARD_H = 320
    CARD_GAP = 60
    MAX_DESC_LINES = 3

    def __init__(self, player=None):
        self.player = player
        self.options = self._build_options()
        self.hover_idx = -1
        self.focus_idx = 0
        self.active = True
        self.result = None
        self.result_index = -1
        self.flash_timer = 0
        self.card_w = self.CARD_W
        self.card_h = self.CARD_H

    # ---------------- 候选能力抽取 ----------------
    def _owned(self, ability_cls):
        ability_cls = ability_cls if isinstance(ability_cls, type) else type(ability_cls)
        for ab in getattr(self.player, 'abilities', []) if self.player else []:
            if type(ab) is ability_cls:
                return ab
        return None

    def _is_maxed(self, ability_cls):
        owned = self._owned(ability_cls)
        return owned is not None and owned.max_stack > 0 and owned.stack >= owned.max_stack

    def _weight(self, ability_obj):
        """实际抽取权重：未拥有的能力更容易被抽到（3 倍）。"""
        owned = self._owned(type(ability_obj))
        return ability_obj.weight * (1.0 if owned is not None else 3.0)

    def _build_options(self):
        """抽取 3 个候选能力；若所有能力都已满层，返回空列表（本次升级作废）。"""
        available = [cls for cls in ability.all_ability_classes() if not self._is_maxed(cls)]
        if not available:
            return []
        pool = [cls() for cls in available]
        picks = []
        while pool and len(picks) < 3:
            weights = [self._weight(obj) for obj in pool]
            chosen = random.choices(pool, weights=weights, k=1)[0]
            pool.remove(chosen)
            picks.append(chosen)
        while len(picks) < 3:
            picks.append(random.choice(available)())  # 可选能力不足3个时允许重复（各卡片独立实例）
        return [UpgradeOption(obj) for obj in picks]

    @property
    def has_options(self):
        """是否还有可升级的能力（全部满层时为 False）。"""
        return len(self.options) > 0

    # ---------------- 文本与布局 ----------------
    @staticmethod
    def wrap_text(font, text, max_width, max_lines=3):
        """按字符宽度自动换行（中文没有空格，不能按空格切分）。"""
        lines, line = [], ''
        raw = str(text)
        for ch in raw:
            if ch == '\n':
                lines.append(line)
                line = ''
                continue
            if line and font.size(line + ch)[0] > max_width:
                lines.append(line)
                line = ''
                if len(lines) >= max_lines:
                    break
            line += ch
        if line and len(lines) < max_lines:
            lines.append(line)
        if len(lines) >= max_lines and len(''.join(lines)) < len(raw.replace('\n', '')):
            lines[-1] = lines[-1][:-1] + '…'
        return lines

    def _scale(self):
        return max(0.6, min(1.0, const.hsize / 900))

    def _build_fonts(self):
        path = "font/BoutiqueBitmap9x9_Bold_1.9.ttf"
        scale = self._scale()
        return {
            'title': ASSETS.font(path, max(14, int(40 * scale))),
            'card_title': ASSETS.font(path, max(12, int(26 * scale))),
            'desc': ASSETS.font(path, max(10, int(19 * scale))),
            'small': ASSETS.font(path, max(9, int(17 * scale))),
            'icon': ASSETS.font(path, max(18, int(44 * scale))),
        }

    def layout(self):
        scale = self._scale()
        self.card_w = int(self.CARD_W * scale)
        self.card_h = int(self.CARD_H * scale)
        gap = int(self.CARD_GAP * scale)
        total_w = self.card_w * 3 + gap * 2
        start_x = (const.wsize - total_w) // 2
        y = const.hsize // 2 - self.card_h // 2 + int(30 * scale)
        for i, opt in enumerate(self.options):
            opt.rect.size = (self.card_w, self.card_h)
            opt.rect.x = start_x + i * (self.card_w + gap)
            opt.base_y = y

    @staticmethod
    def blur_background(screen):
        """截屏并做高斯模糊，作为升级界面的背景。"""
        snap = screen.copy()
        arr = pygame.surfarray.array3d(snap).astype(np.float32)
        arr = np.transpose(arr, (1, 0, 2))
        blurred = gaussian_filter(arr, sigma=(8, 8, 0))
        blurred = np.clip(blurred, 0, 255).astype(np.uint8)
        blurred = np.transpose(blurred, (1, 0, 2))
        blur_surf = pygame.surfarray.make_surface(blurred)
        return pygame.transform.scale(blur_surf, (const.wsize, const.hsize))

    # ---------------- 绘制 ----------------
    def _draw_card(self, screen, opt, focused, fonts):
        rect = opt.rect
        card = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(card, (28, 28, 42, 230), card.get_rect(), border_radius=18)
        # 顶部品质色带
        band_h = int(rect.height * 0.145)
        pygame.draw.rect(card, (*opt.color, 80 if focused else 45),
                         pygame.Rect(0, 0, rect.width, band_h),
                         border_top_left_radius=18, border_top_right_radius=18)
        screen.blit(card, rect.topleft)
        # 描边：聚焦时为品质色加粗
        pygame.draw.rect(screen, opt.color if focused else (110, 110, 135),
                         rect, 6 if focused else 2, border_radius=18)

        # 品质（左）与叠加进度（右）
        tag = fonts['small'].render(opt.quality, True, opt.color)
        screen.blit(tag, (rect.x + 14, rect.y + (band_h - tag.get_height()) // 2))
        if opt.stack_text:
            stack = fonts['small'].render(opt.stack_text, True, (235, 235, 235))
            screen.blit(stack, (rect.right - stack.get_width() - 14, rect.y + (band_h - stack.get_height()) // 2))

        # 图标（缺图时生成占位图标）
        icon_size = int(rect.width * 0.42)
        icon_center = (rect.centerx, rect.y + band_h + int(rect.height * 0.195))
        if opt.icon:
            icon = pygame.transform.smoothscale(opt.icon, (icon_size, icon_size))
            screen.blit(icon, icon.get_rect(center=icon_center))
        else:
            holder = pygame.Surface((icon_size, icon_size), pygame.SRCALPHA)
            pygame.draw.rect(holder, (*opt.color, 60), holder.get_rect(), border_radius=14)
            pygame.draw.rect(holder, (*opt.color, 200), holder.get_rect(), 2, border_radius=14)
            char = fonts['icon'].render(opt.title[0], True, opt.color)
            holder.blit(char, char.get_rect(center=holder.get_rect().center))
            screen.blit(holder, holder.get_rect(center=icon_center))

        # 标题
        title_y = rect.y + band_h + int(rect.height * 0.385)
        title = fonts['card_title'].render(opt.title, True, (255, 255, 255))
        screen.blit(title, (rect.centerx - title.get_width() // 2, title_y))

        # 描述（自动换行）
        desc_y = title_y + title.get_height() + 10
        for line in self.wrap_text(fonts['desc'], opt.desc, rect.width - 28, self.MAX_DESC_LINES):
            surf = fonts['desc'].render(line, True, (205, 205, 215))
            screen.blit(surf, (rect.centerx - surf.get_width() // 2, desc_y))
            desc_y += fonts['desc'].get_height() + 3

    def _draw_owned(self, screen, fonts):
        owned = getattr(self.player, 'abilities', None)
        if not owned:
            return
        text = "已获得：" + "、".join(
            f"{ab.ability_name}×{ab.stack}" if ab.stack > 1 else ab.ability_name for ab in owned)
        surf = fonts['small'].render(text, True, (225, 225, 235))
        screen.blit(surf, (const.wsize // 2 - surf.get_width() // 2, const.hsize - 78))

    def _confirm(self, index):
        if self.result is not None or not (0 <= index < len(self.options)):
            return
        self.result_index = index
        self.result = self.options[index].ability
        self.flash_timer = 8

    def show(self, screen, redraw_callback=None):
        """显示三选一界面并阻塞，返回玩家选中的 Ability 对象（对象包含全部效果与层数）。

        若当前没有任何可升级的能力（全部满层），直接返回 None。
        """
        if not self.has_options:
            return None
        screen = pygame.display.get_surface() or screen
        if redraw_callback:
            redraw_callback()
        blur_surf = self.blur_background(screen)
        overlay = pygame.Surface((const.wsize, const.hsize), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 130))
        clock = pygame.time.Clock()
        self.active = True
        self.result = None
        self.result_index = -1
        self.focus_idx = 0
        self.hover_idx = -1
        self.layout()
        fonts = self._build_fonts()
        while self.active:
            mouse_pos = pygame.mouse.get_pos()
            self.hover_idx = -1
            for i, opt in enumerate(self.options):
                if opt.rect.collidepoint(mouse_pos):
                    self.hover_idx = i
            if self.hover_idx >= 0:
                self.focus_idx = self.hover_idx
            # 悬停/选中卡片平滑抬升
            for i, opt in enumerate(self.options):
                opt.target_lift = 12.0 if i == self.focus_idx else 0.0
                opt.lift += (opt.target_lift - opt.lift) * 0.3
                opt.rect.y = int(opt.base_y - opt.lift)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.VIDEORESIZE:
                    const.set_resolution(event.w, event.h)
                    screen = pygame.display.set_mode((const.wsize, const.hsize), pygame.RESIZABLE)
                    if redraw_callback:
                        redraw_callback()  # 先让主游戏在新窗口上重绘一帧
                    blur_surf = self.blur_background(screen)
                    overlay = pygame.Surface((const.wsize, const.hsize), pygame.SRCALPHA)
                    overlay.fill((0, 0, 0, 130))
                    self.layout()
                    fonts = self._build_fonts()
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_LEFT, pygame.K_a):
                        self.focus_idx = (self.focus_idx - 1) % len(self.options)
                    elif event.key in (pygame.K_RIGHT, pygame.K_d):
                        self.focus_idx = (self.focus_idx + 1) % len(self.options)
                    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                        self._confirm(self.focus_idx)
                    elif event.key in (pygame.K_1, pygame.K_KP1):
                        self._confirm(0)
                    elif event.key in (pygame.K_2, pygame.K_KP2):
                        self._confirm(1)
                    elif event.key in (pygame.K_3, pygame.K_KP3):
                        self._confirm(2)
                    # ESC 不生效：升级必须做出选择
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    for i, opt in enumerate(self.options):
                        if opt.rect.collidepoint(event.pos):
                            self._confirm(i)

            # 高斯模糊背景 + 半透明遮罩
            screen.blit(blur_surf, (0, 0))
            screen.blit(overlay, (0, 0))
            # 标题
            title = fonts['title'].render("选择一个能力升级", True, (255, 220, 90))
            screen.blit(title, (const.wsize // 2 - title.get_width() // 2, max(24, const.hsize // 10)))
            # 三张卡片
            for i, opt in enumerate(self.options):
                self._draw_card(screen, opt, i == self.focus_idx, fonts)
            self._draw_owned(screen, fonts)
            hint = fonts['small'].render("← → 选择    Enter / 1 2 3 确认", True, (200, 200, 210))
            screen.blit(hint, (const.wsize // 2 - hint.get_width() // 2, const.hsize - 44))

            if self.result is not None:
                # 选中反馈：短暂高亮后关闭
                pygame.draw.rect(screen, (255, 255, 255),
                                 self.options[self.result_index].rect, 8, border_radius=18)
                self.flash_timer -= 1
                if self.flash_timer <= 0:
                    self.active = False
            pygame.display.flip()
            clock.tick(60)
        return self.result
