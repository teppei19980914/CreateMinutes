from minutes_app.core.transcriber import whisper_engine
from minutes_app.core.transcriber.whisper_engine import TrackSegment, load_model, transcribe_track


class _FakeSegment:
    def __init__(self, start: float, end: float, text: str) -> None:
        self.start = start
        self.end = end
        self.text = text


class _FakeModel:
    def __init__(self, segments: list[_FakeSegment]) -> None:
        self._segments = segments
        self.transcribe_audio = None
        self.transcribe_kwargs: dict | None = None

    def transcribe(self, audio, **kwargs):
        self.transcribe_audio = audio
        self.transcribe_kwargs = kwargs
        return iter(self._segments), None


class TestTranscribeTrack:
    def test_returns_normalized_segments_with_stripped_text(self, tmp_path) -> None:
        model = _FakeModel([_FakeSegment(0.0, 1.2, "  こんにちは  ")])

        segments = transcribe_track(model, tmp_path / "mic.wav")

        assert segments == [TrackSegment(start_sec=0.0, end_sec=1.2, text="こんにちは")]

    def test_filters_out_segments_that_are_empty_after_stripping(self, tmp_path) -> None:
        model = _FakeModel([_FakeSegment(0.0, 1.0, "   "), _FakeSegment(1.0, 2.0, "発言")])

        segments = transcribe_track(model, tmp_path / "mic.wav")

        assert segments == [TrackSegment(start_sec=1.0, end_sec=2.0, text="発言")]

    def test_calls_transcribe_with_japanese_vad_and_word_timestamps(self, tmp_path) -> None:
        model = _FakeModel([])
        audio_path = tmp_path / "mic.wav"

        transcribe_track(model, audio_path)

        assert model.transcribe_audio == str(audio_path)
        assert model.transcribe_kwargs["language"] == "ja"
        assert model.transcribe_kwargs["vad_filter"] is True
        assert model.transcribe_kwargs["word_timestamps"] is True

    def test_passes_none_as_initial_prompt_when_empty_string(self, tmp_path) -> None:
        model = _FakeModel([])

        transcribe_track(model, tmp_path / "mic.wav", initial_prompt="")

        assert model.transcribe_kwargs["initial_prompt"] is None

    def test_passes_initial_prompt_through_when_given(self, tmp_path) -> None:
        model = _FakeModel([])

        transcribe_track(model, tmp_path / "mic.wav", initial_prompt="用語一覧")

        assert model.transcribe_kwargs["initial_prompt"] == "用語一覧"


class TestLoadModel:
    def test_forwards_model_size_compute_type_and_cpu_threads(self, monkeypatch) -> None:
        captured: dict = {}

        class _FakeWhisperModel:
            def __init__(self, model_size_or_path, device, compute_type, cpu_threads):
                captured["model_size_or_path"] = model_size_or_path
                captured["device"] = device
                captured["compute_type"] = compute_type
                captured["cpu_threads"] = cpu_threads

        monkeypatch.setattr(whisper_engine, "WhisperModel", _FakeWhisperModel)

        load_model("small", compute_type="int8", cpu_threads=2)

        assert captured == {
            "model_size_or_path": "small",
            "device": "cpu",
            "compute_type": "int8",
            "cpu_threads": 2,
        }

    def test_defaults_to_large_v3_turbo_and_int8(self, monkeypatch) -> None:
        captured: dict = {}

        class _FakeWhisperModel:
            def __init__(self, model_size_or_path, device, compute_type, cpu_threads):
                captured["model_size_or_path"] = model_size_or_path
                captured["compute_type"] = compute_type

        monkeypatch.setattr(whisper_engine, "WhisperModel", _FakeWhisperModel)

        load_model()

        assert captured == {"model_size_or_path": "large-v3-turbo", "compute_type": "int8"}
