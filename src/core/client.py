import pygame
import socket
import threading
import re
import json
import const
from image import Image, mFont, InputBox
import sys
from core.mul_game_level import MultiplayerGameLevel
# ClientUIImage类 - 处理图片界面
class ClientUIImage(Image):
    def __init__(self):
        # 使用空路径初始化父类
        super().__init__("", (const.wsize, const.hsize), (0, 0), 0)
        
        # 创建消息输入框 - 使用列表而不是元组作为位置
        self.input_box = InputBox(
            title="",
            font_path="font/BoutiqueBitmap9x9_Bold_1.9.TTF",
            size=18,
            color=(0, 0, 0),
            pos=[50, const.hsize-130],
            box_width=const.wsize - 200,
            box_height=40,
            inactive_color=(255, 255, 255),
            active_color=(240, 240, 255),
            border_color=(0, 0, 0),
            max_length=100
        )
        
        # 创建IP输入框 - 使用列表而不是元组作为位置
        self.ip_box = InputBox(
            title="127.0.0.1:5555",
            font_path="font/BoutiqueBitmap9x9_Bold_1.9.TTF",
            size=18,
            color=(0, 0, 0),
            pos=[50, 200],
            box_width=const.wsize - 100,
            box_height=40,
            inactive_color=(255, 255, 255),
            active_color=(240, 240, 255),
            border_color=(0, 0, 0),
            max_length=21
        )
    
    def draw(self, screen):
        # 绘制输入框
        self.input_box.draw(screen)
        self.ip_box.draw(screen)
    
    def handle_input(self, event):
        # 处理消息输入框
        result = {"action": None, "data": None}
        
        # 处理消息输入框
        input_result = self.input_box.handle_input(event)
        if input_result["action"] is not None:
            result = input_result
        
        # 如果消息输入框没有动作，尝试处理IP输入框
        if result["action"] is None:
            ip_result = self.ip_box.handle_input(event)
            if ip_result["action"] == "send":
                # 如果在IP框按回车，转为连接动作
                result["action"] = "connect"
                result["data"] = self.ip_box.get_text()
        
        return result

# ClientUIText类 - 处理文本界面和按钮
class ClientUIText(mFont):
    def __init__(self):
        # 使用空标题初始化父类
        super().__init__("", "font/BoutiqueBitmap9x9_Bold_1.9.TTF", const.text_size, (0, 0, 0), (0, 0))
        self.texts = {}
        self.buttons = {}
        self.messages = []  # 存储聊天消息
        self.setup_texts()
        self.setup_buttons()
    
    def setup_texts(self):
        # 设置各种文本 - 使用列表而不是元组作为位置
        self.texts["title"] = mFont(const.join_server, "font/BoutiqueBitmap9x9_Bold_1.9.TTF", const.title1_size, (0, 0, 0), [const.wsize//2+50, 100])
        self.texts["status"] = mFont("未连接", "font/BoutiqueBitmap9x9_Bold_1.9.TTF", const.text_size, (0, 0, 0), [120, 150])
    
    def setup_buttons(self):
        # 设置各种按钮 - 使用列表而不是元组作为位置
        self.buttons["connect"] = mFont("连接服务器", "font/BoutiqueBitmap9x9_Bold_1.9.TTF", const.text_size, (100, 100, 255), [const.wsize//2+50, 245])
        self.buttons["exit"] = mFont("返回", "font/BoutiqueBitmap9x9_Bold_1.9.TTF", const.text_size, (100, 100, 255), [const.wsize//2, const.hsize-80])
        self.buttons["send"] = mFont("发送", "font/BoutiqueBitmap9x9_Bold_1.9.TTF", const.text_size, (100, 100, 255), [const.wsize - 60, const.hsize-130])
    
    def update_status(self, status):
        self.texts["status"] = mFont(f"状态: {status}", "font/BoutiqueBitmap9x9_Bold_1.9.TTF", const.text_size, (0, 0, 0), [120, 150])
    
    def add_message(self, message, is_system=False):
        prefix = "[系统] " if is_system else ""
        self.messages.append(f"{prefix}{message}")
        # 保持消息数量在合理范围内
        if len(self.messages) > 10:
            self.messages.pop(0)
    
    def handle_buttons(self, event):
        # 处理按钮点击事件
        result = {"action": None, "data": None}
        
        # 处理连接按钮
        connect_result = self.buttons["connect"].Button(event, "connect")
        if connect_result["state_change"]:
            result["action"] = "connect"
        
        # 处理退出按钮
        exit_result = self.buttons["exit"].Button(event, "exit")
        if exit_result["state_change"]:
            result["action"] = "exit"
        
        # 处理发送按钮
        send_result = self.buttons["send"].Button(event, "send")
        if send_result["state_change"]:
            result["action"] = "send"
        
        return result
    
    def fdraw(self, screen):
        # 绘制所有文本元素
        for text_name,text in self.texts.items():
            text.fdraw(screen)
        
        # 绘制所有按钮
        for button_name,button in self.buttons.items():
            button.fdraw(screen)
        
        # 绘制聊天区域
        chat_rect = pygame.Rect(50, 300, const.wsize - 100, const.hsize-450)
        pygame.draw.rect(screen, (255, 255, 255), chat_rect)
        pygame.draw.rect(screen, (0, 0, 0), chat_rect, 2)
        
        # 绘制聊天消息
        font = pygame.font.Font("font/BoutiqueBitmap9x9_Bold_1.9.TTF", 18)
        for i, message in enumerate(self.messages):
            text_surface = font.render(message, True, (0, 0, 0))
            screen.blit(text_surface, (chat_rect.x + 10, chat_rect.y + 10 + i * 20))

# ClientUI类 - 主类
class ClientUI:
    def __init__(self, screen):
        """初始化客户端UI"""
        self.screen = screen
        self.running = True
        self.client = None
        self.local_ip = "127.0.0.1"
        self.local_port = 5555
        self.client_status = "未连接"
        
        # 创建图片UI和文本UI实例
        self.image_ui = ClientUIImage()
        self.text_ui = ClientUIText()
        self.game_exit_font = mFont(const.exittitle, 'font/BoutiqueBitmap9x9_Bold_1.9.TTF', const.text_size, (230, 100, 150), (const.wsize, 10))
        self.background = Image('picture/bg0.jpg', (const.wsize, const.hsize), (0, 0), 0, 1, 0)
        self.grass_img = pygame.image.load('picture/grass.png').convert()
        
        # 设置背景颜色
        self.bg_color = (240, 240, 240)
        
        # 添加一条欢迎消息
        self.text_ui.add_message("欢迎使用游戏客户端！", True)
        
        # 游戏相关属性
        self.in_game = False
        self.game_level = None
        self.player_name = None
        self.game_state = {}
        self.keys_pressed = {}
    def handle_game_input(self):
        """联机客户端输入处理，发送持续移动/停止指令到服务器"""
        if not self.in_game or not self.client:
            return
        keys = pygame.key.get_pressed()
        direction = None
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            direction = 'left'
        elif keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            direction = 'right'
        elif keys[pygame.K_UP] or keys[pygame.K_w]:
            direction = 'up'
        elif keys[pygame.K_DOWN] or keys[pygame.K_s]:
            direction = 'down'
        # 只在方向变化时发包
        if direction != getattr(self, '_last_move_dir', None):
            if direction:
                try:
                    msg = {"type": "action", "action": {"type": "move", "direction": direction}}
                    self.client.send(json.dumps(msg).encode('utf-8'))
                except Exception as e:
                    self.text_ui.add_message(f"发送移动指令失败: {str(e)}", True)
            else:
                try:
                    msg = {"type": "action", "action": {"type": "stop_move"}}
                    self.client.send(json.dumps(msg).encode('utf-8'))
                except Exception as e:
                    self.text_ui.add_message(f"发送停止移动失败: {str(e)}", True)
            self._last_move_dir = direction
    
    def validate_ip(self, ip_string):
        """
        验证IP地址和端口格式
        格式可以为：xxx.xxx.xxx.xxx:xxxx 或 xxx.xxx.xxx.xxx
        返回：(ip, port) 或 None（如果格式不正确）
        """
        # 检查是否包含端口
        if ':' in ip_string:
            # 使用正则表达式匹配IP地址和端口
            pattern = r'^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d{1,5})$'
            match = re.match(pattern, ip_string)
            
            if not match:
                self.image_ui.ip_box.set_text("IP格式错误")
                return None
            
            # 提取IP和端口
            ip = match.group(1)
            port = int(match.group(2))
        else:
            # 只有IP地址的情况，使用默认端口
            pattern = r'^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})$'
            match = re.match(pattern, ip_string)
            
            if not match:
                self.image_ui.ip_box.set_text("IP格式错误")
                return None
            
            ip = match.group(1)
            port = 5555  # 默认端口
        
        # 验证IP地址的每个部分是否在0-255范围内
        ip_parts = ip.split('.')
        for part in ip_parts:
            if not 0 <= int(part) <= 255:
                self.image_ui.ip_box.set_text("IP范围错误")
                return None
        
        # 验证端口是否在有效范围内
        if not 1 <= port <= 65535:
            self.image_ui.ip_box.set_text("端口范围错误")
            return None
        
        return (ip, port)
    
    def draw(self):
        """绘制UI界面"""
        # 绘制背景
        self.screen.fill(self.bg_color)
        
        # 绘制图片UI和文本UI
        self.image_ui.draw(self.screen)
        self.text_ui.fdraw(self.screen)
        
        # 更新显示
        pygame.display.flip()

    def handle_event(self, event):
        """处理事件"""
        # 处理按钮事件
        button_result = self.text_ui.handle_buttons(event)
        
        # 处理输入框事件
        input_result = self.image_ui.handle_input(event)
        
        # 处理按钮事件
        if button_result["action"] == "connect":
            # 获取IP输入框的内容
            ip_text = self.image_ui.ip_box.get_text()
            # 验证IP地址和端口
            ip_port = self.validate_ip(ip_text)
            if ip_port:
                self.local_ip, self.local_port = ip_port
                self.connect_to_server()
        elif button_result["action"] == "exit":
            self.running = False
        elif button_result["action"] == "send":
            message = self.image_ui.input_box.get_text()
            if message:
                self.send_message(message)
                self.image_ui.input_box.clear()
        
        # 处理输入框事件
        if input_result["action"] == "send":
            message = self.image_ui.input_box.get_text()
            if message:
                self.send_message(message)
                self.image_ui.input_box.clear()
        elif input_result["action"] == "connect":
            # 获取IP输入框的内容
            ip_text = self.image_ui.ip_box.get_text()
            # 验证IP地址和端口
            ip_port = self.validate_ip(ip_text)
            if ip_port:
                self.local_ip, self.local_port = ip_port
                self.connect_to_server()
    
    def connect_to_server(self):
        """连接到服务器"""
        if self.client:
            self.text_ui.add_message("已经连接到服务器", True)
            return
        
        try:
            self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client.connect((self.local_ip, self.local_port))
            self.client_status = "已连接"
            self.text_ui.update_status(self.client_status)
            self.text_ui.add_message(f"成功连接到服务器 {self.local_ip}:{self.local_port}", True)
            
            # 启动接收消息的线程
            threading.Thread(target=self.receive_messages, daemon=True).start()
        except Exception as e:
            self.text_ui.add_message(f"连接失败: {str(e)}", True)
    
    def send_message(self, message):
        """发送消息到服务器"""
        if not self.client:
            self.text_ui.add_message("未连接到服务器，无法发送消息", True)
            return
        try:
            # 检查是否是游戏命令
            if message.startswith("/"):
                command_parts = message.split()
                command = command_parts[0][1:]  # 去掉斜杠
                
                if command == "start" and len(command_parts) == 1:
                    # 发送开始游戏请求
                    msg = {"type": "start_game"}
                    self.client.send(json.dumps(msg).encode('utf-8'))
                    self.text_ui.add_message("已发送开始游戏请求", True)
                    return
                elif command == "quit" and len(command_parts) == 1:
                    # 退出游戏
                    if self.in_game:
                        self.in_game = False
                        msg = {"type": "quit_game"}
                        self.client.send(json.dumps(msg).encode('utf-8'))
                        self.text_ui.add_message("已退出游戏", True)
                    else:
                        self.text_ui.add_message("当前不在游戏中", True)
                    return
            
            # 普通聊天消息
            msg = {
                "type": "chat",
                "message": message,
                "sender": "你"
            }
            self.client.send(json.dumps(msg).encode('utf-8'))
        except Exception as e:
            self.text_ui.add_message(f"发送失败: {str(e)}", True)

    def receive_messages(self):
        """接收服务器消息的线程"""
        while self.running and self.client:
            try:
                data = self.client.recv(4096)  # 增大缓冲区以接收游戏状态
                if data:
                    try:
                        msg = json.loads(data.decode('utf-8'))
                        
                        # 处理不同类型的消息
                        if isinstance(msg, dict):
                            msg_type = msg.get('type')
                            
                            # 聊天消息
                            if 'message' in msg:
                                sender = msg.get('sender', '未知')
                                self.text_ui.add_message(f"{sender}: {msg['message']}")
                            
                            # 游戏开始消息
                            elif msg_type == 'game_start':
                                self.start_game()
                                self.text_ui.add_message("游戏开始！", True)
                            
                            # 游戏状态同步消息
                            elif msg_type == 'sync' and self.in_game:
                                self.handle_sync_message(msg)
                            
                            # 其他消息
                            else:
                                self.text_ui.add_message(f"未知消息类型: {msg_type}", True)
                        else:
                            self.text_ui.add_message(f"无效的消息格式: {msg}", True)
                    except json.JSONDecodeError as e:
                        self.text_ui.add_message(f"消息解析错误: {str(e)}", True)
                    except Exception as e:
                        self.text_ui.add_message(f"处理消息时发生错误: {str(e)}", True)
                else:
                    # 如果收到空消息，表示服务器已断开连接
                    self.client.close()
                    self.client = None
                    self.client_status = "未连接"
                    self.in_game = False
                    self.text_ui.update_status(self.client_status)
                    self.text_ui.add_message("与服务器的连接已断开", True)
                    break
            except ConnectionResetError:
                self.client = None
                self.client_status = "未连接"
                self.in_game = False
                self.text_ui.update_status(self.client_status)
                self.text_ui.add_message("服务器强制关闭连接", True)
                break
            except Exception as e:
                self.client = None
                self.client_status = "未连接"
                self.in_game = False
                self.text_ui.update_status(self.client_status)
                self.text_ui.add_message(f"接收消息错误: {str(e)}", True)
                break
    
    def start_game(self):
        """开始游戏（复用MultiplayerGameLevel的渲染）"""
        self.in_game = True
        # 初始化多人关卡对象
        self.game_level = MultiplayerGameLevel(multiplayer=True)
        # 玩家对象缓存：{player_name: Image实例}
        self.player_objs = {}
        # 敌人对象缓存：[{...Enemy实例...}]
        self.enemy_objs = []
        self.text_ui.add_message("游戏初始化完成", True)

    def handle_sync_message(self, msg):
        """处理同步消息，驱动game_level对象属性"""
        if not isinstance(msg, dict):
            self.text_ui.add_message("无效的同步消息格式", True)
            return
        self.game_state = msg
        # 玩家名识别
        if not self.player_name and 'players' in msg:
            for client in msg['players']:
                if msg['players'][client].get('is_you', False):
                    self.player_name = client
                    self.text_ui.add_message(f"您的玩家名称已设置为: {self.player_name}", True)
                    break
        # --- 同步玩家对象 ---
        if hasattr(self, 'game_level') and self.game_level:
            # 玩家
            players = msg.get('players', {})
            for name, pdata in players.items():
                if name not in self.player_objs:
                    # 创建Image对象，假设所有玩家用同一贴图
                    self.player_objs[name] = Image('picture/Capoo/%d.png', (const.capoo_width, const.capoo_hight), pdata.get('pos', (0,0)), 1, 8, 1)
                obj = self.player_objs[name]
                obj.pos = list(pdata.get('pos', (0,0)))
                obj.facing_left = pdata.get('facing_left', False)
                obj.hp = pdata.get('hp', 100)
                obj.size = pdata.get('size', (const.capoo_width, const.capoo_hight))
                obj.reloade()
            # 敌人
            enemies = msg.get('enemies', [])
            # 数量变化时重建
            if len(self.enemy_objs) != len(enemies):
                from Enemies import Enemy
                self.enemy_objs = [Enemy(None, size=e.get('size', (50,50)), speed=2) for e in enemies]
            for obj, edata in zip(self.enemy_objs, enemies):
                obj.pos = list(edata.get('pos', (0,0)))
                obj.facing_left = edata.get('facing_left', False)
                obj.hp = edata.get('hp', 100)
                obj.size = edata.get('size', (50,50))
                obj.reloade()

    def draw_game(self):
        """复用game_level的draw逻辑进行渲染，并绘制UI和草地背景"""
        if not self.in_game or not self.game_state or not hasattr(self, 'game_level'):
            return
        # 平铺grass.png作为背景
        grass_w, grass_h = self.grass_img.get_width(), self.grass_img.get_height()
        offset_x, offset_y = 0, 0  # 联机模式暂不支持camera
        for x in range(-grass_w, const.wsize + grass_w, grass_w):
            for y in range(-grass_h, const.hsize + grass_h, grass_h):
                screen_x = x - offset_x
                screen_y = y - offset_y
                self.screen.blit(self.grass_img, (screen_x, screen_y))
        # 玩家
        for name, obj in self.player_objs.items():
            obj.draw(self.screen)
        # 敌人
        for obj in self.enemy_objs:
            obj.draw(self.screen)
        # 分数
        score = self.game_state.get('score', 0)
        mFont(f"score:{score}", 'font/BoutiqueBitmap9x9_Bold_1.9.ttf', 50, (230, 100, 150), (const.wsize, 160)).fdraw(self.screen)
        # 退出按钮
        self.game_exit_font.fdraw(self.screen)
        pygame.display.flip()

    def run(self):
        """运行客户端UI，支持UI自适应和主菜单切换"""
        clock = pygame.time.Clock()
        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    # 确保关闭连接
                    if self.client:
                        try:
                            self.client.close()
                        except:
                            pass
                    pygame.quit()
                    sys.exit()
                elif event.type == pygame.VIDEORESIZE:
                    const.wsize, const.hsize = event.w, event.h
                    self.screen = pygame.display.set_mode((const.wsize, const.hsize), pygame.RESIZABLE)
                    # 保留历史消息和状态，重建UI
                    old_messages = self.text_ui.messages if hasattr(self.text_ui, 'messages') else []
                    old_status = self.client_status
                    self.image_ui = ClientUIImage()
                    self.text_ui = ClientUIText()
                    self.text_ui.messages = old_messages
                    self.text_ui.update_status(old_status)
                    # UI自适应
                    self.game_exit_font.pos = [(const.wsize - self.game_exit_font.getrect().width - 10), 10]
                    # 重新加载背景和草地图片
                    self.background = Image('picture/bg0.jpg', (const.wsize, const.hsize), (0, 0), 0, 1, 0)
                    self.grass_img = pygame.image.load('picture/grass.png').convert()
                # 处理所有其他事件（包括窗口缩放）
                if self.in_game:
                    # 处理退出按钮
                    button_result = self.game_exit_font.Button(event, "main_menu")
                    if button_result['state_change']:
                        self.running = False
                        break
                if not self.in_game:
                    self.handle_event(event)
            # 处理游戏输入
            if self.in_game:
                self.handle_game_input()
                self.draw_game()
            else:
                self.draw()
                
            clock.tick(const.fps)
        # 关闭连接
        if self.client:
            try:
                self.client.close()
            except:
                pass