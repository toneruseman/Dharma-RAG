"""Unit tests for :mod:`src.expand.definitional` (rag-day-28)."""

from __future__ import annotations

import pytest

from src.expand.definitional import expand_definitional, is_definitional


class TestIsDefinitional:
    def test_what_is_short_term(self) -> None:
        assert is_definitional("What is satipaṭṭhāna?") == ("satipaṭṭhāna", "en")

    def test_what_is_with_article(self) -> None:
        assert is_definitional("What is the dukkha?") == ("dukkha", "en")

    def test_what_are_plural(self) -> None:
        result = is_definitional("What are the four noble truths?")
        assert result is not None
        term, lang = result
        assert term == "four noble truths"
        assert lang == "en"

    def test_define(self) -> None:
        assert is_definitional("Define satipaṭṭhāna") == ("satipaṭṭhāna", "en")

    def test_meaning_of(self) -> None:
        assert is_definitional("Meaning of dukkha") == ("dukkha", "en")

    def test_definition_of(self) -> None:
        assert is_definitional("Definition of anatta") == ("anatta", "en")

    def test_russian_chto_takoe(self) -> None:
        assert is_definitional("Что такое сатипаттхана?") == ("сатипаттхана", "ru")

    def test_russian_opredelenie(self) -> None:
        assert is_definitional("Определение анатта") == ("анатта", "ru")

    def test_russian_chto_znachit(self) -> None:
        assert is_definitional("Что значит дуккха") == ("дуккха", "ru")

    def test_long_term_skipped(self) -> None:
        # 7+ words after "What is" — relational/specific, not definitional.
        result = is_definitional(
            "What is the relationship between satipaṭṭhāna and anapanasati in practice?"
        )
        assert result is None

    def test_practice_question_not_matched(self) -> None:
        assert is_definitional("How do I work with anger when I'm restless?") is None

    def test_imperative_not_matched(self) -> None:
        assert is_definitional("Tell me about the eightfold path.") is None

    def test_empty_term_skipped(self) -> None:
        # Pattern matches but captured term is empty — should pass through.
        assert is_definitional("What is ?") is None

    def test_mixed_script_uses_russian(self) -> None:
        # Cyrillic prefix → use Russian template even if term is IAST.
        result = is_definitional("Что такое satipaṭṭhāna?")
        assert result == ("satipaṭṭhāna", "ru")


class TestExpandDefinitional:
    def test_satipatthana_smoking_gun(self) -> None:
        # The QA040 smoking gun — matches the documented expected
        # output verbatim (concept doc 28, "Как работает").
        out = expand_definitional("What is satipaṭṭhāna?")
        assert "What is satipaṭṭhāna?" in out
        assert "Discourse on satipaṭṭhāna." in out
        assert "Foundations of satipaṭṭhāna." in out
        assert "Sutta on satipaṭṭhāna." in out

    def test_russian_template(self) -> None:
        out = expand_definitional("Что такое анатта?")
        assert "Что такое анатта?" in out
        assert "Учение о анатта." in out
        assert "Основы анатта." in out
        assert "Сутта о анатта." in out

    def test_non_definitional_passthrough(self) -> None:
        query = "How do I work with anger?"
        assert expand_definitional(query) == query

    def test_long_relational_passthrough(self) -> None:
        query = "What is the relationship between mindfulness and concentration in early Buddhism?"
        assert expand_definitional(query) == query

    def test_empty_query_passthrough(self) -> None:
        assert expand_definitional("") == ""

    @pytest.mark.parametrize(
        "query",
        [
            "Define dukkha",
            "Meaning of jhana",
            "What is anatta?",
            "Что такое метта?",
            "Определение нирваны",
        ],
    )
    def test_short_definitional_always_expands(self, query: str) -> None:
        # Property: any matched short definitional should produce a
        # *longer* string than input.
        expanded = expand_definitional(query)
        assert len(expanded) > len(query)
