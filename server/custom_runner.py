# custom_runner.py
import socket
import json
import sys
import random
import importlib
import os
import traceback

# プロジェクトルートをパスに追加
project_root = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, project_root)

from scripts import script_user  # 来場者がいじるファイル

# ---- script_user から呼ばれる API（コマンドを貯めるだけ） ----
class RemoteAPI:
    def __init__(self):
        self.commands = []
        # config.json から元の値を読む（api.GameAPI と同じ発想）
        self.original_config = {}
        self._load_original_config()

    def _load_original_config(self):
        try:
            with open('config/config.json', 'r', encoding='utf-8') as f:
                self.original_config = json.load(f)
        except Exception:
            self.original_config = {}

    def get_original_config(self, key):
        keys = key.split('.')
        v = self.original_config
        for k in keys:
            if isinstance(v, dict):
                v = v.get(k)
            else:
                return None
        return v

    # ---- 乱数 ----
    def rand(self):
        return random.random()

    # ---- パラメータ変更系 → コマンドに変換 ----
    def set_gravity(self, g):
        # set_param ではなく set_config を使うように変更
        self.set_config("physics.gravity", g)

    def set_max_speed(self, v):
        # set_param ではなく set_config を使うように変更
        self.set_config("physics.max_speed", v)

    def set_config(self, key, value):
        self.commands.append({
            "op": "set_config",
            "key": key,
            "value": value,
        })

    def get_config(self, key):
        # state から現在の config を取得する（動的変更を反映）
        if hasattr(self, '_current_state') and 'config' in self._current_state:
            keys = key.split('.')
            current = self._current_state['config']
            for k in keys:
                if isinstance(current, dict) and k in current:
                    current = current[k]
                else:
                    return None
            return current
        # フォールバック: state が無い場合は original_config を返す
        return self.get_original_config(key)

    def update_config(self, config_dict):
        """
        JSON 形式で config を更新する
        例: api.update_config({"physics": {"gravity": 0.6, "max_speed": 15.0}})
        ネストされたキーは自動的に処理される
        """
        def flatten_dict(d, parent_key=''):
            """ネストされた辞書をフラット化する"""
            items = []
            for k, v in d.items():
                new_key = f"{parent_key}.{k}" if parent_key else k
                if isinstance(v, dict):
                    items.extend(flatten_dict(v, new_key).items())
                else:
                    items.append((new_key, v))
            return dict(items)
        
        flat_config = flatten_dict(config_dict)
        print(f"[DEBUG] update_config called with {len(flat_config)} items") # Debug print
        for key, value in flat_config.items():
            print(f"[DEBUG] set_config: {key} = {value}") # Debug print
            self.set_config(key, value)

    # ---- 敵関連 ----
    def set_enemy_vel(self, enemy_id, vx, vy=None):
        cmd = {
            "op": "set_enemy_vel",
            "id": enemy_id,
        }
        if vx is not None:
            cmd["vx"] = vx
        if vy is not None:
            cmd["vy"] = vy
        self.commands.append(cmd)

    def set_enemy_pos(self, enemy_id, x=None, y=None):
        if x is None and y is None:
            return
        cmd = {
            "op": "set_enemy_pos",
            "id": enemy_id,
        }
        if x is not None:
            cmd["x"] = x
        if y is not None:
            cmd["y"] = y
        self.commands.append(cmd)

    def set_enemy_scale(self, enemy_id, scale):
        if scale is None:
            return
        if enemy_id is None and enemy_id != "all":
            return
        cmd = {
            "op": "set_enemy_scale",
            "scale": float(scale)
        }
        if enemy_id == "all":
            cmd["id"] = "all"
        else:
            cmd["id"] = enemy_id
        self.commands.append(cmd)

    def enemy_jump(self, enemy_id):
        self.commands.append({
            "op": "enemy_jump",
            "id": enemy_id,
        })

    def spawn_enemy(self, x, y, use_gravity=True, speed=2, scale=1.0, 
                    stomp_kills_enemy=True, touch_kills_player=True, bounce_on_stomp=True):
        self.commands.append({
            "op": "spawn_enemy",
            "x": x,
            "y": y,
            "use_gravity": bool(use_gravity),
            "speed": float(speed),
            "scale": float(scale),
            "stomp_kills_enemy": bool(stomp_kills_enemy),
            "touch_kills_player": bool(touch_kills_player),
            "bounce_on_stomp": bool(bounce_on_stomp),
        })

    def show_text(self, text, duration=3.0, color=(255, 255, 255)):
        """画面右上にテキストを表示する（display_textへのエイリアス）"""
        self.display_text(text, duration, color)
    
    def display_text(self, text, duration=3.0, color=(255, 255, 255)):
        """画面右上にテキストを表示する"""
        self.commands.append({
            "op": "display_text",
            "text": str(text),
            "duration": float(duration),
            "color": list(color)
        })

    def spawn_snake(self, x, y, width=60, height=20, speed=3, move_range=150, scale=1.0,
                    stomp_kills_enemy=True, touch_kills_player=True, bounce_on_stomp=True):
        """重力を受けない蛇タイプの敵を生成"""
        self.commands.append({
            "op": "spawn_snake",
            "x": x,
            "y": y,
            "width": width,
            "height": height,
            "speed": speed,
            "move_range": move_range,
            "scale": float(scale),
            "stomp_kills_enemy": bool(stomp_kills_enemy),
            "touch_kills_player": bool(touch_kills_player),
            "bounce_on_stomp": bool(bounce_on_stomp),
        })

    def set_max_jumps(self, max_jumps):
        """プレイヤーの最大ジャンプ回数を設定（複数段ジャンプ）"""
        self.commands.append({
            "op": "set_max_jumps",
            "value": int(max_jumps),
        })

    def set_player_pos(self, x=None, y=None):
        if x is None and y is None:
            return
        cmd = {"op": "set_player_pos"}
        if x is not None:
            cmd["x"] = x
        if y is not None:
            cmd["y"] = y
        self.commands.append(cmd)

    def set_player_vel(self, vx=None, vy=None, limit=False):
        if vx is None and vy is None:
            return
        cmd = {"op": "set_player_vel"}
        if vx is not None:
            cmd["vx"] = vx
        if vy is not None:
            cmd["vy"] = vy
        # include whether to apply max_speed limit; default False -> no limit
        if limit:
            cmd["limit"] = True
        self.commands.append(cmd)

    def set_player_scale(self, scale):
        if scale is None:
            return
        self.commands.append({
            "op": "set_player_scale",
            "scale": float(scale)
        })

    # ---- 背景色 ----
    def set_bg_color(self, rgb):
        self.commands.append({
            "op": "set_bg_color",
            "color": list(rgb),
        })

    # ---- ゴール ----
    def move_goal(self, dx, dy=0):
        self.commands.append({
            "op": "move_goal",
            "dx": dx,
            "dy": dy,
        })

    def get_goal_pos(self):
        # state から取得（main.py で state に goal を載せている）
        if hasattr(self, '_current_state') and 'goal' in self._current_state:
            return self._current_state['goal']
        return None

    def get_camera_pos(self):
        # state からカメラ座標を取得（main.py で state["world"]["camera_x"] に載せている）
        if hasattr(self, '_current_state') and 'world' in self._current_state and 'camera_x' in self._current_state['world']:
            return {'x': self._current_state['world']['camera_x'], 'y': 0}
        return None

    def set_goal_pos(self, x, y):
        self.commands.append({
            "op": "set_goal_pos",
            "x": x,
            "y": y,
        })

    # ---- 足場 ----
    def set_platform_velocity(self, platform_index, vx, vy):
        self.commands.append({
            "op": "set_platform_velocity",
            "index": platform_index,
            "vx": vx,
            "vy": vy,
        })

    def stop_platform(self, platform_index):
        self.commands.append({
            "op": "stop_platform",
            "index": platform_index,
        })

    def get_platform_pos(self, platform_index):
        # state から取得（main.py で state に platforms を載せている）
        if hasattr(self, '_current_state') and 'platforms' in self._current_state:
            platforms = self._current_state['platforms']
            if 0 <= platform_index < len(platforms):
                return platforms[platform_index]
        return None

    # ---- オーバーレイ描画API ----
    def draw_circle(self, x, y, radius, color, width=0):
        """画面上に円を描画（オーバーレイ）- x,yは世界座標（カメラ位置を自動補正）"""
        camera = self.get_camera_pos()
        screen_x = x
        if camera:
            screen_x = x - camera['x']
        self.commands.append({
            "op": "draw_circle",
            "x": int(screen_x),
            "y": int(y),
            "radius": int(radius),
            "color": list(color),
            "width": int(width),
        })

    def draw_rect(self, x, y, width, height, color, line_width=0):
        """画面上に矩形を描画（オーバーレイ）- x,yは世界座標（カメラ位置を自動補正）"""
        camera = self.get_camera_pos()
        screen_x = x
        if camera:
            screen_x = x - camera['x']
        self.commands.append({
            "op": "draw_rect",
            "x": int(screen_x),
            "y": int(y),
            "width": int(width),
            "height": int(height),
            "color": list(color),
            "line_width": int(line_width),
        })

    def draw_line(self, start_x, start_y, end_x, end_y, color, width=1):
        """画面上に線を描画（オーバーレイ）- x座標は世界座標（カメラ位置を自動補正）"""
        camera = self.get_camera_pos()
        screen_start_x = start_x
        screen_end_x = end_x
        if camera:
            screen_start_x = start_x - camera['x']
            screen_end_x = end_x - camera['x']
        self.commands.append({
            "op": "draw_line",
            "start_x": int(screen_start_x),
            "start_y": int(start_y),
            "end_x": int(screen_end_x),
            "end_y": int(end_y),
            "color": list(color),
            "width": int(width),
        })

    def draw_enemy_overlay(self, enemy_id, shape="rect", color=(255, 0, 0), size=50, line_width=0):
        """
        指定した敵の位置にオーバーレイ図形を描画
        
        Parameters:
        - enemy_id: 敵のID（"all" で全敵に適用）
        - shape: "rect" (四角) または "circle" (円)
        - color: RGB タプル
        - size: 図形のサイズ（rect なら幅=高さ、circle なら半径）
        - line_width: 0 で塗りつぶし、1以上で枠線のみ
        """
        self.commands.append({
            "op": "draw_enemy_overlay",
            "enemy_id": enemy_id,
            "shape": shape,
            "color": list(color),
            "size": int(size),
            "line_width": int(line_width),
        })

    def clear_overlay(self):
        """オーバーレイをクリア"""
        self.commands.append({
            "op": "clear_overlay",
        })

    # ---- 敵との衝突判定設定 ----
    def set_enemy_collision(self, stomp_kills_enemy=None, touch_kills_player=None, bounce_on_stomp=None):
        """
        敵との衝突判定を設定
        
        引数:
            stomp_kills_enemy: 踏むと敵を倒すか(True/False)
            touch_kills_player: 触れるとプレイヤーが死ぬか(True/False)
            bounce_on_stomp: 踏んだ時にバウンスするか(True/False)
        """
        if stomp_kills_enemy is not None:
            self.commands.append({
                "op": "set_enemy_collision",
                "key": "stomp_kills_enemy",
                "value": bool(stomp_kills_enemy)
            })
        if touch_kills_player is not None:
            self.commands.append({
                "op": "set_enemy_collision",
                "key": "touch_kills_player",
                "value": bool(touch_kills_player)
            })
        if bounce_on_stomp is not None:
            self.commands.append({
                "op": "set_enemy_collision",
                "key": "bounce_on_stomp",
                "value": bool(bounce_on_stomp)
            })

    # ---- 高レベルAPI ----

    def spawn_symmetric(self, enemy_id, offset_x=60, speed=None, scale=None, use_gravity=None):
        """指定した敵の左右に対称な位置に敵を2体生成するヘルパー

        enemy_id: オリジナル敵の id
        offset_x: 元の敵の x から左右に離す距離（世界座標）
        speed: 生成時に上書きする速度（省略可）
        scale: 生成時に上書きするスケール（省略可）
        use_gravity: 生成時に上書きする重力フラグ（省略可）
        """
        # Runner 側では現在の state が保持されているので、ここで元の敵情報を参照する
        if not hasattr(self, '_current_state'):
            return
        enemies = self._current_state.get('enemies', [])
        base = None
        for e in enemies:
            if e.get('id') == enemy_id:
                base = e
                break
        if base is None:
            return

        # Debug print to runner's stdout so game host can see
        print(f"spawn_symmetric called for id={enemy_id}, base={base}")

        bx = base.get('x', 0)
        by = base.get('y', 0)
        bwidth = base.get('width') or 40
        bheight = base.get('height') or 40
        bmove_range = base.get('move_range') or 100
        bscale = base.get('scale') if base.get('scale') is not None else 1.0
        busg = base.get('use_gravity') if base.get('use_gravity') is not None else True
        bspeed = base.get('speed') if base.get('speed') is not None else 2.0

        # 左右の world_x を決定
        left_x = bx - offset_x
        right_x = bx + offset_x

        # 可能なら上書き
        spawn_speed = float(speed) if speed is not None else float(bspeed)
        spawn_scale = float(scale) if scale is not None else float(bscale)
        spawn_use_gravity = bool(use_gravity) if use_gravity is not None else bool(busg)

        # 2体生成コマンドを追加
        # ログも送っておく（ゲーム内のテキスト表示）
        self.commands.append({"op":"runner_log", "msg": f"spawn_symmetric: base_id={enemy_id}, left={left_x}, right={right_x}, speed={spawn_speed}, scale={spawn_scale}"})
        # include size/move_range so main can reproduce similar enemies
        self.commands.append({
            "op": "spawn_enemy",
            "x": left_x,
            "y": by,
            "use_gravity": spawn_use_gravity,
            "speed": spawn_speed,
            "scale": spawn_scale,
            "move_range": bmove_range,
            "width": bwidth,
            "height": bheight,
        })
        # pass explicit extras as additional keys in command dict (spawn_enemy accepts extra fields)
        self.commands.append({
            "op": "spawn_enemy",
            "x": right_x,
            "y": by,
            "use_gravity": spawn_use_gravity,
            "speed": spawn_speed,
            "scale": spawn_scale,
            "move_range": bmove_range,
            "width": bwidth,
            "height": bheight,
        })




    def spawn_enemy_periodically(self, state, memory, interval_ms=1000, spawn_chance=0.5, offset_x=400):
        """
        定期的にプレイヤーの先に敵を出現させる
        
        引数:
            state: ゲーム状態
            memory: メモリdict（"last_spawn_time"キーを使用）
            interval_ms: 出現間隔（ミリ秒）
            spawn_chance: 出現確率（0.0〜1.0）
            offset_x: プレイヤーからのx方向のオフセット
        """
        if "last_spawn_time" not in memory:
            memory["last_spawn_time"] = 0
        
        now = state["world"]["time_ms"]
        px = state["player"]["x"]
        py = state["player"]["y"]
        
        if now - memory["last_spawn_time"] > interval_ms:
            memory["last_spawn_time"] = now
            if self.rand() < spawn_chance:
                self.spawn_enemy(x=px + offset_x, y=py)

    def enemy_chase_and_jump(self, state, memory, chase_distance=150, jump_chance=0.01, jump_cooldown_ms=500):
        """
        全敵をプレイヤー追尾させ、近い場合はランダムでジャンプ
        """
        if "enemy_jump_cooldown" not in memory:
            memory["enemy_jump_cooldown"] = {}
        
        now = state["world"]["time_ms"]
        px = state["player"]["x"]
        
        for enemy in state["enemies"]:
            enemy_id = enemy["id"]
            dx = px - enemy["x"]
            
            # 敵が近い場合はジャンプの判定
            if abs(dx) < chase_distance:
                # クールダウン管理
                if enemy_id not in memory["enemy_jump_cooldown"]:
                    memory["enemy_jump_cooldown"][enemy_id] = 0
                
                # クールダウンが終わっていれば、一定確率でジャンプ
                if now - memory["enemy_jump_cooldown"][enemy_id] > jump_cooldown_ms:
                    if self.rand() < jump_chance:
                        self.enemy_jump(enemy_id)
                        memory["enemy_jump_cooldown"][enemy_id] = now

    def goal_move_on_approach(self, state, memory, approach_distance=50, move_dy=-200, spawn_enemy_at_goal=True):
        """
        ゴールに接近したらゴールを移動し、元の位置に敵を出現させる（1回のみ）
        
        引数:
            state: ゲーム状態
            memory: メモリdict（"goal_approached"キーを使用）
            approach_distance: 接近と判定する距離
            move_dy: ゴールを移動させるy方向の距離
            spawn_enemy_at_goal: ゴールの元の位置に敵を出現させるか
        """
        if "goal_approached" not in memory:
            memory["goal_approached"] = False
        
        px = state["player"]["x"]
        goal_pos = self.get_goal_pos()
        
        if goal_pos:
            goal_dist = abs(px - goal_pos["x"])
            
            if goal_dist < approach_distance and not memory["goal_approached"]:
                memory["goal_approached"] = True
                if spawn_enemy_at_goal:
                    self.spawn_enemy(x=goal_pos["x"], y=goal_pos["y"])
                self.move_goal(0, move_dy)

    def platform_oscillate(self, memory, platform_indices=[0, 1], speeds=[(0, -1), (0, 1)], move_range=80):
        """
        足場を往復運動させる（上下・左右・斜め対応）
        """
        if "platform_initial_pos" not in memory:
            memory["platform_initial_pos"] = {}
        if "platform_speeds" not in memory:
            memory["platform_speeds"] = {}
        if "platform_range" not in memory:
            memory["platform_range"] = move_range
        
        for idx, platform_index in enumerate(platform_indices):
            pos = self.get_platform_pos(platform_index)
            if pos:
                # 初期座標と速度を記録（初回のみ）
                if platform_index not in memory["platform_initial_pos"]:
                    memory["platform_initial_pos"][platform_index] = {"x": pos["x"], "y": pos["y"]}
                    # 初回に速度を設定
                    if idx < len(speeds):
                        vx, vy = speeds[idx]
                        memory["platform_speeds"][platform_index] = {"vx": vx, "vy": vy}
                        self.set_platform_velocity(platform_index, vx, vy)
                
                initial_pos = memory["platform_initial_pos"][platform_index]
                current_speed = memory["platform_speeds"][platform_index]
                platform_range = memory["platform_range"]
                
                # 移動範囲を超えたら方向転換
                new_vx = current_speed["vx"]
                new_vy = current_speed["vy"]
                
                # Y方向のチェック
                if pos["y"] < initial_pos["y"] - platform_range and current_speed["vy"] < 0:
                    new_vy = -current_speed["vy"]  # 下に反転
                elif pos["y"] > initial_pos["y"] + platform_range and current_speed["vy"] > 0:
                    new_vy = -current_speed["vy"]  # 上に反転
                
                # X方向のチェック
                if pos["x"] < initial_pos["x"] - platform_range and current_speed["vx"] < 0:
                    new_vx = -current_speed["vx"]  # 右に反転
                elif pos["x"] > initial_pos["x"] + platform_range and current_speed["vx"] > 0:
                    new_vx = -current_speed["vx"]  # 左に反転
                
                # 速度が変わった場合のみ更新
                if new_vx != current_speed["vx"] or new_vy != current_speed["vy"]:
                    memory["platform_speeds"][platform_index] = {"vx": new_vx, "vy": new_vy}
                    self.set_platform_velocity(platform_index, new_vx, new_vy)


def main():
    host = "127.0.0.1"
    port = 50000

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))
    f_r = sock.makefile("r")
    f_w = sock.makefile("w")

    api = RemoteAPI()
    did_init = False
    
    print("[DEBUG] custom_runner started") # Debug print

    # script_user をリロードして最新のコードを読み込む
    # ファイルの最終更新時刻を監視し、変更があれば実行時に再読み込みする
    script_path = os.path.join(project_root, "scripts", "script_user.py")
    try:
        last_mtime = os.path.getmtime(script_path)
    except Exception:
        last_mtime = 0
    importlib.reload(script_user)

    while True:
        line = f_r.readline()
        if not line:
            break
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue

        if msg.get("type") != "tick":
            continue

        state = msg["state"]

        # script_user.py がファイル上で更新されていれば再読み込みする
        try:
            mtime = os.path.getmtime(script_path)
            if mtime != last_mtime:
                last_mtime = mtime
                try:
                    importlib.reload(script_user)
                    # reload 時は on_init を再実行させる
                    did_init = False
                    # ゲーム側にスクリプト更新通知を送る
                    try:
                        log_cmd = {"type": "commands", "commands": [
                            {"op": "display_text", "text": "✓ Updated", "duration": 5.0, "color": [0, 200, 0]},
                            {"op": "runner_log", "msg": "script_user.py changed - reloaded"}
                        ]}
                        f_w.write(json.dumps(log_cmd) + "\n")
                        f_w.flush()
                    except Exception:
                        # ログ送信に失敗しても無視
                        pass
                except Exception as e:
                    print("script_user reload error:", e, file=sys.stderr)
                    # エラーを画面に表示（シンプルに）
                    try:
                        err_cmd = {"type": "commands", "commands": [
                            {"op": "display_text", "text": "⚠ Error", "duration": 3.0, "color": [255, 0, 0]}
                        ]}
                        f_w.write(json.dumps(err_cmd) + "\n")
                        f_w.flush()
                    except Exception:
                        pass
        except Exception:
            # ファイルアクセスできない場合は無視
            pass
        
        # API に現在の state を保持させる
        api._current_state = state

        # 初回だけ on_init を呼ぶ（あれば）
        if not did_init and hasattr(script_user, "on_init"):
            try:
                api.commands.clear()
                script_user.on_init(state, api)
                cmds_init = api.commands[:]
                api.commands.clear()
                if cmds_init:
                    out = json.dumps({"type": "commands", "commands": cmds_init})
                    f_w.write(out + "\n")
                    f_w.flush()
            except Exception as e:
                # 標準エラー出力に出す代わりに、ゲーム側へエラー内容を送る
                try:
                    err = traceback.format_exc()
                    f_w.write(json.dumps({"type": "commands", "commands": [
                        {"op": "display_text", "text": "⚠ Error", "duration": 3.0, "color": [255, 0, 0]},
                        {"op": "runner_error", "msg": str(e), "trace": err}
                    ]}) + "\n")
                    f_w.flush()
                except Exception:
                    pass
                print("on_init error:", e, file=sys.stderr)
            did_init = True

        # 毎フレーム on_tick 呼び出し
        try:
            api.commands.clear()
            script_user.on_tick(state, api)
            cmds = api.commands[:]
            api.commands.clear()
        except Exception as e:
            # ゲーム側に例外内容を送る
            try:
                err = traceback.format_exc()
                f_w.write(json.dumps({"type": "commands", "commands": [
                    {"op": "display_text", "text": "⚠ Error", "duration": 3.0, "color": [255, 0, 0]},
                    {"op": "runner_error", "msg": str(e), "trace": err}
                ]}) + "\n")
                f_w.flush()
            except Exception:
                pass
            print("on_tick error:", e, file=sys.stderr)
            cmds = []

        out = json.dumps({"type": "commands", "commands": cmds})
        f_w.write(out + "\n")
        f_w.flush()

if __name__ == "__main__":
    main()
