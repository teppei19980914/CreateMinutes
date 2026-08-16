"""db配下のテストで共有するDB接続フィクスチャ。"""

import pytest

from minutes_app.db import connection
from minutes_app.db.repositories import meetings_repository


@pytest.fixture
def conn(tmp_path):
    """マイグレーション適用済みの実SQLite接続（一時ファイルDB）。"""
    c = connection.connect(tmp_path / "test.db")
    yield c
    c.close()


@pytest.fixture
def meeting_id(conn) -> int:
    """audio_files/utterances のFK先として使う、最小限のmeetingレコードのid。"""
    return meetings_repository.create(conn, uid="uid-1", started_at="2026-08-17T10:00:00")
