"""1トラック分のWASAPI録音（仕様書 #1 / docs/DESIGN.md §5.1 / docs/REQUIREMENTS.md F-1-1）。

Phase 0 骨格のため、60秒ローリング書き出し・暗号化（§5.5）・2トラック統括（session.py）は
Phase 1 以降で追加する。録音は非ブロッキングコールバックで PortAudio 側のスレッドから
直接 WAV へ書き込む方式とし、公式サンプル（device_manager.py のモジュール docstring参照）と
同じ手順（channels/rate はデバイスのネイティブ値、format は paInt16 固定）で
PyAudio.open() を呼び出す。WASAPI ループバックはネイティブのサンプルレート・チャンネル数
以外での取得を保証しないため、16kHz/mono への変換は行わない（変換は文字起こし側で吸収する）。
"""

import array
import wave
from pathlib import Path

import pyaudiowpatch as pyaudio

from minutes_app.core.recorder.device_manager import DeviceInfo

DEFAULT_CHUNK_FRAMES = 512


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
    """1つのWASAPIデバイスをWAVファイルへ録音する。

    使用例::

        pa = pyaudio.PyAudio()
        recorder = TrackRecorder(pa, device, Path("mic.wav"))
        recorder.start()
        ...
        recorder.stop()

    :param pa: 初期化済みの PyAudio インスタンス
    :param device: 録音対象デバイス（device_manager の関数で取得したもの）
    :param output_path: 出力WAVファイルパス。親ディレクトリが無ければ start() 時に作成する
    :param chunk_frames: PortAudioコールバックが1回に受け取るフレーム数。小さいほど
        `last_rms` の更新頻度が上がりレイテンシは下がるが、CPU負荷が増える
    """

    def __init__(
        self,
        pa: pyaudio.PyAudio,
        device: DeviceInfo,
        output_path: Path,
        *,
        chunk_frames: int = DEFAULT_CHUNK_FRAMES,
    ) -> None:
        self._pa = pa
        self._device = device
        self._output_path = output_path
        self._chunk_frames = chunk_frames
        self._wave_writer: wave.Wave_write | None = None
        self._stream = None
        self._last_rms = 0.0

    @property
    def last_rms(self) -> float:
        """直近に受信したフレームのRMS。録音中の疎通確認に使う。"""
        return self._last_rms

    def start(self) -> None:
        """録音を開始する。"""
        if self._stream is not None:
            raise RuntimeError("recording is already in progress")

        self._output_path.parent.mkdir(parents=True, exist_ok=True)
        wave_writer = wave.open(str(self._output_path), "wb")
        wave_writer.setnchannels(self._device.max_input_channels)
        wave_writer.setsampwidth(pyaudio.get_sample_size(pyaudio.paInt16))
        wave_writer.setframerate(self._device.default_sample_rate)
        # コールバックは pa.open() 実行中（start=True既定のため即時開始）にも
        # 発火し得るため、_wave_writer は open() 呼び出し前に確定させる。
        self._wave_writer = wave_writer

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
            self._wave_writer = None
            wave_writer.close()
            raise

    def _on_audio(
        self, in_data: bytes, frame_count: int, time_info: dict, status: int
    ) -> tuple[bytes, int]:
        self._wave_writer.writeframes(in_data)
        self._last_rms = calculate_rms(in_data)
        return (in_data, pyaudio.paContinue)

    def stop(self) -> None:
        """録音を停止し、WAVファイルを確定する。録音中でなければ何もしない。"""
        if self._stream is None:
            return

        self._stream.stop_stream()
        self._stream.close()
        self._stream = None

        if self._wave_writer is not None:
            self._wave_writer.close()
            self._wave_writer = None
