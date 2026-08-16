import sqlite3

from minutes_app.db import connection


def _table_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    return {row["name"] for row in rows}


def test_connect_creates_db_file_and_applies_migrations(tmp_path) -> None:
    db_path = tmp_path / "nested" / "app.db"

    conn = connection.connect(db_path)

    assert db_path.exists()
    tables = _table_names(conn)
    assert {"meetings", "audio_files", "utterances", "schema_migrations"} <= tables
    conn.close()


def test_connect_enables_foreign_keys(tmp_path) -> None:
    conn = connection.connect(tmp_path / "app.db")

    row = conn.execute("PRAGMA foreign_keys").fetchone()

    assert row[0] == 1
    conn.close()


def test_connect_uses_row_factory_for_dict_like_access(tmp_path) -> None:
    conn = connection.connect(tmp_path / "app.db")

    conn.execute(
        "INSERT INTO meetings (uid, started_at, status) VALUES ('u1', '2026-08-17T10:00:00', "
        "'recording')"
    )
    row = conn.execute("SELECT * FROM meetings").fetchone()

    assert row["uid"] == "u1"
    conn.close()


def test_connect_is_idempotent_when_called_twice_on_same_db(tmp_path) -> None:
    db_path = tmp_path / "app.db"

    first = connection.connect(db_path)
    first.execute(
        "INSERT INTO meetings (uid, started_at, status) VALUES ('u1', '2026-08-17T10:00:00', "
        "'recording')"
    )
    first.commit()
    first.close()

    second = connection.connect(db_path)
    row = second.execute("SELECT * FROM meetings").fetchone()

    assert row["uid"] == "u1"
    second.close()


def test_migrate_records_applied_migration_filenames(tmp_path) -> None:
    conn = connection.connect(tmp_path / "app.db")

    filenames = {
        row["filename"] for row in conn.execute("SELECT filename FROM schema_migrations")
    }

    assert "0001_meetings_audio_files_utterances.sql" in filenames
    conn.close()
