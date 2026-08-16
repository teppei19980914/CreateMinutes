import array
import wave

import pytest

from minutes_app.core.recorder.device_manager import DeviceInfo
from minutes_app.core.recorder.track_recorder import TrackRecorder, calculate_rms

# サンプルレート=4Hz の架空デバイス。rolling_seconds=1.0 と組み合わせると
# ローテーション判定の閾値が「4フレーム溜まったら次のファイルへ」となり、
# 4サンプル(=1チャンク)ごとのローテーション挙動を単純な整数計算で検証できる。
ROLLING_TEST_DEVICE = DeviceInfo(
    index=1, name="テスト用", is_loopback=False, max_input_channels=1, default_sample_rate=4
)


def _pcm16(*samples: int) -> bytes:
    return array.array("h", samples).tobytes()


class TestCalculateRms:
    def test_empty_bytes_returns_zero(self) -> None:
        assert calculate_rms(b"") == 0.0

    def test_silence_returns_zero(self) -> None:
        assert calculate_rms(_pcm16(0, 0, 0, 0)) == 0.0

    def test_constant_amplitude_returns_that_amplitude(self) -> None:
        assert calculate_rms(_pcm16(100, -100, 100, -100)) == pytest.approx(100.0)


class TestTrackRecorder:
    def test_start_opens_stream_and_first_rolling_file_with_device_native_format(
        self, fake_pyaudio, mic_device, tmp_path
    ) -> None:
        recorder = TrackRecorder(fake_pyaudio, mic_device, tmp_path, "mic")

        recorder.start()

        assert fake_pyaudio.open_kwargs["channels"] == mic_device.max_input_channels
        assert fake_pyaudio.open_kwargs["rate"] == mic_device.default_sample_rate
        assert fake_pyaudio.open_kwargs["input_device_index"] == mic_device.index
        assert fake_pyaudio.open_kwargs["input"] is True
        assert (tmp_path / "mic_0001.wav").exists()
        assert recorder.rolling_file_paths == [tmp_path / "mic_0001.wav"]

        recorder.stop()

    def test_start_twice_raises(self, fake_pyaudio, mic_device, tmp_path) -> None:
        recorder = TrackRecorder(fake_pyaudio, mic_device, tmp_path, "mic")
        recorder.start()

        with pytest.raises(RuntimeError):
            recorder.start()

        recorder.stop()

    def test_stop_without_start_is_noop(self, fake_pyaudio, mic_device, tmp_path) -> None:
        recorder = TrackRecorder(fake_pyaudio, mic_device, tmp_path, "mic")

        recorder.stop()  # 例外が発生しないことを確認

        assert fake_pyaudio.open_kwargs is None

    def test_callback_writes_frames_and_updates_last_rms(
        self, fake_pyaudio, mic_device, tmp_path
    ) -> None:
        output_dir = tmp_path
        recorder = TrackRecorder(fake_pyaudio, mic_device, output_dir, "mic")
        recorder.start()

        chunk = _pcm16(200, -200, 200, -200)
        out_data, flag = fake_pyaudio.open_kwargs["stream_callback"](chunk, 4, {}, 0)

        assert out_data == chunk
        assert recorder.last_rms == pytest.approx(200.0)

        recorder.stop()

        with wave.open(str(output_dir / "mic_0001.wav"), "rb") as f:
            assert f.getnchannels() == mic_device.max_input_channels
            assert f.getframerate() == mic_device.default_sample_rate
            assert f.getsampwidth() == 2
            assert f.readframes(f.getnframes()) == chunk

    def test_stop_closes_stream_and_finalizes_wave_file(
        self, fake_pyaudio, mic_device, tmp_path
    ) -> None:
        recorder = TrackRecorder(fake_pyaudio, mic_device, tmp_path, "mic")
        recorder.start()

        recorder.stop()

        assert fake_pyaudio.stream.stopped is True
        assert fake_pyaudio.stream.closed is True

        # 停止後の再停止は何もしない
        recorder.stop()

    def test_start_closes_wave_file_and_resets_state_when_stream_open_fails(
        self, fake_pyaudio_cls, mic_device, tmp_path
    ) -> None:
        pa = fake_pyaudio_cls(open_error=OSError("device is busy"))
        recorder = TrackRecorder(pa, mic_device, tmp_path, "mic")

        with pytest.raises(OSError):
            recorder.start()

        assert recorder._wave_writer is None
        assert recorder._stream is None

        # WAVハンドルがリークしていなければ、正常なヘッダーで再オープンできる
        with wave.open(str(tmp_path / "mic_0001.wav"), "rb") as f:
            assert f.getnframes() == 0

    def test_rotates_to_next_file_once_rolling_limit_reached(
        self, fake_pyaudio, tmp_path
    ) -> None:
        # rolling_seconds=1.0 * サンプルレート4Hz = 4フレームで次ファイルへ切り替わる
        recorder = TrackRecorder(
            fake_pyaudio, ROLLING_TEST_DEVICE, tmp_path, "mic", rolling_seconds=1.0
        )
        recorder.start()
        callback = fake_pyaudio.open_kwargs["stream_callback"]
        chunk = _pcm16(10, 10, 10, 10)

        callback(chunk, 4, {}, 0)  # ちょうど閾値(4フレーム)まで file 1 に書き込む
        assert recorder.rolling_file_paths == [tmp_path / "mic_0001.wav"]

        callback(chunk, 4, {}, 0)  # 閾値到達済みのため file 2 へローテーション
        assert recorder.rolling_file_paths == [
            tmp_path / "mic_0001.wav",
            tmp_path / "mic_0002.wav",
        ]

        recorder.stop()

        with wave.open(str(tmp_path / "mic_0001.wav"), "rb") as f:
            assert f.getnframes() == 4
        with wave.open(str(tmp_path / "mic_0002.wav"), "rb") as f:
            assert f.getnframes() == 4
