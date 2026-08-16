"""固有名詞辞書 → initial_prompt生成・後処理置換（仕様書 #1 / docs/DESIGN.md §5.2「固有名詞辞書」
/ docs/REQUIREMENTS.md F-2-6）。

辞書のCRUD・DB保存（`dictionary` テーブル）はPhase 4のUI/設定機能で追加する
（docs/DESIGN.md §3.2「その他」）。Phase 1時点では呼び出し元が `dict[str, str]`
（誤変換表記 → 正表記）をそのまま渡す想定とする。
"""

DEFAULT_MAX_PROMPT_CHARS = 200


def build_initial_prompt(
    dictionary: dict[str, str], *, max_chars: int = DEFAULT_MAX_PROMPT_CHARS
) -> str:
    """辞書の正表記（値）を initial_prompt 文字列へ組み立てる。

    initial_promptには最大トークン制約があるため、値（正表記）のみを登録順（dict挿入順）に
    結合し、`max_chars` を超える手前で打ち切る（上限超過時は登録順で先頭から採用 —
    docs/DESIGN.md §5.2）。

    :param dictionary: 誤変換表記(key) → 正表記(value) の辞書
    :param max_chars: initial_prompt文字列の上限文字数
    :return: `以下の用語が登場します: ...` 形式の文字列。辞書が空なら空文字列
    """
    if not dictionary:
        return ""

    terms: list[str] = []
    for value in dictionary.values():
        candidate = ", ".join([*terms, value])
        if len(candidate) > max_chars:
            break
        terms.append(value)

    if not terms:
        return ""
    return f"以下の用語が登場します: {', '.join(terms)}"


def apply_replacements(text: str, dictionary: dict[str, str]) -> str:
    """誤変換表記(key)を正表記(value)へ後処理置換する（initial_promptによる誘導との二段構え）。"""
    for key, value in dictionary.items():
        text = text.replace(key, value)
    return text
