import pytest

from minutes_app.core.recorder.device_manager import (
    DeviceInfo,
    get_default_input_device,
    get_default_loopback_device,
    list_loopback_devices,
)


def test_list_loopback_devices_converts_raw_dicts_to_device_info(
    fake_pyaudio_cls, loopback_raw_device
) -> None:
    pa = fake_pyaudio_cls(loopback_devices=[loopback_raw_device])

    devices = list_loopback_devices(pa)

    assert devices == [
        DeviceInfo(
            index=7,
            name="スピーカー (Realtek Audio) [Loopback]",
            is_loopback=True,
            max_input_channels=2,
            default_sample_rate=44100,
        )
    ]


def test_list_loopback_devices_returns_empty_list_when_none_found(fake_pyaudio_cls) -> None:
    pa = fake_pyaudio_cls(loopback_devices=[])

    assert list_loopback_devices(pa) == []


def test_get_default_input_device_resolves_mic(fake_pyaudio) -> None:
    device = get_default_input_device(fake_pyaudio)

    assert device == DeviceInfo(
        index=1,
        name="マイク配列 (Realtek Audio)",
        is_loopback=False,
        max_input_channels=1,
        default_sample_rate=48000,
    )


def test_get_default_loopback_device_resolves_loopback_and_truncates_sample_rate(
    fake_pyaudio,
) -> None:
    device = get_default_loopback_device(fake_pyaudio)

    assert device.index == 7
    assert device.is_loopback is True
    assert device.default_sample_rate == 44100


def test_get_default_input_device_propagates_oserror_when_wasapi_unavailable(fake_pyaudio) -> None:
    def _raise(*, d_in: bool = False):
        raise OSError("WASAPI is not available on this system")

    fake_pyaudio.get_default_wasapi_device = _raise

    with pytest.raises(OSError):
        get_default_input_device(fake_pyaudio)


def test_get_default_loopback_device_propagates_lookuperror_when_not_found(fake_pyaudio) -> None:
    def _raise():
        raise LookupError("No analogue is found for passed device")

    fake_pyaudio.get_default_wasapi_loopback = _raise

    with pytest.raises(LookupError):
        get_default_loopback_device(fake_pyaudio)
