"""Read kitbuilder's export_manifest.csv and build one collected Drum Rack
per kit:

    <out>/<Kit>/<Kit>.adg
    <out>/<Kit>/Samples/Imported/<Kit>/01_Kick.wav ...

Each <Kit>/ folder is self-contained — the .adg only references samples by
relative path inside it — which is what Push 3 standalone needs, since it
can't resolve missing media.
"""

from __future__ import annotations

import csv
import re
import shutil
from dataclasses import dataclass
from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath

import soundfile as sf

from rackbuilder import calibration
from rackbuilder.adg import read_adg, write_adg
from rackbuilder.rack import PadSpec, build_rack

BUILD_MANIFEST_FILENAME = "build_manifest.csv"


@dataclass
class ManifestPad:
    kit: str
    pad: int
    category: str
    exported_path: str


@dataclass
class BuildRow:
    kit: str
    pad: int
    category: str
    chain_name: str
    relative_sample_path: str
    midi_note: int


def read_export_manifest(path: str | Path) -> dict[str, list[ManifestPad]]:
    """kit name -> pads sorted by pad number, kits in manifest order."""
    kits: dict[str, list[ManifestPad]] = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            kits.setdefault(row["kit"], []).append(
                ManifestPad(
                    kit=row["kit"],
                    pad=int(row["pad"]),
                    category=row["category"],
                    exported_path=row["exported_path"],
                )
            )
    for pads in kits.values():
        pads.sort(key=lambda p: p.pad)
    return kits


def _parse_any_path(raw: str) -> PurePath:
    # The manifest may have been written on Windows and read elsewhere.
    return PureWindowsPath(raw) if ("\\" in raw or re.match(r"^[A-Za-z]:", raw)) else PurePosixPath(raw)


def resolve_sample(exported_path: str, search_roots: list[Path]) -> Path | None:
    """Find a manifest's exported wav on this machine.

    Tries the path as written, then — for each search root — the longest
    trailing part of the path that exists under it. That copes with both
    kitbuilder layouts (<Kit>/Bank_A/x.wav and Project_N/Bank_XX_<Kit>/x.wav)
    and with the export folder having moved or been exported relative to
    a different working directory.
    """
    direct = Path(exported_path)
    if direct.is_file():
        return direct
    parts = _parse_any_path(exported_path).parts
    for root in search_roots:
        for k in range(len(parts), 0, -1):
            candidate = root.joinpath(*parts[-k:])
            if candidate.is_file():
                return candidate
    return None


_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_folder_name(name: str) -> str:
    """Strip characters Windows (and Push's browser) can't take in a name."""
    cleaned = _ILLEGAL.sub("_", name).strip().rstrip(".")
    return cleaned or "Kit"


def chain_name_for(pad: ManifestPad) -> str:
    """kitbuilder names exported files '<NN>_<Display_Name>.wav' (e.g.
    '02_Kick_2.wav'); recover 'Kick 2' from that, falling back to the plain
    category."""
    stem = _parse_any_path(pad.exported_path).stem
    m = re.match(r"^\d+_(.+)$", stem)
    return m.group(1).replace("_", " ") if m else pad.category


def build_kit(
    kit_name: str,
    pads: list[ManifestPad],
    template_path: str | Path,
    out_root: str | Path,
    search_roots: list[Path],
    base_note: int = calibration.DEFAULT_BASE_NOTE,
    relative_path_type: int = calibration.RELATIVE_PATH_TYPE,
    dry_run: bool = False,
) -> tuple[list[BuildRow], list[str]]:
    warnings: list[str] = []
    folder = safe_folder_name(kit_name)
    kit_dir = Path(out_root) / folder
    sample_dir = kit_dir / calibration.SAMPLES_SUBDIR / folder

    if pads and pads[0].category != "Kick" and any(p.category == "Kick" for p in pads):
        warnings.append(f"{kit_name}: pad {pads[0].pad} is {pads[0].category}, not Kick — the base note won't be a kick")
    if base_note + len(pads) - 1 > 127:
        raise ValueError(f"{kit_name}: {len(pads)} pads from base note {base_note} would run past MIDI note 127")

    specs: list[PadSpec] = []
    rows: list[BuildRow] = []
    for index, pad in enumerate(pads):
        src = resolve_sample(pad.exported_path, search_roots)
        if src is None:
            warnings.append(f"{kit_name}: pad {pad.pad} sample not found ({pad.exported_path}) — skipped")
            continue
        filename = src.name
        dest = sample_dir / filename
        relative = calibration.relative_sample_path(folder, filename)
        midi_note = base_note + index
        name = chain_name_for(pad)
        info = sf.info(str(src))
        specs.append(
            PadSpec(
                name=name,
                midi_note=midi_note,
                relative_path=relative,
                absolute_path=dest.resolve().as_posix(),
                file_size=src.stat().st_size,
                frames=info.frames,
                sample_rate=info.samplerate,
            )
        )
        rows.append(BuildRow(kit_name, pad.pad, pad.category, name, relative, midi_note))
        if not dry_run:
            sample_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)

    if not specs:
        warnings.append(f"{kit_name}: no samples found — rack not built")
        return [], warnings

    if not dry_run:
        tree = build_rack(read_adg(template_path), specs, relative_path_type)
        write_adg(tree, kit_dir / f"{folder}.adg")
    return rows, warnings


def build_all(
    manifest_path: str | Path,
    template_path: str | Path,
    out_root: str | Path,
    samples_root: str | Path | None = None,
    base_note: int = calibration.DEFAULT_BASE_NOTE,
    relative_path_type: int = calibration.RELATIVE_PATH_TYPE,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
    dry_run: bool = False,
) -> tuple[list[BuildRow], list[str]]:
    manifest_path = Path(manifest_path)
    kits = read_export_manifest(manifest_path)
    warnings: list[str] = []

    for name in (include or []) + (exclude or []):
        if name not in kits:
            warnings.append(f"'{name}' isn't a kit in {manifest_path.name}")
    selected = [k for k in kits if (not include or k in include) and k not in (exclude or [])]

    search_roots = [Path(samples_root)] if samples_root else []
    search_roots.append(manifest_path.resolve().parent)

    rows: list[BuildRow] = []
    for kit_name in selected:
        kit_rows, kit_warnings = build_kit(
            kit_name,
            kits[kit_name],
            template_path,
            out_root,
            search_roots,
            base_note=base_note,
            relative_path_type=relative_path_type,
            dry_run=dry_run,
        )
        rows.extend(kit_rows)
        warnings.extend(kit_warnings)
    return rows, warnings


def write_build_manifest(rows: list[BuildRow], out_root: str | Path) -> Path:
    root = Path(out_root)
    root.mkdir(parents=True, exist_ok=True)
    path = root / BUILD_MANIFEST_FILENAME
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["kit", "pad", "category", "chain_name", "relative_sample_path", "midi_note"])
        for r in rows:
            writer.writerow([r.kit, r.pad, r.category, r.chain_name, r.relative_sample_path, r.midi_note])
    return path
