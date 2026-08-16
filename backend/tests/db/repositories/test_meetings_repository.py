from minutes_app.db.repositories import meetings_repository as repo


def test_create_inserts_meeting_with_recording_status(conn) -> None:
    meeting_id = repo.create(conn, uid="uid-1", started_at="2026-08-17T10:00:00")

    row = repo.get_by_id(conn, meeting_id)
    assert row["uid"] == "uid-1"
    assert row["started_at"] == "2026-08-17T10:00:00"
    assert row["status"] == repo.STATUS_RECORDING
    assert row["ended_at"] is None


def test_mark_recorded_sets_status_ended_at_and_duration(conn) -> None:
    meeting_id = repo.create(conn, uid="uid-1", started_at="2026-08-17T10:00:00")

    repo.mark_recorded(
        conn, meeting_id, ended_at="2026-08-17T10:30:00", duration_sec=1800
    )

    row = repo.get_by_id(conn, meeting_id)
    assert row["status"] == repo.STATUS_RECORDED
    assert row["ended_at"] == "2026-08-17T10:30:00"
    assert row["duration_sec"] == 1800


def test_update_status_changes_only_status(conn) -> None:
    meeting_id = repo.create(conn, uid="uid-1", started_at="2026-08-17T10:00:00")

    repo.update_status(conn, meeting_id, repo.STATUS_TRANSCRIBING)

    row = repo.get_by_id(conn, meeting_id)
    assert row["status"] == repo.STATUS_TRANSCRIBING


def test_get_by_id_returns_none_when_not_found(conn) -> None:
    assert repo.get_by_id(conn, 999) is None


def test_get_by_uid_returns_matching_row(conn) -> None:
    repo.create(conn, uid="uid-1", started_at="2026-08-17T10:00:00")

    row = repo.get_by_uid(conn, "uid-1")

    assert row["uid"] == "uid-1"


def test_get_by_uid_returns_none_when_not_found(conn) -> None:
    assert repo.get_by_uid(conn, "missing-uid") is None
