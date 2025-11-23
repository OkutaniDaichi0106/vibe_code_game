import pygame
import sys
import json
import random
import socket
import subprocess
import os
import time
import argparse
# import script_user  # TCP版では不要
# from api import GameAPI  # TCP版では不要
from player import Player
from enemy import Enemy
from level import load_level, is_on_ground

# =========================
# 設定の読み込み
# =========================
with open('config/config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)

# コマンドライン引数で設定を上書き
parser = argparse.ArgumentParser(description="Vibe Code Game")
parser.add_argument("--width", type=int, help="Screen width")
parser.add_argument("--height", type=int, help="Screen height")
parser.add_argument("--fps", type=int, help="FPS")
args = parser.parse_args()

if args.width:
    config['screen']['width'] = args.width
if args.height:
    config['screen']['height'] = args.height
if args.fps:
    config['screen']['fps'] = args.fps

# 設定値を変数に展開
SCREEN_WIDTH = config['screen']['width']
SCREEN_HEIGHT = config['screen']['height']
FPS = config['screen']['fps']

PLAYER_X = config['player']['x']
GROUND_Y = SCREEN_HEIGHT - config['ground']['y_offset']

# 物理パラメータは config から直接読むため、ここでの変数展開は削除
# BG_SCROLL_SPEED = config['physics']['bg_scroll_speed']
# ACCELERATION = config['physics']['acceleration']
# DECELERATION = config['physics']['deceleration']
# MAX_SPEED = config['physics']['max_speed']

# =========================
# 初期化
# =========================
pygame.init()
pygame.mixer.init()
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Side-scrolling Game (Parallax Background)")
clock = pygame.time.Clock()

# 日本語フォントの設定
font_path = "C:/Windows/Fonts/msgothic.ttc"
if os.path.exists(font_path):
    font = pygame.font.Font(font_path, 16)
    large_font = pygame.font.Font(font_path, 20)  # さらに小さく
else:
    font = pygame.font.SysFont("meiryo", 16)
    large_font = pygame.font.SysFont("meiryo", 20)

# 背景画像の読み込み
try:
    bg_image = pygame.image.load('assets/background.png').convert()
    bg_width = bg_image.get_width()
    bg_height = bg_image.get_height()
except:
    bg_image = None
    bg_width = SCREEN_WIDTH
    bg_height = SCREEN_HEIGHT

# タイトル画像の読み込み
try:
    title_image = pygame.image.load('assets/title.png').convert_alpha()
except:
    title_image = None

# 効果音の読み込み
try:
    jump_sound = pygame.mixer.Sound('assets/jump.mp3')
    player_dead_sound = pygame.mixer.Sound('assets/player_dead.mp3')
    enemy_dead_sound = pygame.mixer.Sound('assets/enemy_dead.mp3')
    clear_sound = pygame.mixer.Sound('assets/clear.mp3')
except Exception as e:
    print(f"Failed to load sound effects: {e}")
    jump_sound = None
    player_dead_sound = None
    enemy_dead_sound = None
    clear_sound = None

# =========================
# プレイヤー
# =========================
# GRAVITY = config['physics']['gravity']  # 削除
player = Player(PLAYER_X, GROUND_Y, config)

# ゲーム状態
game_over = False
game_clear = False
game_started = False  # タイトル画面の状態を追加

# オーバーレイ描画リスト
overlay_drawings = []


# 敵との衝突判定設定（APIで変更可能）
enemy_collision_config = {
    "stomp_kills_enemy": True,  # 踏むと敵を倒すか
    "touch_kills_player": True,  # 触れるとプレイヤーが死ぬか
    "bounce_on_stomp": True,     # 踏んだ時にバウンスするか
}

# このフレームで踏んだ・触れた敵のIDリスト
stomped_enemies_this_frame = []
touched_enemies_this_frame = []

# テキスト表示用
display_text = None
display_text_timer = 0
display_text_color = (255, 255, 255)

# AIステータス表示用（右上に常時表示）
ai_status_text = None
ai_status_timer = 0  # プロンプト表示用のタイマー
last_generating_check = 0
last_prompt_check = 0
prompt_flag_shown = False  # プロンプトフラグを既に読み込んだかどうか

# =========================
# 背景（単色＋地面を自前描画）
#   → 実際には画像を読み込んでもOK
# =========================
BG_WIDTH = config['background']['tile_width']
camera_x = 0.0           # カメラのx位置（世界座標）
camera_vx = 0.0          # カメラの速度（慣性用）
camera_target_x = None   # camera を徐々に合わせたい目標座標（None なら追従なし）

# カメラ追従の設定
# 遠いほど強く近づけるため、距離に応じた比例ゲインで速度を決める
CAMERA_FOLLOW_GAIN = 0.12  # 距離 -> 補間速度の比例係数
CAMERA_FOLLOW_MAX = 40.0   # 追従速度の上限

# =========================
# 敵を複数配置
# =========================
enemies = [
    Enemy(world_x=e['world_x'], 
          y=GROUND_Y - e.get('y_offset', 0), 
          move_range=e['move_range'], speed=e['speed'],
          width=e['width'], height=e['height'],
          scale=e.get('scale', 1.0),
          use_gravity=e.get('use_gravity', True),
          stomp_kills_enemy=e.get('stomp_kills_enemy', True),
          touch_kills_player=e.get('touch_kills_player', True),
          bounce_on_stomp=e.get('bounce_on_stomp', True))
    for e in config['enemies']
]

# =========================
# レベル（足場・地面・ゴール）をロード
# =========================
platforms, goal = load_level(config, GROUND_Y)
cliffs = config.get('cliffs', [])

# =========================
# 状態スナップショット関数
# =========================
def make_state():
    return {
        "player": {
            "x": camera_x + player.x_screen,  # 世界座標
            "screen_x": player.x_screen,  # 画面座標
            "y": player.y,
            "vy": player.vy,
            "on_ground": not player.is_jumping,
        },
        "world": {
            "time_ms": pygame.time.get_ticks(),
            "camera_x": camera_x,
            "gravity": config['physics']['gravity'],
        },
        "enemies": [
            {
                "id": e.id,
                "x": e.world_x,
                "y": e.y,
                "use_gravity": e.use_gravity,
                "speed": getattr(e, 'speed', None),
                "move_range": getattr(e, 'move_range', None),
                "width": getattr(e, 'width', None),
                "height": getattr(e, 'height', None),
                "scale": getattr(e, 'scale', None),
            }
            for e in enemies
        ],
        "goal": {"x": goal.world_x, "y": goal.y},
        "platforms": [
            {"x": p.world_x, "y": p.y}
            for p in platforms
        ],
        "collision": {
            "stomped_enemies": stomped_enemies_this_frame,  # このフレームで踏んだ敵のIDリスト
            "touched_enemies": touched_enemies_this_frame,  # このフレームで触れた敵のIDリスト
        },
    }

# =========================
# TCP接続クラス
# =========================
class CustomConnection:
    def __init__(self, host="127.0.0.1", port=50000):
        self.host = host
        self.port = port
        self.server_sock = None
        self.conn = None
        self.buf = b""
        self.proc = None

    def start(self):
        # サーバソケット
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.bind((self.host, self.port))
        self.server_sock.listen(1)

        # custom_runner.py を起動
        # デバッグ用に stdout/stderr を表示するように変更
        self.proc = subprocess.Popen(
            [sys.executable, "server/custom_runner.py"],
            # stdout=subprocess.DEVNULL,
            # stderr=subprocess.STDOUT,
        )

        print("Waiting for custom_runner...")
        self.conn, addr = self.server_sock.accept()
        print("custom_runner connected from", addr)
        self.conn.setblocking(False)

    def restart(self):
        if self.proc and self.proc.poll() is None:
            self.proc.kill()
        if self.conn:
            self.conn.close()
        if self.server_sock:
            self.server_sock.close()
        self.conn = None
        self.server_sock = None
        self.start()

    def send_state(self, state):
        if not self.conn:
            return
        try:
            msg = json.dumps({"type": "tick", "state": state}) + "\n"
            self.conn.sendall(msg.encode("utf-8"))
        except OSError:
            print("send failed, restarting custom_runner")
            self.restart()

    def poll_commands(self):
        if not self.conn:
            return
        try:
            data = self.conn.recv(4096)
            if not data:
                print("custom_runner disconnected, restarting")
                self.restart()
                return
            self.buf += data
        except BlockingIOError:
            pass

        while b"\n" in self.buf:
            line, self.buf = self.buf.split(b"\n", 1)
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line.decode("utf-8"))
            except json.JSONDecodeError:
                continue
            if msg.get("type") == "commands":
                for c in msg.get("commands", []):
                    yield c

# =========================
# コマンド適用関数
# =========================
def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def apply_command(cmd):
    global config, display_text, display_text_timer, display_text_color
    global enemies, platforms, goal, cliffs, SCREEN_WIDTH, SCREEN_HEIGHT, FPS, GROUND_Y, BG_WIDTH
    global camera_x, camera_vx, camera_target_x
    global ai_status_text, ai_status_timer, last_generating_check, last_prompt_check, prompt_flag_shown

    op = cmd.get("op")

    # set_param は set_config に統合されたため削除（互換性のため残す場合は set_config へ転送）
    if op == "set_param":
        # custom_runner 側で set_config に変換しているはずだが、念のため
        key = cmd.get("key")
        val = cmd.get("value")
        if key == "gravity":
            config['physics']['gravity'] = clamp(float(val), -5.0, 5.0)
        elif key == "max_speed":
            config['physics']['max_speed'] = clamp(float(val), 0.5, 30.0)

    elif op == "set_config":
        key = cmd.get("key", "")
        val = cmd.get("value")
        keys = key.split(".")
        cur = config
        for k in keys[:-1]:
            if k not in cur or not isinstance(cur[k], dict):
                cur[k] = {}
            cur = cur[k]
        cur[keys[-1]] = val

        # --- 動的な反映処理 ---
        if key == "enemies":
            enemies.clear()
            enemies.extend([
                Enemy(world_x=e['world_x'], 
                      y=GROUND_Y - e.get('y_offset', 0), 
                      move_range=e['move_range'], speed=e['speed'],
                      width=e['width'], height=e['height'],
                      scale=e.get('scale', 1.0),
                      use_gravity=e.get('use_gravity', True),
                      stomp_kills_enemy=e.get('stomp_kills_enemy', True),
                      touch_kills_player=e.get('touch_kills_player', True),
                      bounce_on_stomp=e.get('bounce_on_stomp', True))
                for e in val
            ])
        elif key == "platforms":
            new_platforms, _ = load_level(config, GROUND_Y)
            platforms.clear()
            platforms.extend(new_platforms)
        elif key == "goal":
            _, new_goal = load_level(config, GROUND_Y)
            goal = new_goal
        elif key.startswith("goal."):
            # ゴールのプロパティが変更された場合も再ロード
            _, new_goal = load_level(config, GROUND_Y)
            goal = new_goal
        elif key == "cliffs":
            cliffs = val
        elif key == "ground.y_offset":
            GROUND_Y = SCREEN_HEIGHT - val
            # 地面が変わったら足場とゴールも再配置
            new_platforms, new_goal = load_level(config, GROUND_Y)
            platforms.clear()
            platforms.extend(new_platforms)
            goal = new_goal
        elif key == "screen.width":
            SCREEN_WIDTH = val
            pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        elif key == "screen.height":
            SCREEN_HEIGHT = val
            pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        elif key == "screen.fps":
            FPS = val
        elif key.startswith("player."):
            if key == "player.width": player.width = val
            elif key == "player.height": player.height = val
            elif key == "player.x": player.x_screen = val
            elif key == "player.color": player.color = tuple(val)
            elif key == "player.scale": player.set_scale(float(val))
        elif key.startswith("enemy."):
            parts = key.split(".")
            if len(parts) == 3 and parts[1].isdigit():
                idx = int(parts[1])
                prop = parts[2]
                if 0 <= idx < len(enemies):
                    if prop == "scale":
                        enemies[idx].set_scale(float(val))
        elif key.startswith("background."):
            if key == "background.tile_width":
                BG_WIDTH = val

    elif op == "spawn_enemy":
        if len(enemies) >= 30:
            return
        x = float(cmd.get("x", camera_x + 800))
        y = float(cmd.get("y", GROUND_Y))
        speed = float(cmd.get("speed", 2.0))
        use_gravity = bool(cmd.get("use_gravity", True))
        scale = float(cmd.get("scale", 1.0))
        move_range = int(cmd.get("move_range", 100))
        width = int(cmd.get("width", 40))
        height = int(cmd.get("height", 40))
        stomp_kills_enemy = bool(cmd.get("stomp_kills_enemy", True))
        touch_kills_player = bool(cmd.get("touch_kills_player", True))
        bounce_on_stomp = bool(cmd.get("bounce_on_stomp", True))
        print(f"[DEBUG] spawn_enemy cmd: x={x}, y={y}, speed={speed}, scale={scale}, use_gravity={use_gravity}, move_range={move_range}, width={width}, height={height}")
        enemies.append(
            Enemy(world_x=x, y=y, move_range=move_range, speed=speed,
                  width=width, height=height, scale=scale, use_gravity=use_gravity,
                  stomp_kills_enemy=stomp_kills_enemy, touch_kills_player=touch_kills_player,
                  bounce_on_stomp=bounce_on_stomp)
        )

    elif op == "spawn_snake":
        if len(enemies) >= 30:
            return
        x = float(cmd.get("x", camera_x + 800))
        y = float(cmd.get("y", 300))
        width = int(cmd.get("width", 60))
        height = int(cmd.get("height", 20))
        speed = float(cmd.get("speed", 3))
        move_range = int(cmd.get("move_range", 150))
        scale = float(cmd.get("scale", 1.0))
        stomp_kills_enemy = bool(cmd.get("stomp_kills_enemy", True))
        touch_kills_player = bool(cmd.get("touch_kills_player", True))
        bounce_on_stomp = bool(cmd.get("bounce_on_stomp", True))
        snake = Enemy(world_x=x, y=y, move_range=move_range, speed=speed,
                     width=width, height=height, scale=scale, use_gravity=False,
                     stomp_kills_enemy=stomp_kills_enemy, touch_kills_player=touch_kills_player,
                     bounce_on_stomp=bounce_on_stomp)
        snake.color = (0, 200, 0)  # 緑色で蛇らしく
        enemies.append(snake)

    elif op == "set_max_jumps":
        max_jumps = int(cmd.get("value", 2))
        player.max_jumps = max(1, min(max_jumps, 10))  # 1〜10回の範囲
        player.jump_count = 0

    elif op == "set_enemy_vel":
        eid = cmd.get("id")
        vx_raw = cmd.get("vx")
        vy_raw = cmd.get("vy")
        if eid is None or (vx_raw is None and vy_raw is None):
            return

        vx = float(vx_raw) if vx_raw is not None else None
        vy = float(vy_raw) if vy_raw is not None else None
        MAX_V = 15.0

        if vx is not None and vy is not None:
            speed2 = vx * vx + vy * vy
            if speed2 > MAX_V * MAX_V:
                scale = MAX_V / (speed2 ** 0.5)
                vx *= scale
                vy *= scale
        elif vx is not None:
            vx = clamp(vx, -MAX_V, MAX_V)
        elif vy is not None:
            vy = clamp(vy, -MAX_V, MAX_V)

        for e in enemies:
            if e.id == eid:
                e.use_api_control = True
                if vx is not None:
                    e.vx = vx
                if vy is not None:
                    e.vy = vy
                break

    elif op == "set_enemy_scale":
        eid = cmd.get("id")
        scale = cmd.get("scale")
        if scale is None:
            return
        target_all = eid == "all"
        if eid is None and not target_all:
            return
        try:
            scale_value = float(scale)
        except (TypeError, ValueError):
            return

        for e in enemies:
            if target_all or e.id == eid:
                e.set_scale(scale_value)
                if not target_all:
                    break

    elif op == "set_enemy_pos":
        eid = cmd.get("id")
        if eid is None:
            return
        x = cmd.get("x")
        y = cmd.get("y")
        if x is None and y is None:
            return

        for e in enemies:
            if e.id == eid:
                if x is not None:
                    new_x = float(x)
                    e.world_x = new_x
                    e.center_x = new_x  # keep patrol origin in sync
                if y is not None:
                    e.y = float(y)
                    if e.use_gravity:
                        e.vy = 0
                break

    elif op == "enemy_jump":
        eid = cmd.get("id")
        jump_strength = -15
        for e in enemies:
            if e.id == eid:
                if e.y >= GROUND_Y:
                    e.vy = jump_strength
                break

    elif op == "set_player_pos":
        x = cmd.get("x")
        y = cmd.get("y")
        if x is not None:
            # 直接ジャンプしてカメラをテレポートするのではなく、目標位置に追従する
            camera_target_x = float(x) - player.x_screen
        if y is not None:
            player.y = float(y)

    elif op == "set_player_vel":
        vx = cmd.get("vx")
        vy = cmd.get("vy")
        limit = bool(cmd.get("limit", False))
        if vx is not None:
            max_spd = max(0.0, float(config['physics']['max_speed']))
            if limit:
                camera_vx = clamp(float(vx), -max_spd, max_spd)
            else:
                camera_vx = float(vx)
        if vy is not None:
            MAX_PLAYER_VY = 60.0
            player.vy = clamp(float(vy), -MAX_PLAYER_VY, MAX_PLAYER_VY)

    elif op == "set_player_scale":
        scale = cmd.get("scale")
        if scale is None:
            return
        try:
            player.set_scale(float(scale))
        except (TypeError, ValueError):
            return

    elif op == "set_bg_color":
        col = cmd.get("color", [135, 206, 235])
        r = clamp(int(col[0]), 0, 255)
        g = clamp(int(col[1]), 0, 255)
        b = clamp(int(col[2]), 0, 255)
        config['background']['color'] = [r, g, b]

    elif op == "move_goal":
        dx = float(cmd.get("dx", 0.0))
        dy = float(cmd.get("dy", 0.0))
        goal.world_x += dx
        goal.y += dy

    elif op == "set_goal_pos":
        goal.world_x = float(cmd.get("x", goal.world_x))
        goal.y = float(cmd.get("y", goal.y))

    elif op == "set_platform_velocity":
        idx = int(cmd.get("index", -1))
        vx = float(cmd.get("vx", 0.0))
        vy = float(cmd.get("vy", 0.0))
        if 0 <= idx < len(platforms):
            platforms[idx].set_velocity(vx, vy)

    elif op == "stop_platform":
        idx = int(cmd.get("index", -1))
        if 0 <= idx < len(platforms):
            platforms[idx].stop()

    elif op == "show_text":
        text = cmd.get("text", "")
        duration = float(cmd.get("duration", 3.0))
        color = cmd.get("color", [255, 255, 255])
        
        display_text = text
        display_text_timer = int(duration * FPS)
        display_text_color = tuple(color)

    elif op == "display_text":
        text = cmd.get("text", "")
        duration = float(cmd.get("duration", 3.0))
        color = cmd.get("color", [255, 255, 255])
        
        display_text = text
        display_text_timer = int(duration * FPS)
        display_text_color = tuple(color)

    elif op == "runner_log":
        # custom_runner からのログを表示
        msg = cmd.get("msg", "")
        print(f"[runner] {msg}")
    elif op == "runner_error":
        # custom_runner 側で発生した例外を表示（トレースバック含む）
        msg = cmd.get("msg", "")
        trace = cmd.get("trace", "")
        print(f"[runner ERROR] {msg}")
        if trace:
            print(trace)

    elif op == "draw_circle":
        x = cmd.get("x", 0)
        y = cmd.get("y", 0)
        radius = cmd.get("radius", 10)
        color = tuple(cmd.get("color", [255, 255, 255]))
        width = cmd.get("width", 0)
        overlay_drawings.append({
            "type": "circle",
            "x": x,
            "y": y,
            "radius": radius,
            "color": color,
            "width": width,
        })

    elif op == "draw_rect":
        x = cmd.get("x", 0)
        y = cmd.get("y", 0)
        width = cmd.get("width", 10)
        height = cmd.get("height", 10)
        color = tuple(cmd.get("color", [255, 255, 255]))
        line_width = cmd.get("line_width", 0)
        overlay_drawings.append({
            "type": "rect",
            "x": x,
            "y": y,
            "width": width,
            "height": height,
            "color": color,
            "line_width": line_width,
        })

    elif op == "draw_line":
        start_x = cmd.get("start_x", 0)
        start_y = cmd.get("start_y", 0)
        end_x = cmd.get("end_x", 0)
        end_y = cmd.get("end_y", 0)
        color = tuple(cmd.get("color", [255, 255, 255]))
        width = cmd.get("width", 1)
        overlay_drawings.append({
            "type": "line",
            "start_x": start_x,
            "start_y": start_y,
            "end_x": end_x,
            "end_y": end_y,
            "color": color,
            "width": width,
        })

    elif op == "clear_overlay":
        overlay_drawings.clear()

    elif op == "draw_enemy_overlay":
        enemy_id = cmd.get("enemy_id")
        shape = cmd.get("shape", "rect")
        color = tuple(cmd.get("color", [255, 0, 0]))
        size = cmd.get("size", 50)
        line_width = cmd.get("line_width", 0)
        
        # 対象の敵を取得
        target_enemies = []
        if enemy_id == "all":
            target_enemies = enemies
        else:
            for e in enemies:
                if e.id == enemy_id:
                    target_enemies.append(e)
                    break
        
        # 各敵にオーバーレイを描画
        for e in target_enemies:
            ex = int(e.world_x - camera_x)
            ey = int(e.y - e.height // 2)
            
            if shape == "circle":
                overlay_drawings.append({
                    "type": "circle",
                    "x": ex,
                    "y": ey,
                    "radius": size,
                    "color": color,
                    "width": line_width,
                })
            else:  # rect
                overlay_drawings.append({
                    "type": "rect",
                    "x": ex - size // 2,
                    "y": ey - size // 2,
                    "width": size,
                    "height": size,
                    "color": color,
                    "line_width": line_width,
                })

    elif op == "set_enemy_collision":
        key = cmd.get("key")
        value = cmd.get("value")
        if key in enemy_collision_config:
            enemy_collision_config[key] = bool(value)

# =========================
# ゲームリセット関数
# =========================
def reset_game():
    global game_over, game_clear, camera_x, camera_vx, enemies, platforms, goal, config, cliffs
    global camera_target_x
    global ai_status_text, ai_status_timer, prompt_flag_shown
    
    # 設定を再読み込み（オブジェクトIDを維持して更新）
    try:
        with open('config/config.json', 'r', encoding='utf-8') as f:
            new_config = json.load(f)
            config.clear()
            config.update(new_config)
    except Exception as e:
        print(f"Failed to reload config: {e}")
    
    game_over = False
    game_clear = False
    camera_x = 0.0
    camera_vx = 0.0
    camera_target_x = None
    
    player.reset()
    
    # 敵を再生成
    enemies.clear()
    enemies.extend([
        Enemy(world_x=e['world_x'], 
              y=GROUND_Y - e.get('y_offset', 0), 
              move_range=e['move_range'], speed=e['speed'],
              width=e['width'], height=e['height'],
              scale=e.get('scale', 1.0),
              use_gravity=e.get('use_gravity', True),
              stomp_kills_enemy=e.get('stomp_kills_enemy', True),
              touch_kills_player=e.get('touch_kills_player', True),
              bounce_on_stomp=e.get('bounce_on_stomp', True))
        for e in config['enemies']
    ])
    
    # 足場とゴールを再生成
    new_platforms, new_goal = load_level(config, GROUND_Y)
    platforms.clear()
    platforms.extend(new_platforms)
    goal = new_goal
    
    # 崖情報を更新
    cliffs = config.get('cliffs', [])
    
    # AIステータステキストをクリア
    ai_status_text = None
    ai_status_timer = 0
    prompt_flag_shown = False
    
    # オーバーレイをクリア
    overlay_drawings.clear()
    
    # 敵との衝突判定設定をリセット
    enemy_collision_config["stomp_kills_enemy"] = True
    enemy_collision_config["touch_kills_player"] = True
    enemy_collision_config["bounce_on_stomp"] = True
    
    # custom_runner を再起動（script_user.py の再読み込みと init 実行）
    custom_conn.restart()
    print("Game Reset!")

# =========================
# TCP接続を初期化
# =========================
custom_conn = CustomConnection()
custom_conn.start()

# =========================
# リロードフラグのチェック用
# =========================
last_reload_check = 0
RELOAD_INTERVAL_MS = 500  # 0.5秒に1回で十分

# =========================
# メインループ
# =========================
running = True
while running:
    dt = clock.tick(FPS)  # ミリ秒
    
    # リロードフラグのチェック
    now = pygame.time.get_ticks()
    if now - last_reload_check > RELOAD_INTERVAL_MS:
        last_reload_check = now
        if os.path.exists("reload.flag"):
            os.remove("reload.flag")
            custom_conn.restart()   # custom_runner を再起動 → 新しい script_user.py がimportされる
    # =========================
    # イベント処理
    # =========================
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        # タイトル画面中はスペースキーでゲーム開始
        if not game_started:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    game_started = True
        else:
            # スペースキーでジャンプ開始
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    # ジャンプ可能な場合のみSEを再生
                    if player.jump_count < player.max_jumps:
                        if jump_sound:
                            jump_sound.play()
                    player.start_jump()
                # R キーでリセット
                if event.key == pygame.K_r:
                    reset_game()
            # スペースキーを離したらジャンプ持続終了
            if event.type == pygame.KEYUP:
                if event.key == pygame.K_SPACE:
                    player.release_jump()

    # =========================
    # AIステータスチェック（0.5秒に1回）
    # =========================
    current_time = pygame.time.get_ticks()
    
    # コード生成中フラグをチェック
    if current_time - last_generating_check > 500:
        last_generating_check = current_time
        if os.path.exists("status_generating.flag"):
            try:
                with open("status_generating.flag", "r", encoding="utf-8") as f:
                    ai_status_text = f.read().strip()
                    ai_status_timer = 1800  # 30秒の上限（60fps想定）
                    prompt_flag_shown = False  # プロンプトはまだ表示されていない
            except:
                pass
        elif os.path.exists("status_custom.flag"):
            # カスタムステータス（/set_status API経由）
            try:
                with open("status_custom.flag", "r", encoding="utf-8") as f:
                    text = f.read().strip()
                    # display_text（右上）として表示
                    display_text = text
                    display_text_timer = 180  # 3秒
                    display_text_color = (0, 0, 0)
                os.remove("status_custom.flag")
            except:
                pass
        elif os.path.exists("status_prompt.flag") and not prompt_flag_shown:
            # プロンプト表示フラグをチェック（一度だけ読み込む）
            try:
                with open("status_prompt.flag", "r", encoding="utf-8") as f:
                    ai_status_text = f.read().strip()
                    ai_status_timer = 1800  # 30秒間表示（60fps想定）
                    prompt_flag_shown = True
                # 読み込んだらフラグを削除
                os.remove("status_prompt.flag")
            except:
                pass
        else:
            # どちらのフラグもない場合はタイマーをカウントダウン
            if ai_status_timer > 0:
                ai_status_timer -= 1
                if ai_status_timer == 0:
                    ai_status_text = None
                    prompt_flag_shown = False
    
    # =========================
    # 入力処理
    # =========================
    if not game_over and not game_clear and game_started:
        keys = pygame.key.get_pressed()
        
        # 慣性を使った横移動（configから毎フレーム取得）
        accel = config['physics']['acceleration']
        decel = config['physics']['deceleration']
        max_spd = config['physics']['max_speed']

        if keys[pygame.K_RIGHT]:
            camera_vx += accel
            if camera_vx > max_spd:
                camera_vx = max_spd
            player.facing_right = True  # 右向き
        elif keys[pygame.K_LEFT]:
            camera_vx -= accel
            if camera_vx < -max_spd:
                camera_vx = -max_spd
            player.facing_right = False  # 左向き
        else:
            # キーが押されていない時は減速
            if camera_vx > 0:
                camera_vx -= decel
                if camera_vx < 0:
                    camera_vx = 0
            elif camera_vx < 0:
                camera_vx += decel
                if camera_vx > 0:
                    camera_vx = 0
        
        camera_x += camera_vx

        # --- camera follow: 距離に応じた追従 ---
        # camera_target_x が設定されている場合、距離に応じて速く/遅く近づく
        if camera_target_x is not None:
            dx = camera_target_x - camera_x
            # 小さければ直接位置合わせして終了
            if abs(dx) < 0.5:
                camera_x = camera_target_x
                camera_target_x = None
            else:
                # 距離を元に補間速度を決める（遠いほど大きく）
                follow_vx = clamp(dx * CAMERA_FOLLOW_GAIN, -CAMERA_FOLLOW_MAX, CAMERA_FOLLOW_MAX)
                camera_x += follow_vx

    # タイトル画面中またはゲーム終了後は更新処理をスキップ
    if game_started and not game_over and not game_clear:
        # =========================
        # 足場の更新
        # =========================
        platform_moves = {}  # 各足場の移動量を記録
        for i, platform in enumerate(platforms):
            dy = platform.update()
            platform_moves[i] = dy

        # =========================
        # プレイヤーの物理演算（ジャンプ）
        # =========================
        # 敵と同様に、現在の GRAVITY を渡してランタイムで変更された値に追従させる
        previous_y = player.y
        player.update()

        # 段差との判定
        player_rect = player.get_rect()
        player_on_platform = None  # プレイヤーが乗っている足場
        
        for i, platform in enumerate(platforms):
            platform_rect = platform.get_rect(camera_x)
            
            # X軸の重なり判定
            if player_rect.right > platform_rect.left and player_rect.left < platform_rect.right:
                # Y軸の通過判定（すり抜け対策）
                # 前フレームで足場より上にいて、現フレームで足場以上（または通過）の位置にいる
                player_bottom = player.y + player.height
                previous_bottom = previous_y + player.height
                platform_top = platform_rect.top
                
                # 落下中 かつ 足場をまたいでいる場合
                if player.vy > 0:
                    # previous_bottom <= platform_top + 10 は、わずかなめり込みや誤差を許容するためのマージン
                    if previous_bottom <= platform_top + 10 and player_bottom >= platform_top:
                        player.land_on(platform_rect.top)
                        player_on_platform = i
                        # 複数の足場を同時に通過する可能性がある場合、最も高い位置（最初に見つかった有効な足場）で停止するのが自然
                        # ここではシンプルに見つかった時点で着地とする
                        break
        
        # 地面判定（崖でない場所のみ）
        player_world_x = camera_x + player.x_screen
        if player.y >= GROUND_Y - player.height and player.vy > 0:
            if is_on_ground(player_world_x, cliffs):
                # 地面がある場所に着地
                player.land_on(GROUND_Y)
            # 地面がない場所（崖）では着地しない
                    
        # プレイヤーが足場に乗っている場合、足場の移動に追従
        if player_on_platform is not None:
            dy = platform_moves[player_on_platform]
            if dy != 0:
                player.y += dy  # 足場の上下移動に追従

        # =========================
        # 更新処理
        # =========================
        current_gravity = config['physics']['gravity']
        for enemy in enemies:
            enemy.update(platforms, GROUND_Y, current_gravity, lambda x: is_on_ground(x, cliffs))
        
        # (state send will happen after collision detection so script_user gets up-to-date info)

        # 画面外に落ちた敵を削除
        enemies[:] = [e for e in enemies if e.y < SCREEN_HEIGHT + 100]

        # =========================
        # 当たり判定
        # =========================
        # このフレームの衝突情報をリセット
        stomped_enemies_this_frame.clear()
        touched_enemies_this_frame.clear()
        
        shoe_rect = player.get_shoe_rect()
        
        # 敵との衝突判定
        enemies_to_remove = []
        enemy_bounced = False  # 敵を踏んだかどうか
        last_stomped_enemy = None  # 最後に踏んだ敵（バウンス設定用）
        for enemy in enemies:
            enemy_rect = enemy.get_rect(camera_x)
            # 靴との当たり判定（敵が死ぬ）
            if shoe_rect.colliderect(enemy_rect) and player.vy > 0:
                stomped_enemies_this_frame.append(enemy.id)  # 踏んだ敵を記録
                if enemy.stomp_kills_enemy:
                    if enemy_dead_sound:
                        enemy_dead_sound.play()
                    enemies_to_remove.append(enemy)
                enemy_bounced = True  # 敵を踏んだ
                last_stomped_enemy = enemy
            # プレイヤー本体との当たり判定（ゲームオーバー）
            elif player_rect.colliderect(enemy_rect):
                touched_enemies_this_frame.append(enemy.id)  # 触れた敵を記録
                if enemy.touch_kills_player:
                    if player_dead_sound:
                        player_dead_sound.play()
                    game_over = True
        
        # ---- script_user（TCP越し）を呼ぶ ----
        # 衝突判定が済んだら、まだ敵を削除する前に state を送る
        # こうすることで script_user 側は踏んだ敵のプロパティも参照できる
        state_dict = make_state()
        custom_conn.send_state(state_dict)
        for cmd in custom_conn.poll_commands():
            apply_command(cmd)

        # 敵を削除（runner にコマンドが反映された後に削除）
        for enemy in enemies_to_remove:
            enemies.remove(enemy)

        # 敵を踏んだ場合のジャンプ処理
        if enemy_bounced and last_stomped_enemy and last_stomped_enemy.bounce_on_stomp:
            keys = pygame.key.get_pressed()
            player.stomp_enemy(keys[pygame.K_SPACE])

        # ゴール判定
        goal_rect = goal.get_rect(camera_x)
        if player_rect.colliderect(goal_rect):
            if clear_sound:
                clear_sound.play()
            game_clear = True

        # 崖判定（プレイヤーが地面の範囲外で、足場にも乗っていない場合）
        player_world_x = camera_x + player.x_screen
        if player.y >= GROUND_Y and not is_on_ground(player_world_x, cliffs) and player_on_platform is None:
            if player_dead_sound:
                player_dead_sound.play()
            game_over = True

        # 上方向へ画面外に出たら死亡にする（例: 重力が0のときの無限上昇対策）
        # プレイヤーの下端が画面上端よりさらに一定量上に行ったらゲームオーバー
        if player.y + player.height < -100:
            if player_dead_sound:
                player_dead_sound.play()
            game_over = True
    elif game_started:
        # ゲーム終了後、Rキーでリスタート
        keys = pygame.key.get_pressed()
        if keys[pygame.K_r]:
            reset_game()

    # =========================
    # 描画
    # =========================
    
    # タイトル画面の描画
    if not game_started:

        # 白背景で描画
        screen.fill((255, 255, 255))
        # タイトル画像をアスペクト比を保ってリサイズして描画
        if title_image:
            # 画面に対する最大サイズ（マージンを残す）
            max_w = int(SCREEN_WIDTH * 1.35)
            max_h = int(SCREEN_HEIGHT * 0.9)
            iw, ih = title_image.get_size()
            # scale <= 1.0 にして拡大しすぎないようにする（必要なら1.0を超える許可可）
            scale = min(max_w / iw, max_h / ih)
            new_w = max(1, int(iw * scale))
            new_h = max(1, int(ih * scale))
            try:
                scaled_title = pygame.transform.smoothscale(title_image, (new_w, new_h))
            except Exception:
                scaled_title = pygame.transform.scale(title_image, (new_w, new_h))

            # 画像を中央やや上に配置し、スタート文は画像の下に表示
            title_rect = scaled_title.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 20))
            screen.blit(scaled_title, title_rect)




        pygame.display.flip()
        continue  # ゲーム画面の描画をスキップ
    
    # 背景画像のスクロール描画
    if bg_image:
        # カメラ位置に応じた背景のオフセットを計算（視差効果のため、少し遅めにスクロール）
        bg_scroll_x = int(camera_x * 0.5) % bg_width
        
        # 画面を埋めるために必要な枚数を計算
        num_tiles = (SCREEN_WIDTH // bg_width) + 2
        
        for i in range(num_tiles):
            x_pos = i * bg_width - bg_scroll_x
            # 背景画像を縦に拡大して描画
            scaled_bg = pygame.transform.scale(bg_image, (bg_width, SCREEN_HEIGHT))
            screen.blit(scaled_bg, (x_pos, 0))
    else:
        # 背景画像が読み込めない場合は単色
        screen.fill(tuple(config['background']['color']))

    # 地面（崖以外の部分を描画）
    # 画面内に見える範囲を計算
    view_start_x = camera_x
    view_end_x = camera_x + SCREEN_WIDTH
    
    # 現在の描画開始位置
    current_draw_x = view_start_x
    
    # 崖リストをソート（念のため）
    sorted_cliffs = sorted(cliffs, key=lambda c: c['start_x'])
    
    # 画面内の崖を探して、それ以外の部分を描画
    for cliff in sorted_cliffs:
        cliff_start = cliff['start_x']
        cliff_end = cliff['end_x']
        
        # 崖が現在の描画位置より右にある場合、そこまでを地面として描画
        if cliff_start > current_draw_x:
            # 描画範囲の終端（崖の始まり、または画面端）
            draw_end_x = min(cliff_start, view_end_x)
            
            if draw_end_x > current_draw_x:
                screen_x = int(current_draw_x - camera_x)
                width = int(draw_end_x - current_draw_x)
                
                ground_rect = pygame.Rect(screen_x, GROUND_Y, width, SCREEN_HEIGHT - GROUND_Y)
                pygame.draw.rect(screen, (255, 255, 255), ground_rect)
                pygame.draw.rect(screen, tuple(config['ground']['color']), ground_rect, 3)
        
        # 現在位置を崖の終わりに進める（ただし、崖が画面より左で終わっている場合は現在位置を変えない）
        if cliff_end > current_draw_x:
            current_draw_x = cliff_end
            
        # 画面外に出たら終了
        if current_draw_x >= view_end_x:
            break
            
    # 最後の崖の後ろから画面端までを描画
    if current_draw_x < view_end_x:
        screen_x = int(current_draw_x - camera_x)
        width = int(view_end_x - current_draw_x)
        
        ground_rect = pygame.Rect(screen_x, GROUND_Y, width, SCREEN_HEIGHT - GROUND_Y)
        pygame.draw.rect(screen, (255, 255, 255), ground_rect)
        pygame.draw.rect(screen, tuple(config['ground']['color']), ground_rect, 3)

    # プレイヤー（画面上で位置固定）
    # カメラが動いているか、またはキー入力がある場合に「動いている」とみなす
    is_moving = abs(camera_vx) > 0.1
    player.draw(screen, is_moving)

    # 段差
    for platform in platforms:
        platform.draw(screen, camera_x)

    # 敵
    for enemy in enemies:
        enemy.draw(screen, camera_x)

    # ゴール
    goal.draw(screen, camera_x)

    # 情報表示
    if game_over:
        info_text = "GAME OVER! Press R to restart"
        text_surf = font.render(info_text, True, (255, 0, 0))
        text_rect = text_surf.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
        screen.blit(text_surf, text_rect)
    elif game_clear:
        info_text = "GOAL! You cleared the game! Press R to restart"
        text_surf = font.render(info_text, True, (0, 200, 0))
        text_rect = text_surf.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
        screen.blit(text_surf, text_rect)
    else:
        info_text = f"Use LEFT/RIGHT to scroll / SPACE to jump / Enemies: {len(enemies)}"
        text_surf = font.render(info_text, True, (0, 0, 0))
        screen.blit(text_surf, (10, 10))

    # カスタムテキスト表示(右上) - シンプルな表示
    if display_text and display_text_timer > 0:
        # 黒文字、背景なし、枠線なし
        text_surf = large_font.render(display_text, True, (0, 0, 0)) # 強制的に黒

        text_w, text_h = text_surf.get_size()
        text_x = SCREEN_WIDTH - text_w - 10
        text_y = 10

        screen.blit(text_surf, (text_x, text_y))

        display_text_timer -= 1
    
    # AIステータステキスト表示（右上、display_textの下）
    if ai_status_text:
        status_surf = large_font.render(ai_status_text, True, (0, 0, 0))
        status_w, status_h = status_surf.get_size()
        status_x = SCREEN_WIDTH - status_w - 10
        status_y = 35  # display_textの下に表示
        screen.blit(status_surf, (status_x, status_y))

    # オーバーレイ描画
    for drawing in overlay_drawings:
        if drawing["type"] == "circle":
            pygame.draw.circle(screen, drawing["color"], (drawing["x"], drawing["y"]), drawing["radius"], drawing["width"])
        elif drawing["type"] == "rect":
            rect = pygame.Rect(drawing["x"], drawing["y"], drawing["width"], drawing["height"])
            pygame.draw.rect(screen, drawing["color"], rect, drawing["line_width"])
        elif drawing["type"] == "line":
            pygame.draw.line(screen, drawing["color"], (drawing["start_x"], drawing["start_y"]), (drawing["end_x"], drawing["end_y"]), drawing["width"])

    pygame.display.flip()

# 終了処理
pygame.quit()
sys.exit()
