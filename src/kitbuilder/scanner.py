"""Phase 1 — walk --source, classify every audio file, write scan_index.json."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import soundfile as sf

from kitbuilder.classifier import classify_filename

SCAN_INDEX_FILENAME = "scan_index.json"

# The SP-404 MKII natively handles 44.1kHz and 48kHz PCM. Anything else gets
# flagged for the export-time format-fix step. (Not stated verbatim in the
# unit's spec sheet; treated as a reasonable assumption for this tool.)
SUPPORTED_SAMPLE_RATES = {44100, 48000}
SUPPORTED_PCM_SUBTYPES = {"PCM_16", "PCM_24"}

SUBTYPE_BIT_DEPTH = {
    "PCM_16": 16,
    "PCM_24": 24,
    "PCM_32": 32,
    "PCM_S8": 8,
    "PCM_U8": 8,
    "FLOAT": 32,
    "DOUBLE": 64,
}


@dataclass
class FileRecord:
    path: str
    pack: str
    filename: str
    size_bytes: int
    sample_rate: int
    bit_depth: int | None
    subtype: str
    duration_sec: float
    category: str
    ambiguous_categories: list[str]
    needs_conversion: bool
    format_flags: list[str] = field(default_factory=list)


def _is_excluded(rel_parts: tuple[str, ...], exclude_folders: list[str]) -> bool:
    excluded_lower = {name.lower() for name in exclude_folders}
    # Only folder components matter (last part is the filename).
    return any(part.lower() in excluded_lower for part in rel_parts[:-1])


def _pack_name(rel_parts: tuple[str, ...]) -> str:
    """Pack = top-level folder under --source. Loose files at the root
    (no subfolder) fall back to a synthetic "(root)" pack name."""
    return rel_parts[0] if len(rel_parts) > 1 else "(root)"


def _format_flags(subtype: str, sample_rate: int) -> tuple[bool, list[str]]:
    flags = []
    needs_conversion = False
    if subtype not in SUPPORTED_PCM_SUBTYPES:
        needs_conversion = True
        flags.append(f"needs conversion ({subtype} is not 16/24-bit PCM)")
    if sample_rate not in SUPPORTED_SAMPLE_RATES:
        needs_conversion = True
        flags.append(f"needs conversion (sample rate {sample_rate}Hz unsupported)")
    return needs_conversion, flags


def scan_file(path: Path, source_root: Path, categories: dict[str, list[str]]) -> FileRecord:
    rel_parts = path.relative_to(source_root).parts
    info = sf.info(str(path))
    needs_conversion, format_flags = _format_flags(info.subtype, info.samplerate)
    category, ambiguous = classify_filename(path.name, categories)
    return FileRecord(
        path=str(path.resolve()),
        pack=_pack_name(rel_parts),
        filename=path.name,
        size_bytes=path.stat().st_size,
        sample_rate=info.samplerate,
        bit_depth=SUBTYPE_BIT_DEPTH.get(info.subtype),
        subtype=info.subtype,
        duration_sec=round(info.frames / info.samplerate, 3) if info.samplerate else 0.0,
        category=category,
        ambiguous_categories=ambiguous,
        needs_conversion=needs_conversion,
        format_flags=format_flags,
    )


def scan_source(source: str | Path, config: dict[str, Any]) -> list[FileRecord]:
    source_root = Path(source)
    if not source_root.is_dir():
        raise FileNotFoundError(f"--source folder not found: {source_root}")

    extensions = {ext.lower() for ext in config["extensions"]}
    exclude_folders = config["exclude_folders"]
    categories = config["categories"]

    records: list[FileRecord] = []
    for path in sorted(source_root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in extensions:
            continue
        rel_parts = path.relative_to(source_root).parts
        if _is_excluded(rel_parts, exclude_folders):
            continue
        records.append(scan_file(path, source_root, categories))
    return records


def write_scan_index(
    records: list[FileRecord], out_dir: str | Path, source: str | Path
) -> Path:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    index_path = out_path / SCAN_INDEX_FILENAME
    payload = {
        "source": str(Path(source).resolve()),
        "file_count": len(records),
        "files": [asdict(r) for r in records],
    }
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return index_path


def load_scan_index(out_dir: str | Path) -> dict[str, Any]:
    index_path = Path(out_dir) / SCAN_INDEX_FILENAME
    if not index_path.exists():
        raise FileNotFoundError(
            f"{SCAN_INDEX_FILENAME} not found in {out_dir} — run `kitbuilder scan` first"
        )
    with open(index_path, encoding="utf-8") as f:
        return json.load(f)
