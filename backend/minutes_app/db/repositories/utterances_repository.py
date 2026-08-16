"""`utterances` テーブルのDB操作の単一実装箇所（仕様書 #1 / docs/DESIGN.md §3.2 / F-2-5）。

コミットは呼び出し元の責務とする（`meetings_repository` と同じ方針。理由はそちらのdocstring参照）。
"""

import sqlite3

from minutes_app.core.transcriber.merger import Utterance


def bulk_insert(conn: sqlite3.Connection, meeting_id: int, utterances: list[Utterance]) -> None:
    """`merger.merge_tracks` の出力をそのまま一括登録する。"""
    conn.executemany(
        "INSERT INTO utterances "
        "(meeting_id, seq_no, speaker, started_ms, ended_ms, text, chunk_index) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            (
                meeting_id,
                u.seq_no,
                u.speaker,
                u.started_ms,
                u.ended_ms,
                u.text,
                u.chunk_index,
            )
            for u in utterances
        ],
    )


def list_by_meeting(conn: sqlite3.Connection, meeting_id: int) -> list[sqlite3.Row]:
    """発言ID(seq_no)昇順で取得する（UI表示・根拠参照の基準順序、docs/DESIGN.md §3.2）。"""
    return conn.execute(
        "SELECT * FROM utterances WHERE meeting_id = ? ORDER BY seq_no", (meeting_id,)
    ).fetchall()
