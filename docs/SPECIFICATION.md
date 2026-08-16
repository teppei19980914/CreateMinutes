# SPECIFICATION.md — 機能仕様書

本ドキュメントは各機能に通し番号を振り、コード側のコメントから `仕様書 #N` の形で参照できるようにする
（`CODING_RULES.md`「コメントの書き方」①の前提となる文書）。

## 機能仕様一覧

| # | 画面/機能名 | 概要 | 入力 | 出力 | 例外・エッジケース | ステータス |
|---|---|---|---|---|---|---|
| 1 | ループバック録音PoC（Phase 0） | マイク・WASAPIループバックの既定デバイスを解決し、それぞれをWAVへ録音する骨格 | 録音時間（秒）・出力先ディレクトリ | mic.wav / loopback.wav（デバイスのネイティブ rate/channels、16bit PCM） | 対応デバイス無し（WASAPI未対応環境・ループバック対応デバイス未検出）は例外を送出し握りつぶさない | 実装中（実機での会議アプリ併用検証待ち） |

## 各機能の詳細

### #1 ループバック録音PoC（Phase 0）

**概要**: `docs/REQUIREMENTS.md` Phase 0「ループバック録音PoC」に対応する最小実装。マイク入力と
WASAPIループバック（既定出力デバイスの相手音声）をそれぞれ独立にWAVファイルへ録音し、実際の
会議アプリ起動状態でも相手音声が取得できることを実証するための土台を提供する。
`backend/minutes_app/core/recorder/session.py`（2トラック統括・結合・復旧検出）、60秒ローリング
書き出し、暗号化は対象外（Phase 1 で追加）。

**画面/エンドポイント**: UIなし。開発者向けCLI `uv run python -m minutes_app.core.recorder.poc_verify`
（`backend/minutes_app/core/recorder/poc_verify.py`）。

**入力**: `--seconds`（録音時間、既定15秒）、`--output-dir`（WAV出力先、既定 `data/poc_recordings`）。

**出力**: `<output-dir>/mic.wav` / `<output-dir>/loopback.wav`。録音中はコンソールへ両トラックの
RMS（`calculate_rms`）を一定間隔で表示し、無音でないことの一次確認に使う。

**例外・エッジケース**: WASAPI非対応環境（`OSError`）、既定出力デバイスに対応するループバック
デバイスが見つからない場合（`LookupError`）はいずれも呼び出し元へ伝播させ、CLI実行時はスタック
トレースとして表示する（フォールバック処理は設けない。テストカバレッジ対象外）。

**関連ドキュメント**: `docs/DESIGN.md` §5.1「Phase 0 実装メモ」・§9（実装順序）、
`docs/REQUIREMENTS.md` §4 F-1-1・F-1-5・§7 Phase 0・§8 未確定事項#1。

## 変更履歴

| 日付 | # | 変更内容 | 変更理由 |
|---|---|---|---|
| 2026-08-16 | 1 | ループバック録音PoC（Phase 0）を新規追加 | Phase 0 着手（device_manager/track_recorder骨格の実装） |
