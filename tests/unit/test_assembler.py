from kitbuilder.assembler import assemble_kits
from kitbuilder.scanner import scan_source


def _kits(source_dir, config):
    records = scan_source(source_dir, config)
    scan_index = {"source": str(source_dir), "file_count": len(records), "files": [r.__dict__ for r in records]}
    return {k.name: k for k in assemble_kits(scan_index, config)}


def test_one_kit_per_top_level_pack(source_dir, config):
    kits = _kits(source_dir, config)
    assert set(kits.keys()) == {"Zander Lowfi Drums", "Tiny Pack", "Big Pack", "Format Test Pack"}


def test_weak_kit_flagged_below_threshold(source_dir, config):
    kits = _kits(source_dir, config)
    assert kits["Tiny Pack"].weak is True
    assert kits["Tiny Pack"].distinct_category_count == 2


def test_rich_pack_not_weak(source_dir, config):
    kits = _kits(source_dir, config)
    assert kits["Zander Lowfi Drums"].weak is False


def test_duplicate_categories_are_not_collapsed(source_dir, config):
    kits = _kits(source_dir, config)
    pads = [p for bank in kits["Zander Lowfi Drums"].banks for p in bank]
    kick_names = sorted(p.display_name for p in pads if p.category == "Kick")
    # kick_01, kick_02, kick_03 (subfolder) all present, individually numbered
    assert kick_names == ["Kick", "Kick 2", "Kick 3"]


def test_unclassified_not_assigned_a_pad(source_dir, config):
    kits = _kits(source_dir, config)
    kit = kits["Zander Lowfi Drums"]
    pad_filenames = {p.filename for bank in kit.banks for p in bank}
    assert "weird_sound.wav" not in pad_filenames
    assert any(f.filename == "weird_sound.wav" for f in kit.unclassified)


def test_bank_overflow_and_alternates(source_dir, config):
    kits = _kits(source_dir, config)
    big = kits["Big Pack"]
    assert big.total_classified == 35  # 20 kick + 10 snare + 5 clap
    assert len(big.banks) == 2
    assert big.total_pads_used == 32  # pads_per_bank(16) * banks_per_kit_max(2)
    assert len(big.banks[0]) == 16
    assert len(big.banks[1]) == 16
    assert big.weak is False  # 3 distinct categories

    alt_claps = big.alternates.get("Clap", [])
    assert len(alt_claps) == 3  # 5 claps total, only 2 fit


def test_pad_numbers_reset_per_bank(source_dir, config):
    kits = _kits(source_dir, config)
    big = kits["Big Pack"]
    assert [p.pad for p in big.banks[0]] == list(range(1, 17))
    assert [p.pad for p in big.banks[1]] == list(range(1, 17))


def test_excluded_midi_file_never_reaches_assembler(source_dir, config):
    kits = _kits(source_dir, config)
    kit = kits["Zander Lowfi Drums"]
    all_names = {p.filename for bank in kit.banks for p in bank} | {f.filename for f in kit.unclassified}
    assert "should_be_excluded_kick.wav" not in all_names
