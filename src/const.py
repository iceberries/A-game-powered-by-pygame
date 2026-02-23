import pygame  # 导入pygame库
import image

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
Enemy_x = 100
Enemy_y = 750
Enemy_HP = 1
AttackEnemy_HP = 100
color=(0, 0, 0)  # 设置背景颜色
player_score = 10
player_max_score = 10  # 新增：记录最高分
upgrade_pending = False  # 新增：是否需要弹出升级界面
bgm_vol = 0.5
sfx_vol = 0.5
fps = 60  # 设置帧率
text_size = 40  # 设置全局字体大小
title1_size = 80  # 设置标题字体大小
title2_size = 60  # 设置副标题字体大小
FullSrceen_Switch = False
Srceen_Mode = [pygame.RESIZABLE, pygame.FULLSCREEN]
SWITCH_PATHS = ['picture/component/Switch_Off.png', 'picture/component/Switch_On.png']

def update_score(now_size):
    global player_score
    player_score = int((now_size+100 - capoo_width)/10)
    check_and_trigger_upgrade()  # 新增：每次分数变动后检查升级
    return player_score

def check_and_trigger_upgrade():
    global player_score, player_max_score, upgrade_pending
    if player_score >= player_max_score + 10:
        player_max_score = player_score
        player_score = player_max_score  # 分数重置为最高分
        upgrade_pending = True  # 标记需要弹出升级界面

def Reset_Game_Const():
    global capoo_x, capoo_y, capoo_width, capoo_hight, Enemy_x, Enemy_y,player_score
    capoo_x=wsize/2
    capoo_y=750
    capoo_width = 100
    capoo_hight = 70
    Enemy_x = 100
    Enemy_y = 750
    player_score = 10