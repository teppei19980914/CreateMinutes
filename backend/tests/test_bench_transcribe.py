import array
import wave
from datetime import datetime
from pathlib import Path

import pytest

from minutes_app import bench_transcribe
from minutes_app.core.transcriber.whisper_engine import TrackSegment
from minutes_app.db import connection
from minutes_app.db.repositories import meetings_repository


def _write_wav(path: Path, *, seconds: float, sample_rate: int = 16000, channels: int = 1) -> None:
    frame_count = round(seconds * sample_rate)
    samples = array.array("h", [0] * (frame_count * channels))
    with wave.open(str(path), "wb") as f:
        f.setnchannels(channels)
        f.setsampwidth(2)
        f.setframerate(sample_rate)
        f.writeframes(samples.tobytes())


def _make_session_dir(
    tmp_path: Path, *, mic_seconds: float = 1.0, loopback_seconds: float = 1.0
) -> Path:
    session_dir = tmp_path / "session"
    session_dir.mkdir()
    _write_wav(session_dir / "mic.wav", seconds=mic_seconds)
    _write_wav(session_dir / "loopback.wav", seconds=loopback_seconds)
    return session_dir


def _fake_transcribe_track(model, audio_path: Path, *, initial_prompt: str = ""):
    if audio_path.name == "mic.wav":
        return [TrackSegment(0.0, 1.0, "マイク発言")]
    return [TrackSegment(2.0, 3.0, "ループバック発言")]


class TestWavDurationSec:
    def test_returns_duration_from_frame_count_and_rate(self, tmp_path) -> None:
        path = tmp_path / "a.wav"
        _write_wav(path, seconds=2.5, sample_rate=16000)

        assert bench_transcribe._wav_duration_sec(path) == pytest.approx(2.5)


class TestRecordSession:
    def test_records_both_tracks_and_returns_result_with_timestamps(
        self, fake_pyaudio, tmp_path
    ) -> None:
        result = bench_transcribe.record_session(fake_pyaudio, tmp_path, 0.0)

        assert result.session_dir.parent == tmp_path
        assert (result.session_dir / "mic.wav").exists()
        assert (result.session_dir / "loopback.wav").exists()
        assert result.started_at <= result.ended_at

    def test_finalizes_recording_when_interrupted_before_seconds_elapse(
        self, fake_pyaudio, tmp_path, monkeypatch
    ) -> None:
        def _raise_keyboard_interrupt(seconds: float) -> None:
            raise KeyboardInterrupt

        monkeypatch.setattr(bench_transcribe.time, "sleep", _raise_keyboard_interrupt)

        result = bench_transcribe.record_session(fake_pyaudio, tmp_path, 3600.0)

        assert (result.session_dir / "mic.wav").exists()
        assert (result.session_dir / "loopback.wav").exists()
        assert result.started_at <= result.ended_at


class TestRunPipeline:
    def test_persists_meeting_audio_files_and_utterances(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(bench_transcribe, "load_model", lambda model_size: "fake-model")
        monkeypatch.setattr(bench_transcribe, "transcribe_track", _fake_transcribe_track)
        session_dir = _make_session_dir(tmp_path)
        db_path = tmp_path / "app.db"

        result = bench_transcribe.run_pipeline(session_dir, db_path)

        assert result.utterance_count == 2
        assert result.audio_duration_sec == pytest.approx(1.0)
        assert result.real_time_factor >= 0.0

        conn = connection.connect(db_path)
        meeting = meetings_repository.get_by_id(conn, result.meeting_id)
        assert meeting["status"] == meetings_repository.STATUS_AWAITING_STRUCTURING
        assert meeting["duration_sec"] == 1

        audio_files = conn.execute(
            "SELECT track FROM audio_files WHERE meeting_id = ? ORDER BY track",
            (result.meeting_id,),
        ).fetchall()
        assert {row["track"] for row in audio_files} == {"mic", "loopback"}

        utterances = conn.execute(
            "SELECT speaker, text FROM utterances WHERE meeting_id = ? ORDER BY seq_no",
            (result.meeting_id,),
        ).fetchall()
        assert [dict(row) for row in utterances] == [
            {"speaker": "self", "text": "マイク発言"},
            {"speaker": "other", "text": "ループバック発言"},
        ]
        conn.close()

    def test_rolls_back_everything_when_transcription_fails_partway(
        self, tmp_path, monkeypatch
    ) -> None:
        monkeypatch.setattr(bench_transcribe, "load_model", lambda model_size: "fake-model")

        call_count = {"n": 0}

        def _fail_on_second_track(model, audio_path, *, initial_prompt=""):
            call_count["n"] += 1
            if call_count["n"] == 2:
                raise RuntimeError("transcription crashed")
            return []

        monkeypatch.setattr(bench_transcribe, "transcribe_track", _fail_on_second_track)
        session_dir = _make_session_dir(tmp_path)
        db_path = tmp_path / "app.db"

        with pytest.raises(RuntimeError):
            bench_transcribe.run_pipeline(session_dir, db_path)

        conn = connection.connect(db_path)
        meetings = conn.execute("SELECT * FROM meetings").fetchall()
        audio_files = conn.execute("SELECT * FROM audio_files").fetchall()
        assert meetings == []
        assert audio_files == []
        conn.close()

    def test_uses_explicit_started_at_and_ended_at_when_given(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(bench_transcribe, "load_model", lambda model_size: "fake-model")
        monkeypatch.setattr(bench_transcribe, "transcribe_track", _fake_transcribe_track)
        session_dir = _make_session_dir(tmp_path)
        db_path = tmp_path / "app.db"
        started_at = datetime(2026, 8, 17, 10, 0, 0)
        ended_at = datetime(2026, 8, 17, 10, 0, 1)

        result = bench_transcribe.run_pipeline(
            session_dir, db_path, started_at=started_at, ended_at=ended_at
        )

        conn = connection.connect(db_path)
        meeting = meetings_repository.get_by_id(conn, result.meeting_id)
        assert meeting["started_at"] == started_at.isoformat()
        assert meeting["ended_at"] == ended_at.isoformat()
        conn.close()

    def test_derives_started_at_from_ended_at_minus_audio_duration_when_omitted(
        self, tmp_path, monkeypatch
    ) -> None:
        monkeypatch.setattr(bench_transcribe, "load_model", lambda model_size: "fake-model")
        monkeypatch.setattr(bench_transcribe, "transcribe_track", _fake_transcribe_track)
        session_dir = _make_session_dir(tmp_path, mic_seconds=2.0, loopback_seconds=2.0)
        db_path = tmp_path / "app.db"

        result = bench_transcribe.run_pipeline(session_dir, db_path)

        conn = connection.connect(db_path)
        meeting = meetings_repository.get_by_id(conn, result.meeting_id)
        started_at = datetime.fromisoformat(meeting["started_at"])
        ended_at = datetime.fromisoformat(meeting["ended_at"])
        assert (ended_at - started_at).total_seconds() == pytest.approx(2.0)
        assert started_at != ended_at
        conn.close()

    def test_passes_initial_prompt_built_from_dictionary(self, tmp_path, monkeypatch) -> None:
        captured_prompts: list[str] = []

        def _capture(model, audio_path, *, initial_prompt=""):
            captured_prompts.append(initial_prompt)
            return []

        monkeypatch.setattr(bench_transcribe, "load_model", lambda model_size: "fake-model")
        monkeypatch.setattr(bench_transcribe, "transcribe_track", _capture)
        session_dir = _make_session_dir(tmp_path)

        bench_transcribe.run_pipeline(
            session_dir, tmp_path / "app.db", dictionary={"にゅーとんX": "NewtonX"}
        )

        assert captured_prompts == ["以下の用語が登場します: NewtonX"] * 2


class TestParseArgs:
    def test_defaults_are_none_for_session_dir_and_record_seconds(self) -> None:
        args = bench_transcribe._parse_args([])

        assert args.session_dir is None
        assert args.record_seconds is None
        assert args.model_size == bench_transcribe.DEFAULT_MODEL_SIZE

    def test_parses_session_dir(self) -> None:
        args = bench_transcribe._parse_args(["--session-dir", "data/audio/xxx"])

        assert args.session_dir == Path("data/audio/xxx")

    def test_parses_record_seconds(self) -> None:
        args = bench_transcribe._parse_args(["--record-seconds", "30"])

        assert args.record_seconds == 30.0


class TestMain:
    def test_returns_error_when_neither_session_dir_nor_record_seconds_given(self, capsys) -> None:
        exit_code = bench_transcribe.main([])

        assert exit_code == 1
        assert "--session-dir" in capsys.readouterr().err

    def test_processes_existing_session_dir(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(bench_transcribe, "load_model", lambda model_size: "fake-model")
        monkeypatch.setattr(bench_transcribe, "transcribe_track", _fake_transcribe_track)
        session_dir = _make_session_dir(tmp_path)
        db_path = tmp_path / "app.db"

        exit_code = bench_transcribe.main(
            ["--session-dir", str(session_dir), "--db-path", str(db_path)]
        )

        assert exit_code == 0
        assert db_path.exists()

    def test_records_then_processes_when_record_seconds_given(
        self, fake_pyaudio, tmp_path, monkeypatch
    ) -> None:
        monkeypatch.setattr(bench_transcribe.pyaudio, "PyAudio", lambda: fake_pyaudio)
        monkeypatch.setattr(bench_transcribe, "load_model", lambda model_size: "fake-model")
        monkeypatch.setattr(bench_transcribe, "transcribe_track", _fake_transcribe_track)
        db_path = tmp_path / "app.db"
        output_dir = tmp_path / "audio"

        exit_code = bench_transcribe.main(
            [
                "--record-seconds",
                "0",
                "--output-dir",
                str(output_dir),
                "--db-path",
                str(db_path),
            ]
        )

        assert exit_code == 0
        assert db_path.exists()
