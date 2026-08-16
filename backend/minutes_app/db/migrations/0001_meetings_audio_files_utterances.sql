-- Phase 1 スコープ（docs/DESIGN.md §3.2 / §9）: meetings / audio_files / utterances のみ。
-- minutes / minute_items / comments / jobs 等は Phase 2 以降のマイグレーションで追加する。

CREATE TABLE meetings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uid TEXT UNIQUE NOT NULL,
    name TEXT,
    meeting_type TEXT,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    duration_sec INTEGER,
    status TEXT NOT NULL,
    custom_instruction TEXT,
    output_options TEXT,
    is_deleted INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- audio_files.encrypted は Phase 1 では常に 0（平文WAV）。Phase 4 で crypto/file_crypto.py
-- による暗号化を導入した時点で 1 を書き込むようになる（docs/DESIGN.md §5.1 実装メモ参照）。
CREATE TABLE audio_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_id INTEGER NOT NULL REFERENCES meetings (id),
    track TEXT NOT NULL,
    stage TEXT NOT NULL,
    path TEXT NOT NULL,
    encrypted INTEGER NOT NULL DEFAULT 0,
    expires_at TEXT,
    deleted_at TEXT
);

CREATE INDEX idx_audio_files_meeting_id ON audio_files (meeting_id);

CREATE TABLE utterances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_id INTEGER NOT NULL REFERENCES meetings (id),
    seq_no INTEGER NOT NULL,
    speaker TEXT NOT NULL,
    started_ms INTEGER NOT NULL,
    ended_ms INTEGER NOT NULL,
    text TEXT NOT NULL,
    revised_text TEXT,
    chunk_index INTEGER
);

CREATE INDEX idx_utterances_meeting_id_seq_no ON utterances (meeting_id, seq_no);
