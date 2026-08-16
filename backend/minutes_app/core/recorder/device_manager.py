"""WASAPI入力デバイス（マイク・ループバック）の列挙・既定デバイス解決。

仕様書 #1（docs/SPECIFICATION.md）/ docs/DESIGN.md §5.1「デバイス管理」/
docs/REQUIREMENTS.md F-1-1・F-1-5 に対応する Phase 0 骨格。
デバイス情報の取得は pyaudiowpatch（PortAudio の WASAPI 拡張）の
PyAudio インスタンスに委譲し、本モジュールは戻り値の dict を型付き DeviceInfo へ
変換する薄いラッパーに徹する（呼び出し方は公式サンプル
https://github.com/s0d3s/PyAudioWPatch/blob/master/examples/pawp_record_wasapi_loopback.py
のデバイス解決ロジックに準拠）。
"""

from dataclasses import dataclass

import pyaudiowpatch as pyaudio


@dataclass(frozen=True)
class DeviceInfo:
    """録音対象デバイス1件分の情報（PortAudio の PaDeviceInfo から必要分のみ抽出）。"""

    index: int
    name: str
    is_loopback: bool
    max_input_channels: int
    default_sample_rate: int


def _to_device_info(raw_device_info: dict) -> DeviceInfo:
    return DeviceInfo(
        index=raw_device_info["index"],
        name=raw_device_info["name"],
        is_loopback=raw_device_info["isLoopbackDevice"],
        max_input_channels=raw_device_info["maxInputChannels"],
        default_sample_rate=int(raw_device_info["defaultSampleRate"]),
    )


def list_loopback_devices(pa: pyaudio.PyAudio) -> list[DeviceInfo]:
    """WASAPIループバックデバイス（相手音声の取得元）を列挙する。

    :param pa: 初期化済みの PyAudio インスタンス
    :return: 検出順（PortAudio のデバイスインデックス順）の DeviceInfo 一覧。0件のこともある
    """
    return [_to_device_info(raw) for raw in pa.get_loopback_device_info_generator()]


def get_default_input_device(pa: pyaudio.PyAudio) -> DeviceInfo:
    """OS既定のマイク入力デバイスを取得する（F-1-5）。

    :param pa: 初期化済みの PyAudio インスタンス
    :return: 既定入力デバイスの DeviceInfo
    :raises OSError: WASAPI が利用できない環境の場合
    """
    return _to_device_info(pa.get_default_wasapi_device(d_in=True))


def get_default_loopback_device(pa: pyaudio.PyAudio) -> DeviceInfo:
    """既定の出力デバイス（スピーカー）に対応するループバックデバイスを取得する（F-1-5）。

    :raises LookupError: 既定出力デバイスに対応するループバックデバイスが見つからない場合
    :raises OSError: WASAPI が利用できない環境の場合
    """
    return _to_device_info(pa.get_default_wasapi_loopback())
