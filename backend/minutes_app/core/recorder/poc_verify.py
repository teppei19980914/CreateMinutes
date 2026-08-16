"""Phase 0 手動検証スクリプト（仕様書 #1 / docs/REQUIREMENTS.md Phase 0「ループバック録音PoC」）。

会議アプリ（Teams/Zoom等）を起動し相手の音声を再生している状態でこのスクリプトを実行し、
録音停止後に生成される loopback.wav を再生することで、実際の会議アプリ起動状態でも
相手音声が取得できることを人手で確認する。マイク・ループバックそれぞれの実測RMSを
録音中コンソールへ表示し、無音でないことの一次確認にも使える。

実行例: `uv run python -m minutes_app.core.recorder.poc_verify --seconds 15`
"""

import argparse
import sys
import time
from pathlib import Path

import pyaudiowpatch as pyaudio

from minutes_app.core.recorder.device_manager import (
    get_default_input_device,
    get_default_loopback_device,
)
from minutes_app.core.recorder.track_recorder import TrackRecorder

DEFAULT_DURATION_SECONDS = 15.0
DEFAULT_OUTPUT_DIR = Path("data") / "poc_recordings"
DEFAULT_POLL_INTERVAL_SECONDS = 0.5


def run(
    pa: pyaudio.PyAudio,
    duration_seconds: float,
    output_dir: Path,
    *,
    poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
) -> tuple[Path, Path]:
    """マイク・ループバックを同時録音し、生成したWAVファイルのパスを返す。"""
    output_dir.mkdir(parents=True, exist_ok=True)

    mic_device = get_default_input_device(pa)
    loopback_device = get_default_loopback_device(pa)
    mic_path = output_dir / "mic.wav"
    loopback_path = output_dir / "loopback.wav"

    print(f"[mic]      {mic_device.name}")
    print(f"[loopback] {loopback_device.name}")
    print(f"{duration_seconds}秒間録音します。会議アプリで相手の音声を再生してください。")

    mic_recorder = TrackRecorder(pa, mic_device, mic_path)
    loopback_recorder = TrackRecorder(pa, loopback_device, loopback_path)

    mic_recorder.start()
    loopback_recorder.start()
    try:
        elapsed = 0.0
        while elapsed < duration_seconds:
            time.sleep(poll_interval_seconds)
            elapsed += poll_interval_seconds
            print(
                f"  {elapsed:6.1f}s / mic RMS={mic_recorder.last_rms:8.1f} "
                f"loopback RMS={loopback_recorder.last_rms:8.1f}"
            )
    finally:
        mic_recorder.stop()
        loopback_recorder.stop()

    print(f"完了: {mic_path} / {loopback_path}")
    return mic_path, loopback_path


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--seconds", type=float, default=DEFAULT_DURATION_SECONDS, help="録音時間（秒）"
    )
    parser.add_argument(
        "--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="WAV出力先ディレクトリ"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    with pyaudio.PyAudio() as pa:
        run(pa, args.seconds, args.output_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
