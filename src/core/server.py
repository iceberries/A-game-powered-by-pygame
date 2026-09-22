import socket
import threading
import queue
import pygame
import time
import const
from image import Image, mFont, InputBox
import sys
from core.game_world import GameWorld, MAX_PLAYERS as ROOM_CAPACITY
from core.protocol import (
    MessageBuffer,
    ProtocolError,
    send_message as send_packet,
    validate_client_message,
)
from core.assets import ASSETS


class GameServer:
    """线程边界清晰的服务器：读写线程只处理字节，模拟线程独占游戏状态。"""

    MAX_PLAYERS = ROOM_CAPACITY

    def __init__(self, host='0.0.0.0', port=5555):
        self.host = host
        self.port = port
        self.local_ip = host
        self.server_socket = None
        self.clients = []
        self.clients_lock = threading.Lock()
        self.running = False
        self.game_running = False
        self.current_game = None
        self.message_callback = None
        self.client_count_callback = None
        self.sync_interval = 0.1
        self.tick_interval = const.FIXED_DT
        self.incoming = queue.Queue()
        self.game_commands = queue.Queue()
        self.ui_events = queue.Queue()
        self._next_client_id = 1

    def start(self):
        """启动服务器"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.port = self.server_socket.getsockname()[1]
            self.server_socket.listen(5)
            self.server_socket.settimeout(0.5)
            self.running = True
            self.local_ip = socket.gethostbyname(socket.gethostname())
            threading.Thread(target=self.accept_clients, daemon=True).start()
            threading.Thread(target=self.dispatch_messages, daemon=True).start()
            return True
        except Exception as e:
            print(f"服务器启动失败: {e}")
            return False

    def stop(self):
        """停止服务器"""
        self.running = False
        with self.clients_lock:
            self.game_running = False
            clients = list(self.clients)
            self.clients.clear()
        for client in clients:
            client['closed'] = True
            try:
                client['outbox'].put_nowait(None)
            except queue.Full:
                pass
            self._close_socket(client['socket'])
        if self.server_socket:
            self._close_socket(self.server_socket)
            self.server_socket = None

    @staticmethod
    def _close_socket(sock):
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            sock.close()
        except OSError:
            pass

    def accept_clients(self):
        while self.running:
            try:
                client_socket, address = self.server_socket.accept()
                client_socket.settimeout(0.5)
                with self.clients_lock:
                    # start_game 与接入共用同一把锁，保证客户端要么进入本局，
                    # 要么收到 game_in_progress，不能卡在两者之间。
                    if not self.running:
                        client_info = None
                        rejection = None
                    elif self.game_running:
                        client_info = None
                        rejection = {
                            'code': 'game_in_progress',
                            'message': '游戏已开始，请稍后重连。',
                        }
                    elif len(self.clients) >= self.MAX_PLAYERS:
                        client_info = None
                        rejection = {
                            'code': 'room_full',
                            'message': f'房间已满（{self.MAX_PLAYERS}/{self.MAX_PLAYERS}）。',
                        }
                    else:
                        rejection = None
                        client_id = self._next_client_id
                        self._next_client_id += 1
                        client_info = {
                            'socket': client_socket,
                            'address': address,
                            'name': f"Player_{client_id}",
                            'outbox': queue.Queue(maxsize=256),
                            'closed': False,
                            'last_sequence': -1,
                        }
                    if client_info is not None:
                        self.clients.append(client_info)
                if client_info is None:
                    if rejection is not None:
                        send_packet(client_socket, {
                            'type': 'error',
                            **rejection,
                        })
                    self._close_socket(client_socket)
                    continue

                threading.Thread(
                    target=self.write_client,
                    args=(client_info,),
                    daemon=True,
                ).start()
                threading.Thread(
                    target=self.read_client,
                    args=(client_info,),
                    daemon=True,
                ).start()
                self._send_to_client(client_info, {
                    'type': 'welcome',
                    'player_name': client_info['name'],
                    'player_count': self.client_count,
                    'max_players': self.MAX_PLAYERS,
                })
                message = {
                    'type': 'system',
                    'message': f"欢迎 {client_info['name']} 加入服务器！",
                    'player_count': self.client_count,
                    'max_players': self.MAX_PLAYERS,
                }
                self.broadcast(message)
                self._emit_ui('message', message)
                self._emit_ui('client_count', self.client_count)
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"接受客户端连接时出错: {e}")
                    time.sleep(0.1)

    @property
    def client_count(self):
        with self.clients_lock:
            return len(self.clients)

    def read_client(self, client_info):
        decoder = MessageBuffer()
        sock = client_info['socket']
        try:
            while self.running and not client_info['closed']:
                try:
                    data = sock.recv(65536)
                except socket.timeout:
                    continue
                if not data:
                    break
                for message in decoder.feed(data):
                    validate_client_message(message)
                    self.incoming.put((client_info, message))
        except (OSError, ProtocolError) as exc:
            if self.running and not client_info['closed']:
                self._send_to_client(client_info, {
                    'type': 'error',
                    'code': 'protocol_error',
                    'message': str(exc),
                })
        finally:
            self.remove_client(client_info)

    def write_client(self, client_info):
        try:
            while self.running and not client_info['closed']:
                try:
                    message = client_info['outbox'].get(timeout=0.5)
                except queue.Empty:
                    continue
                if message is None:
                    break
                send_packet(client_info['socket'], message)
        except OSError:
            pass
        finally:
            self.remove_client(client_info)

    def dispatch_messages(self):
        while self.running:
            try:
                client, message = self.incoming.get(timeout=0.1)
            except queue.Empty:
                continue
            message_type = message.get('type')
            if message_type == 'chat':
                outgoing = {
                    'type': 'chat',
                    'sender': client['name'],
                    'message': message['message'].strip(),
                }
                self.broadcast(outgoing)
                self._emit_ui('message', outgoing)
            elif message_type == 'action' and self.game_running:
                sequence = message['sequence']
                if sequence <= client['last_sequence']:
                    continue
                client['last_sequence'] = sequence
                self.game_commands.put({
                    'player': client['name'],
                    'sequence': sequence,
                    'action': message['action'],
                })
            elif message_type == 'ping':
                self._send_to_client(client, {
                    'type': 'pong',
                    'client_time': message.get('client_time'),
                    'server_time': time.time(),
                })

    def remove_client(self, client_info):
        with self.clients_lock:
            if client_info['closed']:
                return
            client_info['closed'] = True
            if client_info in self.clients:
                self.clients.remove(client_info)
            count = len(self.clients)
        self._close_socket(client_info['socket'])
        try:
            client_info['outbox'].put_nowait(None)
        except queue.Full:
            pass
        self.game_commands.put({
            'player': client_info['name'],
            'sequence': client_info['last_sequence'] + 1,
            'action': {'type': 'quit_game'},
        })
        leave_msg = {
            'type': 'system',
            'message': f"{client_info['name']} 离开了服务器",
            'player_count': count,
            'max_players': self.MAX_PLAYERS,
        }
        self.broadcast(leave_msg)
        self._emit_ui('message', leave_msg)
        self._emit_ui('client_count', count)

    def _send_to_client(self, client, message):
        if client['closed']:
            return False
        try:
            client['outbox'].put_nowait(message)
            return True
        except queue.Full:
            self._close_socket(client['socket'])
            return False

    def broadcast(self, message):
        with self.clients_lock:
            clients = list(self.clients)
        for client in clients:
            self._send_to_client(client, message)

    def send_message(self, message_text):
        message = {
            'type': 'chat',
            'sender': 'Server',
            'message': message_text
        }
        self.broadcast(message)
        self._emit_ui('message', message)

    def get_server_info(self):
        return {
            'ip': self.local_ip,
            'port': self.port,
            'player_count': self.client_count,
            'max_players': self.MAX_PLAYERS,
        }

    def _emit_ui(self, event_type, payload):
        self.ui_events.put((event_type, payload))

    def poll_ui_events(self):
        """只由 Pygame 主线程调用，在这里执行 UI 回调。"""
        while True:
            try:
                event_type, payload = self.ui_events.get_nowait()
            except queue.Empty:
                break
            if event_type == 'message' and self.message_callback:
                self.message_callback(payload)
            elif event_type == 'client_count' and self.client_count_callback:
                self.client_count_callback(payload)

    def _drain_game_commands(self):
        commands = []
        while True:
            try:
                commands.append(self.game_commands.get_nowait())
            except queue.Empty:
                return commands

    def game_loop(self, game):
        try:
            next_tick = time.perf_counter()
            next_sync = next_tick
            while self.running and self.game_running:
                now = time.perf_counter()
                if now < next_tick:
                    time.sleep(next_tick - now)
                    continue
                game_running = game.step(
                    self.tick_interval,
                    self._drain_game_commands(),
                )
                next_tick += self.tick_interval
                now = time.perf_counter()
                if now >= next_sync:
                    state_msg = {'type': 'sync', **game.snapshot()}
                    self.broadcast(state_msg)
                    next_sync = now + self.sync_interval
                if not game_running:
                    break
                if now - next_tick > self.tick_interval:
                    next_tick = now + self.tick_interval
        finally:
            with self.clients_lock:
                self.game_running = False
            self.current_game = None
            game_running_msg = {
                'type': 'game_end',
                'message': '游戏循环已结束',
                'player_count': self.client_count,
                'max_players': self.MAX_PLAYERS,
            }
            self.broadcast(game_running_msg)
            self._emit_ui('message', game_running_msg)

    def start_game(self):
        with self.clients_lock:
            if not self.running or self.game_running:
                return False
            clients = list(self.clients)
            if not clients:
                return False
            self.game_running = True
        try:
            game = GameWorld(
                [client['name'] for client in clients],
                world_size=(const.wsize, const.hsize),
            )
        except Exception:
            with self.clients_lock:
                self.game_running = False
            raise
        self.current_game = game
        snapshot = game.snapshot()
        for client in clients:
            self._send_to_client(client, {
                'type': 'game_start',
                'you': client['name'],
                **snapshot,
            })
        threading.Thread(target=self.game_loop, args=(game,), daemon=True).start()
        return True

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
    
    def update_server_info(self, ip, port, player_count, max_players=ROOM_CAPACITY):
        self.texts["ip"] = mFont(f"IP地址: {ip}", "font/BoutiqueBitmap9x9_Bold_1.9.TTF", const.text_size, (0, 0, 0), (const.wsize-70, 150))
        self.texts["port"] = mFont(f"端口: {port}", "font/BoutiqueBitmap9x9_Bold_1.9.TTF", const.text_size, (0, 0, 0), (const.wsize-70, 190))
        self.texts["players"] = mFont(f"在线人数: {player_count}/{max_players}", "font/BoutiqueBitmap9x9_Bold_1.9.TTF", const.text_size, (0, 0, 0), (260, 190))
    
    def update_start_button(self, is_running):
        # 只更新按钮文本，不新建对象，避免状态丢失
        btn = self.buttons["start"]
        btn.title = "停止服务器" if is_running else "启动服务器"
        btn.mfont = ASSETS.font(btn.path, btn.size)
        btn.text = ASSETS.text(btn.title, btn.path, btn.size, btn.color)
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
        font = ASSETS.font(
            "font/BoutiqueBitmap9x9_Bold_1.9.TTF",
            int(const.text_size * 0.8),
        )
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
                    msg_surface = ASSETS.text(
                        line, "font/BoutiqueBitmap9x9_Bold_1.9.TTF",
                        int(const.text_size * 0.8), color,
                    )
                    screen.blit(msg_surface, (chat_rect.left + 10, y_offset))
                    y_offset += line_height
                    line = word + " "
                else:
                    line = test_line
            # 绘制最后一行
            if line:
                msg_surface = ASSETS.text(
                    line, "font/BoutiqueBitmap9x9_Bold_1.9.TTF",
                    int(const.text_size * 0.8), color,
                )
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
        elif message['type'] in ('system', 'game_end'):
            self.text_ui.add_system_message(message['message'], time.strftime("%H:%M:%S"))
            self.player_count = message['player_count']
            if self.server and self.server_status == "运行中":
                server_info = self.server.get_server_info()
                self.text_ui.update_server_info(
                    server_info['ip'], server_info['port'], self.player_count,
                    server_info['max_players'],
                )
    
    def on_client_count_change(self, count):
        """处理客户端数量变化"""
        self.player_count = count
        if self.server and self.server_status == "运行中":
            server_info = self.server.get_server_info()
            self.text_ui.update_server_info(
                server_info['ip'], server_info['port'], self.player_count,
                server_info['max_players'],
            )
    
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
                if not self.server.start_game():
                    self.text_ui.add_system_message(
                        "无法开始：请确认已有玩家连接且当前没有进行中的游戏。",
                        time.strftime("%H:%M:%S"),
                    )
        
        # 处理输入框事件
        if input_result["action"] == "send":
            message = input_result["data"]
            if message:
                self.send_message(message)
        
        return True
    def update_ui(self):
        # 始终根据当前状态刷新按钮文本
        if self.server_status == "运行中":
            server_info = self.server.get_server_info() if self.server else {
                "ip": "", "port": "", "player_count": 0,
                "max_players": ROOM_CAPACITY,
            }
            self.text_ui.update_server_info(
                server_info['ip'], server_info['port'], self.player_count,
                server_info['max_players'],
            )
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
                    const.set_resolution(event.w, event.h)
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

            # 网络线程只写入队列，所有 Pygame/UI 更新都在主线程执行。
            if self.server:
                self.server.poll_ui_events()

            # 绘制界面
            self.update_ui()
            self.draw()
            clock.tick(const.RENDER_FPS)
