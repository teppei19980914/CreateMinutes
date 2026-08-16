"""recorder配下のテストで共有するPyAudio(pyaudiowpatch)テストダブル。

`FakePyAudio`/`FakeStream` を各テストファイルが個別に実装すると、pyaudiowpatch実APIの
シグネチャ変更時に修正漏れが起きやすい（DRY違反）ため、本ファイルに一元化する。
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
    """device_manager/track_recorder/poc_verify のテストで共有する PyAudio テストダブル。

    `with pyaudio.PyAudio() as pa:` 形式（poc_verify.main）でも直接（他テスト）でも使えるよう、
    コンテキストマネージャも常に実装する。

    :param loopback_devices: get_loopback_device_info_generator() が返す生dictのリスト
    :param default_input: get_default_wasapi_device(d_in=True) の戻り値
    :param default_loopback: get_default_wasapi_loopback() の戻り値
    :param open_error: 指定時、open() 呼び出しでこの例外を送出する（異常系テスト用）
    """

    def __init__(
        self,
        *,
        loopback_devices: list[dict] | None = None,
        default_input: dict | None = None,
        default_loopback: dict | None = None,
        open_error: Exception | None = None,
    ) -> None:
        self._loopback_devices = (
            loopback_devices if loopback_devices is not None else [LOOPBACK_RAW_DEVICE]
        )
        self._default_input = default_input if default_input is not None else MIC_RAW_DEVICE
        self._default_loopback = (
            default_loopback if default_loopback is not None else LOOPBACK_RAW_DEVICE
        )
        self._open_error = open_error
        self.open_kwargs: dict | None = None
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
        if self._open_error is not None:
            raise self._open_error
        return self.stream

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
