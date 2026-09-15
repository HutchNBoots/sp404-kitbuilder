"""Phase 4 — copy approved kits into a clean per-kit staging folder.

Only kits ticked `[x]` in kits.md are exported. Files are always copied
(never moved) — the source library is never touched. Anything flagged
`needs_conversion` during scan gets converted to 16-bit/44.1kHz PCM on
the way out; the fixed copy is written, the original is left alone.
"""

from __future__ import annotations

import csv
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf

from kitbuilder.assembler import Kit, assemble_kits
from kitbuilder.reporter import parse_approved_kits

MANIFEST_FILENAME = "export_manifest.csv"
_BANK_LETTERS = "ABCDEFGHIJ"
TARGET_SAMPLE_RATE = 44100


@dataclass
class ManifestRow:
    kit: str
    bank: str
    pad: int
    category: str
    source_path: str
    exported_path: str
    converted: bool
    project: str = ""


def _sanitize(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_")


def _resample(data: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    n_frames = data.shape[0]
    if n_frames < 2 or orig_sr == target_sr:
        return data
    new_n = max(1, round(n_frames * target_sr / orig_sr))
    old_idx = np.linspace(0, n_frames - 1, num=n_frames)
    new_idx = np.linspace(0, n_frames - 1, num=new_n)
    return np.stack([np.interp(new_idx, old_idx, data[:, ch]) for ch in range(data.shape[1])], axis=1)


def _convert_with_soundfile(src: Path, dest: Path) -> None:
    data, sr = sf.read(str(src), dtype="float64", always_2d=True)
    if sr != TARGET_SAMPLE_RATE:
        data = _resample(data, sr, TARGET_SAMPLE_RATE)
    sf.write(str(dest), data, TARGET_SAMPLE_RATE, subtype="PCM_16")


def _convert_with_ffmpeg(src: Path, dest: Path) -> None:
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", str(src),
            "-ar", str(TARGET_SAMPLE_RATE),
            "-sample_fmt", "s16",
            str(dest),
        ],
        check=True,
    )


def _convert_file(src: Path, dest: Path) -> None:
    if shutil.which("ffmpeg"):
        _convert_with_ffmpeg(src, dest)
    else:
        _convert_with_soundfile(src, dest)


def export_kits(
    kits: list[Kit],
    approved: dict[str, bool],
    export_root: str | Path,
    dry_run: bool = False,
    kits_per_project: int | None = None,
) -> tuple[list[ManifestRow], list[str]]:
    """Copy every approved kit's assigned pads into export_root.

    Approved kits are exported in the order they appear in `approved`
    (kits.md lists complete kits best-first, so that order is preserved).

    When kits_per_project is set, kits are bundled into Project_N folders
    of that many kits each — matching the SP-404 MKII's 10 banks/project —
    with each kit's folder tagged Bank_XX for the hardware bank it would
    occupy in that project. Without it, kits export flat as
    <export_root>/<Kit Name>/Bank_A/... as before.

    Returns (manifest_rows, warnings). Nothing is written when dry_run.
    """
    rows: list[ManifestRow] = []
    warnings: list[str] = []
    root = Path(export_root)

    by_name = {k.name: k for k in kits}
    for name, checked in approved.items():
        if checked and name not in by_name:
            warnings.append(f"kits.md has '{name}' checked, but it's no longer among the scanned kits")

    approved_kits = [by_name[name] for name, checked in approved.items() if checked and name in by_name]

    for index, kit in enumerate(approved_kits):
        if kits_per_project:
            project_name = f"Project_{index // kits_per_project + 1}"
            bank_slot = index % kits_per_project + 1
            kit_root = root / project_name / f"Bank_{bank_slot:02d}_{kit.name}"
        else:
            project_name = ""
            kit_root = root / kit.name

        for bank_index, bank in enumerate(kit.banks):
            bank_name = f"Bank_{_BANK_LETTERS[bank_index]}"
            dest_dir = kit_root if kits_per_project else (kit_root / bank_name)
            if not dry_run:
                dest_dir.mkdir(parents=True, exist_ok=True)
            for pad in bank:
                src = Path(pad.path)
                dest = dest_dir / f"{pad.pad:02d}_{_sanitize(pad.display_name)}{src.suffix.lower()}"
                if not dry_run:
                    if pad.needs_conversion:
                        _convert_file(src, dest)
                    else:
                        shutil.copy2(src, dest)
                rows.append(
                    ManifestRow(
                        kit=kit.name,
                        bank=bank_name,
                        pad=pad.pad,
                        category=pad.category,
                        source_path=str(src),
                        exported_path=str(dest),
                        converted=pad.needs_conversion,
                        project=project_name,
                    )
                )
    return rows, warnings


def write_manifest(rows: list[ManifestRow], export_root: str | Path) -> Path:
    root = Path(export_root)
    root.mkdir(parents=True, exist_ok=True)
    manifest_path = root / MANIFEST_FILENAME
    with open(manifest_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["kit", "bank", "pad", "category", "source_path", "exported_path", "converted", "project"])
        for row in rows:
            writer.writerow(
                [row.kit, row.bank, row.pad, row.category, row.source_path, row.exported_path, row.converted, row.project]
            )
    return manifest_path


def load_approved_and_kits(in_dir: str | Path, scan_index: dict[str, Any], config: dict[str, Any]) -> tuple[list[Kit], dict[str, bool]]:
    kits_md_path = Path(in_dir) / "kits.md"
    if not kits_md_path.exists():
        raise FileNotFoundError(f"kits.md not found in {in_dir} — run `kitbuilder report` first")
    kits = assemble_kits(scan_index, config)
    approved = parse_approved_kits(kits_md_path)
    return kits, approved
