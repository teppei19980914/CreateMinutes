"""実行時パスの一元解決（docs/DESIGN.md §2「パス解決原則」・ゼロハードコーディング）。

PyInstaller配布時は `sys.frozen` が True になり、実行ファイル（.exe）の置き場所が
アプリのルートになる。開発時は本ファイルの位置（backend/minutes_app/constants/）から
3階層上のリポジトリルートをアプリのルートとみなす。`data/` `models/` のパスは
本モジュール経由でのみ解決し、他モジュールで直書きしない。
"""

import sys
from pathlib import Path


def get_app_root() -> Path:
    """アプリのルートディレクトリを解決する（配布時はexe基準、開発時はリポジトリルート基準）。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[3]


def get_data_dir() -> Path:
    """DB・音声等、実行時に生成されるデータの格納先（docs/DESIGN.md §2）。"""
    return get_app_root() / "data"


def get_models_dir() -> Path:
    """Whisperモデルの格納先（docs/DESIGN.md §2）。"""
    return get_app_root() / "models"


def get_db_path() -> Path:
    """SQLite DB本体のパス（docs/DESIGN.md §2 `data/app.db`）。"""
    return get_data_dir() / "app.db"


def get_audio_dir() -> Path:
    """録音セッションごとの音声格納先ルート（docs/DESIGN.md §2 `data/audio/{meeting_uid}`）。"""
    return get_data_dir() / "audio"
