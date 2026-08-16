"""faster-whisperラッパ（仕様書 #1 / docs/DESIGN.md §5.2 / docs/REQUIREMENTS.md F-2-1〜F-2-3）。

モデルのロードは重い処理（初回はHugging Faceからモデル本体をダウンロード。ネットワーク
到達性は確認済み — docs/DESIGN.md §10 #3 参照）ため、`load_model` は呼び出し元が
1度だけ実行してインスタンスを使い回す想定とする。`transcribe_track` はロード済みモデルを
受け取るだけの薄いラッパーとし、実モデルをダウンロードしない単体テストを可能にする。

モデルサイズ文字列（"small" / "medium" / "large-v3-turbo"）は
`backend/.venv/Lib/site-packages/faster_whisper/utils.py` の `_MODELS` 辞書で
実在を確認済み（F-2-1: 設定画面から turbo/medium/small に切替可能）。

F-2-3「音声をチャンク分割し、CPUコア数に応じて並列処理する」・docs/DESIGN.md §5.1
「並列制御（録音中はWhisper並列チャンク数を `max(1, cpu_count // 2)` に制限）」について、
Phase 1では独自の音声チャンク分割・複数チャンクの並列実行（マルチプロセス化）は実装せず、
`WhisperModel` 自身の `cpu_threads` パラメータ（CTranslate2の内部スレッド数）による
簡易対応に留める。理由: (1) faster-whisper自体が内部でVADベースのセグメント分割・
バッチ処理を行うため、アプリ側での二重のチャンク分割は複雑度に見合う効果が不明。
(2) 60分会議の実測ベンチマーク（§8 未確定事項#2）を先に行い、実際のボトルネックが
明らかになってから並列化方式を決めるべき判断のため。録音中の並列数制御
（`max(1, cpu_count // 2)`）と、ボトルネックが確認された場合の本格的なチャンク並列化は
`core/queue/job_queue.py` 完成（Phase 4）と合わせて再検討する。
"""

from dataclasses import dataclass
from pathlib import Path

from faster_whisper import WhisperModel

DEFAULT_MODEL_SIZE = "large-v3-turbo"
DEFAULT_COMPUTE_TYPE = "int8"


@dataclass(frozen=True)
class TrackSegment:
    """1トラック分の文字起こしセグメント（音声ファイル先頭からの相対秒）。"""

    start_sec: float
    end_sec: float
    text: str


def load_model(
    model_size: str = DEFAULT_MODEL_SIZE,
    *,
    compute_type: str = DEFAULT_COMPUTE_TYPE,
    cpu_threads: int = 0,
) -> WhisperModel:
    """WhisperModelをCPU向けにロードする。

    :param model_size: faster-whisperのモデルサイズ文字列
    :param compute_type: 量子化方式。既定はCPU向けの int8（docs/REQUIREMENTS.md §3.2 技術スタック）
    :param cpu_threads: CPUスレッド数（F-2-3「CPUコア数に応じて並列処理する」）。
        0を指定するとfaster-whisper既定値（4）が使われる
    """
    return WhisperModel(
        model_size, device="cpu", compute_type=compute_type, cpu_threads=cpu_threads
    )


def transcribe_track(
    model: WhisperModel,
    audio_path: Path,
    *,
    initial_prompt: str = "",
) -> list[TrackSegment]:
    """1トラック分のWAVを文字起こしし、正規化したセグメント一覧を返す。

    VAD（無音区間スキップ、F-2-2）・単語タイムスタンプを有効にして呼び出す。
    faster-whisperの `transcribe()` はジェネレータを返す遅延評価APIのため、
    ここで即座にリスト化して実行を完了させる。

    :param model: `load_model` で取得したロード済みモデル
    :param audio_path: 文字起こし対象のWAVファイル（`session.py` の結合済みトラック）
    :param initial_prompt: `dictionary.build_initial_prompt` の出力（空文字列可）
    """
    segments, _info = model.transcribe(
        str(audio_path),
        language="ja",
        vad_filter=True,
        word_timestamps=True,
        initial_prompt=initial_prompt or None,
    )
    return [
        TrackSegment(start_sec=segment.start, end_sec=segment.end, text=segment.text.strip())
        for segment in segments
        if segment.text.strip()
    ]
