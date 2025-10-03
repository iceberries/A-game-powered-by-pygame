import socket
import threading
import json
import copy
import pygame
import time
import const
from image import Image, mFont, InputBox
import sys
from core.mul_game_level import MultiplayerGameLevel
class GameServer:
    """游戏服务器类，处理网络通信"""
    def __init__(self, host='0.0.0.0', port=5555):
        self.host = host
        self.port = port
        self.server_socket = None
        self.clients = []  # 存储客户端连接
        self.clients_lock = threading.Lock()  # 用于线程安全操作
        self.running = False
        self.message_callback = None  # 消息回调函数
        self.sync_interval = 0.1  # 游戏状态同步间隔（秒）
        self.client_count_callback = None  # 客户端数量变化回调函数
        
    def start(self):
        """启动服务器"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            self.running = True
            
            # 获取本机IP地址
            self.local_ip = socket.gethostbyname(socket.gethostname())
            
            # 启动接受客户端线程
            accept_thread = threading.Thread(target=self.accept_clients)
            accept_thread.daemon = True
            accept_thread.start()
            
            return True
        except Exception as e:
            print(f"服务器启动失败: {e}")
            return False
    
    def stop(self):
        """停止服务器"""
        self.running = False
        
        # 关闭所有客户端连接
        with self.clients_lock:
            for client in self.clients:
                try:
                    client['socket'].close()
                except:
                    pass
            self.clients.clear()
        
        # 关闭服务器socket
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
    
    def accept_clients(self):
        """接受客户端连接的线程函数"""
        while self.running:
            try:
                client_socket, address = self.server_socket.accept()
                
                # 创建客户端信息字典
                client_info = {
                    'socket': client_socket,
                    'address': address,
                    'name': f"Player_{len(self.clients) + 1}"
                }
                
                # 添加到客户端列表
                with self.clients_lock:
                    self.clients.append(client_info)
                
                # 发送欢迎消息
                welcome_msg = {
                    'type': 'system',
                    'message': f"欢迎 {client_info['name']} 加入服务器！",
                    'player_count': len(self.clients)
                }
                self.broadcast(welcome_msg)
                
                # 启动客户端处理线程
                client_thread = threading.Thread(target=self.handle_client, args=(client_info,))
                client_thread.daemon = True
                client_thread.start()
                
                # 更新客户端数量
                if self.client_count_callback:
                    self.client_count_callback(len(self.clients))
                    
            except Exception as e:
                if self.running:
                    print(f"接受客户端连接时出错: {e}")
                    time.sleep(0.1)
    
    def handle_client(self, client_info):
        """处理单个客户端的线程函数"""
        client_socket = client_info['socket']
        
        while self.running:
            try:
                # 接收数据
                data = client_socket.recv(4096)
                if not data:
                    break
                
                # 解析JSON消息
                message = json.loads(data.decode('utf-8'))
                
                # 处理消息
                if message['type'] == 'chat':
                    # 添加发送者信息
                    message['sender'] = client_info['name']
                    
                    # 广播消息（broadcast方法内部会调用message_callback）
                    self.broadcast(message)
                
            except Exception as e:
                print(f"处理客户端消息时出错: {e}")
                break
        
        # 客户端断开连接
        self.remove_client(client_info)
    
    def remove_client(self, client_info):
        """移除客户端"""
        # 先移除再广播，避免广播时操作已关闭socket
        with self.clients_lock:
            if client_info in self.clients:
                self.clients.remove(client_info)
                try:
                    client_info['socket'].close()
                except:
                    pass
        # 广播离开消息
        leave_msg = {
            'type': 'system',
            'message': f"{client_info['name']} 离开了服务器",
            'player_count': len(self.clients)
        }
        self.broadcast(leave_msg)
        # 更新客户端数量
        if self.client_count_callback:
            self.client_count_callback(len(self.clients))

    def broadcast(self, message):
        """广播消息给所有客户端"""
        message_data = json.dumps(message).encode('utf-8')
        remove_list = []
        with self.clients_lock:
            clients_copy = self.clients.copy()
        for client in clients_copy:
            try:
                client['socket'].sendall(message_data)
            except Exception as e:
                # 记录需要移除的客户端
                remove_list.append(client)
        # 移除失效客户端，防止下次继续崩溃
        if remove_list:
            with self.clients_lock:
                for client in remove_list:
                    if client in self.clients:
                        try:
                            client['socket'].close()
                        except:
                            pass
                        self.clients.remove(client)
        # 调用消息回调
        if self.message_callback:
            self.message_callback(message)
    
    def send_message(self, message_text):
        """发送服务器消息"""
        message = {
            'type': 'chat',
            'sender': 'Server',
            'message': message_text
        }
        self.broadcast(message)
    
    def get_server_info(self):
        """获取服务器信息"""
        return {
            'ip': self.local_ip,
            'port': self.port,
            'player_count': len(self.clients)
        }
    
    def game_loop(self, game, players):
        """多人游戏主循环，独立线程运行"""
        try:
            while self.running:
                loop_start = time.time()
                players_copy = copy.deepcopy(players)
                game_running = game.update(players_copy)
                state_msg = {
                    'type': 'sync',
                    'players': players_copy,
                    'enemies': game.get_enemies_state(),
                    'map': game.get_map_state(),
                }
                self.broadcast(state_msg)
                if not game_running:
                    break
                elapsed = time.time() - loop_start
                remaining = max(0.0, self.sync_interval - elapsed)
                if remaining > 0:
                    time.sleep(remaining)
        finally:
            game_running_msg = {
                'type': 'system',
                'message': '游戏循环已结束',
                'player_count': len(self.clients)
            }
            self.broadcast(game_running_msg)

    def start_game(self):
        """启动游戏（多线程，避免阻塞UI）"""
        game = MultiplayerGameLevel(multiplayer=True)
        players = {}
        with self.clients_lock:
            client_snapshot = self.clients.copy()
        for idx, client in enumerate(client_snapshot):
            players[client['name']] = {
                'pos': game.get_spawn_point(idx),
                'hp': 100,
                'size': (const.capoo_width, const.capoo_hight),
                'score': 0,
                'action': None,
                'facing_left': False,
                'attacking': False,
                'attack_damage': 10
            }
        start_msg = {
            'type': 'game_start',
            'players': copy.deepcopy(players),
            'map': game.get_map_state()
        }
        self.broadcast(start_msg)
        threading.Thread(target=self.game_loop, args=(game, players), daemon=True).start()

class ServerUIImage(Image):
    def __init__(self):
        # 使用空路径初始化父类
        super().__init__("", (const.wsize, const.hsize), (0, 0), 0)
        
        # 创建消息输入框
        self.input_box = InputBox(
            title="",
            font_path="font/BoutiqueBitmap9x9_Bold_1.9.TTF",
            size=18,
            color=(0, 0, 0),
            pos=(50, const.hsize - 100),
            box_width=const.wsize - 250,
            box_height=40,
            inactive_color=(255, 255, 255),
            active_color=(240, 240, 255),
            border_color=(0, 0, 0),
            max_length=100
        )
    
    def draw(self, screen):
        # 绘制输入框
        self.input_box.draw(screen)
    
    def handle_input(self, event):
        # 处理消息输入框
        result = {"action": None, "data": None}
        
        # 处理消息输入框
        input_result = self.input_box.handle_input(event)
        if input_result["action"] == "send":
            result["action"] = "send"
            result["data"] = self.input_box.get_text()
        
        return result

# ServerUIText类 - 处理文本界面和按钮
class ServerUIText(mFont):
    def __init__(self):
        # 使用空标题初始化父类
        super().__init__("", "font/BoutiqueBitmap9x9_Bold_1.9.TTF", const.text_size, (0, 0, 0), (0, 0))
        self.texts = {}
        self.buttons = {}
        self.messages = []  # 存储聊天消息
        self.setup_texts()
        self.setup_buttons()
    
    def setup_texts(self):
        # 设置各种文本
        self.texts["title"] = mFont(const.create_server, "font/BoutiqueBitmap9x9_Bold_1.9.TTF", const.title1_size, (0, 0, 0), (const.wsize//2+140, 20))
        self.texts["status"] = mFont("未启动", "font/BoutiqueBitmap9x9_Bold_1.9.TTF", const.text_size, (0, 0, 0), (250, 150))
    
    def setup_buttons(self):
        # 设置各种按钮
        self.buttons["start"] = mFont("启动服务器", "font/BoutiqueBitmap9x9_Bold_1.9.TTF", const.text_size, (100, 100, 255), (const.wsize//2+120, 200))
        self.buttons["exit"] = mFont("返回", "font/BoutiqueBitmap9x9_Bold_1.9.TTF", const.text_size, (100, 100, 255), (const.wsize//2, const.hsize - 60))
        self.buttons["send"] = mFont("发送", "font/BoutiqueBitmap9x9_Bold_1.9.TTF", const.text_size, (100, 100, 255), (const.wsize - 100, const.hsize - 100))
        self.buttons["start_game"] = mFont("开始游戏", "font/BoutiqueBitmap9x9_Bold_1.9.TTF", const.text_size, (100, 200, 100), (const.wsize//2+110, 120))
    
    def update_status(self, status):
        self.texts["status"] = mFont(f"服务器状态: {status}", "font/BoutiqueBitmap9x9_Bold_1.9.TTF", const.text_size, (0, 0, 0), (355, 150))
    
    def update_server_info(self, ip, port, player_count):
        self.texts["ip"] = mFont(f"IP地址: {ip}", "font/BoutiqueBitmap9x9_Bold_1.9.TTF", const.text_size, (0, 0, 0), (const.wsize-70, 150))
        self.texts["port"] = mFont(f"端口: {port}", "font/BoutiqueBitmap9x9_Bold_1.9.TTF", const.text_size, (0, 0, 0), (const.wsize-70, 190))
        self.texts["players"] = mFont(f"在线人数: {player_count}", "font/BoutiqueBitmap9x9_Bold_1.9.TTF", const.text_size, (0, 0, 0), (220, 190))
    
    def update_start_button(self, is_running):
        # 只更新按钮文本，不新建对象，避免状态丢失
        btn = self.buttons["start"]
        btn.title = "停止服务器" if is_running else "启动服务器"
        btn.mfont = pygame.font.Font(btn.path, btn.size)
        btn.text = btn.mfont.render(btn.title, True, btn.color)
        # 保持位置不变
    
    def add_chat_message(self, sender, message, time_str):
        """添加聊天消息"""
        self.messages.append({
            'type': 'chat',
            'sender': sender,
            'message': message,
            'time': time_str
        })
        # 限制消息数量，防止过多
        if len(self.messages) > 100:
            self.messages.pop(0)
    
    def add_system_message(self, message, time_str):
        """添加系统消息"""
        self.messages.append({
            'type': 'system',
            'message': message,
            'time': time_str
        })
        # 限制消息数量，防止过多
        if len(self.messages) > 100:
            self.messages.pop(0)
    
    def handle_buttons(self, event, server_running=False):
        # 处理按钮点击事件
        result = {"action": None, "data": None}
        
        # 处理启动/停止按钮
        start_result = self.buttons["start"].Button(event, "start")
        if start_result["state_change"]:
            result["action"] = "start"
        
        # 处理退出按钮
        exit_result = self.buttons["exit"].Button(event, "exit")
        if exit_result["state_change"]:
            result["action"] = "exit"
        
        # 处理发送按钮
        send_result = self.buttons["send"].Button(event, "send")
        if send_result["state_change"]:
            result["action"] = "send"

        # 只在服务器运行时处理“开始游戏”按钮
        if server_running:
            start_game_result = self.buttons["start_game"].Button(event, "start_game")
            if start_game_result["state_change"]:
                result["action"] = "start_game"
        
        return result
    
    def fdraw(self, screen, server_running=False):
        # 绘制所有文本元素
        for text_name, text in self.texts.items():
            text.fdraw(screen)
        # 绘制所有按钮
        for button_name, button in self.buttons.items():
            # 只在服务器运行时显示“开始游戏”按钮
            if button_name == "start_game" and not server_running:
                continue
            button.fdraw(screen)
        
        # 绘制聊天区域
        chat_rect = pygame.Rect(50, 300, const.wsize - 100, const.hsize - 450)
        pygame.draw.rect(screen, (255, 255, 255), chat_rect)
        pygame.draw.rect(screen, (0, 0, 0), chat_rect, 2)
        
        # 绘制聊天消息
        self.draw_messages(screen, chat_rect)
    
    def draw_messages(self, screen, chat_rect):
        # 绘制聊天消息
        y_offset = chat_rect.top + 10
        font = pygame.font.Font("font/BoutiqueBitmap9x9_Bold_1.9.TTF", int(const.text_size * 0.8))
        line_height = font.get_height() + 2
        # 动态计算可显示的最大消息数
        max_lines = max(1, (chat_rect.height - 20) // line_height)
        for message in self.messages[-max_lines:]:
            if message['type'] == 'chat':
                msg_text = f"[{message['time']}] {message['sender']}: {message['message']}"
                color = (0, 0, 180) if message['sender'] == 'Server' else (0, 0, 0)
            else:  # 系统消息
                msg_text = f"[{message['time']}] {message['message']}"
                color = (180, 0, 0)  # 系统消息用红色
            # 处理长消息换行
            words = msg_text.split(' ')
            line = ""
            for word in words:
                test_line = line + word + " "
                # 如果当前行加上新单词超过聊天框宽度，则换行
                if font.size(test_line)[0] > chat_rect.width - 20:
                    msg_surface = font.render(line, True, color)
                    screen.blit(msg_surface, (chat_rect.left + 10, y_offset))
                    y_offset += line_height
                    line = word + " "
                else:
                    line = test_line
            # 绘制最后一行
            if line:
                msg_surface = font.render(line, True, color)
                screen.blit(msg_surface, (chat_rect.left + 10, y_offset))
                y_offset += line_height

# ServerUI类 - 主类
class ServerUI:
    def __init__(self, screen):
        """初始化服务器UI"""
        self.screen = screen
        self.running = False
        self.server = None
        self.server_status = "未启动"
        self.player_count = 0
        
        # 创建图片UI和文本UI实例
        self.image_ui = ServerUIImage()
        self.text_ui = ServerUIText()
        
        # 设置背景颜色
        self.bg_color = (240, 240, 240)
        
        # 添加一条欢迎消息
        self.text_ui.add_system_message("欢迎使用游戏服务器！", time.strftime("%H:%M:%S"))
    
    def start_server(self):
        """启动服务器"""
        if self.server is None:
            self.server = GameServer()
            self.server.message_callback = self.on_message
            self.server.client_count_callback = self.on_client_count_change
            if self.server.start():
                self.server_status = "运行中"
                server_info = self.server.get_server_info()
                self.text_ui.add_system_message(f"服务器已启动 - IP: {server_info['ip']}, 端口: {server_info['port']}", time.strftime("%H:%M:%S"))
                self.update_ui()  # 立即刷新按钮和服务器信息
                return True
            else:
                self.server = None
                self.server_status = "启动失败"
                self.update_ui()
                return False
        return False
    
    def stop_server(self):
        """停止服务器"""
        if self.server:
            self.server.stop()
            self.server = None
            self.server_status = "已停止"
            self.text_ui.add_system_message("服务器已停止", time.strftime("%H:%M:%S"))
            self.text_ui.update_status(self.server_status)
            self.text_ui.update_start_button(False)
    
    def on_message(self, message):
        """处理收到的消息"""
        if message['type'] == 'chat':
            self.text_ui.add_chat_message(message['sender'], message['message'], time.strftime("%H:%M:%S"))
        elif message['type'] == 'system':
            self.text_ui.add_system_message(message['message'], time.strftime("%H:%M:%S"))
            self.player_count = message['player_count']
            if self.server and self.server_status == "运行中":
                server_info = self.server.get_server_info()
                self.text_ui.update_server_info(server_info['ip'], server_info['port'], self.player_count)
    
    def on_client_count_change(self, count):
        """处理客户端数量变化"""
        self.player_count = count
        if self.server and self.server_status == "运行中":
            server_info = self.server.get_server_info()
            self.text_ui.update_server_info(server_info['ip'], server_info['port'], self.player_count)
    
    def send_message(self, message):
        """发送消息到所有客户端"""
        if message.strip() and self.server:
            self.server.send_message(message)
            self.image_ui.input_box.clear()
    
    def draw(self):
        """绘制UI界面"""
        # 绘制背景
        self.screen.fill(self.bg_color)
        
        # 绘制图片UI和文本UI
        self.image_ui.draw(self.screen)
        self.text_ui.fdraw(self.screen, server_running=(self.server_status == "运行中"))
        
        # 更新显示
        pygame.display.flip()
    
    def handle_event(self, event):
        """处理事件"""
        # 处理按钮事件
        button_result = self.text_ui.handle_buttons(event, server_running=(self.server_status == "运行中"))
        input_result = self.image_ui.handle_input(event)
        
        # 处理按钮事件
        if button_result["action"] == "start":
            if self.server_status == "未启动" or self.server_status == "已停止":
                self.start_server()
            else:
                self.stop_server()
        elif button_result["action"] == "exit":
            if self.server:
                self.stop_server()
            self.running = False
            return False
        elif button_result["action"] == "send":
            message = self.image_ui.input_box.get_text()
            if message:
                self.send_message(message)
        elif button_result["action"] == "start_game":
            if self.server:
                self.server.start_game()
        
        # 处理输入框事件
        if input_result["action"] == "send":
            message = input_result["data"]
            if message:
                self.send_message(message)
        
        return True
    def update_ui(self):
        # 始终根据当前状态刷新按钮文本
        if self.server_status == "运行中":
            server_info = self.server.get_server_info() if self.server else {"ip": "", "port": "", "player_count": 0}
            self.text_ui.update_server_info(server_info['ip'], server_info['port'], self.player_count)
            self.text_ui.update_status(self.server_status)
            self.text_ui.update_start_button(True)
        else:
            self.text_ui.update_status(self.server_status)
            self.text_ui.update_start_button(False)
    def run(self):
        """运行服务器UI"""
        self.running = True
        clock = pygame.time.Clock()
        
        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    if self.server:
                        self.stop_server()
                        self.update_ui()
                    self.running = False
                    self.update_ui()
                    pygame.quit()
                    sys.exit()
                    break
                elif event.type == pygame.VIDEORESIZE:
                    # 同时更新const.py中的窗口大小变量，确保在退出后再次进入时使用正确的窗口大小
                    const.wsize, const.hsize = event.w, event.h
                    self.screen = pygame.display.set_mode((const.wsize, const.hsize), pygame.RESIZABLE)
                    # 重新布局UI元素，保留历史消息
                    old_messages = self.text_ui.messages if hasattr(self.text_ui, 'messages') else []
                    self.image_ui = ServerUIImage()
                    self.text_ui = ServerUIText()
                    self.text_ui.messages = old_messages
                    self.update_ui()
                # 处理其他事件
                if not self.handle_event(event):
                    break
            
            # 绘制界面
            self.update_ui()
            self.draw()
            clock.tick(const.fps)