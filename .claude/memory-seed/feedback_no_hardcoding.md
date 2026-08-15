---
name: feedback_no_hardcoding
description: ゼロハードコーディング原則の判定基準は CODING_RULES.md に一本化（本メモリは由来の記録のみ）
type: feedback
originSessionId: 2256dc31-9f5d-432f-9efc-bc90c56fcf76
---
判定基準（対象範囲・配置先・除外条件）は `CODING_RULES.md`「② ゼロハードコーディング」を参照。本メモリはルールの重複記述を避けるため、由来のみ記録する。

**Why:** 複数プロジェクト（GrowthEngine, HomePage, MindFlow）で繰り返し指示された共通ルール。表記変更やi18n対応時に全ファイル検索が必要になるのを防ぐため、テンプレート導入時に `CODING_RULES.md` として明文化した。
