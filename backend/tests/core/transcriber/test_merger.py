from minutes_app.core.transcriber.merger import (
    SPEAKER_OTHER,
    SPEAKER_SELF,
    _overlap_ratio,
    merge_tracks,
)
from minutes_app.core.transcriber.whisper_engine import TrackSegment


def test_merge_tracks_returns_empty_list_for_empty_inputs() -> None:
    assert merge_tracks([], []) == []


def test_overlap_ratio_is_zero_when_segment_a_has_zero_duration() -> None:
    # faster-whisperが理論上ゼロ長のセグメントを返した場合でも ZeroDivisionError にならない
    assert _overlap_ratio(1000, 1000, 500, 1500) == 0.0


def test_merge_tracks_labels_mic_as_self_and_loopback_as_other() -> None:
    mic = [TrackSegment(0.0, 1.0, "自分の発言")]
    loopback = [TrackSegment(10.0, 11.0, "相手の発言")]

    utterances = merge_tracks(mic, loopback)

    assert [u.speaker for u in utterances] == [SPEAKER_SELF, SPEAKER_OTHER]


def test_merge_tracks_sorts_segments_across_tracks_by_start_time() -> None:
    mic = [TrackSegment(5.0, 6.0, "後の発言")]
    loopback = [TrackSegment(0.0, 1.0, "先の発言")]

    utterances = merge_tracks(mic, loopback)

    assert [u.text for u in utterances] == ["先の発言", "後の発言"]
    assert [u.seq_no for u in utterances] == [1, 2]


def test_merge_tracks_removes_loopback_echo_of_own_mic_speech() -> None:
    mic = [TrackSegment(0.0, 2.0, "これはテストです")]
    loopback = [TrackSegment(0.1, 2.1, "これはテストです")]  # micとほぼ重複・同一テキスト

    utterances = merge_tracks(mic, loopback)

    assert len(utterances) == 1
    assert utterances[0].speaker == SPEAKER_SELF


def test_merge_tracks_keeps_loopback_segment_when_overlap_is_low() -> None:
    mic = [TrackSegment(0.0, 2.0, "これはテストです")]
    # 重複はわずか(0.1秒/1秒=10%)なので相手発言として残る
    loopback = [TrackSegment(1.9, 2.9, "これはテストです")]

    utterances = merge_tracks(mic, loopback)

    assert len(utterances) == 2
    assert {u.speaker for u in utterances} == {SPEAKER_SELF, SPEAKER_OTHER}


def test_merge_tracks_keeps_loopback_segment_when_text_differs() -> None:
    mic = [TrackSegment(0.0, 2.0, "こんにちは")]
    loopback = [TrackSegment(0.0, 2.0, "全然違う内容の発言です")]  # 重複は100%だが類似度が低い

    utterances = merge_tracks(mic, loopback)

    assert len(utterances) == 2


def test_merge_tracks_removes_echo_when_overlap_ratio_is_exactly_at_threshold() -> None:
    # loopback区間は1.0秒(1000ms)、mic区間との重複はちょうど800ms = 80%（閾値ちょうど）
    mic = [TrackSegment(0.0, 0.8, "これはテストです")]
    loopback = [TrackSegment(0.0, 1.0, "これはテストです")]

    utterances = merge_tracks(mic, loopback)

    assert len(utterances) == 1
    assert utterances[0].speaker == SPEAKER_SELF


def test_merge_tracks_removes_echo_when_text_similarity_is_exactly_at_threshold() -> None:
    # difflib.SequenceMatcher(None, "ABCDE", "ABCDX").ratio() == 0.8（閾値ちょうど、要事前確認済み）
    mic = [TrackSegment(0.0, 2.0, "ABCDE")]
    loopback = [TrackSegment(0.0, 2.0, "ABCDX")]

    utterances = merge_tracks(mic, loopback)

    assert len(utterances) == 1
    assert utterances[0].speaker == SPEAKER_SELF


def test_merge_tracks_does_not_merge_when_gap_equals_threshold_exactly() -> None:
    # 閾値は「未満」なら統合(<)。ちょうどmerge_gap_msの間隔は統合しない。
    mic = [
        TrackSegment(0.0, 1.0, "こんにちは"),
        TrackSegment(2.5, 3.5, "別の発言"),  # 開始2500ms - 前発言終了1000ms = ちょうど1500ms
    ]

    utterances = merge_tracks(mic, [], merge_gap_ms=1500)

    assert len(utterances) == 2


def test_merge_tracks_merges_consecutive_same_speaker_within_gap() -> None:
    mic = [
        TrackSegment(0.0, 1.0, "こんにちは"),
        TrackSegment(1.5, 2.5, "よろしくお願いします"),
    ]

    utterances = merge_tracks(mic, [], merge_gap_ms=1500)

    assert len(utterances) == 1
    assert utterances[0].text == "こんにちは よろしくお願いします"
    assert utterances[0].started_ms == 0
    assert utterances[0].ended_ms == 2500


def test_merge_tracks_does_not_merge_when_gap_exceeds_threshold() -> None:
    mic = [
        TrackSegment(0.0, 1.0, "こんにちは"),
        TrackSegment(5.0, 6.0, "別の話題です"),
    ]

    utterances = merge_tracks(mic, [], merge_gap_ms=1500)

    assert len(utterances) == 2


def test_merge_tracks_does_not_merge_different_speakers_even_if_adjacent() -> None:
    mic = [TrackSegment(0.0, 1.0, "自分の発言")]
    loopback = [TrackSegment(1.1, 2.0, "相手の発言")]

    utterances = merge_tracks(mic, loopback, merge_gap_ms=1500)

    assert len(utterances) == 2


def test_merge_tracks_assigns_chunk_index_by_ten_minute_boundary() -> None:
    mic = [
        TrackSegment(0.0, 1.0, "1つ目のチャンク"),
        TrackSegment(650.0, 651.0, "2つ目のチャンク"),  # 650秒 = 10分50秒
    ]

    utterances = merge_tracks(mic, [], merge_gap_ms=0)

    assert utterances[0].chunk_index == 0
    assert utterances[1].chunk_index == 1


def test_merge_tracks_filters_out_empty_text_segments() -> None:
    mic = [TrackSegment(0.0, 1.0, ""), TrackSegment(1.0, 2.0, "発言")]

    utterances = merge_tracks(mic, [])

    assert len(utterances) == 1
    assert utterances[0].text == "発言"


def test_merge_tracks_assigns_sequential_seq_no_starting_at_one() -> None:
    mic = [
        TrackSegment(0.0, 1.0, "1"),
        TrackSegment(10.0, 11.0, "2"),
        TrackSegment(20.0, 21.0, "3"),
    ]

    utterances = merge_tracks(mic, [])

    assert [u.seq_no for u in utterances] == [1, 2, 3]
