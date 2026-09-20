import pygame  # 导入pygame库

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
wsize = 1536
hsize = 864
capoo_x=wsize/2
capoo_y=750
capoo_width = 100
capoo_hight = 70
# 玩家体型只有下限，没有上限：
#   体型越大约束越强 —— get_shrink_speed() 的衰减随体型指数增长，靠这一点自然平衡，
#   同时攻击判定区随体型一起变大（“长臂”等能力再在此基础上放大）。
#   衰减到下限即视为“体型归零”，由关卡判定游戏结束。
capoo_min_width = 40
capoo_min_hight = 28
Enemy_x = 100
Enemy_y = 750
Enemy_HP = 1
AttackEnemy_HP = 100
color=(0, 0, 0)  # 设置背景颜色
player_score = 10
player_max_score = 10  # 记录最高分
enemies_defeated = 0  # 累计击杀数
upgrade_kill_step = 5  # 每击杀多少敌人解锁一次升级三选一
upgrade_earned = 0  # 已按击杀进度发放的升级次数
upgrade_pending = False  # 是否需要弹出升级界面
upgrade_pending_count = 0  # 待处理的升级次数（可能一次积攒多次）
bgm_vol = 0.5
sfx_vol = 0.5
# 渲染帧率与逻辑更新频率分开。游戏规则统一使用秒作为时间单位。
SIMULATION_HZ = 60
FIXED_DT = 1.0 / SIMULATION_HZ
RENDER_FPS = 120
MAX_FRAME_TIME = 0.1
TIME_EPSILON = 1e-9

# 保留旧名称，供尚未迁移的 UI/网络代码使用。
fps = SIMULATION_HZ
text_size = 40  # 设置全局字体大小
title1_size = 80  # 设置标题字体大小
title2_size = 60  # 设置副标题字体大小
FullSrceen_Switch = False
Srceen_Mode = [pygame.RESIZABLE, pygame.FULLSCREEN]
SWITCH_PATHS = ['picture/component/Switch_Off.png', 'picture/component/Switch_On.png']

def update_score(now_size):
    global player_score, player_max_score
    player_score = score_from_size(now_size)
    player_max_score = max(player_max_score, player_score)
    check_and_trigger_upgrade()  # 每次分数变动后检查升级
    return player_score

def register_kill():
    """击杀敌人时调用：累计击杀数，并按击杀进度解锁升级三选一。"""
    global enemies_defeated
    enemies_defeated += 1
    return check_and_trigger_upgrade()

def check_and_trigger_upgrade():
    """每击杀 upgrade_kill_step 个敌人，就积攒一次升级三选一。"""
    global upgrade_earned, upgrade_pending, upgrade_pending_count
    earned = enemies_defeated // upgrade_kill_step
    if earned > upgrade_earned:
        upgrade_pending_count += earned - upgrade_earned
        upgrade_earned = earned
    upgrade_pending = upgrade_pending_count > 0
    return upgrade_pending_count

def clamp_capoo_size(width, height):
    """体型只有下限（所有体型变化的统一入口），返回 (宽, 高)。

    不设上限：成长会被随体型变快的衰减自然拉回平衡点。
    """
    return (max(capoo_min_width, width), max(capoo_min_hight, height))

def score_from_size(now_size):
    """由体型宽度换算分数（与 update_score 同一公式，供 HUD 等处只读使用）。"""
    return int((now_size + 100 - capoo_width) / 10)

def Reset_Game_Const():
    global capoo_x, capoo_y, capoo_width, capoo_hight, Enemy_x, Enemy_y
    global player_score, player_max_score, enemies_defeated, upgrade_earned
    global upgrade_pending, upgrade_pending_count
    capoo_x=wsize/2
    capoo_y=750
    capoo_width = 100
    capoo_hight = 70
    Enemy_x = 100
    Enemy_y = 750
    player_score = 10
    player_max_score = 10
    enemies_defeated = 0
    upgrade_earned = 0
    upgrade_pending = False
    upgrade_pending_count = 0
