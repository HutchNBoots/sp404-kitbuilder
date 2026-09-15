import csv

import soundfile as sf

from kitbuilder.assembler import assemble_kits
from kitbuilder.exporter import export_kits, write_manifest
from kitbuilder.scanner import scan_source


def _scan_index(source_dir, config):
    records = scan_source(source_dir, config)
    return {"source": str(source_dir), "file_count": len(records), "files": [r.__dict__ for r in records]}


def test_export_copies_only_approved_kits(source_dir, config, tmp_path):
    scan_index = _scan_index(source_dir, config)
    kits = assemble_kits(scan_index, config)
    approved = {k.name: (k.name == "Tiny Pack") for k in kits}

    export_root = tmp_path / "export"
    rows, warnings = export_kits(kits, approved, export_root, dry_run=False)

    assert warnings == []
    assert all(r.kit == "Tiny Pack" for r in rows)
    assert (export_root / "Tiny Pack" / "Bank_A" / "01_Kick.wav").exists()
    assert not (export_root / "Zander Lowfi Drums").exists()


def test_export_never_spans_more_than_bank_a(source_dir, config, tmp_path):
    scan_index = _scan_index(source_dir, config)
    kits = assemble_kits(scan_index, config)
    approved = {k.name: (k.name == "Zander Lowfi Drums") for k in kits}

    export_root = tmp_path / "export"
    export_kits(kits, approved, export_root, dry_run=False)

    assert (export_root / "Zander Lowfi Drums" / "Bank_A").is_dir()
    assert not (export_root / "Zander Lowfi Drums" / "Bank_B").exists()


def test_export_sequential_naming_matches_pad_order(source_dir, config, tmp_path):
    scan_index = _scan_index(source_dir, config)
    kits = assemble_kits(scan_index, config)
    zander = next(k for k in kits if k.name == "Zander Lowfi Drums")
    expected = [
        f"{p.pad:02d}_{p.display_name.replace(' ', '_').replace('/', '_')}{p.path[p.path.rindex('.'):].lower()}"
        for p in zander.banks[0]
    ]

    approved = {k.name: (k.name == "Zander Lowfi Drums") for k in kits}
    export_root = tmp_path / "export"
    export_kits(kits, approved, export_root, dry_run=False)

    exported = sorted(p.name for p in (export_root / "Zander Lowfi Drums" / "Bank_A").glob("*"))
    assert exported == sorted(expected)


def test_multi_kit_pack_exports_each_labeled_kit_separately(source_dir, config, tmp_path):
    scan_index = _scan_index(source_dir, config)
    kits = assemble_kits(scan_index, config)
    approved = {k.name: k.name.startswith("Drum Bundle") for k in kits}

    export_root = tmp_path / "export"
    export_kits(kits, approved, export_root, dry_run=False)

    assert (export_root / "Drum Bundle — Sugar" / "Bank_A").is_dir()
    assert (export_root / "Drum Bundle — Spice" / "Bank_A").is_dir()
    assert (export_root / "Drum Bundle" / "Bank_A").is_dir()  # leftover pool


def test_export_converts_flagged_files(source_dir, config, tmp_path):
    scan_index = _scan_index(source_dir, config)
    kits = assemble_kits(scan_index, config)
    approved = {k.name: (k.name == "Format Test Pack") for k in kits}

    export_root = tmp_path / "export"
    rows, _ = export_kits(kits, approved, export_root, dry_run=False)

    float32_row = next(r for r in rows if "float32" in r.source_path)
    assert float32_row.converted is True
    info = sf.info(float32_row.exported_path)
    assert info.subtype == "PCM_16"
    assert info.samplerate == 44100

    oddrate_row = next(r for r in rows if "oddrate" in r.source_path)
    assert oddrate_row.converted is True
    info2 = sf.info(oddrate_row.exported_path)
    assert info2.samplerate == 44100

    ok24_row = next(r for r in rows if "ok24" in r.source_path)
    assert ok24_row.converted is False


def test_export_never_touches_source_files(source_dir, config, tmp_path):
    scan_index = _scan_index(source_dir, config)
    kits = assemble_kits(scan_index, config)
    approved = {k.name: True for k in kits}

    before = {p: p.stat().st_mtime for p in source_dir.rglob("*.wav")}
    export_kits(kits, approved, tmp_path / "export", dry_run=False)
    after = {p: p.stat().st_mtime for p in source_dir.rglob("*.wav")}
    assert before == after


def test_dry_run_writes_nothing(source_dir, config, tmp_path):
    scan_index = _scan_index(source_dir, config)
    kits = assemble_kits(scan_index, config)
    approved = {k.name: True for k in kits}

    export_root = tmp_path / "export"
    rows, _ = export_kits(kits, approved, export_root, dry_run=True)
    assert len(rows) > 0
    assert not export_root.exists()


def test_manifest_csv(source_dir, config, tmp_path):
    scan_index = _scan_index(source_dir, config)
    kits = assemble_kits(scan_index, config)
    approved = {k.name: True for k in kits}

    export_root = tmp_path / "export"
    rows, _ = export_kits(kits, approved, export_root, dry_run=False)
    manifest_path = write_manifest(rows, export_root)

    with open(manifest_path, newline="", encoding="utf-8") as f:
        csv_rows = list(csv.DictReader(f))
    assert len(csv_rows) == len(rows)
    assert set(csv_rows[0].keys()) == {"kit", "bank", "pad", "category", "source_path", "exported_path", "converted"}
