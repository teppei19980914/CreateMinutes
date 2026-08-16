import array
import wave

import pytest

from minutes_app.core.recorder.track_recorder import TrackRecorder, calculate_rms


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
    def test_start_opens_stream_with_device_native_format(
        self, fake_pyaudio, mic_device, tmp_path
    ) -> None:
        output_path = tmp_path / "mic.wav"
        recorder = TrackRecorder(fake_pyaudio, mic_device, output_path)

        recorder.start()

        assert fake_pyaudio.open_kwargs["channels"] == mic_device.max_input_channels
        assert fake_pyaudio.open_kwargs["rate"] == mic_device.default_sample_rate
        assert fake_pyaudio.open_kwargs["input_device_index"] == mic_device.index
        assert fake_pyaudio.open_kwargs["input"] is True
        assert output_path.exists()

        recorder.stop()

    def test_start_twice_raises(self, fake_pyaudio, mic_device, tmp_path) -> None:
        recorder = TrackRecorder(fake_pyaudio, mic_device, tmp_path / "mic.wav")
        recorder.start()

        with pytest.raises(RuntimeError):
            recorder.start()

        recorder.stop()

    def test_stop_without_start_is_noop(self, fake_pyaudio, mic_device, tmp_path) -> None:
        recorder = TrackRecorder(fake_pyaudio, mic_device, tmp_path / "mic.wav")

        recorder.stop()  # 例外が発生しないことを確認

        assert fake_pyaudio.open_kwargs is None

    def test_callback_writes_frames_and_updates_last_rms(
        self, fake_pyaudio, mic_device, tmp_path
    ) -> None:
        output_path = tmp_path / "mic.wav"
        recorder = TrackRecorder(fake_pyaudio, mic_device, output_path)
        recorder.start()

        chunk = _pcm16(200, -200, 200, -200)
        out_data, flag = fake_pyaudio.open_kwargs["stream_callback"](chunk, 4, {}, 0)

        assert out_data == chunk
        assert recorder.last_rms == pytest.approx(200.0)

        recorder.stop()

        with wave.open(str(output_path), "rb") as f:
            assert f.getnchannels() == mic_device.max_input_channels
            assert f.getframerate() == mic_device.default_sample_rate
            assert f.getsampwidth() == 2
            assert f.readframes(f.getnframes()) == chunk

    def test_stop_closes_stream_and_finalizes_wave_file(
        self, fake_pyaudio, mic_device, tmp_path
    ) -> None:
        recorder = TrackRecorder(fake_pyaudio, mic_device, tmp_path / "mic.wav")
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
        output_path = tmp_path / "mic.wav"
        recorder = TrackRecorder(pa, mic_device, output_path)

        with pytest.raises(OSError):
            recorder.start()

        assert recorder._wave_writer is None
        assert recorder._stream is None

        # WAVハンドルがリークしていれば、正常なヘッダーで再オープンできない
        with wave.open(str(output_path), "rb") as f:
            assert f.getnframes() == 0
