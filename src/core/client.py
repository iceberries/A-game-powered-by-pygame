import pygame
import socket
import threading
import queue
import re
import const
from image import Image, mFont, InputBox
import sys
import camera
from Enemies import Enemy, AttackChicken, GreenCapoo
from core.protocol import MessageBuffer, ProtocolError, Sequence, send_message as send_packet
from core.assets import ASSETS
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
        for i, message in enumerate(self.messages):
            text_surface = ASSETS.text(
                message, "font/BoutiqueBitmap9x9_Bold_1.9.TTF", 18,
                (0, 0, 0),
            )
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
        self.player_count = 0
        self.max_players = 4
        
        # 创建图片UI和文本UI实例
        self.image_ui = ClientUIImage()
        self.text_ui = ClientUIText()
        self.game_exit_font = mFont(const.exittitle, 'font/BoutiqueBitmap9x9_Bold_1.9.TTF', const.text_size, (230, 100, 150), (const.wsize, 10))
        self.background = Image('picture/bg0.jpg', (const.wsize, const.hsize), (0, 0), 0, 1, 0)
        self.grass_img = ASSETS.image('picture/grass.png')
        
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
        self.incoming_messages = queue.Queue()
        self.send_lock = threading.Lock()
        self.action_sequence = Sequence()
        self._last_server_tick = -1
        # 每次成功连接都有独立代次。旧接收线程的断线事件不能关闭新连接。
        self._connection_generation = 0
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
                self.send_action("move", direction=direction)
            else:
                self.send_action("stop_move")
            self._last_move_dir = direction

    def send_action(self, action_type, **params):
        sock = self.client
        if not sock:
            return False
        message = {
            "type": "action",
            "sequence": self.action_sequence.next(),
            "action": {"type": action_type, **params},
        }
        try:
            send_packet(sock, message, self.send_lock)
            return True
        except OSError as exc:
            self.incoming_messages.put({
                "_local_type": "network_error",
                "_generation": self._connection_generation,
                "message": str(exc),
            })
            return False
    
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
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.settimeout(5.0)
            sock.connect((self.local_ip, self.local_port))
            sock.settimeout(0.5)
            self.client = sock
            self._connection_generation += 1
            generation = self._connection_generation
            self.client_status = "已连接"
            self.text_ui.update_status(self.client_status)
            self.text_ui.add_message(f"成功连接到服务器 {self.local_ip}:{self.local_port}", True)
            
            # 启动接收消息的线程
            threading.Thread(
                target=self.receive_messages,
                args=(sock, generation),
                daemon=True,
            ).start()
        except Exception as e:
            try:
                sock.close()
            except OSError:
                pass
            if self.client is sock:
                self.client = None
            self.text_ui.add_message(f"连接失败: {str(e)}", True)
    
    def send_message(self, message):
        """发送消息到服务器"""
        if not self.client:
            self.text_ui.add_message("未连接到服务器，无法发送消息", True)
            return
        if message.strip() == "/start":
            self.text_ui.add_message("只有房主可以在服务器界面开始游戏", True)
            return
        if message.strip() == "/quit":
            if self.in_game:
                self.send_action("quit_game")
                self.in_game = False
                self.text_ui.add_message("已退出游戏", True)
            return
        try:
            send_packet(
                self.client,
                {"type": "chat", "message": message},
                self.send_lock,
            )
        except OSError as exc:
            self.text_ui.add_message(f"发送失败: {str(exc)}", True)

    def receive_messages(self, sock, generation):
        """网络线程只解码字节并写入队列，不调用任何 Pygame/UI API。"""
        decoder = MessageBuffer()
        reason = "与服务器的连接已断开"
        try:
            while self.running and self.client is sock:
                try:
                    data = sock.recv(65536)
                except socket.timeout:
                    continue
                if not data:
                    break
                for message in decoder.feed(data):
                    self.incoming_messages.put(message)
        except (OSError, ProtocolError) as exc:
            reason = f"网络错误: {exc}"
        finally:
            self.incoming_messages.put({
                "_local_type": "disconnected",
                "_generation": generation,
                "message": reason,
            })

    def process_network_messages(self):
        """由 Pygame 主线程调用，安全地修改 UI 和渲染对象。"""
        while True:
            try:
                message = self.incoming_messages.get_nowait()
            except queue.Empty:
                return
            local_type = message.get("_local_type")
            if local_type in {"disconnected", "network_error"}:
                if message.get("_generation") != self._connection_generation:
                    continue
                self.close_connection()
                self.in_game = False
                self.player_count = 0
                self.client_status = "未连接"
                self.text_ui.update_status(self.client_status)
                self.text_ui.add_message(message.get("message", "网络已断开"), True)
                continue

            message_type = message.get("type")
            if message_type == "welcome":
                self.player_name = message.get("player_name")
                self.update_room_status(message)
                self.text_ui.add_message(f"您的玩家名称: {self.player_name}", True)
            elif message_type == "chat":
                self.text_ui.add_message(
                    f"{message.get('sender', '未知')}: {message.get('message', '')}"
                )
            elif message_type == "system":
                self.update_room_status(message)
                self.text_ui.add_message(message.get("message", ""), True)
            elif message_type == "game_start":
                self.player_name = message.get("you", self.player_name)
                self.player_count = len(message.get("players", {}))
                self.start_game(message)
                self.client_status = (
                    f"游戏中 · {self.player_count}/{self.max_players}"
                )
                self.text_ui.update_status(self.client_status)
                self.text_ui.add_message("游戏开始！", True)
            elif message_type == "sync" and self.in_game:
                self.handle_sync_message(message)
            elif message_type == "game_end":
                self.in_game = False
                self.update_room_status(message)
                self.text_ui.add_message(message.get("message", "游戏结束"), True)
            elif message_type == "error":
                self.text_ui.add_message(message.get("message", "服务器错误"), True)

    def update_room_status(self, message):
        if "player_count" in message:
            self.player_count = message["player_count"]
        if "max_players" in message:
            self.max_players = message["max_players"]
        if self.in_game:
            self.client_status = (
                f"游戏中 · {self.player_count}/{self.max_players}"
            )
        else:
            self.client_status = (
                f"已连接 · 房间 {self.player_count}/{self.max_players}"
            )
        self.text_ui.update_status(self.client_status)

    def close_connection(self):
        sock = self.client
        self.client = None
        if not sock:
            return
        self._connection_generation += 1
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            sock.close()
        except OSError:
            pass

    def start_game(self, initial_state):
        """在主线程创建纯渲染对象。"""
        self.in_game = True
        self.player_objs = {}
        self.enemy_objs = {}
        self.camera = camera.Camera(const.wsize, const.hsize)
        self._last_server_tick = -1
        self.handle_sync_message(initial_state)
        self.text_ui.add_message("游戏初始化完成", True)

    def handle_sync_message(self, msg):
        """处理同步消息，驱动game_level对象属性"""
        if not isinstance(msg, dict):
            self.text_ui.add_message("无效的同步消息格式", True)
            return
        server_tick = msg.get("tick", -1)
        if server_tick <= self._last_server_tick:
            return
        self._last_server_tick = server_tick
        self.game_state = msg
        players = msg.get('players', {})
        for removed in set(self.player_objs) - set(players):
            del self.player_objs[removed]
        for name, pdata in players.items():
            if name not in self.player_objs:
                self.player_objs[name] = Image(
                    'picture/Capoo/%d.png',
                    tuple(pdata.get('size', (const.capoo_width, const.capoo_hight))),
                    pdata.get('pos', (0, 0)),
                    1, 8, 1,
                )
            obj = self.player_objs[name]
            obj.pos = list(pdata.get('pos', (0, 0)))
            obj.facing_left = pdata.get('facing_left', False)
            obj.hp = pdata.get('hp', 100)
            obj.size = tuple(pdata.get('size', (const.capoo_width, const.capoo_hight)))
            obj.is_attacking = pdata.get('attacking', False)
            if obj.is_attacking:
                # 客户端不自行推进权威状态；根据服务端时间渲染对应攻击帧。
                obj.attack_frame = pdata.get('attack_elapsed', 0.0)
                obj.play_attack_animation(0.0)
            else:
                obj.reloade()

        enemy_states = {str(item['id']): item for item in msg.get('enemies', [])}
        for removed in set(self.enemy_objs) - set(enemy_states):
            del self.enemy_objs[removed]
        target = self.player_objs.get(self.player_name)
        for enemy_id, edata in enemy_states.items():
            enemy_type = edata.get('type')
            if enemy_type in {'attack', 'attack_chicken'}:
                expected_type = AttackChicken
            elif enemy_type == 'green_capoo':
                expected_type = GreenCapoo
            else:
                expected_type = Enemy
            obj = self.enemy_objs.get(enemy_id)
            if obj is None or not isinstance(obj, expected_type):
                obj = expected_type(
                    target,
                    size=tuple(edata.get('size', (50, 50))),
                    speed=0,
                )
                self.enemy_objs[enemy_id] = obj
            obj.player = target
            obj.pos = list(edata.get('pos', (0, 0)))
            obj.facing_left = edata.get('facing_left', False)
            obj.hp = edata.get('hp', 1)
            obj.size = tuple(edata.get('size', (50, 50)))
            if isinstance(obj, AttackChicken):
                obj.is_attacking = edata.get('attacking', False)
                if obj.is_attacking:
                    # 使用服务端权威的攻击时间选择 Enemy/AT 动画帧。
                    obj.attack_frame = edata.get('attack_elapsed', 0.0)
                    obj.play_animation(0.0)
                else:
                    obj.play_animation(0.0)
            else:
                obj.reloade()

    def draw_game(self):
        """客户端只渲染服务器快照，不在本地运行权威规则。"""
        if not self.in_game or not self.game_state:
            return
        shared_center = self.game_state.get('camera', {}).get('center')
        if (isinstance(shared_center, (list, tuple))
                and len(shared_center) == 2):
            # 所有客户端使用服务端计算的存活玩家几何中心，保持共享视野。
            self.camera.update_center(shared_center)
        grass_w, grass_h = self.grass_img.get_width(), self.grass_img.get_height()
        offset_x = self.camera.offset_x % grass_w
        offset_y = self.camera.offset_y % grass_h
        for x in range(-grass_w, const.wsize + grass_w, grass_w):
            for y in range(-grass_h, const.hsize + grass_h, grass_h):
                screen_x = x - offset_x
                screen_y = y - offset_y
                self.screen.blit(self.grass_img, (screen_x, screen_y))
        # 玩家
        for name, obj in self.player_objs.items():
            obj.draw(self.screen, self.camera)
        # 敌人
        for obj in self.enemy_objs.values():
            obj.draw(self.screen, self.camera)
        # 分数
        score = self.game_state.get('players', {}).get(
            self.player_name, {}
        ).get('score', 0)
        mFont(f"score:{score}", 'font/BoutiqueBitmap9x9_Bold_1.9.ttf', 50, (230, 100, 150), (const.wsize, 160)).fdraw(self.screen)
        # 退出按钮
        self.game_exit_font.fdraw(self.screen)
        pygame.display.flip()

    def run(self):
        """运行客户端UI，支持UI自适应和主菜单切换"""
        clock = pygame.time.Clock()
        while self.running:
            self.process_network_messages()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    self.close_connection()
                    pygame.quit()
                    sys.exit()
                elif event.type == pygame.VIDEORESIZE:
                    const.set_resolution(event.w, event.h)
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
                    self.grass_img = ASSETS.image('picture/grass.png')
                    if hasattr(self, 'camera'):
                        self.camera.resize(const.wsize, const.hsize)
                # 处理所有其他事件（包括窗口缩放）
                if self.in_game:
                    if event.type == pygame.KEYDOWN and event.key == pygame.K_j:
                        self.send_action("attack")
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
                
            clock.tick(const.RENDER_FPS)
        # 关闭连接
        self.close_connection()
