"""Build a bilingual search vocabulary uniformly from the bundled past reports."""

from collections import Counter
from functools import lru_cache
from importlib.resources import files
import re


# Preserve technical phrases such as “SSL handshake”, a camel-case class or a path.
TECH_PHRASE = re.compile(r"[A-Za-z][A-Za-z0-9_/-]*(?: [A-Za-z][A-Za-z0-9_/-]*)*")


@lru_cache(maxsize=1)
def report_vocabulary() -> dict[str, list[str]]:
    folder = files("fivewhys").joinpath("data", "postmortems")
    by_title = {}
    for path in sorted(folder.iterdir(), key=lambda p: p.name):
        if not path.name.endswith(".md"):
            continue
        text = path.read_text(encoding="utf-8")
        title = text.splitlines()[0].removeprefix("# 장애 보고서: ")
        title = re.sub(r"\s*\(\d{4}-\d{2}-\d{2}\)\s*$", "", title)
        summary = re.search(r"^## 요약\s*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
        if summary:
            by_title[title] = list(dict.fromkeys(TECH_PHRASE.findall(summary[1])))
    counts = Counter(term for terms in by_title.values() for term in terms)
    # Purely shared abbreviations are poor selectors. Each remaining entry has
    # identical extraction rules, independent of the current incident or question.
    return {
        title: [term for term in terms if counts[term] == 1]
        for title, terms in by_title.items()
    }


def _features(text: str) -> set[str]:
    words = set(re.findall(r"[a-z0-9]+|[가-힣]+", text.lower()))
    # Hangul particles often attach to a noun; English technical identifiers can
    # be compared as full tokens without matching unrelated service suffixes.
    return {w for w in words if len(w) >= 2} | {
        word[i : i + 2]
        for word in words
        if re.fullmatch(r"[가-힣]+", word)
        for i in range(len(word) - 1)
    }


@lru_cache(maxsize=1)
def _document_frequencies() -> Counter:
    folder = files("fivewhys").joinpath("data", "postmortems")
    counts = Counter()
    for path in folder.iterdir():
        if path.name.endswith(".md"):
            counts.update(_features(path.read_text(encoding="utf-8")))
    return counts


def relevant_vocabulary(question: str) -> dict[str, list[str]]:
    """Rank title/summary terms by overlap, discounting corpus-wide common words."""
    glossary = report_vocabulary()
    query = _features(question)
    counts = _document_frequencies()
    scores = {}
    for title, terms in glossary.items():
        overlap = query & _features(title + " " + " ".join(terms))
        scores[title] = sum(1 / counts[term] for term in sorted(overlap))
    peak = max(scores.values(), default=0)
    if not peak:
        return {}
    ranked = sorted(scores, key=scores.get, reverse=True)
    return {
        title: glossary[title] for title in ranked[:2] if scores[title] >= peak * 0.65
    }
