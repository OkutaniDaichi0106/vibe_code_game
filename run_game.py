#!/usr/bin/env python
# ゲームを起動するメインスクリプト

import sys
import os

# プロジェクトルートをカレントディレクトリに設定
project_root = os.path.dirname(__file__)
os.chdir(project_root)

# srcディレクトリをパスに追加
sys.path.insert(0, os.path.join(project_root, 'src'))

# main.pyを実行
if __name__ == "__main__":
    import subprocess
    cmd = [sys.executable, os.path.join(project_root, 'src', 'main.py')] + sys.argv[1:]
    subprocess.run(cmd, cwd=project_root)
