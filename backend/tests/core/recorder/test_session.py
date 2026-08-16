import array
import wave
from datetime import datetime

import pytest

from minutes_app.core.recorder.session import (
    RecordingSession,
    combine_rolling_files,
    find_incomplete_sessions,
)


def _pcm16(*samples: int) -> bytes:
    return array.array("h", samples).tobytes()


class TestRecordingSession:
    def test_start_opens_both_tracks_under_a_generated_session_dir(
        self, fake_pyaudio, tmp_path
    ) -> None:
        session = RecordingSession(fake_pyaudio, tmp_path)

        session.start()

        assert session.session_dir == tmp_path / session.meeting_uid
        assert session.is_recording is True
        assert len(fake_pyaudio.open_calls) == 2
        assert (session.session_dir / "mic_0001.wav").exists()
        assert (session.session_dir / "loopback_0001.wav").exists()

        session.stop()

    def test_start_uses_given_meeting_uid(self, fake_pyaudio, tmp_path) -> None:
        session = RecordingSession(fake_pyaudio, tmp_path, meeting_uid="fixed-uid")

        session.start()

        assert session.session_dir == tmp_path / "fixed-uid"

        session.stop()

    def test_start_twice_raises(self, fake_pyaudio, tmp_path) -> None:
        session = RecordingSession(fake_pyaudio, tmp_path)
        session.start()

        with pytest.raises(RuntimeError):
            session.start()

        session.stop()

    def test_stop_without_start_raises(self, fake_pyaudio, tmp_path) -> None:
        session = RecordingSession(fake_pyaudio, tmp_path)

        with pytest.raises(RuntimeError):
            session.stop()

    def test_stop_combines_rolling_files_for_both_tracks(
        self, fake_pyaudio, tmp_path
    ) -> None:
        session = RecordingSession(fake_pyaudio, tmp_path)
        session.start()

        mic_callback = fake_pyaudio.open_calls[0]["stream_callback"]
        loopback_callback = fake_pyaudio.open_calls[1]["stream_callback"]
        mic_chunk = _pcm16(1, 2, 3, 4)
        loopback_chunk = _pcm16(5, 6, 7, 8, 9, 10)
        mic_callback(mic_chunk, 4, {}, 0)
        loopback_callback(loopback_chunk, 3, {}, 0)

        result = session.stop()

        assert result.session_dir == session.session_dir
        assert result.mic_path == session.session_dir / "mic.wav"
        assert result.loopback_path == session.session_dir / "loopback.wav"
        with wave.open(str(result.mic_path), "rb") as f:
            assert f.readframes(f.getnframes()) == mic_chunk
        with wave.open(str(result.loopback_path), "rb") as f:
            assert f.readframes(f.getnframes()) == loopback_chunk

    def test_stop_resets_state_so_session_can_be_restarted(
        self, fake_pyaudio, tmp_path
    ) -> None:
        session = RecordingSession(fake_pyaudio, tmp_path)
        session.start()
        session.stop()

        assert session.is_recording is False

    def test_stop_returns_started_at_and_ended_at(self, fake_pyaudio, tmp_path) -> None:
        session = RecordingSession(fake_pyaudio, tmp_path)

        before_start = datetime.now()
        session.start()
        result = session.stop()
        after_stop = datetime.now()

        assert before_start <= result.started_at <= result.ended_at <= after_stop

    def test_rms_properties_reflect_underlying_recorders(
        self, fake_pyaudio, tmp_path
    ) -> None:
        session = RecordingSession(fake_pyaudio, tmp_path)

        assert session.mic_last_rms == 0.0
        assert session.loopback_last_rms == 0.0

        session.start()
        mic_callback = fake_pyaudio.open_calls[0]["stream_callback"]
        loopback_callback = fake_pyaudio.open_calls[1]["stream_callback"]
        mic_callback(_pcm16(100, -100, 100, -100), 4, {}, 0)
        loopback_callback(_pcm16(50, -50, 50, -50), 4, {}, 0)

        assert session.mic_last_rms == pytest.approx(100.0)
        assert session.loopback_last_rms == pytest.approx(50.0)

        session.stop()

    def test_start_rolls_back_mic_recorder_when_loopback_open_fails(
        self, fake_pyaudio_cls, tmp_path
    ) -> None:
        pa = fake_pyaudio_cls(open_error=OSError("device is busy"), open_fails_on_call=2)
        session = RecordingSession(pa, tmp_path)

        with pytest.raises(OSError):
            session.start()

        assert session.is_recording is False
        assert pa.streams[0].stopped is True
        assert pa.streams[0].closed is True


class TestCombineRollingFiles:
    def test_combines_multiple_rolling_files_in_sequence_order(self, tmp_path) -> None:
        session_dir = tmp_path / "session"
        session_dir.mkdir()
        for index, samples in enumerate([(1, 2), (3, 4), (5, 6)], start=1):
            with wave.open(str(session_dir / f"mic_{index:04d}.wav"), "wb") as f:
                f.setnchannels(1)
                f.setsampwidth(2)
                f.setframerate(16000)
                f.writeframes(_pcm16(*samples))

        combined_path = combine_rolling_files(session_dir, "mic")

        assert combined_path == session_dir / "mic.wav"
        with wave.open(str(combined_path), "rb") as f:
            assert f.getnchannels() == 1
            assert f.getframerate() == 16000
            assert f.readframes(f.getnframes()) == _pcm16(1, 2, 3, 4, 5, 6)

    def test_raises_file_not_found_when_no_rolling_files_exist(self, tmp_path) -> None:
        session_dir = tmp_path / "empty-session"
        session_dir.mkdir()

        with pytest.raises(FileNotFoundError):
            combine_rolling_files(session_dir, "mic")


class TestFindIncompleteSessions:
    def test_returns_empty_list_when_base_dir_does_not_exist(self, tmp_path) -> None:
        assert find_incomplete_sessions(tmp_path / "missing") == []

    def test_detects_session_with_rolling_files_but_no_combined_file(self, tmp_path) -> None:
        incomplete_dir = tmp_path / "incomplete-session"
        incomplete_dir.mkdir()
        (incomplete_dir / "mic_0001.wav").write_bytes(b"")

        assert find_incomplete_sessions(tmp_path) == [incomplete_dir]

    def test_ignores_session_with_combined_file_present(self, tmp_path) -> None:
        complete_dir = tmp_path / "complete-session"
        complete_dir.mkdir()
        (complete_dir / "mic_0001.wav").write_bytes(b"")
        (complete_dir / "mic.wav").write_bytes(b"")

        assert find_incomplete_sessions(tmp_path) == []

    def test_ignores_directory_with_no_rolling_files(self, tmp_path) -> None:
        empty_dir = tmp_path / "no-rolling-files"
        empty_dir.mkdir()

        assert find_incomplete_sessions(tmp_path) == []
