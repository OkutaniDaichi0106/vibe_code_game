# Vibe Code Game

横スクロール型のプラットフォームゲームで、来場者が自然言語でゲームの挙動を変更できるインタラクティブな展示システムです。

## プロジェクト構造

```text
vibe_code_game/
├── src/                          # ゲームのコアコード
│   ├── main.py                   # メインゲームループ
│   ├── player.py                 # プレイヤークラス
│   ├── enemy.py                  # 敵クラス
│   └── level.py                  # レベル管理
│
├── scripts/                      # ユーザースクリプト
│   ├── script_user.py           # 実際に使用されるスクリプト
│   └── examples/                 # サンプルスクリプト集
│       └── default.py           # デフォルトサンプル
│
├── server/                       # サーバー関連
│   ├── server.py                # FastAPIサーバー
│   ├── custom_runner.py         # スクリプト実行ランナー
│   └── requirements_server.txt  # サーバー用依存関係
│
├── config/                       # 設定ファイル
│   └── config.json              # ゲーム設定
│
├── assets/                       # ゲームアセット
│   ├── enemy/                    # 敵アセット
│   ├── goal/                     # ゴールアセット
│   └── player/                   # プレイヤーアセット
│
├── docs/                         # ドキュメント
│   ├── AI_PROMPT.md              # AI用プロンプト
│   ├── API_REFERENCE.md          # API リファレンス
│   └── SERVER_SETUP.md           # サーバー設定手順
│
├── level_editor.py               # レベルエディタ
├── run_game.py                  # ゲーム起動スクリプト
├── run_server.py                # サーバー起動スクリプト
└── README.md                     # このファイル
```

## セットアップ

### 依存関係のインストール

```powershell
# ゲーム用
pip install pygame

# サーバー用（オプション）
pip install -r server/requirements_server.txt
```

### 環境変数の設定

`.env`ファイルにOpenAI APIキーを設定（サーバー機能を使う場合）:

```
OPENAI_API_KEY=your-api-key-here
```

## 起動方法

### ゲームのみを起動

```powershell
python run_game.py
```

または直接:

```powershell
cd src
python main.py
```

### サーバー付きで起動

1. サーバーを起動:

```powershell
python run_server.py
```

または直接:

```powershell
cd server
python server.py
```

2. 別のターミナルでゲームを起動:

```powershell
python run_game.py
```

3. ブラウザで `http://localhost:8000` にアクセスして、自然言語でゲームを改変

## 操作方法

- **左右キー**: カメラスクロール（プレイヤー移動）
- **スペースキー**: ジャンプ
- **Rキー**: リセット

## カスタマイズ

### スクリプトの編集

`scripts/script_user.py`を編集してゲームの挙動を変更できます。

サンプルスクリプトは`scripts/examples/`にあります。

### 設定の変更

`config/config.json`でゲームの各種パラメータを調整できます。

詳細は`docs/API_REFERENCE.md`を参照してください。

## ライセンス

MIT License
