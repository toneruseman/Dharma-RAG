"""Pāli glossary для query-expansion.

Зачем:
    BGE-M3 multilingual encoder хорошо понимает EN/RU, но проседает на
    bare-Pāli ("что такое jhāna") и на кириллических транслитерациях
    ("что такое джхана") — в корпусе слова в формах ``jhāna`` или
    ``meditative absorption``, и multilingual-эмбеддинг не всегда
    стягивает «джхана» к нужным чанкам.

    Решение — расширять запрос **до** encode'а: добавляем к тексту
    запроса каноническую палийскую lemma и её EN/RU значения из DPD.
    Пример::

        "что такое джхана?"
        → "что такое джхана? jhāna meditative absorption медитация"

Источники данных:
    - ``data/glossary/dpd_full.json`` — 50k Pāli лемм с EN+RU
      переводами. Собран из github.com/sc-voice/ms-dpd (CC-BY-NC 4.0)
      скриптом ``scripts/build_dpd_glossary.py``.
    - ``data/glossary/cyrillic.yaml`` — ручной слой кириллических
      написаний (~155 high-freq терминов, 288 вариантов). DPD кириллицу
      не содержит — без этого слоя «джхана» не резолвится.

Лицензия:
    DPD под CC-BY-NC 4.0 — Non-Commercial. Для MVP / исследования
    подходит. Перед коммерциализацией — заменять на открытый источник
    или договариваться с авторами DPD.
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GlossaryEntry:
    """Одна палийская лемма с переводами."""

    pali: str
    pos: tuple[str, ...]
    meanings_en: tuple[str, ...]
    meanings_ru: tuple[str, ...]


class Glossary:
    """Палийский глоссарий. Резолвит токены запроса в Pāli леммы и
    добавляет переводы в текст запроса."""

    def __init__(
        self,
        *,
        dpd: dict[str, GlossaryEntry],
        cyrillic_to_pali: dict[str, str],
    ) -> None:
        self._dpd = dpd
        self._cyrillic_to_pali = cyrillic_to_pali
        # Индекс по «обездиакритенной» форме: jhana → jhāna. Полезен,
        # когда пользователь набирает Pāli без диакритик.
        self._dpd_no_diacritics: dict[str, str] = {}
        for lemma in dpd:
            stripped = _strip_diacritics(lemma)
            # Если коллизия (jhana и jhāna без диакритик одинаковы) —
            # оставляем первый. На практике коллизии редки.
            self._dpd_no_diacritics.setdefault(stripped, lemma)

    @property
    def size(self) -> dict[str, int]:
        """Сколько записей в каждом слое — для логов и /health."""
        return {
            "dpd_lemmas": len(self._dpd),
            "cyrillic_variants": len(self._cyrillic_to_pali),
        }

    def expand_query(
        self,
        query: str,
        *,
        max_meanings: int = 1,
        max_terms: int = 5,
    ) -> str:
        """Возвращает расширенный запрос.

        Если ни один токен не нашёлся в глоссарии — возвращается
        исходный ``query`` без изменений.

        Args:
            query: исходный текст запроса.
            max_meanings: сколько EN+RU значений добавлять на один
                распознанный термин. Default ``1`` подобран на rag-day-23
                tuning eval (`docs/EVAL_PALI_TUNING.md`): на targeted
                golden set ``max_meanings=1`` даёт ref_hit@5 +9 pp над
                baseline (vs +1 pp для max=2 — слишком много синонимов
                размывает запрос). ``0`` добавляет только Pāli лемму,
                без переводов — полезно если encoder и так понимает
                смысловое поле, нужен только мостик cyrillic→Pāli.
            max_terms: верхняя граница на число распознанных терминов
                в одном запросе. Защита от раздувания запроса в случае,
                если он целиком из палийских слов.
        """
        tokens = _tokenize(query)
        if not tokens:
            return query

        added: list[str] = []
        seen: set[str] = {t.lower() for t in tokens}
        terms_expanded = 0

        for token in tokens:
            if terms_expanded >= max_terms:
                break
            pali, entry = self._lookup(token)
            if pali is None:
                continue
            terms_expanded += 1
            # Сначала добавляем каноническую Pāli lemma (если отличается
            # от токена — особенно важно для cyrillic→pali резолва).
            if pali.lower() not in seen:
                seen.add(pali.lower())
                added.append(pali)
            if entry is not None:
                for meaning in entry.meanings_en[:max_meanings]:
                    key = meaning.lower()
                    if key not in seen:
                        seen.add(key)
                        added.append(meaning)
                for meaning in entry.meanings_ru[:max_meanings]:
                    key = meaning.lower()
                    if key not in seen:
                        seen.add(key)
                        added.append(meaning)

        if not added:
            return query
        return f"{query} {' '.join(added)}"

    def _lookup(self, token: str) -> tuple[str | None, GlossaryEntry | None]:
        """Ищет токен. Возвращает (pali_lemma, dpd_entry).

        Стратегии в порядке убывания точности:
          1. Кириллический слой (token == «джхана» → "jhāna") —
             ВСЕГДА разрешён, кириллица не пересекается с английским
          2. Прямое совпадение в DPD, **только если в токене есть
             палийские диакритики** ("jhāna" → DPD)
          3. Без диакритик через стрип, **только если стрип реально
             что-то снял** (i.e., у токена были диакритики)

        Зачем такой строгий фильтр на ASCII: DPD содержит ~50k лемм,
        включая односимвольные служебные ("a", "na", "va") и обычные
        английские заимствования ("buddha", "sutta", "kamma"). На
        английских запросах эти леммы шумно матчатся (см. day-23
        mini-eval): расширение `Buddha` в `Awakened One Будда
        Пробужденный` ломает semantic context для ENGLISH retrieval,
        потому что corpus уже понимает английское "Buddha" в нужном
        смысле без нашей помощи.

        Реальная польза глоссария — только там, где у encoder'а
        пробел: bare-Pāli с диакритиками + кириллические транслитерации.
        ASCII-Pāli без диакритик ("jhana") теряем, но пользователь
        может набрать "jhāna" или "джхана" и получить расширение.
        """
        token_l = token.lower()

        # 1. Кириллица — всегда.
        if token_l in self._cyrillic_to_pali:
            pali = self._cyrillic_to_pali[token_l]
            return pali, self._dpd.get(pali)

        # 2/3. Pāli с диакритиками — прямой lookup или через strip.
        if _has_pali_diacritics(token_l):
            if token_l in self._dpd:
                return token_l, self._dpd[token_l]
            stripped = _strip_diacritics(token_l)
            if stripped in self._dpd_no_diacritics:
                canonical = self._dpd_no_diacritics[stripped]
                if canonical != token_l:
                    return canonical, self._dpd[canonical]

        return None, None


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


_DEFAULT_DPD_PATH = Path("data/glossary/dpd_full.json")
_DEFAULT_CYRILLIC_PATH = Path("data/glossary/cyrillic.yaml")


def load_glossary(
    *,
    dpd_path: Path | None = None,
    cyrillic_path: Path | None = None,
) -> Glossary:
    """Загружает глоссарий из дефолтных или явно указанных путей.

    Бросает ``FileNotFoundError`` если файлы отсутствуют — вызывающий
    код решает что делать (фоллбэк на None / отключить expansion).
    """
    dpd_path = dpd_path or _DEFAULT_DPD_PATH
    cyrillic_path = cyrillic_path or _DEFAULT_CYRILLIC_PATH

    raw = json.loads(dpd_path.read_text(encoding="utf-8"))
    dpd: dict[str, GlossaryEntry] = {}
    for lemma, payload in raw.items():
        dpd[lemma] = GlossaryEntry(
            pali=payload["lemma"],
            pos=tuple(payload.get("pos", ())),
            meanings_en=tuple(payload.get("meanings_en", ())),
            meanings_ru=tuple(payload.get("meanings_ru", ())),
        )

    cyrillic_data = yaml.safe_load(cyrillic_path.read_text(encoding="utf-8"))
    cyrillic_to_pali: dict[str, str] = {}
    for entry in cyrillic_data:
        pali = entry["pali"]
        for variant in entry["cyrillic"]:
            # Нормализуем: NFC + lowercase.
            key = unicodedata.normalize("NFC", variant).lower()
            # При коллизии (один кириллический вариант → две Pāli леммы)
            # оставляем первое попавшееся, но логируем.
            if key in cyrillic_to_pali and cyrillic_to_pali[key] != pali:
                logger.warning(
                    "Cyrillic variant %r collides: %s vs %s — keeping first",
                    variant,
                    cyrillic_to_pali[key],
                    pali,
                )
                continue
            cyrillic_to_pali[key] = pali

    glossary = Glossary(dpd=dpd, cyrillic_to_pali=cyrillic_to_pali)
    logger.info("Loaded glossary: %s", glossary.size)
    return glossary


# ---------------------------------------------------------------------------
# Helpers (tokenization, diacritic stripping)
# ---------------------------------------------------------------------------

# Регулярка: ловим последовательности букв (включая Unicode-letter,
# Pāli-диакритики и кириллицу) + дефис между буквами (для составных
# вроде "благородная-истина" в cyrillic.yaml).
_TOKEN_RE = re.compile(r"[^\W\d_]+(?:-[^\W\d_]+)*", flags=re.UNICODE)


def _tokenize(text: str) -> list[str]:
    """Простая токенизация для lookup'а в глоссарии."""
    if not text:
        return []
    text = unicodedata.normalize("NFC", text)
    return [m.group(0).lower() for m in _TOKEN_RE.finditer(text)]


def _strip_diacritics(s: str) -> str:
    """``jhāna`` → ``jhana``. Только для латиницы — кириллицу не трогаем."""
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _has_pali_diacritics(s: str) -> bool:
    """``True``, если в токене есть combining mark (макрон, точка снизу,
    тильда и т.п.) — характерно для Pāli транслитерации (jhāna, paṭiccasamuppāda).

    Используется как guard для DPD-lookup'а: pure-ASCII токены ("buddha",
    "sutta", "a", "from") не должны матчить DPD-леммы, иначе расширение
    шумит на английских запросах. См. ``Glossary._lookup`` rationale.
    """
    nfd = unicodedata.normalize("NFD", s)
    return any(unicodedata.category(c) == "Mn" for c in nfd)


__all__ = [
    "Glossary",
    "GlossaryEntry",
    "_has_pali_diacritics",
    "_strip_diacritics",
    "_tokenize",
    "load_glossary",
]
