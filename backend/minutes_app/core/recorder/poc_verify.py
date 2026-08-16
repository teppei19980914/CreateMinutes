"""録音の手動検証スクリプト（仕様書 #1 / docs/REQUIREMENTS.md Phase 0「ループバック録音PoC」・
Phase 1 F-1-3 60秒ローリング）。

会議アプリ（Teams/Zoom等）を起動し相手の音声を再生している状態でこのスクリプトを実行し、
録音停止後に生成される loopback.wav を再生することで、実際の会議アプリ起動状態でも
相手音声が取得できることを人手で確認する。マイク・ループバックそれぞれの実測RMSを
録音中コンソールへ表示し、無音でないことの一次確認にも使える。`RecordingSession`
（session.py）をそのまま利用するため、60秒ローリング・結合も実際の動作を通して確認できる。

実行例: `uv run python -m minutes_app.core.recorder.poc_verify --seconds 15`
"""

import argparse
import sys
import time
from pathlib import Path

import pyaudiowpatch as pyaudio

from minutes_app.core.recorder.session import RecordingSession

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
    """マイク・ループバックを同時録音し、結合済みWAVファイルのパスを返す。"""
    session = RecordingSession(pa, output_dir)

    print(f"録音セッション: {session.session_dir}")
    print(f"{duration_seconds}秒間録音します。会議アプリで相手の音声を再生してください。")

    session.start()
    try:
        elapsed = 0.0
        while elapsed < duration_seconds:
            time.sleep(poll_interval_seconds)
            elapsed += poll_interval_seconds
            print(
                f"  {elapsed:6.1f}s / mic RMS={session.mic_last_rms:8.1f} "
                f"loopback RMS={session.loopback_last_rms:8.1f}"
            )
    finally:
        result = session.stop()

    print(f"完了: {result.mic_path} / {result.loopback_path}")
    return result.mic_path, result.loopback_path


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
