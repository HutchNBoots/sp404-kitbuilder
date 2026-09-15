"""Phase 2 — group scanned files by pack into candidate SP-404 kits.

A kit lives on exactly one bank (16 pads). Fill order:
  1. Basics: one Kick, one Snare, one Hat (closed or open, whichever the
     pack has) — a kit missing any of these is flagged incomplete.
  2. Everything else in core_categories priority order, each capped at
     max_variations_per_category (default 2: e.g. Kick, Kick 2 — never
     Kick 3), up to a ceiling of (pads_per_bank - reserved_melodic_pads).
  3. The last reserved_melodic_pads pads are set aside for melodic_categories
     content if the pack has any; otherwise they're left free for the user
     to drop their own melodic samples in later — never backfilled with
     more drum/perc variations.
Overflow beyond those caps/ceilings becomes "alternates". Unclassified
("Other") files are listed but never assigned a pad.

Packs are also checked for a shared, non-generic filename token (e.g.
"BB3_hat_closed_sugar.wav") that suggests a real kit name distinct from
the pack folder — see _infer_kit_groups.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from kitbuilder.classifier import OTHER

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STRUCTURAL_TOKEN_DOC_FREQ = 0.6  # a token in >60% of a pack's filenames is a shared prefix/code, not a kit name
_DOMINANT_LABEL_SHARE = 0.6  # a single label covering >=60% of classifiable files just renames the pack's kit


@dataclass
class FileRef:
    category: str
    display_name: str
    filename: str
    path: str
    format_flags: list[str]
    needs_conversion: bool


@dataclass
class PadAssignment(FileRef):
    pad: int


@dataclass
class Kit:
    name: str
    banks: list[list[PadAssignment]]
    alternates: dict[str, list[FileRef]]
    unclassified: list[FileRef]
    weak: bool
    missing_basics: list[str]
    distinct_category_count: int
    total_classified: int
    total_pads_used: int
    melodic_pads_used: int
    melodic_pads_reserved: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "banks": [[asdict(p) for p in bank] for bank in self.banks],
            "alternates": {cat: [asdict(f) for f in files] for cat, files in self.alternates.items()},
            "unclassified": [asdict(f) for f in self.unclassified],
            "weak": self.weak,
            "missing_basics": self.missing_basics,
            "distinct_category_count": self.distinct_category_count,
            "total_classified": self.total_classified,
            "total_pads_used": self.total_pads_used,
            "melodic_pads_used": self.melodic_pads_used,
            "melodic_pads_reserved": self.melodic_pads_reserved,
        }


def _file_ref(record: dict[str, Any], display_name: str) -> FileRef:
    return FileRef(
        category=record["category"],
        display_name=display_name,
        filename=record["filename"],
        path=record["path"],
        format_flags=record["format_flags"],
        needs_conversion=record["needs_conversion"],
    )


# --- kit-name inference from filename tokens -------------------------------


def _infer_filename_labels(records: list[dict[str, Any]], flattened_keywords: set[str]) -> dict[str, str | None]:
    tokens_by_path = {r["path"]: _TOKEN_RE.findall(Path(r["filename"]).stem.lower()) for r in records}

    doc_freq: Counter[str] = Counter()
    for tokens in tokens_by_path.values():
        for token in set(tokens):
            doc_freq[token] += 1
    n = len(tokens_by_path)

    def is_structural(token: str) -> bool:
        # A token shared by *every* file is the pack's one true kit name,
        # not a boilerplate prefix/code — only tokens common but not
        # universal (a shared prefix like "BB3") count as structural.
        freq = doc_freq[token] / n if n else 0
        return (
            token in flattened_keywords
            or token.isdigit()
            or len(token) <= 2
            or _STRUCTURAL_TOKEN_DOC_FREQ < freq < 1.0
        )

    labels: dict[str, str | None] = {}
    for path, tokens in tokens_by_path.items():
        candidates = [t for t in tokens if not is_structural(t)]
        labels[path] = candidates[-1] if candidates else None
    return labels


def _satisfies_basics(records: list[dict[str, Any]], required_basics: list[list[str]]) -> bool:
    categories_present = {r["category"] for r in records}
    return all(any(cat in categories_present for cat in group) for group in required_basics)


def _infer_kit_groups(
    pack_name: str, records: list[dict[str, Any]], config: dict[str, Any]
) -> list[tuple[str, list[dict[str, Any]]]]:
    if not config["infer_kit_name_from_filename"]:
        return [(pack_name, records)]

    classifiable = [r for r in records if r["category"] != OTHER]
    if len(classifiable) < 2:
        return [(pack_name, records)]

    flattened_keywords = {kw.lower() for keywords in config["categories"].values() for kw in keywords}
    labels = _infer_filename_labels(classifiable, flattened_keywords)

    by_label: dict[str, list[dict[str, Any]]] = {}
    for r in classifiable:
        label = labels.get(r["path"])
        if label:
            by_label.setdefault(label, []).append(r)

    required_basics = config["required_basics"]
    qualifying = {label: recs for label, recs in by_label.items() if _satisfies_basics(recs, required_basics)}

    if len(qualifying) >= 2:
        labeled_paths = {r["path"] for recs in qualifying.values() for r in recs}
        groups = [(f"{pack_name} — {label.title()}", recs) for label, recs in sorted(qualifying.items())]
        leftover = [r for r in records if r["path"] not in labeled_paths]
        if leftover:
            groups.append((pack_name, leftover))
        return groups

    if len(qualifying) == 1:
        (label, recs), = qualifying.items()
        if len(recs) >= _DOMINANT_LABEL_SHARE * len(classifiable):
            return [(f"{pack_name} — {label.title()}", records)]

    return [(pack_name, records)]


# --- pad/bank assembly ------------------------------------------------------


def _assemble_one_kit(kit_name: str, records: list[dict[str, Any]], config: dict[str, Any]) -> Kit:
    pads_per_bank = config["pads_per_bank"]
    reserved_melodic = config["reserved_melodic_pads"]
    max_variations = config["max_variations_per_category"]
    core_categories = config["core_categories"]
    melodic_categories = config["melodic_categories"]
    required_basics = config["required_basics"]

    by_category: dict[str, list[dict[str, Any]]] = {}
    unclassified_records = []
    for record in records:
        if record["category"] == OTHER:
            unclassified_records.append(record)
        else:
            by_category.setdefault(record["category"], []).append(record)
    for files in by_category.values():
        files.sort(key=lambda r: r["filename"])

    capped = {cat: files[:max_variations] for cat, files in by_category.items()}
    overflow_by_category = {cat: files[max_variations:] for cat, files in by_category.items() if len(files) > max_variations}

    def ref_at(category: str, index: int) -> FileRef:
        record = capped[category][index]
        display_name = category if index == 0 else f"{category} {index + 1}"
        return _file_ref(record, display_name)

    missing_basics: list[str] = []
    consumed: dict[str, int] = {cat: 0 for cat in capped}
    tier1: list[FileRef] = []
    for group in required_basics:
        chosen = next((cat for cat in group if capped.get(cat)), None)
        if chosen:
            tier1.append(ref_at(chosen, 0))
            consumed[chosen] = 1
        else:
            missing_basics.append(" or ".join(group))

    tier2: list[FileRef] = []
    for category in core_categories:
        files = capped.get(category, [])
        for i in range(consumed.get(category, 0), len(files)):
            tier2.append(ref_at(category, i))
        consumed[category] = len(files)

    core_pool = tier1 + tier2
    core_capacity = pads_per_bank - reserved_melodic
    core_assigned, core_overflow_refs = core_pool[:core_capacity], core_pool[core_capacity:]

    melodic_pool: list[FileRef] = []
    for category in melodic_categories:
        for i in range(len(capped.get(category, []))):
            melodic_pool.append(ref_at(category, i))
    melodic_assigned, melodic_overflow_refs = melodic_pool[:reserved_melodic], melodic_pool[reserved_melodic:]

    all_assigned = core_assigned + melodic_assigned
    bank = [
        PadAssignment(
            category=ref.category,
            display_name=ref.display_name,
            filename=ref.filename,
            path=ref.path,
            format_flags=ref.format_flags,
            needs_conversion=ref.needs_conversion,
            pad=i,
        )
        for i, ref in enumerate(all_assigned, start=1)
    ]
    banks = [bank] if bank else []

    alternates: dict[str, list[FileRef]] = {}
    for category, files in overflow_by_category.items():
        for j, record in enumerate(files, start=max_variations + 1):
            alternates.setdefault(category, []).append(_file_ref(record, f"{category} {j}"))
    for ref in core_overflow_refs + melodic_overflow_refs:
        alternates.setdefault(ref.category, []).append(ref)

    unclassified = sorted((_file_ref(r, OTHER) for r in unclassified_records), key=lambda r: r.filename)

    return Kit(
        name=kit_name,
        banks=banks,
        alternates=alternates,
        unclassified=unclassified,
        weak=bool(missing_basics),
        missing_basics=missing_basics,
        distinct_category_count=len(by_category),
        total_classified=sum(len(files) for files in by_category.values()),
        total_pads_used=len(all_assigned),
        melodic_pads_used=len(melodic_assigned),
        melodic_pads_reserved=reserved_melodic,
    )


def assemble_kits(scan_index: dict[str, Any], config: dict[str, Any]) -> list[Kit]:
    by_pack: dict[str, list[dict[str, Any]]] = {}
    for record in scan_index["files"]:
        by_pack.setdefault(record["pack"], []).append(record)

    kits = []
    for pack_name, records in by_pack.items():
        for kit_name, kit_records in _infer_kit_groups(pack_name, records, config):
            kits.append(_assemble_one_kit(kit_name, kit_records, config))
    return sorted(kits, key=lambda k: k.name.lower())
