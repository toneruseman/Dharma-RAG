"""Сборка консолидированного глоссария из ms-dpd JS-файлов.

Источник — https://github.com/sc-voice/ms-dpd (CC-BY-NC 4.0). Скрипт
парсит 4 ``.mjs``-файла (это ES-модули с одной ``export const X = {...}``
конструкцией, внутри которой валидный JSON) и сворачивает их в один JSON
с точками входа по канонической форме (lemma).

Результат — ``data/glossary/dpd_full.json``. Запускается один раз вручную;
сами ``.mjs``-файлы в репо не коммитим (15 MB), а скрипт — коммитим как
рецепт пересборки.

Структура итогового JSON::

    {
      "<lemma>": {
        "lemma": "jhāna",
        "pos": ["n.nt", ...],
        "meanings_en": ["meditative absorption", ...],   # до 5
        "meanings_ru": ["джхана", ...],                   # до 5
      },
      ...
    }

Запуск::

    python scripts/build_dpd_glossary.py
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "glossary" / "dpd_raw"
OUT_PATH = Path(__file__).resolve().parent.parent / "data" / "glossary" / "dpd_full.json"

MAX_MEANINGS_PER_LEMMA = 5  # после этого порога пользы ноль, шум растёт


def _parse_mjs(path: Path) -> dict[str, str]:
    """Извлекает словарь из одной ``export const X = {...}`` конструкции.

    Файлы ms-dpd аккуратные — литерал JS-объекта почти полностью
    совпадает с JSON. Единственное расхождение — ключи без кавычек
    (но в наших файлах все ключи в кавычках, проверено ручным осмотром).
    """
    text = path.read_text(encoding="utf-8")
    match = re.search(r"=\s*(\{.*\})\s*;?\s*$", text, re.DOTALL)
    if not match:
        raise ValueError(f"Не нашёл объект в {path.name}")
    return json.loads(match.group(1))


def _split_meanings(raw: str) -> list[str]:
    """Разбивает строку определения на список значений.

    DPD использует ``;`` (синонимы внутри одного смысла), ``||``
    (альтернативные смыслы) и одинарный ``|`` (служебный маркер вокруг
    "literal" / "альтернатива"). Для query-expansion разница между этими
    разделителями не важна — нам нужен плоский список синонимов. Поэтому
    режем по всем трём и стрипаем висящие ``|`` по краям.
    """
    if not raw or raw.isspace():
        return []
    pieces: list[str] = []
    for sense in raw.split("||"):
        for chunk in sense.split("|"):
            for syn in chunk.split(";"):
                cleaned = syn.strip().strip("|").strip()
                if cleaned:
                    pieces.append(cleaned)
    # Дедупликация с сохранением порядка (Python 3.7+ dict).
    return list(dict.fromkeys(pieces))


_LEMMA_SENSE_RE = re.compile(r"\s+\d+(\.\d+)?$")


def _normalise_lemma(raw_lemma: str) -> str:
    """Убирает суффикс смысла (``"akaṅkha 1.1"`` → ``"akaṅkha"``)."""
    return _LEMMA_SENSE_RE.sub("", raw_lemma).strip()


def build_glossary() -> dict[str, dict[str, Any]]:
    def_pali = _parse_mjs(RAW_DIR / "definition-pali.mjs")
    def_en = _parse_mjs(RAW_DIR / "definition-en.mjs")
    def_ru = _parse_mjs(RAW_DIR / "definition-ru.mjs")

    print(f"  DEF_PALI:  {len(def_pali):>7} entries")
    print(f"  DEF_EN:    {len(def_en):>7} entries")
    print(f"  DEF_RU:    {len(def_ru):>7} entries")

    lemmas: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"meanings_en": [], "meanings_ru": [], "pos": set()}
    )
    skipped = 0

    for entry_id, pali_str in def_pali.items():
        parts = pali_str.split("|")
        # Ожидаем минимум 5 полей: pattern|pos|construction|stem|lemma.
        # Менее того — служебная запись (буква алфавита, префикс), пропускаем.
        if len(parts) < 5:
            skipped += 1
            continue
        pos = parts[1].strip()
        lemma = _normalise_lemma(parts[4])
        if not lemma:
            skipped += 1
            continue

        bucket = lemmas[lemma]
        if pos:
            bucket["pos"].add(pos)

        for piece in _split_meanings(def_en.get(entry_id, "")):
            if piece not in bucket["meanings_en"]:
                bucket["meanings_en"].append(piece)
        for piece in _split_meanings(def_ru.get(entry_id, "")):
            if piece not in bucket["meanings_ru"]:
                bucket["meanings_ru"].append(piece)

    # Финализация: pos из set в sorted list, обрезка хвостов значений.
    out: dict[str, dict[str, Any]] = {}
    ru_count = 0
    en_count = 0
    for lemma, bucket in lemmas.items():
        meanings_en = bucket["meanings_en"][:MAX_MEANINGS_PER_LEMMA]
        meanings_ru = bucket["meanings_ru"][:MAX_MEANINGS_PER_LEMMA]
        if meanings_en:
            en_count += 1
        if meanings_ru:
            ru_count += 1
        out[lemma] = {
            "lemma": lemma,
            "pos": sorted(bucket["pos"]),
            "meanings_en": meanings_en,
            "meanings_ru": meanings_ru,
        }

    print(f"  unique lemmas:       {len(out):>7}")
    print(f"  with EN meanings:    {en_count:>7} ({en_count/len(out)*100:.1f}%)")
    print(f"  with RU meanings:    {ru_count:>7} ({ru_count/len(out)*100:.1f}%)")
    print(f"  skipped raw entries: {skipped:>7}")
    return out


def main() -> None:
    if not RAW_DIR.exists():
        raise SystemExit(
            f"Missing dir: {RAW_DIR}. Download 4 .mjs from github.com/sc-voice/ms-dpd:\n"
            "  dpd/definition-pali.mjs\n"
            "  dpd/index.mjs\n"
            "  dpd/en/definition-en.mjs\n"
            "  dpd/ru/definition-ru.mjs"
        )

    print(f"Building glossary from {RAW_DIR.relative_to(RAW_DIR.parent.parent.parent)}...")
    glossary = build_glossary()

    # Нормализуем юникод в NFC, чтобы кириллические/палийские символы
    # сравнивались побайтово.
    def _nfc(value: Any) -> Any:
        if isinstance(value, str):
            return unicodedata.normalize("NFC", value)
        if isinstance(value, list):
            return [_nfc(v) for v in value]
        if isinstance(value, dict):
            return {_nfc(k): _nfc(v) for k, v in value.items()}
        return value

    glossary = _nfc(glossary)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(glossary, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    size_mb = OUT_PATH.stat().st_size / 1024 / 1024
    print(f"Wrote {OUT_PATH} ({size_mb:.2f} MB)")


if __name__ == "__main__":
    main()
