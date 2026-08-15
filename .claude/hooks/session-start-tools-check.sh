#!/usr/bin/env bash
# SessionStart hook: セキュリティツールの導入状況を毎セッション冒頭で可視化する
#
# 背景: secret-scan.sh(gitleaks) / vuln-scan.sh(osv-scanner) / CI(security.yml) はいずれも
#       未導入・未有効化でも「無音でスキップ」する設計（コスト最小化のためopt-in）。
#       そのため導入し忘れたまま気づかず開発が続くリスクがある。
#       本Hookはブロックせず、セッション開始時に1回だけ状態を知らせることでそのリスクを下げる。
#
# git-automation-config の有無に関わらず常に実行する（session-start-git.sh とは独立）。

set -u

cd "$(git rev-parse --show-toplevel 2>/dev/null || echo .)" || exit 0

MISSING=0

if command -v gitleaks >/dev/null 2>&1; then
  echo "[tools-check] gitleaks: 導入済み"
else
  echo "[tools-check] gitleaks: 未導入（secret-scan.shはgrepフォールバックで動作中）— https://github.com/gitleaks/gitleaks"
  MISSING=1
fi

if command -v osv-scanner >/dev/null 2>&1; then
  echo "[tools-check] osv-scanner: 導入済み"
else
  echo "[tools-check] osv-scanner: 未導入（vuln-scan.shはスキップ中、依存脆弱性スキャンが行われていません）— https://google.github.io/osv-scanner/installation/"
  MISSING=1
fi

if [ -f ".github/workflows/security.yml" ]; then
  echo "[tools-check] CI security workflow: 有効"
elif [ -f ".github/workflows/security.yml.template" ]; then
  echo "[tools-check] CI security workflow: 未有効化（.template を外してリネームすると有効化されます）"
  MISSING=1
fi

if [ "$MISSING" -eq 1 ]; then
  echo "[tools-check] 上記は必須ではありませんが、セキュリティ向上のため導入を推奨します"
fi

exit 0
