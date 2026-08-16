"""backend/tests 全体で共有するPyAudio(pyaudiowpatch)テストダブル。

`FakePyAudio`/`FakeStream` を各テストファイルが個別に実装すると、pyaudiowpatch実APIの
シグネチャ変更時に修正漏れが起きやすい（DRY違反）ため、本ファイルに一元化する。
（トップレベルの `conftest.py` に置くことで、recorder配下だけでなく `bench_transcribe`
等の録音セッションを扱う全テストから再利用できる。）
"""

import pytest

from minutes_app.core.recorder.device_manager import DeviceInfo

MIC_RAW_DEVICE = {
    "index": 1,
    "name": "マイク配列 (Realtek Audio)",
    "isLoopbackDevice": False,
    "maxInputChannels": 1,
    "defaultSampleRate": 48000.0,
}

LOOPBACK_RAW_DEVICE = {
    "index": 7,
    "name": "スピーカー (Realtek Audio) [Loopback]",
    "isLoopbackDevice": True,
    "maxInputChannels": 2,
    "defaultSampleRate": 44100.0,
}

MIC_DEVICE = DeviceInfo(
    index=1, name="マイク", is_loopback=False, max_input_channels=1, default_sample_rate=16000
)


class FakeStream:
    """pyaudiowpatch.Stream の骨格を模したテストダブル。"""

    def __init__(self) -> None:
        self.stopped = False
        self.closed = False

    def stop_stream(self) -> None:
        self.stopped = True

    def close(self) -> None:
        self.closed = True


class FakePyAudio:
    """device_manager/track_recorder/session/poc_verify/bench_transcribe のテストで共有する
    PyAudio テストダブル。

    `with pyaudio.PyAudio() as pa:` 形式でも直接（他テスト）でも使えるよう、
    コンテキストマネージャも常に実装する。

    :param loopback_devices: get_loopback_device_info_generator() が返す生dictのリスト
    :param default_input: get_default_wasapi_device(d_in=True) の戻り値
    :param default_loopback: get_default_wasapi_loopback() の戻り値
    :param open_error: 指定時、open() 呼び出しでこの例外を送出する（異常系テスト用）
    :param open_fails_on_call: 指定時、`open_error` をこの呼び出し回数目（1始まり）のみで
        送出する。省略時は毎回送出する（2トラック中の片方だけ失敗させたい場合に使う）
    """

    def __init__(
        self,
        *,
        loopback_devices: list[dict] | None = None,
        default_input: dict | None = None,
        default_loopback: dict | None = None,
        open_error: Exception | None = None,
        open_fails_on_call: int | None = None,
    ) -> None:
        self._loopback_devices = (
            loopback_devices if loopback_devices is not None else [LOOPBACK_RAW_DEVICE]
        )
        self._default_input = default_input if default_input is not None else MIC_RAW_DEVICE
        self._default_loopback = (
            default_loopback if default_loopback is not None else LOOPBACK_RAW_DEVICE
        )
        self._open_error = open_error
        self._open_fails_on_call = open_fails_on_call
        self.open_kwargs: dict | None = None
        self.open_calls: list[dict] = []
        self.streams: list[FakeStream] = []
        self.stream = FakeStream()

    def get_loopback_device_info_generator(self):
        yield from self._loopback_devices

    def get_default_wasapi_device(self, *, d_in: bool = False):
        assert d_in is True
        return self._default_input

    def get_default_wasapi_loopback(self):
        return self._default_loopback

    def open(self, **kwargs):
        self.open_kwargs = kwargs
        self.open_calls.append(kwargs)
        call_number = len(self.open_calls)
        should_fail = self._open_error is not None and (
            self._open_fails_on_call is None or call_number == self._open_fails_on_call
        )
        if should_fail:
            raise self._open_error
        stream = FakeStream()
        self.streams.append(stream)
        self.stream = stream
        return stream

    def __enter__(self) -> FakePyAudio:
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        return False


@pytest.fixture
def fake_pyaudio_cls():
    """FakePyAudio クラスそのもの。異常系等、個別のコンストラクタ引数を指定したい場合に使う。"""
    return FakePyAudio


@pytest.fixture
def fake_pyaudio() -> FakePyAudio:
    """既定のマイク/ループバックデバイスを持つ FakePyAudio インスタンス。"""
    return FakePyAudio()


@pytest.fixture
def mic_device() -> DeviceInfo:
    return MIC_DEVICE


@pytest.fixture
def mic_raw_device() -> dict:
    return dict(MIC_RAW_DEVICE)


@pytest.fixture
def loopback_raw_device() -> dict:
    return dict(LOOPBACK_RAW_DEVICE)
