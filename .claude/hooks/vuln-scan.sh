#!/usr/bin/env bash
# Stop hook: 依存関係の既知脆弱性を OSV データベース（最新の脆弱性情報）と突き合わせてスコアリング表示する
#
# 使用ツール: osv-scanner (https://github.com/google/osv-scanner, Google製 / Apache-2.0)
#   コマンド仕様: https://google.github.io/osv-scanner/usage/
#   出力仕様:     https://google.github.io/osv-scanner/output/
#   終了コード:   0 = 脆弱性なし / 1 = 既知の脆弱性あり(重大度問わず) / 127,128 = 実行時エラー
#
# 方針（品質担保とコスト抑制の両立）:
#   - osv-scanner が未インストールなら何もせずスキップする（gitleaks と同じ opt-in 方式。必須化しない）
#   - 重大度で自動ブロックする信頼できる CLI フラグが公式ドキュメントで確認できなかったため、
#     本Hookでは自動ブロックは行わずレポートのみ行う（誤ってCIを止めてしまうより、開発者が
#     CVSSスコアを見て判断する方が実利が大きいため）。ブロックしたい場合は運用ルールとして
#     「HIGH/CRITICAL 検出時は手動でリリース判断する」等を OPERATIONS.md に定める

set -u

cd "$(git rev-parse --show-toplevel 2>/dev/null || echo .)" || exit 0

if ! command -v osv-scanner >/dev/null 2>&1; then
  echo "[vuln-scan] osv-scanner 未インストールのためスキップ（推奨インストール: https://google.github.io/osv-scanner/installation/）"
  exit 0
fi

echo "=== Vulnerability Scan (OSV) ==="
osv-scanner scan -r . --format table || true
echo "=== Vulnerability Scan 完了 — CVSS/重大度は上記を参照。自動ブロックはしないため、CRITICAL/HIGH があれば対応要否を判断してください ==="
exit 0
