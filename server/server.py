# server.py (ゲームPCで常駐させる)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel
import uvicorn
import openai

import os
import re
import json
from dotenv import load_dotenv
import google.generativeai as genai


load_dotenv()
app = FastAPI()

# APIプロバイダーの設定
api_provider = None
if os.getenv("OPENAI_API_KEY"):
    api_provider = "openai"
    openai.api_key = os.getenv("OPENAI_API_KEY")
elif os.getenv("GEMINI_API_KEY"):
    api_provider = "gemini"
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
else:
    print("警告: OPENAI_API_KEY または GEMINI_API_KEY 環境変数が設定されていません")

# CORS設定を追加（ngrokなど外部からのアクセスに対応）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # すべてのオリジンを許可（開発用）
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],  # 必要なメソッドのみ許可
    allow_headers=["*"],  # すべてのヘッダーを許可
)

class PromptBody(BaseModel):
    prompt: str


# ストリーム出力用の区切りトークン
COMMENT_START_TOKEN = "[[[COMMENT_START]]]"
COMMENT_END_TOKEN = "[[[COMMENT_END]]]"
CODE_START_TOKEN = "[[[CODE_START]]]"
CODE_END_TOKEN = "[[[CODE_END]]]"


def extract_code_block(full_text: str) -> str:
    """
    モデル出力テキストから CODE 部分だけを取り出す。
    見つからなければ空文字を返す。
    """
    start = full_text.find(CODE_START_TOKEN)
    if start == -1:
        return ""
    start += len(CODE_START_TOKEN)
    end = full_text.find(CODE_END_TOKEN, start)
    if end == -1:
        return ""
    return full_text[start:end].strip()


def extract_comment_block(full_text: str) -> str:
    """
    モデル出力テキストから COMMENT 部分だけを取り出す。
    見つからなければ空文字を返す。
    """
    start = full_text.find(COMMENT_START_TOKEN)
    if start == -1:
        return ""
    start += len(COMMENT_START_TOKEN)
    end = full_text.find(COMMENT_END_TOKEN, start)
    if end == -1:
        return ""
    return full_text[start:end].strip()


# AI_PROMPT.mdの内容を読み込み
def load_system_prompt():
    try:
        with open("docs/AI_PROMPT.md", "r", encoding="utf-8") as f:
            content = f.read()
        
        # script_user.pyの内容をリアルタイムで読み込み
        try:
            with open("scripts/script_user.py", "r", encoding="utf-8") as f:
                current_script = f.read()
            
            # AI_PROMPT.md内の既存script_user.py部分を現在の内容で置き換え
            pattern = r'## 既存の script_user\.py\n\n現在の `script_user\.py` の内容は以下の通りです：\n\n```python\n.*?\n```'
            replacement = (
                "## 既存の script_user.py\n\n"
                "現在の `script_user.py` の内容は以下の通りです：\n\n"
                f"```python\n{current_script}\n```"
            )
            content = re.sub(pattern, replacement, content, flags=re.DOTALL)
            
        except Exception as e:
            print(f"警告: script_user.py の読み込みに失敗しました: {e}")
        
        # AI_PROMPT.md の末尾に「ユーザーからの要望」セクションがあるので、そこまでを返す
        return content
    except Exception as e:
        return f"エラー: AI_PROMPT.md が読み込めませんでした - {e}"


@app.get("/", response_class=HTMLResponse)
async def index():
    # スマホ用の超シンプルUI
    return """
<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8" />
  <title>ゲーム改変プロンプト</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    body { font-family: system-ui, sans-serif; padding: 12px; }
    textarea { width: 100%; min-height: 140px; }
    button { padding: 8px 16px; margin-top: 8px; }
    .status { margin-top: 8px; white-space: pre-wrap; }
  </style>
</head>
<body>
  <h1>ゲーム改変プロンプト</h1>
  <p>例: 「敵が定期的に降って来るようにして」</p>
  <textarea id="prompt" placeholder="ここにやりたい改変内容を書いてください"></textarea><br>
  <button id="send">送信</button>
  <button id="reset" style="margin-left: 8px; background-color: #dc3545; color: white;">リセット</button>
  <div class="status" id="status"></div>
  <script>
    console.log("JavaScript loaded successfully!");
    
    const sendBtn = document.getElementById("send");
    const resetBtn = document.getElementById("reset");
    const promptEl = document.getElementById("prompt");
    const statusEl = document.getElementById("status");
    
    console.log("Elements found:", {sendBtn, resetBtn, promptEl, statusEl});
    
    // シンプルなテストから始める
    sendBtn.onclick = async () => {
      console.log("Send button clicked!");
      const prompt = promptEl.value.trim();
      if (!prompt) {
        statusEl.textContent = "プロンプトを入力してください。";
        return;
      }
      
      statusEl.textContent = "送信中...";
      
      try {
        const res = await fetch("/update_script_stream", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ prompt }),
        });
        console.log("Response status:", res.status, res.statusText);
        
        if (!res.ok) {
          statusEl.textContent = "エラー: " + res.status + " " + res.statusText;
          return;
        }
        
        // ストリーミングレスポンスの処理
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let commentShown = false;
        
        console.log("Starting to read stream");
        
        while (true) {
          const { done, value } = await reader.read();
          
          if (done) {
            // ストリーム終了時に残りのデータをデコード
            const remaining = decoder.decode();
            if (remaining) {
              buffer += remaining;
              console.log("Added remaining data:", remaining);
            }
            console.log("Stream ended, final buffer length:", buffer.length);
            console.log("Final buffer content:", buffer.substring(0, 200));
            break;
          }
          
          // 各チャンクをデコードしてバッファに追加
          const chunk = decoder.decode(value, { stream: true });
          buffer += chunk;
          
          // デバッグ: バッファの現在の状態を確認
          console.log("Buffer updated, length:", buffer.length, "ends with:", buffer.slice(-50));
          
          // コメント終了トークンを検出したらすぐに表示
          if (!commentShown && buffer.includes("[[[COMMENT_END]]]")) {
            const commentStart = buffer.indexOf("[[[COMMENT_START]]]");
            const commentEnd = buffer.indexOf("[[[COMMENT_END]]]");
            if (commentStart !== -1 && commentEnd !== -1) {
              // COMMENT_START_TOKEN の長さを加算して実際のコメント開始位置を取得
              const actualCommentStart = commentStart + 19; // [[[COMMENT_START]]] の長さ
              const comment = buffer.substring(actualCommentStart, commentEnd).trim();
              statusEl.textContent = comment + "\\n\\nコード生成中...";
              commentShown = true;
              console.log("Comment displayed:", comment);
              console.log("Comment start pos:", commentStart, "actual start:", actualCommentStart, "end:", commentEnd);
            }
          }
        }
        
        // ストリーム完了
        if (commentShown) {
          const commentStart = buffer.indexOf("[[[COMMENT_START]]]");
          const commentEnd = buffer.indexOf("[[[COMMENT_END]]]");
          const actualCommentStart = commentStart + 19; // [[[COMMENT_START]]] の長さ
          const comment = buffer.substring(actualCommentStart, commentEnd).trim();
          statusEl.textContent = comment + "\\n\\n✓ 完了しました。";
        } else {
          statusEl.textContent = "✓ 完了しました。";
        }
        console.log("Stream processing completed");
        
      } catch (e) {
        statusEl.textContent = "通信エラー: " + e.message;
        console.error("Error:", e);
      }
    };

    resetBtn.onclick = async () => {
      console.log("Reset button clicked!");
      if (!confirm("script_user.pyを初期状態に戻しますか？")) {
        return;
      }
      
      statusEl.textContent = "リセット中...";
      
      try {
        const res = await fetch("/reset_script", {
          method: "POST",
        });
        console.log("Reset response status:", res.status);
        
        if (res.ok) {
          const data = await res.json();
          statusEl.textContent = data.message || "script_user.py を初期状態に戻しました。";
          promptEl.value = "";
          console.log("Reset successful:", data);
        } else {
          statusEl.textContent = "リセットエラー: " + res.status;
        }
      } catch (e) {
        statusEl.textContent = "通信エラー: " + e.message;
        console.error("Reset error:", e);
      }
    };
    
    console.log("Event listeners attached successfully!");
  </script>
</body>
</html>
    """


@app.post("/update_script")
async def update_script(body: PromptBody):
    try:
        # 1. プロンプトを組み立て
        system_prompt = load_system_prompt()
        
        # デバッグ: プロンプトの先頭と末尾を確認
        print(f"=== System Prompt (最初の200文字) ===")
        print(system_prompt[:200])
        print(f"=== System Prompt (最後の200文字) ===")
        print(system_prompt[-200:])
        
        # AI_PROMPT.md の最後に「## ユーザーからの要望」セクションがあるので、
        # そこにユーザーのプロンプトを挿入する
        if "{ユーザーの自然言語プロンプトをここに挿入}" in system_prompt:
            system_prompt = system_prompt.replace(
                "{ユーザーの自然言語プロンプトをここに挿入}",
                body.prompt
            )
            print("=== プロンプト挿入成功（置き換え方式） ===")
        else:
            # フォールバック: 末尾に追加
            system_prompt += f"\n\n## ユーザーからの要望\n\n{body.prompt}"
            print("=== プロンプト挿入成功（末尾追加方式） ===")

        # 2. AI API呼び出し（コード生成）
        if api_provider == "openai":
            resp = openai.chat.completions.create(
                model="gpt-5.1",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": body.prompt},
                ],
            )
            response_content = resp.choices[0].message.content
        elif api_provider == "gemini":
            # モデル名を修正: 無料枠で使えるFlashモデルを指定
            model = genai.GenerativeModel("models/gemini-flash-latest")
            resp = model.generate_content(system_prompt + "\n\n" + body.prompt)
            response_content = resp.text
        else:
            return {
                "status": "error",
                "error": "API key not set"
            }
        
        # デバッグ: レスポンス全体をログに出力
        print(f"=== Full Response Content (length: {len(response_content)}) ===")
        print(response_content[:500])  # 最初の500文字
        print("...")
        print(response_content[-500:])  # 最後の500文字

        # まずはモデル出力に COMMENT/CODE トークンが含まれているか確認する
        comment = ""
        code = ""
        if COMMENT_START_TOKEN in response_content or CODE_START_TOKEN in response_content:
            # COMMENT と CODE をそれぞれ抜き出す(見つからなければ空文字)
            comment = extract_comment_block(response_content)
            code = extract_code_block(response_content)
            print(f"=== Token-based extraction ===")
            print(f"Comment length: {len(comment)}")
            print(f"Code length: {len(code)}")
            print(f"Code preview (first 200 chars): {code[:200] if code else '(empty)'}")
        else:
            # 既存の JSON パース方式を試す
            try:
                # JSON部分を抽出（```json ... ``` でラップされている場合に対応）
                if "```json" in response_content:
                    json_start = response_content.find("```json") + 7
                    json_end = response_content.find("```", json_start)
                    json_str = response_content[json_start:json_end].strip()
                elif "```" in response_content:
                    json_start = response_content.find("```") + 3
                    json_end = response_content.find("```", json_start)
                    json_str = response_content[json_start:json_end].strip()
                else:
                    json_str = response_content.strip()

                result = json.loads(json_str)
                code = result.get("script_user", "")
                comment = result.get("comment", "")
            except Exception as ex:
                # JSONパースに失敗したら、念のため COMMENT/CODE を再試行
                print(f"JSON parse failed: {ex}. Falling back to token extraction.")
                comment = extract_comment_block(response_content)
                code = extract_code_block(response_content)

        # 3. script_user.py を上書き保存(コードが空でない場合のみ)
        if code:
            try:
                with open("scripts/script_user.py", "w", encoding="utf-8") as f:
                    f.write(code)
                print(f"=== script_user.py updated successfully ({len(code)} chars) ===")
            except Exception as e:
                print(f"script write failed: {e}")
        else:
            print("=== WARNING: No code extracted, script_user.py NOT updated ===")

        # 4. 「リロードフラグ」を立てる
        with open("reload.flag", "w", encoding="utf-8") as f:
            f.write("")

        return {
            "status": "ok",
            "comment": comment,
            "code_length": len(code)
        }
    
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


@app.post("/update_script_stream")
async def update_script_stream(body: PromptBody):
    """
    OpenAI からの出力をストリームでそのままクライアントに流しつつ、
    最後に CODE 部分だけ script_user.py に保存する。
    """
    try:
        # 1. プロンプトを組み立て
        system_prompt = load_system_prompt()

        if "{ユーザーの自然言語プロンプトをここに挿入}" in system_prompt:
            system_prompt = system_prompt.replace(
                "{ユーザーの自然言語プロンプトをここに挿入}",
                body.prompt
            )
        else:
            system_prompt += f"\n\n## ユーザーからの要望\n\n{body.prompt}"

        openai.api_key = os.getenv("OPENAI_API_KEY")

        def event_stream():
            full_text = ""
            comment_extracted = False
            buffer = ""  # チャンクをまとめるバッファ
            try:
                print("=== AI API (stream) リクエスト送信 ===")
                if api_provider == "openai":
                    stream = openai.chat.completions.create(
                        model="gpt-5.1",
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": body.prompt},
                        ],
                        stream=True,  # ストリーミング有効化
                    )
                    for chunk in stream:
                        delta = chunk.choices[0].delta
                        content = getattr(delta, "content", None) or ""
                        if not content:
                            continue
                        
                        buffer += content
                        full_text += content
                        
                        # バッファが一定サイズになったら、または特定のトークンが現れたら送信
                        should_yield = (
                            len(buffer) >= 50 or  # 50文字以上溜まったら
                            COMMENT_END_TOKEN in buffer or  # コメント終了トークンが出現したら
                            CODE_START_TOKEN in buffer  # コード開始トークンが出現したら
                        )
                        
                        if should_yield:
                            print(f"=== Yielding buffer ({len(buffer)} chars): {buffer[:100]}... ===")
                            yield buffer
                            buffer = ""  # バッファをクリア
                        
                        # コメント部分が完成したらログに出力(デバッグ用)
                        if not comment_extracted and COMMENT_END_TOKEN in full_text:
                            comment = extract_comment_block(full_text)
                            if comment:
                                print(f"=== Comment extracted early: {comment[:100]}... ===")
                                comment_extracted = True
                                # ゲームUIに「コード生成中」を表示するためのフラグファイル作成
                                try:
                                    with open("status_generating.flag", "w", encoding="utf-8") as f:
                                        f.write("コード生成中...")
                                    print("=== status_generating.flag created ===")
                                except Exception as e:
                                    print(f"Failed to create status flag: {e}")
                elif api_provider == "gemini":
                    # モデル名を修正: 無料枠で使えるFlashモデルを指定
                    model = genai.GenerativeModel("models/gemini-flash-latest")
                    response = model.generate_content(system_prompt + "\n\n" + body.prompt, stream=True)
                    for chunk in response:
                        content = chunk.text
                        if not content:
                            continue
                        
                        buffer += content
                        full_text += content
                        
                        # バッファが一定サイズになったら、または特定のトークンが現れたら送信
                        should_yield = (
                            len(buffer) >= 50 or  # 50文字以上溜まったら
                            COMMENT_END_TOKEN in buffer or  # コメント終了トークンが出現したら
                            CODE_START_TOKEN in buffer  # コード開始トークンが出現したら
                        )
                        
                        if should_yield:
                            print(f"=== Yielding buffer ({len(buffer)} chars): {buffer[:100]}... ===")
                            yield buffer
                            buffer = ""  # バッファをクリア
                        
                        # コメント部分が完成したらログに出力(デバッグ用)
                        if not comment_extracted and COMMENT_END_TOKEN in full_text:
                            comment = extract_comment_block(full_text)
                            if comment:
                                print(f"=== Comment extracted early: {comment[:100]}... ===")
                                comment_extracted = True
                                # ゲームUIに「コード生成中」を表示するためのフラグファイル作成
                                try:
                                    with open("status_generating.flag", "w", encoding="utf-8") as f:
                                        f.write("コード生成中...")
                                    print("=== status_generating.flag created ===")
                                except Exception as e:
                                    print(f"Failed to create status flag: {e}")
                else:
                    yield "[SERVER ERROR] API key not set"
                    return

                # 残りのバッファを送信
                if buffer:
                    print(f"=== Yielding final buffer ({len(buffer)} chars) ===")
                    yield buffer

                # 全チャンク受信後、CODE ブロックだけ抜き出して保存
                print(f"=== Stream complete, extracting code (total length: {len(full_text)}) ===")
                code = extract_code_block(full_text)
                if code:
                    with open("scripts/script_user.py", "w", encoding="utf-8") as f:
                        f.write(code)
                    with open("reload.flag", "w", encoding="utf-8") as f:
                        f.write("")
                    print(f"=== script_user.py を更新しました（stream, {len(code)} chars） ===")
                    
                    # 生成中フラグを削除
                    if os.path.exists("status_generating.flag"):
                        os.remove("status_generating.flag")
                    
                    # ゲームUIにユーザープロンプトを表示するためのファイル作成
                    try:
                        prompt_preview = body.prompt[:30] + "..." if len(body.prompt) > 30 else body.prompt
                        with open("status_prompt.flag", "w", encoding="utf-8") as f:
                            f.write(f"適用: {prompt_preview}")
                        print(f"=== status_prompt.flag created with: {prompt_preview} ===")
                    except Exception as e:
                        print(f"Failed to create prompt flag: {e}")
                else:
                    print("警告: CODE ブロックが出力に見つかりませんでした")
                    print(f"Full text preview: {full_text[:500]}")

            except Exception as e:
                err = f"\n[SERVER ERROR] {e}"
                print(err)
                yield err

        return StreamingResponse(
            event_stream(),
            media_type="text/plain; charset=utf-8",
        )

    except Exception as e:
        def error_stream():
            msg = f"[SERVER ERROR (outer)]: {e}"
            print(msg)
            yield msg
        return StreamingResponse(
            error_stream(),
            media_type="text/plain; charset=utf-8",
            status_code=500,
        )


@app.post("/reset_script")
async def reset_script():
    """
    script_user.py を初期状態（script_user_default.py）に戻す
    """
    try:
        # script_user_default.py が存在するか確認
        if not os.path.exists("scripts/examples/default.py"):
            return {
                "status": "error",
                "message": "デフォルトファイル (default.py) が見つかりません"
            }
        
        # default.py の内容を読み込む
        with open("scripts/examples/default.py", "r", encoding="utf-8") as f:
            default_code = f.read()
        
        # script_user.py を上書き
        with open("scripts/script_user.py", "w", encoding="utf-8") as f:
            f.write(default_code)
        
        # リロードフラグを立てる
        with open("reload.flag", "w", encoding="utf-8") as f:
            f.write("")
        
        return {
            "status": "ok",
            "message": "script_user.py を初期状態に戻しました。ゲームに反映されます。"
        }
    
    except Exception as e:
        return {
            "status": "error",
            "message": f"リセット中にエラーが発生しました: {str(e)}"
        }


@app.get("/info")
async def root():
    return {"message": "ゲームスクリプト更新サーバー稼働中"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/test_cors")
async def test_cors():
    """CORSテスト用エンドポイント"""
    return {"message": "CORS is working!", "timestamp": "2025-01-21"}


class StatusBody(BaseModel):
    text: str
    duration: int = 180  # デフォルト3秒（60fps想定）


@app.post("/set_status")
async def set_status(body: StatusBody):
    """
    ゲームの右上にテキストを表示する（ファイル経由）
    """
    try:
        # ソケット通信ではなく、フラグファイル経由で通知する
        # main.py が status_custom.flag を監視するように修正が必要
        with open("status_custom.flag", "w", encoding="utf-8") as f:
            f.write(body.text)
        return {"status": "ok", "text": body.text}
    except Exception as e:
        return {"status": "error", "error": str(e)}


import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Game Server")
    parser.add_argument("--port", type=int, default=8001, help="Port number (default: 8001)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host address (default: 0.0.0.0)")
    parser.add_argument("--no-ngrok", action="store_true", help="Disable ngrok")
    args = parser.parse_args()

    # 環境変数チェック
    if not os.getenv("OPENAI_API_KEY") and not os.getenv("GEMINI_API_KEY"):
        print("警告: OPENAI_API_KEY または GEMINI_API_KEY 環境変数が設定されていません")
        print("環境変数を設定してください")
    
    # ngrok を使用してトンネルを作成
    if not args.no_ngrok:
        try:
            from pyngrok import ngrok
            
            # ngrok トンネルを開く
            public_url = ngrok.connect(args.port, bind_tls=True)
            print(f"\n{'='*60}")
            print(f"✓ ngrok トンネル作成完了")
            print(f"{'='*60}")
            print(f"公開 URL: {public_url}")
            print(f"ローカルサーバー: http://localhost:{args.port}")
            print(f"{'='*60}\n")
            
        except Exception as e:
            print(f"⚠ ngrok の初期化に失敗しました: {e}")
            print("ngrok なしでサーバーを起動します\n")
    else:
        print("ngrok は無効化されています")
    
    uvicorn.run(app, host=args.host, port=args.port)
