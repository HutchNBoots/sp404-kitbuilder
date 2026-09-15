"""Phase 2 — group scanned files by pack into candidate SP-404 kits.

One candidate kit per pack folder. Within a kit, files fill pads in the
fixed category priority order from categories.yaml. Multiple files in the
same category are NOT collapsed: they all get pads, back-to-back, suffixed
"Category 2", "Category 3", ... as long as room remains. Overflow beyond
the kit's bank capacity becomes "alternates"; unclassified ("Other") files
are listed but never assigned a pad.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from kitbuilder.classifier import OTHER


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
    distinct_category_count: int
    total_classified: int
    total_pads_used: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "banks": [[asdict(p) for p in bank] for bank in self.banks],
            "alternates": {cat: [asdict(f) for f in files] for cat, files in self.alternates.items()},
            "unclassified": [asdict(f) for f in self.unclassified],
            "weak": self.weak,
            "distinct_category_count": self.distinct_category_count,
            "total_classified": self.total_classified,
            "total_pads_used": self.total_pads_used,
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


def _assemble_one_kit(pack_name: str, records: list[dict[str, Any]], config: dict[str, Any]) -> Kit:
    pads_per_bank = config["pads_per_bank"]
    banks_per_kit_max = config["banks_per_kit_max"]
    weak_threshold = config["weak_kit_category_threshold"]
    category_order = list(config["categories"].keys())

    by_category: dict[str, list[dict[str, Any]]] = {}
    unclassified_records = []
    for record in records:
        if record["category"] == OTHER:
            unclassified_records.append(record)
        else:
            by_category.setdefault(record["category"], []).append(record)

    ordered_refs: list[FileRef] = []
    for category in category_order:
        files = sorted(by_category.get(category, []), key=lambda r: r["filename"])
        for i, record in enumerate(files, start=1):
            display_name = category if i == 1 else f"{category} {i}"
            ordered_refs.append(_file_ref(record, display_name))

    total_classified = len(ordered_refs)
    distinct_category_count = len(by_category)
    weak = distinct_category_count < weak_threshold

    capacity = pads_per_bank * banks_per_kit_max
    assigned, leftover = ordered_refs[:capacity], ordered_refs[capacity:]

    banks: list[list[PadAssignment]] = []
    for start in range(0, len(assigned), pads_per_bank):
        chunk = assigned[start : start + pads_per_bank]
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
            for i, ref in enumerate(chunk, start=1)
        ]
        banks.append(bank)

    alternates: dict[str, list[FileRef]] = {}
    for ref in leftover:
        alternates.setdefault(ref.category, []).append(ref)

    unclassified = sorted(
        (_file_ref(r, OTHER) for r in unclassified_records), key=lambda r: r.filename
    )

    return Kit(
        name=pack_name,
        banks=banks,
        alternates=alternates,
        unclassified=unclassified,
        weak=weak,
        distinct_category_count=distinct_category_count,
        total_classified=total_classified,
        total_pads_used=len(assigned),
    )


def assemble_kits(scan_index: dict[str, Any], config: dict[str, Any]) -> list[Kit]:
    by_pack: dict[str, list[dict[str, Any]]] = {}
    for record in scan_index["files"]:
        by_pack.setdefault(record["pack"], []).append(record)

    kits = [
        _assemble_one_kit(pack_name, records, config)
        for pack_name, records in by_pack.items()
    ]
    return sorted(kits, key=lambda k: k.name.lower())
