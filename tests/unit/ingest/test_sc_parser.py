"""Unit tests for the SuttaCentral bilara parser.

We build a miniature bilara tree inside a pytest ``tmp_path`` so the
tests never touch the real ~500 MB checkout. This keeps them fast, CI-
friendly, and independent of upstream SuttaCentral changes.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.ingest.suttacentral import (
    BilaraFile,
    FileKind,
    iter_bilara_files,
    iter_segments,
    parse_bilara_file,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _write(path: Path, payload: dict[str, str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


@pytest.fixture
def bilara_tree(tmp_path: Path) -> Path:
    """Build a minimal bilara-data layout with two translations + one root.

    Keeping this in one fixture (rather than a JSON fixture file) means
    the expected structure is visible right next to the assertions and
    can be tweaked per-test without maintaining on-disk goldens.
    """
    root = tmp_path / "bilara-data"

    # English translation, sujato — mn1.
    _write(
        root / "translation" / "en" / "sujato" / "sutta" / "mn" / "mn1_translation-en-sujato.json",
        {
            "mn1:0.1": "Middle Discourses 1 ",
            "mn1:0.2": "The Root of All Things ",
            "mn1:1.1": "So I have heard. ",
        },
    )
    # German translation, sabbamitta — mn1, uses diacritics.
    _write(
        root
        / "translation"
        / "de"
        / "sabbamitta"
        / "sutta"
        / "mn"
        / "mn1_translation-de-sabbamitta.json",
        {
            "mn1:0.1": "Mittlere Lehrreden 1 ",
            "mn1:0.2": "Die Wurzel aller Dinge ",
        },
    )
    # Root Pali, ms — mn1.
    _write(
        root / "root" / "pli" / "ms" / "sutta" / "mn" / "mn1_root-pli-ms.json",
        {
            "mn1:0.1": "Majjhima Nikāya 1 ",
            "mn1:0.2": "Mūlapariyāyasutta ",
        },
    )
    # Range-form uid (AN collections use ``an1.1-10`` style names).
    _write(
        root
        / "translation"
        / "en"
        / "sujato"
        / "sutta"
        / "an"
        / "an1"
        / "an1.1-10_translation-en-sujato.json",
        {"an1.1-10:0.1": "Numbered Discourses 1.1–10 "},
    )
    # A metadata file that is valid JSON but not a bilara text — the
    # parser must quietly skip it instead of raising.
    _write(root / "_author.json", {"sujato": "Bhikkhu Sujato"})

    return root


# ---------------------------------------------------------------------------
# iter_bilara_files
# ---------------------------------------------------------------------------


def test_iter_finds_all_translations_and_roots(bilara_tree: Path) -> None:
    files = list(iter_bilara_files(bilara_tree))
    assert len(files) == 4
    # Metadata file must not leak in.
    assert all(f.path.name != "_author.json" for f in files)


def test_iter_filters_by_kind(bilara_tree: Path) -> None:
    translations = list(iter_bilara_files(bilara_tree, kind=FileKind.TRANSLATION))
    roots = list(iter_bilara_files(bilara_tree, kind=FileKind.ROOT))
    assert len(translations) == 3
    assert len(roots) == 1
    assert all(f.kind is FileKind.TRANSLATION for f in translations)
    assert roots[0].language == "pli"


def test_iter_filters_by_language_and_author(bilara_tree: Path) -> None:
    en_sujato = list(iter_bilara_files(bilara_tree, language="en", author="sujato"))
    # Two MN/AN files under sujato/en — root Pali and the German one must not match.
    assert len(en_sujato) == 2
    assert {f.uid for f in en_sujato} == {"mn1", "an1.1-10"}


def test_iter_filters_by_nikaya(bilara_tree: Path) -> None:
    mn_only = list(iter_bilara_files(bilara_tree, nikaya="mn"))
    assert len(mn_only) == 3
    assert all(f.nikaya == "mn" for f in mn_only)


def test_iter_errors_on_missing_root(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        list(iter_bilara_files(tmp_path / "does-not-exist"))


def test_iter_errors_on_non_bilara_directory(tmp_path: Path) -> None:
    (tmp_path / "not-bilara").mkdir()
    with pytest.raises(FileNotFoundError):
        list(iter_bilara_files(tmp_path / "not-bilara"))


# ---------------------------------------------------------------------------
# parse_bilara_file
# ---------------------------------------------------------------------------


def test_parse_bilara_file_extracts_all_metadata(bilara_tree: Path) -> None:
    path = (
        bilara_tree
        / "translation"
        / "en"
        / "sujato"
        / "sutta"
        / "mn"
        / "mn1_translation-en-sujato.json"
    )
    bf = parse_bilara_file(path, bilara_tree)
    assert bf == BilaraFile(
        path=path,
        uid="mn1",
        kind=FileKind.TRANSLATION,
        language="en",
        author="sujato",
        nikaya="mn",
    )


def test_parse_bilara_file_handles_range_uid(bilara_tree: Path) -> None:
    path = (
        bilara_tree
        / "translation"
        / "en"
        / "sujato"
        / "sutta"
        / "an"
        / "an1"
        / "an1.1-10_translation-en-sujato.json"
    )
    bf = parse_bilara_file(path, bilara_tree)
    assert bf.uid == "an1.1-10"
    assert bf.nikaya == "an"


def test_parse_bilara_file_rejects_bad_name(tmp_path: Path) -> None:
    bad = tmp_path / "bogus.json"
    bad.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="Not a bilara file name"):
        parse_bilara_file(bad, tmp_path)


# ---------------------------------------------------------------------------
# iter_segments
# ---------------------------------------------------------------------------


def test_iter_segments_preserves_order_and_text(bilara_tree: Path) -> None:
    path = (
        bilara_tree
        / "translation"
        / "en"
        / "sujato"
        / "sutta"
        / "mn"
        / "mn1_translation-en-sujato.json"
    )
    bf = parse_bilara_file(path, bilara_tree)
    segments = list(iter_segments(bf))
    assert [s.segment_id for s in segments] == [
        "mn1:0.1",
        "mn1:0.2",
        "mn1:1.1",
    ]
    # Trailing spaces are preserved — the cleaner stage decides how to
    # handle them, not the parser.
    assert segments[0].text == "Middle Discourses 1 "
    assert segments[0].source is bf


def test_iter_segments_preserves_pali_diacritics(bilara_tree: Path) -> None:
    path = bilara_tree / "root" / "pli" / "ms" / "sutta" / "mn" / "mn1_root-pli-ms.json"
    bf = parse_bilara_file(path, bilara_tree)
    segments = list(iter_segments(bf))
    assert any("Majjhima Nikāya" in s.text for s in segments)
    assert any("Mūlapariyāyasutta" in s.text for s in segments)


def test_iter_segments_rejects_non_dict_json(tmp_path: Path) -> None:
    root = tmp_path / "bilara-data"
    bad_path = (
        root / "translation" / "en" / "sujato" / "sutta" / "mn" / "mn1_translation-en-sujato.json"
    )
    bad_path.parent.mkdir(parents=True, exist_ok=True)
    bad_path.write_text('["not", "a", "dict"]', encoding="utf-8")
    bf = parse_bilara_file(bad_path, root)
    with pytest.raises(ValueError, match="expected a JSON object"):
        list(iter_segments(bf))


def test_iter_segments_rejects_non_string_values(tmp_path: Path) -> None:
    root = tmp_path / "bilara-data"
    bad_path = (
        root / "translation" / "en" / "sujato" / "sutta" / "mn" / "mn1_translation-en-sujato.json"
    )
    bad_path.parent.mkdir(parents=True, exist_ok=True)
    bad_path.write_text('{"mn1:0.1": 42}', encoding="utf-8")
    bf = parse_bilara_file(bad_path, root)
    with pytest.raises(ValueError, match="non-string value"):
        list(iter_segments(bf))
