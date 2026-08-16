"""DB接続の生成とマイグレーション適用（仕様書 #1 / docs/DESIGN.md §2・§3 db/connection.py）。

Phase 1 では平文SQLiteを使う。SQLCipher暗号化・keyring経由の鍵管理（`core/crypto/key_manager.py`）
は §9 実装順序表でPhase 4に割り当てられているため、Phase 1時点でDBを暗号化すると
鍵管理未実装のまま暗号鍵を扱うことになり本末転倒（docs/DESIGN.md 改訂履歴 v0.12 参照）。
マイグレーションは `migrations/` 配下の連番SQLファイルのうち、未適用のものだけを
起動時に自動適用する素朴な仕組みとする（Django/Alembic 等のマイグレーションツールは
導入せず、規模に見合う最小実装とする）。
"""

import sqlite3
from pathlib import Path

_MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def connect(db_path: Path) -> sqlite3.Connection:
    """DBへ接続し、未適用のマイグレーションを適用した上で Connection を返す。

    :param db_path: DBファイルのパス（`app_constants.get_db_path()` 等）
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    migrate(conn)
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    """`migrations/*.sql` のうち未適用のものをファイル名昇順に適用する。"""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        "filename TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT (datetime('now')))"
    )
    applied = {row["filename"] for row in conn.execute("SELECT filename FROM schema_migrations")}

    for migration_path in sorted(_MIGRATIONS_DIR.glob("*.sql")):
        if migration_path.name in applied:
            continue
        conn.executescript(migration_path.read_text(encoding="utf-8"))
        conn.execute(
            "INSERT INTO schema_migrations (filename) VALUES (?)", (migration_path.name,)
        )
    conn.commit()
