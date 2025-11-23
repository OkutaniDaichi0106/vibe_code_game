# 来場者が編集するスクリプト（デフォルト版）
# このファイルを編集してゲームをカスタマイズしてください！

memory = {}  # ゲームの状態を記憶する辞書（待機時間、タイマーなど）

def on_init(state, api):
    """
    ゲーム開始時（ゲーム起動時・リセット時）に1回だけ実行されます。
    ここで設定を変更してからゲームを起動してください。
    """
    # ---------- ゲームの物理演算 ----------
    # api.update_config を使ってゲームの設定を変更します。
    api.update_config({
        
        # ---------- プレイヤー設定 ----------
        """
        前提条件
        デフォルトのプレイヤーの幅は 40 ピクセル、高さは 60 ピクセル、座標の基準点は中心（x軸）と足元（y軸）である。
        デフォルトの小ジャンプの高さが100ピクセル、大ジャンプの高さが150ピクセルである。

"""
        "player": {
            "x": 200,          # プレイヤーの初期位置（画面左端からの距離）
            "scale": 1,
        },
        
        # ---------- 物理演算 ----------
        "physics": {
            "gravity": 0.8,           # 重力（高いほど落下が速くなる）
            "jump_strength": -10,     # ジャンプ力（負の値で上方向に作用）
            "acceleration": 0.333,    # 加速度（高いほど素早く加速）
            "deceleration": 0.2,      # 減速度（高いほど素早く減速）
            "max_speed": 5.33,        # 最大速度
            "bg_scroll_speed": 5      # 背景スクロール速度
        },
        
        # ---------- 地面設定 ----------
        "ground": {
            "y_offset": 80,           # 画面下部から地面までの距離
        },
        
        # ---------- ゴール（クリア条件） ----------
        "goal": {
            "world_x": 3000,  # ゴールの世界座標 X
            "world_y": 0,     # ゴールの世界座標 Y（相対）
            "width": 60,      # ゴールの幅
            "height": 80,     # ゴールの高さ
        },
        
        # ---------- 敵設定 ----------
        """
        前提条件
        デフォルトの敵の幅は 40 ピクセル、高さは 40 ピクセル、座標の基準点は中心（x軸）と足元（y軸）である。

"""       
        "enemies": [
            # 敵 1: 高い位置にいる敵
            {
            "world_x": 385,        # 敵の世界座標 X
            "move_range": 80,      # 敵が左右に動く幅
            "speed": 2,            # 敵の移動速度
            "width": 40,           # 敵の幅
            "height": 40,          # 敵の高さ
            "scale": 1,            # 表示スケール
            "use_gravity": True,  # 重力を使うか（False = 空中に浮く）
            "y_offset": 127,       # 地面からの高さ
            "stomp_kills_enemy": True,    # 踏むと敵を倒すか
            "touch_kills_player": True,   # 触れるとプレイヤーが死ぬか
            "bounce_on_stomp": True       # 踏んだ時にバウンスするか
            },
            # 敵 2: 中間の高さにいる敵
            {
            "world_x": 1065,
            "move_range": 60,
            "speed": 1.5,
            "width": 40,
            "height": 40,
            "scale": 1,
            "use_gravity": False,
            # y_offset がない場合は 0（地面上）
            "stomp_kills_enemy": True,
            "touch_kills_player": True,
            "bounce_on_stomp": True
            },
            # 敵 3: 低い位置にいる敵
            {
            "world_x": 1941,
            "move_range": 100,
            "speed": 2,
            "width": 40,
            "height": 40,
            "scale": 1,
            "use_gravity": False,
            "y_offset": 112,
            "stomp_kills_enemy": True,
            "touch_kills_player": True,
            "bounce_on_stomp": True
            }
        ],
        
        # ---------- 足場（ジャンプ用の足場） ----------
        "platforms": [
            # 足場 1: 最初の足場
            {"world_x": 300, "y_offset": 100, "width": 150},
            # 足場 2
            {"world_x": 698, "y_offset": 110, "width": 160},
            # 足場 3
            {"world_x": 1300, "y_offset": 120, "width": 150},
            # 足場 4
            {"world_x": 2098, "y_offset": 84, "width": 120},
            # 足場 5
            {"world_x": 2289, "y_offset": 148, "width": 120},
            # 足場 6
            {"world_x": 2484, "y_offset": 87, "width": 140},
            # 足場 7: ゴール付近の足場
            {"world_x": 2720, "y_offset": 40, "width": 160}
        ],
        
        # ---------- 崖（地面がないエリア） ----------

        # 崖の間は地面がないので落ちるとゲームオーバー
        "cliffs": [
            # 崖 1
            {"start_x": 590, "end_x": 905},
            # 崖 2
            {"start_x": 1237, "end_x": 1653},
            # 崖 3: 最後の大きな崖
            {"start_x": 2041, "end_x": 2919}
        ]

    })
  
def on_tick(state, api):
    # # プレイヤー位置と現在時刻を取得
    # px = state["player"]["x"]
    # py = state["player"]["y"]
    # now = state["world"]["time_ms"]

    # # ---------- ゴールに仕掛けるトラップの処理 (明示的な引数) ----------
    # api.goal_move_on_approach(state, memory, approach_distance=50, move_dy=-200, spawn_enemy_at_goal=True)
    # # ---------- プレイヤーに追従する敵の処理 (明示的な引数) ----------
    # api.enemy_chase_and_jump(state, memory, chase_distance=150, jump_chance=0.01, jump_cooldown_ms=500)
    # # ---------- 一定間隔で敵が出現する処理 (明示的にデフォルトを指定) ----------
    # api.spawn_enemy_periodically(state, memory, interval_ms=1000, spawn_chance=0.5, offset_x=400)
    # # ---------- 足場が動く処理 (明示的にデフォルトを指定) ----------
    # api.platform_oscillate(memory, platform_indices=[0, 1], speeds=[(0, -1), (0, 1)], move_range=80)

    pass

    