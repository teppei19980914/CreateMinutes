"""1トラック分のWASAPI録音（仕様書 #1 / docs/DESIGN.md §5.1 / docs/REQUIREMENTS.md F-1-1・F-1-3）。

録音は非ブロッキングコールバックで PortAudio 側のスレッドから直接 WAV へ書き込む方式とし、
公式サンプル（device_manager.py のモジュール docstring参照）と同じ手順（channels/rate は
デバイスのネイティブ値、format は paInt16 固定）で PyAudio.open() を呼び出す。WASAPI
ループバックはネイティブのサンプルレート・チャンネル数以外での取得を保証しないため、
16kHz/mono への変換は行わない（変換は文字起こし側で吸収する）。

60秒（既定）単位でファイルをローテーションする（F-1-3）。オーディオストリーム自体は
停止せず継続させたまま、コールバック内でファイル書き込み先だけを切り替えることで、
ローテーション時の録音欠落を避ける。暗号化（§5.5）は Phase 4 で追加するため、
Phase 1 の時点ではローリングファイルは平文WAVのまま保存する
（docs/DESIGN.md 改訂履歴 v0.12 参照）。
"""

import array
import wave
from pathlib import Path

import pyaudiowpatch as pyaudio

from minutes_app.core.recorder.device_manager import DeviceInfo

DEFAULT_CHUNK_FRAMES = 512
DEFAULT_ROLLING_SECONDS = 60.0
ROLLING_SEQUENCE_DIGITS = 4


def rolling_file_glob(track_name: str) -> str:
    """`{track_name}_NNNN.wav` 形式のローリングファイルを探すglobパターン。

    書き込み側（`TrackRecorder._open_next_file`）と探索側（`rolling_file_paths` /
    `session.list_rolling_files` / `session.find_incomplete_sessions`）で連番桁数の
    定義が食い違わないよう、命名規則をこの関数へ一元化する。
    """
    digits = "[0-9]" * ROLLING_SEQUENCE_DIGITS
    return f"{track_name}_{digits}.wav"


def calculate_rms(frames: bytes) -> float:
    """16bit PCMフレームのRMS(二乗平均平方根)を計算する。疎通確認（レベルメーター）用途。

    :param frames: リトルエンディアンの16bit PCM生データ（モノラル/ステレオ問わず先頭から解釈）
    :return: サンプル振幅のRMS値（dBFS等の音量スケールへの変換は行わない）
    """
    if not frames:
        return 0.0
    samples = array.array("h")
    samples.frombytes(frames)
    return (sum(sample * sample for sample in samples) / len(samples)) ** 0.5


class TrackRecorder:
    """1つのWASAPIデバイスを、60秒単位でローテーションしながらWAVファイルへ録音する。

    使用例::

        pa = pyaudio.PyAudio()
        recorder = TrackRecorder(pa, device, Path("data/audio/xxx"), "mic")
        recorder.start()
        ...
        recorder.stop()
        # recorder.rolling_file_paths が mic_0001.wav, mic_0002.wav, ... のリスト

    :param pa: 初期化済みの PyAudio インスタンス
    :param device: 録音対象デバイス（device_manager の関数で取得したもの）
    :param output_dir: ローリングファイルの出力先ディレクトリ。無ければ start() 時に作成する
    :param track_name: ファイル名の接頭辞（`mic` / `loopback` 等）
    :param rolling_seconds: この秒数分のフレームが溜まるたびに次の連番ファイルへ切り替える
    :param chunk_frames: PortAudioコールバックが1回に受け取るフレーム数。小さいほど
        `last_rms` の更新頻度が上がりレイテンシは下がるが、CPU負荷が増える
    """

    def __init__(
        self,
        pa: pyaudio.PyAudio,
        device: DeviceInfo,
        output_dir: Path,
        track_name: str,
        *,
        rolling_seconds: float = DEFAULT_ROLLING_SECONDS,
        chunk_frames: int = DEFAULT_CHUNK_FRAMES,
    ) -> None:
        self._pa = pa
        self._device = device
        self._output_dir = output_dir
        self._track_name = track_name
        self._rolling_frame_limit = round(rolling_seconds * device.default_sample_rate)
        self._chunk_frames = chunk_frames
        self._wave_writer: wave.Wave_write | None = None
        self._frames_in_current_file = 0
        self._sequence = 0
        self._stream = None
        self._last_rms = 0.0

    @property
    def last_rms(self) -> float:
        """直近に受信したフレームのRMS。録音中の疎通確認に使う。"""
        return self._last_rms

    @property
    def rolling_file_paths(self) -> list[Path]:
        """これまでに書き出したローリングファイルのパス（連番昇順）。"""
        return sorted(self._output_dir.glob(rolling_file_glob(self._track_name)))

    def _open_next_file(self) -> None:
        self._sequence += 1
        path = self._output_dir / (
            f"{self._track_name}_{self._sequence:0{ROLLING_SEQUENCE_DIGITS}d}.wav"
        )
        wave_writer = wave.open(str(path), "wb")
        wave_writer.setnchannels(self._device.max_input_channels)
        wave_writer.setsampwidth(pyaudio.get_sample_size(pyaudio.paInt16))
        wave_writer.setframerate(self._device.default_sample_rate)
        self._wave_writer = wave_writer
        self._frames_in_current_file = 0

    def start(self) -> None:
        """録音を開始する。"""
        if self._stream is not None:
            raise RuntimeError("recording is already in progress")

        self._output_dir.mkdir(parents=True, exist_ok=True)
        # コールバックは pa.open() 実行中（start=True既定のため即時開始）にも
        # 発火し得るため、最初のファイルは open() 呼び出し前に確定させる。
        self._open_next_file()

        try:
            self._stream = self._pa.open(
                format=pyaudio.paInt16,
                channels=self._device.max_input_channels,
                rate=self._device.default_sample_rate,
                frames_per_buffer=self._chunk_frames,
                input=True,
                input_device_index=self._device.index,
                stream_callback=self._on_audio,
            )
        except Exception:
            # デバイス排他エラー等でストリームを開けなかった場合、WAVハンドルを
            # リークさせず、再度 start() できる状態に戻す。
            wave_writer = self._wave_writer
            self._wave_writer = None
            wave_writer.close()
            raise

    def _on_audio(
        self, in_data: bytes, frame_count: int, time_info: dict, status: int
    ) -> tuple[bytes, int]:
        if self._frames_in_current_file >= self._rolling_frame_limit:
            self._wave_writer.close()
            self._open_next_file()
        self._wave_writer.writeframes(in_data)
        self._frames_in_current_file += frame_count
        self._last_rms = calculate_rms(in_data)
        return (in_data, pyaudio.paContinue)

    def stop(self) -> None:
        """録音を停止し、書き込み中のローリングファイルを確定する。録音中でなければ何もしない。"""
        if self._stream is None:
            return

        self._stream.stop_stream()
        self._stream.close()
        self._stream = None

        if self._wave_writer is not None:
            self._wave_writer.close()
            self._wave_writer = None
