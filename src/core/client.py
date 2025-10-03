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
        """开始游戏"""
        self.in_game = True
        self.game_level = MultiplayerGameLevel(multiplayer=True)
        self.text_ui.add_message("游戏初始化完成", True)
    
    def handle_sync_message(self, msg):
        """处理同步消息"""
        if not isinstance(msg, dict):
            self.text_ui.add_message("无效的同步消息格式", True)
            return
        
        # 更新游戏状态
        self.game_state = msg
        
        # 如果是第一次收到同步消息，确定自己的玩家名称
        if not self.player_name and 'players' in msg:
            for client in msg['players']:
                # 假设服务器会在玩家数据中包含一个标识符
                if msg['players'][client].get('is_you', False):
                    self.player_name = client
                    self.text_ui.add_message(f"您的玩家名称已设置为: {self.player_name}", True)
                    break
    
    def send_action(self, action_type, params=None):
        """发送游戏操作到服务器"""
        if not self.client or not self.in_game:
            self.text_ui.add_message("未连接到服务器或不在游戏中，无法发送操作", True)
            return
            
        if not isinstance(action_type, str) or not action_type.strip():
            self.text_ui.add_message("无效的操作类型", True)
            return
            
        action = {
            "type": "action",
            "action": {
                "type": action_type,
                **(params or {})
            }
        }
        
        try:
            self.client.send(json.dumps(action).encode('utf-8'))
            self.text_ui.add_message(f"操作 {action_type} 已发送", False)
        except ConnectionResetError:
            self.client = None
            self.client_status = "未连接"
            self.text_ui.update_status(self.client_status)
            self.text_ui.add_message("服务器已断开连接", True)
        except Exception as e:
            self.text_ui.add_message(f"发送操作失败: {str(e)}", True)
    
    def handle_game_input(self):
        """处理游戏输入"""
        if not self.in_game:
            return
            
        # 获取键盘状态
        keys = pygame.key.get_pressed()
        
        # 移动控制
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self.send_action('move', {'direction': 'left'})
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.send_action('move', {'direction': 'right'})
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            self.send_action('move', {'direction': 'up'})
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            self.send_action('move', {'direction': 'down'})
            
        # 攻击控制
        if keys[pygame.K_SPACE] and not self.keys_pressed.get(pygame.K_SPACE):
            self.send_action('attack')
            self.keys_pressed[pygame.K_SPACE] = True
        elif not keys[pygame.K_SPACE]:
            self.keys_pressed[pygame.K_SPACE] = False
    
    def draw_game(self):
        """绘制游戏画面"""
        if not self.in_game or not self.game_state:
            return
            
        # 清空屏幕
        self.screen.fill((0, 0, 0))
        
        # 绘制地图
        if 'map' in self.game_state:
            # 这里应该根据地图数据绘制地图
            pass
        
        # 绘制玩家
        if 'players' in self.game_state:
            for player_name, player_data in self.game_state['players'].items():
                # 绘制玩家精灵
                pos = player_data.get('pos', (0, 0))
                size = player_data.get('size', (const.capoo_width, const.capoo_hight))
                facing_left = player_data.get('facing_left', False)
                
                # 简单绘制一个矩形表示玩家
                color = (0, 255, 0) if player_name == self.player_name else (255, 0, 0)
                pygame.draw.rect(self.screen, color, pygame.Rect(pos[0], pos[1], size[0], size[1]))
                
                # 绘制玩家名称
                font = pygame.font.Font("font/BoutiqueBitmap9x9_Bold_1.9.TTF", 14)
                name_surface = font.render(player_name, True, (255, 255, 255))
                self.screen.blit(name_surface, (pos[0], pos[1] - 20))
                
                # 绘制血条
                hp = player_data.get('hp', 100)
                hp_width = size[0] * (hp / 100)
                pygame.draw.rect(self.screen, (255, 0, 0), pygame.Rect(pos[0], pos[1] - 10, size[0], 5))
                pygame.draw.rect(self.screen, (0, 255, 0), pygame.Rect(pos[0], pos[1] - 10, hp_width, 5))
        
        # 绘制敌人
        if 'enemies' in self.game_state:
            for enemy in self.game_state['enemies']:
                # 绘制敌人精灵
                pos = enemy.get('pos', (0, 0))
                size = enemy.get('size', (30, 30))
                
                # 简单绘制一个矩形表示敌人
                pygame.draw.rect(self.screen, (255, 0, 255), pygame.Rect(pos[0], pos[1], size[0], size[1]))
        
        # 更新显示
        pygame.display.flip()
    
    def run(self):
        """运行客户端UI"""
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
                # 处理所有其他事件（包括窗口缩放）
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