#!/usr/bin/env bash
# テンプレート自体のメンテナンス用スクリプト（.claude/hooks/ には置かない = setup.sh でも配布されない）
#
# .claude/agents・.claude/skills・.claude/hooks の実ファイル数と、
# README.md / setup.sh に書かれた件数表記が一致しているかを機械的に検証する。
#
# 目的: 「エージェントを追加したのに件数表記の更新を1箇所忘れる」横展開漏れを、
#       LLMのgrep確認任せにせず決定的に検知するため（実際にsetup.shのhooks件数漏れを1回検知済み）。
#
# 使い方: bash scripts/verify-template.sh
# テンプレートの構成（agents/skills/hooksファイル）を変更した後、コミット前に実行する。

set -u

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT" || exit 1

FAIL=0

check_count() {
  local label="$1"
  local actual="$2"
  local stated="$3"
  local location="$4"

  if [ -z "$stated" ]; then
    echo "[!] $label: $location に件数表記が見つからず（検証できません）"
    FAIL=1
    return
  fi

  if [ "$actual" != "$stated" ]; then
    echo "[NG] $label: 実ファイル数=$actual だが $location の表記=$stated"
    FAIL=1
  else
    echo "[OK] $label: $actual 件（$location と一致）"
  fi
}

AGENTS_ACTUAL="$(ls .claude/agents/*.md 2>/dev/null | wc -l | tr -d ' ')"
SKILLS_ACTUAL="$(ls .claude/skills/*.md 2>/dev/null | wc -l | tr -d ' ')"
HOOKS_ACTUAL="$(ls .claude/hooks/*.sh 2>/dev/null | wc -l | tr -d ' ')"

README_AGENTS="$(grep 'agents/.*エージェント（' README.md | grep -oE '[0-9]+' | head -1)"
README_SKILLS="$(grep 'skills/.*スキル（' README.md | grep -oE '[0-9]+' | head -1)"

SETUP_AGENTS="$(grep 'agents/ ([0-9]* エージェント)' setup.sh | grep -oE '[0-9]+' | head -1)"
SETUP_SKILLS="$(grep 'skills/ ([0-9]* スキル)' setup.sh | grep -oE '[0-9]+' | head -1)"
SETUP_HOOKS="$(grep 'hooks/ ([0-9]* hooks)' setup.sh | grep -oE '[0-9]+' | head -1)"

echo "=== テンプレート件数整合性チェック ==="
check_count "agents (README)" "$AGENTS_ACTUAL" "$README_AGENTS" "README.md"
check_count "agents (setup.sh)" "$AGENTS_ACTUAL" "$SETUP_AGENTS" "setup.sh"
check_count "skills (README)" "$SKILLS_ACTUAL" "$README_SKILLS" "README.md"
check_count "skills (setup.sh)" "$SKILLS_ACTUAL" "$SETUP_SKILLS" "setup.sh"
check_count "hooks (setup.sh)" "$HOOKS_ACTUAL" "$SETUP_HOOKS" "setup.sh"

if [ "$FAIL" -eq 1 ]; then
  echo "=== 不整合あり。該当ファイルの件数表記を修正してください ==="
  exit 1
fi

echo "=== 整合性OK ==="
exit 0
