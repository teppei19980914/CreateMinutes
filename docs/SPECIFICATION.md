# SPECIFICATION.md — 機能仕様書

本ドキュメントは各機能に通し番号を振り、コード側のコメントから `仕様書 #N` の形で参照できるようにする
（`CODING_RULES.md`「コメントの書き方」①の前提となる文書）。

## 機能仕様一覧

| # | 画面/機能名 | 概要 | 入力 | 出力 | 例外・エッジケース | ステータス |
|---|---|---|---|---|---|---|
| 1 | ループバック録音PoC（Phase 0） | マイク・WASAPIループバックの既定デバイスを解決し、それぞれをWAVへ録音する骨格 | 録音時間（秒）・出力先ディレクトリ | mic.wav / loopback.wav（デバイスのネイティブ rate/channels、16bit PCM） | 対応デバイス無し（WASAPI未対応環境・ループバック対応デバイス未検出）は例外を送出し握りつぶさない | 実装中（実機での会議アプリ併用検証待ち） |
| 2 | 2トラック録音+STT+ベンチマーク（Phase 1） | 60秒ローリング録音・結合・復旧検出、faster-whisperによる2トラック文字起こし、話者ラベル付きマージ、meetings/audio_files/utterancesへのDB永続化 | 録音時間（秒）または既存セッションディレクトリ・Whisperモデルサイズ | DB（meetings/audio_files/utterances）・処理時間/実時間比のベンチマークレポート | 音声デバイス排他エラー、ローリングファイル0件時の結合失敗はいずれも例外伝播（フォールバックなし） | 実装中（60分会議での実測ベンチマーク・実運用モデル確定は未実施） |

## 各機能の詳細

### #1 ループバック録音PoC（Phase 0）

**概要**: `docs/REQUIREMENTS.md` Phase 0「ループバック録音PoC」に対応する最小実装。マイク入力と
WASAPIループバック（既定出力デバイスの相手音声）をそれぞれ独立にWAVファイルへ録音し、実際の
会議アプリ起動状態でも相手音声が取得できることを実証するための土台を提供する。Phase 1で
`session.py`（2トラック統括）に統合され、現在は内部的に `session.py` を利用する。

**画面/エンドポイント**: UIなし。開発者向けCLI `uv run python -m minutes_app.core.recorder.poc_verify`
（`backend/minutes_app/core/recorder/poc_verify.py`）。

**入力**: `--seconds`（録音時間、既定15秒）、`--output-dir`（WAV出力先、既定 `data/poc_recordings`）。

**出力**: `<output-dir>/{meeting_uid}/mic.wav` / `loopback.wav`。録音中はコンソールへ両トラックの
RMS（`calculate_rms`）を一定間隔で表示し、無音でないことの一次確認に使う。

**例外・エッジケース**: WASAPI非対応環境（`OSError`）、既定出力デバイスに対応するループバック
デバイスが見つからない場合（`LookupError`）はいずれも呼び出し元へ伝播させ、CLI実行時はスタック
トレースとして表示する（フォールバック処理は設けない。テストカバレッジ対象外）。

**関連ドキュメント**: `docs/DESIGN.md` §5.1「Phase 0 実装メモ」・§9（実装順序）、
`docs/REQUIREMENTS.md` §4 F-1-1・F-1-5・§7 Phase 0・§8 未確定事項#1。

### #2 2トラック録音+STT+ベンチマーク（Phase 1）

**概要**: `docs/REQUIREMENTS.md` Phase 1「2トラック録音 + STT + ベンチマーク」に対応する実装。
マイク・ループバックを60秒ローリングで同時録音し（F-1-3）、終了時に結合する（`session.py`）。
faster-whisperで各トラックを個別に文字起こしし（F-2-1・F-2-2）、時系列マージ・自声エコー除去・
話者ラベル付与・発言統合を行い（F-2-4・F-2-5、`merger.py`）、`meetings`/`audio_files`/`utterances`
へ永続化する（`db/repositories/`）。`bench_transcribe.py` が録音（または既存セッション指定）から
DB永続化までを一気通貫で実行し、処理時間の実時間比（real_time_factor）を報告する。

**設計判断（Phase1時点の簡略化。詳細はdocs/DESIGN.md §5.1「Phase 1 実装メモ」参照）**:
- DB・音声ファイルとも暗号化なしの平文で保存する（SQLCipher鍵管理 `key_manager.py` はPhase 4）
- 録音はデバイスのネイティブ rate/channels のまま保存し、16kHz/mono への変換は行わない
- F-2-3「CPUコア数に応じた並列処理」は、独自のチャンク分割+マルチプロセスではなく
  faster-whisperの `cpu_threads` パラメータで実現する

**画面/エンドポイント**: UIなし。開発者向けCLI
`uv run python -m minutes_app.bench_transcribe`（`backend/minutes_app/bench_transcribe.py`）。

**入力**: `--record-seconds`（その場で録音）または `--session-dir`（既存セッション）のいずれか必須、
`--model-size`（既定 large-v3-turbo）、`--db-path`・`--output-dir`（既定は `app_constants` 参照）。

**出力**: `meetings`/`audio_files`/`utterances` へのDBレコード。コンソールへ発言数・音声長・
処理時間・実時間比を表示する。

**例外・エッジケース**: `--session-dir`/`--record-seconds` 両方省略時はエラーメッセージを表示し
終了コード1を返す（フォールバックなし）。録音セッションを別プロセスの `--session-dir` として後から
処理する場合、正確な開始時刻が失われるため `mic.wav` の更新日時から逆算する
（同一プロセスで録音から処理まで行う場合は実測の開始・終了時刻を使用）。
`--record-seconds` で指定した秒数より実際の会議が早く終わり、経過前にCtrl+C
（KeyboardInterrupt）で中断した場合も、その時点までの録音を確定・結合してから
文字起こし・DB永続化まで実行する（`record_session()` が `KeyboardInterrupt` を捕捉して
`RecordingSession.stop()` を呼ぶ）。

**関連ドキュメント**: `docs/DESIGN.md` §5.1「Phase 1 実装メモ」・§5.2・§9（実装順序）、
`docs/REQUIREMENTS.md` §4 F-1-1〜F-1-8・F-2-1〜F-2-7・§7 Phase 1・§8 未確定事項#2〜#3。

## 変更履歴

| 日付 | # | 変更内容 | 変更理由 |
|---|---|---|---|
| 2026-08-16 | 1 | ループバック録音PoC（Phase 0）を新規追加 | Phase 0 着手（device_manager/track_recorder骨格の実装） |
| 2026-08-17 | 1, 2 | Phase 1（2トラック録音+STT+ベンチマーク）を新規追加。#1をsession.py利用に更新 | Phase 1 着手（60秒ローリング・DB永続化・faster-whisper統合・2トラックマージの実装） |
