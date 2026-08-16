"""`meetings` テーブルのDB操作の単一実装箇所（仕様書 #1 / docs/DESIGN.md §3.2 §4.1）。

状態遷移（`status`）は docs/DESIGN.md §4.1 のステートマシンに従う。Phase 1 で到達する状態は
`recording` → `recorded` → `transcribing` → `awaiting_structuring`（構造化はPhase 2）。

コミットは呼び出し元の責務とする（本モジュールは `conn.commit()` を呼ばない）。
`bench_transcribe.run_pipeline()` のように、複数テーブルへの書き込みを1つの録音セッション
処理として扱う場合、途中で例外が発生した際に中途半端な状態（例: meetings は `recording` の
ままなのに audio_files だけ登録済み）がDBに残らないよう、呼び出し元が一連の処理をまとめて
1トランザクションとしてコミットする（コミット前に例外で接続がcloseされれば自動ロールバックされる）。
"""

import sqlite3

STATUS_RECORDING = "recording"
STATUS_RECORDED = "recorded"
STATUS_TRANSCRIBING = "transcribing"
STATUS_AWAITING_STRUCTURING = "awaiting_structuring"


def create(conn: sqlite3.Connection, *, uid: str, started_at: str) -> int:
    """録音開始時に呼び出し、`recording` 状態の会議レコードを作成する（F-1-7）。

    :return: 作成した meetings.id
    """
    cursor = conn.execute(
        "INSERT INTO meetings (uid, started_at, status) VALUES (?, ?, ?)",
        (uid, started_at, STATUS_RECORDING),
    )
    return cursor.lastrowid


def mark_recorded(
    conn: sqlite3.Connection, meeting_id: int, *, ended_at: str, duration_sec: int
) -> None:
    """録音・ローリングファイル結合が完了した際に呼び出す（F-1-7）。"""
    conn.execute(
        "UPDATE meetings SET status = ?, ended_at = ?, duration_sec = ?, "
        "updated_at = datetime('now') WHERE id = ?",
        (STATUS_RECORDED, ended_at, duration_sec, meeting_id),
    )


def update_status(conn: sqlite3.Connection, meeting_id: int, status: str) -> None:
    """タイムスタンプ更新を伴わない単純な状態遷移（transcribing / awaiting_structuring 等）。"""
    conn.execute(
        "UPDATE meetings SET status = ?, updated_at = datetime('now') WHERE id = ?",
        (status, meeting_id),
    )


def get_by_id(conn: sqlite3.Connection, meeting_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM meetings WHERE id = ?", (meeting_id,)).fetchone()


def get_by_uid(conn: sqlite3.Connection, uid: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM meetings WHERE uid = ?", (uid,)).fetchone()
