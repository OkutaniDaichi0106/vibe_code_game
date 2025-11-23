# Script API リファレンス (簡易版)

`script_user.py` で利用できる公開 API 一覧。RemoteAPI 実装と同期済みで、不要・旧仕様は削除済みです。

## 目次

1. [乱数 / 基本](#乱数--基本)
2. [設定操作](#設定操作)
3. [プレイヤー制御](#プレイヤー制御)
4. [敵制御](#敵制御)
5. [ゴール制御](#ゴール制御)
6. [足場制御](#足場制御)
7. [背景 / 表示](#背景--表示)
8. [高レベル API](#高レベル-api)
9. [デバッグ / ログ](#デバッグ--ログ)
10. [注意点まとめ](#注意点まとめ)
11. [使用例](#使用例)

---

## 乱数 / 基本

### `api.rand()`

0.0〜1.0 の乱数を返します。

---

## 設定操作

### `api.set_gravity(g)`

重力を設定。範囲: -5.0〜5.0。

### `api.set_max_speed(v)`

入力加速による最大横速度。範囲: 0.5〜30.0。

### `api.set_config(key, value)`

単一キーを更新（ドット記法ネスト対応）。例: `api.set_config("player.scale", 2.0)` でプレイヤーサイズ2倍、`api.set_config("enemy.0.scale", 0.5)` で0番目の敵を半分サイズに。

### `api.get_config(key)` / `api.get_original_config(key)`

現在値 / 起動時の元値を取得。

### `api.update_config(dict_obj)`

ネスト辞書を展開し複数キー更新。

---

## プレイヤー制御

### `api.set_player_pos(x=None, y=None)`

プレイヤーのワールド座標を設定。`x` 指定時はカメラが距離依存速度でスムーズ追従。

### `api.set_player_vel(vx=None, vy=None, limit=False)`

横スクロール速度と垂直速度を直接上書き。`limit=True` の場合のみ `physics.max_speed` を適用。`vy` は安全のため内部で ±60 にクランプ。

### `api.set_max_jumps(n)`

最大ジャンプ回数 (1〜10)。着地でリセット。

### `api.set_player_scale(scale)`

プレイヤー全体の倍率を変更（0.25〜4.0）。足元を基準に拡縮するため、大きくしても地面にめり込まず、当たり判定/画像/靴も同時に調整されます。

---

## 敵制御

### `api.spawn_enemy(x, y, use_gravity=True, speed=2.0, scale=1.0, stomp_kills_enemy=True, touch_kills_player=True, bounce_on_stomp=True)`

通常敵を生成（最大 30 体）。`scale` でサイズ倍率を指定（0.25～4.0）。

**衝突判定パラメータ:**
- `stomp_kills_enemy`: 踏むと敵を倒すか（デフォルト: True）
- `touch_kills_player`: 触れるとプレイヤーが死ぬか（デフォルト: True）
- `bounce_on_stomp`: 踏んだ時にバウンスするか（デフォルト: True）

### `api.spawn_snake(x, y, width=60, height=20, speed=3, move_range=150, scale=1.0, stomp_kills_enemy=True, touch_kills_player=True, bounce_on_stomp=True)`

重力無しの往復移動蛇型敵。`scale` でサイズ倍率を指定（0.25～4.0）。

**衝突判定パラメータ:**
- `stomp_kills_enemy`: 踏むと敵を倒すか（デフォルト: True）
- `touch_kills_player`: 触れるとプレイヤーが死ぬか（デフォルト: True）
- `bounce_on_stomp`: 踏んだ時にバウンスするか（デフォルト: True）

### `api.set_enemy_vel(enemy_id, vx=None, vy=None)`

敵速度を直接指定。両軸指定時は合成速度が 15.0 を超えると正規化。片方のみならその軸を ±15 にクランプ。省略した軸は変更なし。

### `api.set_enemy_pos(enemy_id, x=None, y=None)`

敵位置を即時テレポート。`x` 指定時 patrol 原点も更新。`y` 指定＋重力ありなら `vy=0`。

### `api.enemy_jump(enemy_id)`

地面や足場上にいる敵をジャンプさせる（固定強さ）。

### `api.set_enemy_scale(enemy_id, scale)`

指定した敵（または `enemy_id="all"` で全員）の倍率を変更。範囲は 0.25～4.0。足元を基準に拡縮し、当たり判定とスプライトを一括で更新します。

### `api.set_enemy_collision(stomp_kills_enemy=None, touch_kills_player=None, bounce_on_stomp=None)`

全敵の衝突判定設定を変更（グローバル設定）。各パラメータは省略可能。

**例:**
```python
# 敵を踏んでも倒せないようにする
api.set_enemy_collision(stomp_kills_enemy=False)

# 敵に触れても死なないようにする
api.set_enemy_collision(touch_kills_player=False)

# バウンスを無効にする
api.set_enemy_collision(bounce_on_stomp=False)
```

**注意:** 各敵は `config.json` または `spawn_enemy`/`spawn_snake` のパラメータで個別に設定できます。このメソッドは既存の敵の設定を変更しません。

---

## ゴール制御

### `api.get_goal_pos()`

ゴール位置 `{"x": world_x, "y": y}` を取得。

### `api.move_goal(dx, dy=0)`

相対移動。

### `api.set_goal_pos(x, y)`

絶対座標で再配置。

### ゴール関連高レベル

`api.goal_move_on_approach(state, memory, ...)` 接近時にゴール退避＋元位置へ敵生成（1回）。

---

## 足場制御

### `api.get_platform_pos(index)`

足場の現在位置。

### `api.set_platform_velocity(index, vx, vy)`

足場の移動速度設定。

### `api.stop_platform(index)`

停止。

### 高レベル

`api.platform_oscillate(memory, ...)` 指定足場を往復運動。

---

## 背景 / 表示

### `api.set_bg_color((r,g,b))`

背景色を即時変更。

### `api.display_text(text, duration=3.0, color=(255,255,255))`

右上にメッセージ表示（再呼び出しで上書き）。

### `api.show_text(text, duration=3.0, color=(255,255,255))`

`display_text` のエイリアス（後方互換性のため残されています）。

---

## 高レベル API

### `api.spawn_enemy_periodically(state, memory, interval_ms=1000, spawn_chance=0.5, offset_x=400)`

一定間隔＋確率でプレイヤー前方に敵生成。

### `api.enemy_chase_and_jump(state, memory, chase_distance=150, jump_chance=0.01, jump_cooldown_ms=500)`

敵を追尾させ近距離でランダムジャンプ。

### `api.goal_move_on_approach(state, memory, approach_distance=50, move_dy=-200, spawn_enemy_at_goal=True)`

ゴール接近イベント演出。

### `api.platform_oscillate(memory, platform_indices=[0,1], speeds=[(0,-1),(0,1)], move_range=80)`

足場往復の自動反転制御。

---

## デバッグ / ログ

内部コマンド（直接 API 呼び出し不要）：

- `runner_log` ゲーム側へログ送信。
- `runner_error` スクリプト例外内容表示。

---

## 注意点まとめ

1. 入力操作による横加速は常に `physics.max_speed` 制限。`set_player_vel(limit=False)` は無制限。
2. 垂直速度は内部的に ±60 へクランプし物理暴走を防止。
3. 敵速度は合成 15.0 超過で正規化し不自然な瞬間移動を抑制。
4. 敵総数 30 超過の `spawn_enemy` / `spawn_snake` は無視。
5. `set_player_pos(x)` はカメラを滑らか追従させるため一瞬でジャンプしない。
6. 大き過ぎる `vx` を頻繁に与えると背景スクロールが粗く見える場合あり（演出目的で許容）。
7. `update_config` は構造丸ごと差し替えではなくキー更新用途推奨。

---

## 使用例

```python
# 物理設定をまとめて変更
api.update_config({"physics": {"gravity": 0.6, "max_speed": 12.0}})

# ゴールへ滑らか移動開始
goal = api.get_goal_pos()
if goal:
    api.set_player_pos(x=goal["x"])

# 敵へ高速ベクトル付与
for e in state["enemies"]:
    api.set_enemy_vel(e["id"], vx=14, vy=-12)

# 足場往復開始
api.platform_oscillate(memory, platform_indices=[0,1], speeds=[(0,-1),(0,1)], move_range=100)

# プレイヤーを巨大化
api.set_player_scale(1.8)

# メッセージ表示
api.display_text("Start!", duration=2.0)

# 衝突判定設定を持つ敵を生成
api.spawn_enemy(x=1000, y=400, stomp_kills_enemy=False, touch_kills_player=False)

# 全敵の衝突判定を変更
api.set_enemy_collision(touch_kills_player=False)
```

---

最終更新: RemoteAPI 実装と同期。
