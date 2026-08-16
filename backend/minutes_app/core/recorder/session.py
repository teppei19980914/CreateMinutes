"""マイク・ループバックの2トラック録音統括（仕様書 #1 / docs/DESIGN.md §5.1「録音セッション」
/ docs/REQUIREMENTS.md F-1-1・F-1-3・F-1-4）。

`TrackRecorder` を2本（マイク/ループバック）同時に開始・停止し、終了時にローリングファイルを
1本へ結合する。異常終了時の復旧提案（F-1-4）は、次回起動時に「ローリングファイルはあるが
結合済みファイルが無い」セッションディレクトリを検出する `find_incomplete_sessions` として
提供する（実際にユーザーへ提案するUIはPhase 3以降）。暗号化（§5.5）はPhase 4で追加するため、
Phase 1では結合後ファイルも平文WAVのまま保存する（docs/DESIGN.md 改訂履歴 v0.12 参照）。
"""

import uuid
import wave
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pyaudiowpatch as pyaudio

from minutes_app.core.recorder.device_manager import (
    get_default_input_device,
    get_default_loopback_device,
)
from minutes_app.core.recorder.track_recorder import (
    DEFAULT_ROLLING_SECONDS,
    TrackRecorder,
    rolling_file_glob,
)

MIC_TRACK_NAME = "mic"
LOOPBACK_TRACK_NAME = "loopback"


@dataclass(frozen=True)
class RecordingSessionResult:
    """録音セッション終了時に得られる結合済みファイルの情報（F-1-7: 開始・終了時刻の記録）。"""

    session_dir: Path
    mic_path: Path
    loopback_path: Path
    started_at: datetime
    ended_at: datetime


class RecordingSession:
    """1会議分のマイク・ループバック録音（2トラック）を統括する。

    使用例::

        with pyaudio.PyAudio() as pa:
            session = RecordingSession(pa, base_dir)
            session.start()
            ...
            result = session.stop()  # result.mic_path / result.loopback_path

    :param pa: 初期化済みの PyAudio インスタンス
    :param base_dir: セッションディレクトリ（`base_dir/{meeting_uid}/`）の親ディレクトリ
    :param meeting_uid: セッション識別子。省略時は自動生成（UUID hex）
    :param rolling_seconds: 各トラックのファイルローテーション間隔（TrackRecorder参照）
    """

    def __init__(
        self,
        pa: pyaudio.PyAudio,
        base_dir: Path,
        *,
        meeting_uid: str | None = None,
        rolling_seconds: float = DEFAULT_ROLLING_SECONDS,
    ) -> None:
        self._pa = pa
        self.meeting_uid = meeting_uid or uuid.uuid4().hex
        self.session_dir = base_dir / self.meeting_uid
        self._rolling_seconds = rolling_seconds
        self._started_at: datetime | None = None
        self._mic_recorder: TrackRecorder | None = None
        self._loopback_recorder: TrackRecorder | None = None

    @property
    def is_recording(self) -> bool:
        """録音中かどうか（`start()`済みで`stop()`前ならTrue）。"""
        return self._mic_recorder is not None

    @property
    def mic_last_rms(self) -> float:
        """マイクトラックの直近RMS。録音中の疎通確認に使う（未録音時は0.0）。"""
        return self._mic_recorder.last_rms if self._mic_recorder is not None else 0.0

    @property
    def loopback_last_rms(self) -> float:
        """ループバックトラックの直近RMS。録音中の疎通確認に使う（未録音時は0.0）。"""
        return self._loopback_recorder.last_rms if self._loopback_recorder is not None else 0.0

    def start(self) -> None:
        """マイク・ループバックの録音を同時に開始する。"""
        if self._mic_recorder is not None:
            raise RuntimeError("recording is already in progress")

        self.session_dir.mkdir(parents=True, exist_ok=True)
        mic_device = get_default_input_device(self._pa)
        loopback_device = get_default_loopback_device(self._pa)

        mic_recorder = TrackRecorder(
            self._pa,
            mic_device,
            self.session_dir,
            MIC_TRACK_NAME,
            rolling_seconds=self._rolling_seconds,
        )
        loopback_recorder = TrackRecorder(
            self._pa,
            loopback_device,
            self.session_dir,
            LOOPBACK_TRACK_NAME,
            rolling_seconds=self._rolling_seconds,
        )

        mic_recorder.start()
        try:
            loopback_recorder.start()
        except Exception:
            mic_recorder.stop()
            raise

        self._started_at = datetime.now()
        self._mic_recorder = mic_recorder
        self._loopback_recorder = loopback_recorder

    def stop(self) -> RecordingSessionResult:
        """録音を停止し、両トラックのローリングファイルを結合して返す（F-1-7）。"""
        if self._mic_recorder is None or self._loopback_recorder is None:
            raise RuntimeError("recording has not been started")

        self._mic_recorder.stop()
        self._loopback_recorder.stop()
        self._mic_recorder = None
        self._loopback_recorder = None
        started_at = self._started_at
        ended_at = datetime.now()
        self._started_at = None

        mic_path = combine_rolling_files(self.session_dir, MIC_TRACK_NAME)
        loopback_path = combine_rolling_files(self.session_dir, LOOPBACK_TRACK_NAME)
        return RecordingSessionResult(
            self.session_dir, mic_path, loopback_path, started_at, ended_at
        )


def list_rolling_files(session_dir: Path, track_name: str) -> list[Path]:
    """指定トラックのローリングファイルを連番昇順で列挙する。"""
    return sorted(session_dir.glob(rolling_file_glob(track_name)))


def combined_file_path(session_dir: Path, track_name: str) -> Path:
    """結合済みファイルの想定パス（`{track_name}.wav`）を返す。実体の存在は保証しない。"""
    return session_dir / f"{track_name}.wav"


def combine_rolling_files(session_dir: Path, track_name: str) -> Path:
    """ローリング書き出しされた `{track_name}_NNNN.wav` 群を `{track_name}.wav` へ結合する。

    :raises FileNotFoundError: 対象トラックのローリングファイルが1つも無い場合
    """
    parts = list_rolling_files(session_dir, track_name)
    if not parts:
        raise FileNotFoundError(f"no rolling files found for track '{track_name}' in {session_dir}")

    output_path = combined_file_path(session_dir, track_name)
    with wave.open(str(parts[0]), "rb") as first:
        params = first.getparams()

    with wave.open(str(output_path), "wb") as out:
        out.setparams(params)
        for part in parts:
            with wave.open(str(part), "rb") as part_reader:
                out.writeframes(part_reader.readframes(part_reader.getnframes()))

    return output_path


def find_incomplete_sessions(base_dir: Path) -> list[Path]:
    """結合済みファイルが無いのにローリングファイルが残っているセッションを検出する（F-1-4）。

    :param base_dir: `RecordingSession` に渡したものと同じ親ディレクトリ
    :return: 復旧提案の対象となるセッションディレクトリ一覧（`session_dir`）
    """
    if not base_dir.exists():
        return []

    incomplete = []
    for session_dir in sorted(p for p in base_dir.iterdir() if p.is_dir()):
        has_rolling = any(session_dir.glob(rolling_file_glob("*")))
        mic_combined = combined_file_path(session_dir, MIC_TRACK_NAME)
        loopback_combined = combined_file_path(session_dir, LOOPBACK_TRACK_NAME)
        has_combined = mic_combined.exists() or loopback_combined.exists()
        if has_rolling and not has_combined:
            incomplete.append(session_dir)
    return incomplete
