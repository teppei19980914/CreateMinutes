from datetime import datetime

from minutes_app.db.repositories import audio_files_repository as repo


def test_compute_expires_at_adds_thirty_days() -> None:
    created_at = datetime(2026, 8, 17, 10, 0, 0)

    assert repo.compute_expires_at(created_at) == datetime(2026, 9, 16, 10, 0, 0).isoformat()


def test_create_inserts_audio_file_linked_to_meeting(conn, meeting_id) -> None:
    audio_file_id = repo.create(
        conn,
        meeting_id=meeting_id,
        track="mic",
        stage=repo.STAGE_RAW_WAV,
        path="data/audio/uid-1/mic.wav",
        expires_at="2026-09-16T10:00:00",
    )

    rows = repo.list_by_meeting(conn, meeting_id)
    assert len(rows) == 1
    assert rows[0]["id"] == audio_file_id
    assert rows[0]["track"] == "mic"
    assert rows[0]["stage"] == repo.STAGE_RAW_WAV
    assert rows[0]["path"] == "data/audio/uid-1/mic.wav"
    assert rows[0]["expires_at"] == "2026-09-16T10:00:00"
    assert rows[0]["encrypted"] == 0


def test_list_by_meeting_returns_rows_in_insertion_order(conn, meeting_id) -> None:
    repo.create(conn, meeting_id=meeting_id, track="mic", stage=repo.STAGE_RAW_WAV, path="mic.wav")
    repo.create(
        conn,
        meeting_id=meeting_id,
        track="loopback",
        stage=repo.STAGE_RAW_WAV,
        path="loopback.wav",
    )

    rows = repo.list_by_meeting(conn, meeting_id)

    assert [row["track"] for row in rows] == ["mic", "loopback"]


def test_list_by_meeting_returns_empty_list_when_none_exist(conn, meeting_id) -> None:
    assert repo.list_by_meeting(conn, meeting_id) == []
