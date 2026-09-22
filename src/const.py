from core.game_rules import DEFAULT_RULES
from core.state import DISPLAY_SETTINGS, GAME_CONFIG, GAME_SESSION

gametitle = "Capoo Fight"
icontitle = "capoo fight"  # 设置游戏标题
starttitle = "Single Player" #start按钮
exittitle = "Exit"
configtitle = "Config"
multiplayertitle = "Multi Player"
start_server = "Host Game"
start_client = "Join Game"
create_server = "服务端"  # 服务器创建界面标题
join_server = "客户端"

# 设置窗口大小为屏幕分辨率
wsize = DISPLAY_SETTINGS.width
hsize = DISPLAY_SETTINGS.height
capoo_x=wsize/2
capoo_y=750
capoo_width, capoo_hight = map(int, GAME_CONFIG.player_size)
# 玩家体型只有下限，没有上限：
#   体型越大约束越强 —— get_shrink_speed() 的衰减随体型指数增长，靠这一点自然平衡，
#   同时攻击判定区随体型一起变大（“长臂”等能力再在此基础上放大）。
#   衰减到下限即视为“体型归零”，由关卡判定游戏结束。
capoo_min_width, capoo_min_hight = map(int, GAME_CONFIG.player_min_size)
Enemy_x = 100
Enemy_y = 750
Enemy_HP = GAME_CONFIG.enemy_hp
AttackEnemy_HP = GAME_CONFIG.attack_enemy_hp
color=(0, 0, 0)  # 设置背景颜色
player_score = GAME_SESSION.score
player_max_score = GAME_SESSION.max_score  # 记录最高分
enemies_defeated = GAME_SESSION.enemies_defeated  # 累计击杀数
upgrade_kill_step = GAME_CONFIG.upgrade_kill_base
upgrade_earned = GAME_SESSION.upgrade_earned
upgrade_pending = GAME_SESSION.upgrade_pending
upgrade_pending_count = GAME_SESSION.upgrade_pending_count
bgm_vol = DISPLAY_SETTINGS.bgm_volume
sfx_vol = DISPLAY_SETTINGS.sfx_volume
# 渲染帧率与逻辑更新频率分开。游戏规则统一使用秒作为时间单位。
SIMULATION_HZ = GAME_CONFIG.simulation_hz
FIXED_DT = GAME_CONFIG.fixed_dt
RENDER_FPS = GAME_CONFIG.render_fps
MAX_FRAME_TIME = GAME_CONFIG.max_frame_time
TIME_EPSILON = GAME_CONFIG.time_epsilon

# 保留旧名称，供尚未迁移的 UI/网络代码使用。
fps = SIMULATION_HZ
text_size = 40  # 设置全局字体大小
title1_size = 80  # 设置标题字体大小
title2_size = 60  # 设置副标题字体大小
FullSrceen_Switch = DISPLAY_SETTINGS.fullscreen
SWITCH_PATHS = ['picture/component/Switch_Off.png', 'picture/component/Switch_On.png']


def set_resolution(width, height):
    global wsize, hsize
    DISPLAY_SETTINGS.resize(width, height)
    wsize, hsize = DISPLAY_SETTINGS.width, DISPLAY_SETTINGS.height


def set_fullscreen(enabled):
    global FullSrceen_Switch
    DISPLAY_SETTINGS.fullscreen = bool(enabled)
    FullSrceen_Switch = DISPLAY_SETTINGS.fullscreen


def set_bgm_volume(value):
    global bgm_vol
    DISPLAY_SETTINGS.set_bgm_volume(value)
    bgm_vol = DISPLAY_SETTINGS.bgm_volume


def set_sfx_volume(value):
    global sfx_vol
    DISPLAY_SETTINGS.set_sfx_volume(value)
    sfx_vol = DISPLAY_SETTINGS.sfx_volume


def _sync_session_aliases():
    global player_score, player_max_score, enemies_defeated
    global upgrade_earned, upgrade_pending, upgrade_pending_count
    player_score = GAME_SESSION.score
    player_max_score = GAME_SESSION.max_score
    enemies_defeated = GAME_SESSION.enemies_defeated
    upgrade_earned = GAME_SESSION.upgrade_earned
    upgrade_pending_count = GAME_SESSION.upgrade_pending_count
    upgrade_pending = GAME_SESSION.upgrade_pending

def update_score(now_size):
    score = GAME_SESSION.update_score(now_size, DEFAULT_RULES)
    _sync_session_aliases()
    return score

def register_kill():
    """击杀敌人时调用：累计击杀数，并按击杀进度解锁升级三选一。"""
    pending = GAME_SESSION.register_kill(GAME_CONFIG)
    _sync_session_aliases()
    return pending

def check_and_trigger_upgrade():
    """按 5、10、20、40……的指数击杀需求积攒升级三选一。"""
    pending = GAME_SESSION.check_upgrades(GAME_CONFIG)
    _sync_session_aliases()
    return pending

def clamp_capoo_size(width, height):
    """体型只有下限（所有体型变化的统一入口），返回 (宽, 高)。

    不设上限：成长会被随体型变快的衰减自然拉回平衡点。
    """
    return DEFAULT_RULES.clamp_size(width, height)

def score_from_size(now_size):
    """由体型宽度换算分数（与 update_score 同一公式，供 HUD 等处只读使用）。"""
    return DEFAULT_RULES.score_from_size(now_size)

def Reset_Game_Const():
    global capoo_x, capoo_y, capoo_width, capoo_hight, Enemy_x, Enemy_y
    capoo_x=wsize/2
    capoo_y=750
    capoo_width = 100
    capoo_hight = 70
    Enemy_x = 100
    Enemy_y = 750
    GAME_SESSION.reset()
    _sync_session_aliases()
