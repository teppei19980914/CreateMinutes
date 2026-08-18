"""Phase 1 ベンチマーク・手動検証スクリプト（仕様書 #1 / docs/REQUIREMENTS.md Phase 1
「2トラック録音 + STT + ベンチマーク」・§5 非機能要件「60分会議の文字起こしを実測」）。

既存の録音セッション（mic.wav/loopback.wavが結合済みのディレクトリ、`session.py`の出力）を
指定するか、`--record-seconds` でその場で録音してから、文字起こし→2トラックマージ→
DB永続化までを一気通貫で実行し、各ステップの所要時間と実時間比（処理時間/音声長）を報告する。
60分会議での実測（docs/REQUIREMENTS.md §8 未確定事項#2）は、実際に長時間の録音を
行った上で本スクリプトを実行することで確認する。

実行例::

    # その場で録音してから処理
    uv run python -m minutes_app.bench_transcribe --record-seconds 60

    # 既存の録音セッションを処理
    uv run python -m minutes_app.bench_transcribe --session-dir data/audio/xxxxx
"""

import argparse
import sys
import time
import wave
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import pyaudiowpatch as pyaudio

from minutes_app.constants.app_constants import get_audio_dir, get_db_path
from minutes_app.core.recorder.session import (
    LOOPBACK_TRACK_NAME,
    MIC_TRACK_NAME,
    RecordingSession,
    RecordingSessionResult,
    combined_file_path,
)
from minutes_app.core.transcriber.dictionary import build_initial_prompt
from minutes_app.core.transcriber.merger import merge_tracks
from minutes_app.core.transcriber.whisper_engine import (
    DEFAULT_MODEL_SIZE,
    load_model,
    transcribe_track,
)
from minutes_app.db import connection
from minutes_app.db.repositories import (
    audio_files_repository,
    meetings_repository,
    utterances_repository,
)


@dataclass(frozen=True)
class BenchmarkResult:
    """1会議分のパイプライン実行結果（ベンチマーク指標を含む）。"""

    meeting_id: int
    utterance_count: int
    audio_duration_sec: float
    transcribe_duration_sec: float
    real_time_factor: float


def _wav_duration_sec(path: Path) -> float:
    with wave.open(str(path), "rb") as f:
        return f.getnframes() / f.getframerate()


def record_session(
    pa: pyaudio.PyAudio, output_base_dir: Path, seconds: float
) -> RecordingSessionResult:
    """その場でマイク・ループバックを録音し、結合済みファイル情報（開始・終了時刻付き）を返す。

    実際の会議は `seconds` より早く終わることがあるため、経過前にCtrl+C
    （KeyboardInterrupt）で中断した場合もその時点までの録音を確定させてから返す。
    """
    session = RecordingSession(pa, output_base_dir)
    session.start()
    try:
        time.sleep(seconds)
    except KeyboardInterrupt:
        print("Ctrl+Cを検知しました。ここまでの録音を確定します...")
    return session.stop()


def run_pipeline(
    session_dir: Path,
    db_path: Path,
    *,
    started_at: datetime | None = None,
    ended_at: datetime | None = None,
    model_size: str = DEFAULT_MODEL_SIZE,
    dictionary: dict[str, str] | None = None,
) -> BenchmarkResult:
    """録音済みセッション(mic.wav/loopback.wav)を文字起こし・マージ・DB永続化する。

    :param started_at: 録音開始時刻（F-1-7）。省略時は `mic.wav` の更新日時から
        `ended_at - 音声長` を逆算する（`--session-dir` で過去のセッションを直接
        指定した場合のフォールバック。`record_session` と同一プロセスで連携する場合は
        `RecordingSessionResult.started_at` をそのまま渡すこと）
    :param ended_at: 録音終了時刻。省略時は `mic.wav` の更新日時（ファイル結合完了時刻）を使う
    """
    mic_path = combined_file_path(session_dir, MIC_TRACK_NAME)
    loopback_path = combined_file_path(session_dir, LOOPBACK_TRACK_NAME)
    audio_duration_sec = max(_wav_duration_sec(mic_path), _wav_duration_sec(loopback_path))

    if ended_at is None:
        ended_at = datetime.fromtimestamp(mic_path.stat().st_mtime)
    if started_at is None:
        started_at = ended_at - timedelta(seconds=audio_duration_sec)

    conn = connection.connect(db_path)
    try:
        meeting_id = meetings_repository.create(
            conn, uid=session_dir.name, started_at=started_at.isoformat()
        )
        meetings_repository.mark_recorded(
            conn,
            meeting_id,
            ended_at=ended_at.isoformat(),
            duration_sec=round(audio_duration_sec),
        )

        expires_at = audio_files_repository.compute_expires_at(ended_at)
        for track_name, path in (
            (MIC_TRACK_NAME, mic_path),
            (LOOPBACK_TRACK_NAME, loopback_path),
        ):
            audio_files_repository.create(
                conn,
                meeting_id=meeting_id,
                track=track_name,
                stage=audio_files_repository.STAGE_RAW_WAV,
                path=str(path),
                expires_at=expires_at,
            )

        meetings_repository.update_status(
            conn, meeting_id, meetings_repository.STATUS_TRANSCRIBING
        )

        initial_prompt = build_initial_prompt(dictionary or {})
        model = load_model(model_size)

        transcribe_started = time.monotonic()
        mic_segments = transcribe_track(model, mic_path, initial_prompt=initial_prompt)
        loopback_segments = transcribe_track(model, loopback_path, initial_prompt=initial_prompt)
        transcribe_duration_sec = time.monotonic() - transcribe_started

        utterances = merge_tracks(mic_segments, loopback_segments)
        utterances_repository.bulk_insert(conn, meeting_id, utterances)

        meetings_repository.update_status(
            conn, meeting_id, meetings_repository.STATUS_AWAITING_STRUCTURING
        )

        real_time_factor = (
            transcribe_duration_sec / audio_duration_sec if audio_duration_sec else 0.0
        )
        # meeting作成〜utterances登録までを1トランザクションとしてまとめてコミットする。
        # 途中で例外が発生した場合はコミットされず、下のfinallyでconn.close()するだけで
        # 自動的にロールバックされる（中途半端な状態がDBに残らない）。
        conn.commit()
        return BenchmarkResult(
            meeting_id=meeting_id,
            utterance_count=len(utterances),
            audio_duration_sec=audio_duration_sec,
            transcribe_duration_sec=transcribe_duration_sec,
            real_time_factor=real_time_factor,
        )
    finally:
        conn.close()


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--session-dir", type=Path, default=None, help="既存の録音セッションディレクトリ"
    )
    parser.add_argument(
        "--record-seconds",
        type=float,
        default=None,
        help="指定時、その場でこの秒数だけ録音してから処理する",
    )
    parser.add_argument(
        "--model-size", type=str, default=DEFAULT_MODEL_SIZE, help="faster-whisperのモデルサイズ"
    )
    parser.add_argument(
        "--db-path", type=Path, default=None, help="既定: app_constants.get_db_path()"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="--record-seconds指定時の録音先。既定: app_constants.get_audio_dir()",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    if args.session_dir is None and args.record_seconds is None:
        print("--session-dir か --record-seconds のいずれかを指定してください。", file=sys.stderr)
        return 1

    session_dir = args.session_dir
    started_at = None
    ended_at = None
    if session_dir is None:
        output_dir = args.output_dir or get_audio_dir()
        print(f"{args.record_seconds}秒間録音します。会議アプリで音声を再生してください。")
        with pyaudio.PyAudio() as pa:
            recording_result = record_session(pa, output_dir, args.record_seconds)
        session_dir = recording_result.session_dir
        started_at = recording_result.started_at
        ended_at = recording_result.ended_at

    db_path = args.db_path or get_db_path()
    print(f"文字起こし中... (model={args.model_size})")
    result = run_pipeline(
        session_dir, db_path, started_at=started_at, ended_at=ended_at, model_size=args.model_size
    )

    print(f"meeting_id={result.meeting_id} 発言数={result.utterance_count}")
    print(
        f"音声長={result.audio_duration_sec:.1f}s 処理時間={result.transcribe_duration_sec:.1f}s "
        f"実時間比={result.real_time_factor:.2f}x"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
