"""Filename -> category classification, driven by categories.yaml."""

from __future__ import annotations

OTHER = "Other"


def classify_filename(filename: str, categories: dict[str, list[str]]) -> tuple[str, list[str]]:
    """Classify a filename against an ordered category->keywords map.

    Matching is case-insensitive and checks anywhere in the filename (not
    just the start). The first category (in config order) with a keyword
    hit wins. Any *other* categories that also matched are returned so
    callers can log the ambiguity for manual review.

    Returns (category, ambiguous_other_categories). category is "Other"
    when nothing matched.
    """
    lower = filename.lower()
    matches = [
        category
        for category, keywords in categories.items()
        if any(keyword.lower() in lower for keyword in keywords)
    ]
    if not matches:
        return OTHER, []
    return matches[0], matches[1:]
