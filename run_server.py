#!/usr/bin/env python
# サーバーを起動するスクリプト

import sys
import os
import subprocess

# プロジェクトルートとサーバーディレクトリのパスを取得
project_root = os.path.dirname(__file__)
server_dir = os.path.join(project_root, 'server')

# server.pyを実行（カレントディレクトリはプロジェクトルート）
if __name__ == "__main__":
    # 引数をそのまま渡す
    cmd = [sys.executable, os.path.join(server_dir, 'server.py')] + sys.argv[1:]
    subprocess.run(cmd, cwd=project_root)
