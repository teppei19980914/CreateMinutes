"""`audio_files` テーブルのDB操作の単一実装箇所（仕様書 #1 / docs/DESIGN.md §3.2 / F-9）。

`encrypted` は Phase 1 では常に0（平文WAV）。暗号化（§5.5）はPhase 4で追加する
（docs/DESIGN.md §5.1「Phase 1 実装メモ」参照）。

コミットは呼び出し元の責務とする（`meetings_repository` と同じ方針。理由はそちらのdocstring参照）。
"""

import sqlite3
from datetime import datetime, timedelta

STAGE_RAW_WAV = "raw_wav"
STAGE_COMPRESSED = "compressed"

# F-9-2「音声は1ヶ月保持し、超過分は自動で物理削除する」。暦月加算はstdlibのみでは煩雑なため、
# 30日での近似とする（物理削除バッチ自体はPhase 4のキュー機能で実装するため、Phase 1時点では
# expires_atは記録するのみで参照されない）。
EXPIRES_AFTER_DAYS = 30


def compute_expires_at(created_at: datetime) -> str:
    """F-9-2の保持期限（作成日+30日、ISO8601文字列）を計算する。"""
    return (created_at + timedelta(days=EXPIRES_AFTER_DAYS)).isoformat()


def create(
    conn: sqlite3.Connection,
    *,
    meeting_id: int,
    track: str,
    stage: str,
    path: str,
    expires_at: str | None = None,
) -> int:
    """音声ファイルレコードを作成する。

    :param track: `mic` / `loopback`（`session.MIC_TRACK_NAME` / `LOOPBACK_TRACK_NAME` を使う）
    :param stage: `raw_wav` / `compressed`（本モジュールの定数を使う）
    :return: 作成した audio_files.id
    """
    cursor = conn.execute(
        "INSERT INTO audio_files (meeting_id, track, stage, path, expires_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (meeting_id, track, stage, path, expires_at),
    )
    return cursor.lastrowid


def list_by_meeting(conn: sqlite3.Connection, meeting_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM audio_files WHERE meeting_id = ? ORDER BY id", (meeting_id,)
    ).fetchall()
