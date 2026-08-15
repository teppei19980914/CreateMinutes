#!/bin/bash
# 編集されたファイルの拡張子に応じてフォーマッタを振り分ける。
# backend/*.py -> ruff format（uvプロジェクト） / frontend/* -> prettier
set -uo pipefail

FILE="${1:-}"
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

[ -z "$FILE" ] && exit 0
[ -f "$FILE" ] || exit 0

case "$FILE" in
  *.py)
    if [ -d "$REPO_ROOT/backend" ]; then
      (cd "$REPO_ROOT/backend" && uv run ruff format "$FILE" 2>/dev/null)
    fi
    ;;
  *.ts|*.tsx|*.js|*.jsx|*.json|*.css|*.md)
    if [ -d "$REPO_ROOT/frontend" ] && [[ "$FILE" == *"/frontend/"* || "$FILE" == *"\\frontend\\"* ]]; then
      (cd "$REPO_ROOT/frontend" && npx prettier --write "$FILE" 2>/dev/null)
    fi
    ;;
esac

exit 0
