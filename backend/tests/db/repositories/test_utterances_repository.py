from minutes_app.core.transcriber.merger import Utterance
from minutes_app.db.repositories import utterances_repository as repo


def test_bulk_insert_persists_all_fields(conn, meeting_id) -> None:
    utterances = [
        Utterance(
            seq_no=1, speaker="self", started_ms=0, ended_ms=1000, text="こんにちは", chunk_index=0
        ),
        Utterance(
            seq_no=2,
            speaker="other",
            started_ms=1000,
            ended_ms=2000,
            text="よろしく",
            chunk_index=0,
        ),
    ]

    repo.bulk_insert(conn, meeting_id, utterances)

    rows = repo.list_by_meeting(conn, meeting_id)
    assert len(rows) == 2
    assert rows[0]["seq_no"] == 1
    assert rows[0]["speaker"] == "self"
    assert rows[0]["started_ms"] == 0
    assert rows[0]["ended_ms"] == 1000
    assert rows[0]["text"] == "こんにちは"
    assert rows[0]["chunk_index"] == 0
    assert rows[0]["revised_text"] is None


def test_bulk_insert_with_empty_list_inserts_nothing(conn, meeting_id) -> None:
    repo.bulk_insert(conn, meeting_id, [])

    assert repo.list_by_meeting(conn, meeting_id) == []


def test_list_by_meeting_orders_by_seq_no(conn, meeting_id) -> None:
    utterances = [
        Utterance(
            seq_no=2, speaker="self", started_ms=1000, ended_ms=2000, text="2番目", chunk_index=0
        ),
        Utterance(
            seq_no=1, speaker="self", started_ms=0, ended_ms=1000, text="1番目", chunk_index=0
        ),
    ]

    repo.bulk_insert(conn, meeting_id, utterances)

    rows = repo.list_by_meeting(conn, meeting_id)
    assert [row["seq_no"] for row in rows] == [1, 2]
