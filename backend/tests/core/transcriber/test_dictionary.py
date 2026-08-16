from minutes_app.core.transcriber.dictionary import apply_replacements, build_initial_prompt


class TestBuildInitialPrompt:
    def test_returns_empty_string_for_empty_dictionary(self) -> None:
        assert build_initial_prompt({}) == ""

    def test_lists_values_in_insertion_order(self) -> None:
        dictionary = {"にゅーとんX": "NewtonX", "せらく": "セラク"}

        prompt = build_initial_prompt(dictionary)

        assert prompt == "以下の用語が登場します: NewtonX, セラク"

    def test_truncates_from_the_point_max_chars_would_be_exceeded(self) -> None:
        dictionary = {"a": "AAAAA", "b": "BBBBB", "c": "CCCCC"}

        prompt = build_initial_prompt(dictionary, max_chars=10)

        assert prompt == "以下の用語が登場します: AAAAA"

    def test_returns_empty_string_when_even_first_term_exceeds_max_chars(self) -> None:
        dictionary = {"a": "AAAAAAAAAAAAAAAAAAAA"}

        assert build_initial_prompt(dictionary, max_chars=5) == ""


class TestApplyReplacements:
    def test_replaces_all_keys_with_their_values(self) -> None:
        text = "にゅーとんXとせらくについて話しました"
        dictionary = {"にゅーとんX": "NewtonX", "せらく": "セラク"}

        assert apply_replacements(text, dictionary) == "NewtonXとセラクについて話しました"

    def test_returns_original_text_when_dictionary_is_empty(self) -> None:
        assert apply_replacements("そのままのテキスト", {}) == "そのままのテキスト"

    def test_returns_original_text_when_no_keys_match(self) -> None:
        result = apply_replacements("関係ないテキスト", {"にゅーとんX": "NewtonX"})

        assert result == "関係ないテキスト"
