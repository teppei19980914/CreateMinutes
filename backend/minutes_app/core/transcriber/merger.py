"""2トラック時系列マージ・話者ラベル付与（仕様書 #1 / docs/DESIGN.md §5.2「マージ仕様」/
docs/REQUIREMENTS.md F-2-4・F-2-5）。

mic.wav と loopback.wav は同一の `RecordingSession` 内でほぼ同時に録音開始されるため、
両トラックの相対秒（0秒起点）はそのまま同一の時間軸として扱う。録音開始の呼び出し順序に
起因する数十ミリ秒程度のズレは、10分単位のチャンク分割（F-3-1想定）や1.5秒の発言統合
閾値に対して無視できる誤差として扱い、厳密な同期処理は行わない。
"""

import difflib
from dataclasses import dataclass

from minutes_app.core.transcriber.whisper_engine import TrackSegment

SPEAKER_SELF = "self"
SPEAKER_OTHER = "other"

DEFAULT_ECHO_OVERLAP_RATIO = 0.8
DEFAULT_ECHO_TEXT_SIMILARITY = 0.8
DEFAULT_MERGE_GAP_MS = 1500
DEFAULT_CHUNK_MS = 600_000


@dataclass(frozen=True)
class Utterance:
    """マージ後の1発言（DB `utterances` テーブルへそのまま永続化できる粒度）。"""

    seq_no: int
    speaker: str
    started_ms: int
    ended_ms: int
    text: str
    chunk_index: int


@dataclass(frozen=True)
class _LabeledSegment:
    speaker: str
    started_ms: int
    ended_ms: int
    text: str


def _to_ms(seconds: float) -> int:
    return round(seconds * 1000)


def _label(segments: list[TrackSegment], speaker: str) -> list[_LabeledSegment]:
    return [
        _LabeledSegment(speaker, _to_ms(seg.start_sec), _to_ms(seg.end_sec), seg.text)
        for seg in segments
        if seg.text
    ]


def _overlap_ratio(a_start: int, a_end: int, b_start: int, b_end: int) -> float:
    """区間 a に対する、a・b の重複時間の比率（0.0〜1.0）。"""
    overlap = max(0, min(a_end, b_end) - max(a_start, b_start))
    a_duration = a_end - a_start
    if a_duration <= 0:
        return 0.0
    return overlap / a_duration


def _is_echo(loopback_seg: _LabeledSegment, mic_segments: list[_LabeledSegment]) -> bool:
    for mic_seg in mic_segments:
        overlap = _overlap_ratio(
            loopback_seg.started_ms, loopback_seg.ended_ms, mic_seg.started_ms, mic_seg.ended_ms
        )
        if overlap < DEFAULT_ECHO_OVERLAP_RATIO:
            continue
        similarity = difflib.SequenceMatcher(None, loopback_seg.text, mic_seg.text).ratio()
        if similarity >= DEFAULT_ECHO_TEXT_SIMILARITY:
            return True
    return False


def _remove_echo(
    mic_segments: list[_LabeledSegment], loopback_segments: list[_LabeledSegment]
) -> list[_LabeledSegment]:
    """自声回り込み（mic発話とのエコー）とみなせるloopbackセグメントを除去する

    （docs/DESIGN.md §5.2 手順3）。
    """
    return [seg for seg in loopback_segments if not _is_echo(seg, mic_segments)]


def _merge_consecutive_same_speaker(
    segments: list[_LabeledSegment], *, gap_ms: int
) -> list[_LabeledSegment]:
    """同一話者の連続セグメントを、間隔がgap_ms未満なら1発言に統合する

    （docs/DESIGN.md §5.2 手順4）。
    """
    if not segments:
        return []

    merged = [segments[0]]
    for seg in segments[1:]:
        last = merged[-1]
        if seg.speaker == last.speaker and seg.started_ms - last.ended_ms < gap_ms:
            merged[-1] = _LabeledSegment(
                speaker=last.speaker,
                started_ms=last.started_ms,
                ended_ms=max(last.ended_ms, seg.ended_ms),
                text=f"{last.text} {seg.text}",
            )
        else:
            merged.append(seg)
    return merged


def merge_tracks(
    mic_segments: list[TrackSegment],
    loopback_segments: list[TrackSegment],
    *,
    merge_gap_ms: int = DEFAULT_MERGE_GAP_MS,
    chunk_ms: int = DEFAULT_CHUNK_MS,
) -> list[Utterance]:
    """2トラックの文字起こし結果を時系列マージし、話者ラベル付き発言ログを生成する。

    手順（docs/DESIGN.md §5.2「マージ仕様」）:
    1. 両トラックをstarted_msでソートしてマージ
    2. speakerは由来トラックで決定（mic→self, loopback→other）
    3. エコー除去（自声回り込みの破棄）
    4. 同一話者の連続セグメントを閾値未満の間隔なら統合
    5. seq_no採番、10分境界でchunk_index付与（統合後の発言単位のため、発言途中では切れない）

    :param mic_segments: `transcribe_track` の出力（マイクトラック）
    :param loopback_segments: `transcribe_track` の出力（ループバックトラック）
    :param merge_gap_ms: 同一話者の連続発言とみなす間隔の閾値（既定1.5秒）
    :param chunk_ms: 構造化チャンクの境界間隔（既定10分）
    """
    mic_labeled = _label(mic_segments, SPEAKER_SELF)
    loopback_labeled = _remove_echo(mic_labeled, _label(loopback_segments, SPEAKER_OTHER))

    combined = sorted(mic_labeled + loopback_labeled, key=lambda s: s.started_ms)
    merged = _merge_consecutive_same_speaker(combined, gap_ms=merge_gap_ms)

    return [
        Utterance(
            seq_no=seq_no,
            speaker=seg.speaker,
            started_ms=seg.started_ms,
            ended_ms=seg.ended_ms,
            text=seg.text,
            chunk_index=seg.started_ms // chunk_ms,
        )
        for seq_no, seg in enumerate(merged, start=1)
    ]
