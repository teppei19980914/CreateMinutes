from minutes_app.core.recorder import poc_verify
from minutes_app.core.recorder.poc_verify import main, run


def test_run_creates_two_wav_files(fake_pyaudio, tmp_path) -> None:
    mic_path, loopback_path = run(fake_pyaudio, 0.0, tmp_path)

    assert mic_path.name == "mic.wav"
    assert loopback_path.name == "loopback.wav"
    assert mic_path.parent == loopback_path.parent
    assert mic_path.parent.parent == tmp_path
    assert mic_path.exists()
    assert loopback_path.exists()


def test_run_prints_progress_while_recording(fake_pyaudio, tmp_path, capsys) -> None:
    run(fake_pyaudio, 0.02, tmp_path, poll_interval_seconds=0.01)

    captured = capsys.readouterr()
    assert "RMS" in captured.out
    assert "完了" in captured.out


def test_main_parses_args_and_invokes_run(fake_pyaudio, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(poc_verify.pyaudio, "PyAudio", lambda: fake_pyaudio)

    exit_code = main(["--seconds", "0", "--output-dir", str(tmp_path)])

    assert exit_code == 0
    session_dirs = [p for p in tmp_path.iterdir() if p.is_dir()]
    assert len(session_dirs) == 1
    assert (session_dirs[0] / "mic.wav").exists()
    assert (session_dirs[0] / "loopback.wav").exists()


def test_parse_args_applies_defaults_when_flags_omitted() -> None:
    args = poc_verify._parse_args([])

    assert args.seconds == poc_verify.DEFAULT_DURATION_SECONDS
    assert args.output_dir == poc_verify.DEFAULT_OUTPUT_DIR
