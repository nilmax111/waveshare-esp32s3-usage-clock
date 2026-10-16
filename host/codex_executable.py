"""Resolve installed Codex without relying on an interactive shell PATH."""
import os
import shutil
from pathlib import Path

def candidates():
    found = shutil.which('codex')
    if found:
        yield Path(found)
    for root in (Path('/Applications'), Path.home() / 'Applications'):
        for app in ('ChatGPT.app', 'Codex.app'):
            resources = root / app / 'Contents/Resources'
            yield resources / 'codex-cli/CodexCLI.app/Contents/MacOS/codex'
            yield resources / 'codex'
    for root in ('/opt/homebrew/bin', '/usr/local/bin'):
        yield Path(root) / 'codex'

def resolve():
    for path in candidates():
        if path.is_file() and os.access(path, os.X_OK):
            return str(path)
    raise RuntimeError('Codex executable missing; reinstall or update the Codex desktop app')

if __name__ == '__main__':
    try:
        print('Codex 程序检查通过：' + resolve())
    except RuntimeError:
        print('找不到可执行的 Codex 程序；请检查桌面应用安装。其他平台仍可启动。')
        raise SystemExit(1)
