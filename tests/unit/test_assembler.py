from kitbuilder.assembler import assemble_kits
from kitbuilder.scanner import scan_source


def _kits(source_dir, config):
    records = scan_source(source_dir, config)
    scan_index = {"source": str(source_dir), "file_count": len(records), "files": [r.__dict__ for r in records]}
    return {k.name: k for k in assemble_kits(scan_index, config)}


def test_one_kit_per_pack_when_no_naming_signal(source_dir, config):
    kits = _kits(source_dir, config)
    assert "Zander Lowfi Drums" in kits
    assert "Tiny Pack" in kits
    assert "Big Pack" in kits


def test_incomplete_kit_missing_hat(source_dir, config):
    kits = _kits(source_dir, config)
    tiny = kits["Tiny Pack"]
    assert tiny.weak is True
    assert tiny.missing_basics == ["Hat Closed or Hat Open"]


def test_complete_kit_not_flagged(source_dir, config):
    kits = _kits(source_dir, config)
    assert kits["Zander Lowfi Drums"].weak is False
    assert kits["Zander Lowfi Drums"].missing_basics == []


def test_basics_placed_first(source_dir, config):
    kits = _kits(source_dir, config)
    pads = kits["Zander Lowfi Drums"].banks[0]
    assert [p.display_name for p in pads[:3]] == ["Kick", "Snare", "Hat Closed"]


def test_max_two_variations_per_category(source_dir, config):
    kits = _kits(source_dir, config)
    big = kits["Big Pack"]  # 20 kicks, 10 snares, 5 claps, no hat -> missing hat
    pads = big.banks[0]
    kick_pads = [p.display_name for p in pads if p.category == "Kick"]
    assert kick_pads == ["Kick", "Kick 2"]
    assert big.weak is True
    assert big.missing_basics == ["Hat Closed or Hat Open"]

    kick_alternates = [f.display_name for f in big.alternates["Kick"]]
    assert kick_alternates == [f"Kick {i}" for i in range(3, 21)]


def test_kit_never_spans_more_than_one_bank(source_dir, config):
    kits = _kits(source_dir, config)
    for kit in kits.values():
        assert len(kit.banks) <= 1


def test_melodic_pads_reserved_and_used(source_dir, config):
    kits = _kits(source_dir, config)
    zander = kits["Zander Lowfi Drums"]
    assert zander.melodic_pads_reserved == 4
    assert zander.melodic_pads_used == 4  # Bass, FX, Vocal, Loop all present
    melodic_pads = zander.banks[0][-4:]
    assert {p.category for p in melodic_pads} == {"Bass", "FX", "Vocal", "Loop"}


def test_melodic_pads_left_free_when_absent(source_dir, config):
    kits = _kits(source_dir, config)
    tiny = kits["Tiny Pack"]
    assert tiny.melodic_pads_used == 0
    assert tiny.total_pads_used == 2  # Kick + Snare only, no melodic backfill


def test_unclassified_not_assigned_a_pad(source_dir, config):
    kits = _kits(source_dir, config)
    kit = kits["Zander Lowfi Drums"]
    pad_filenames = {p.filename for bank in kit.banks for p in bank}
    assert "weird_sound.wav" not in pad_filenames
    assert any(f.filename == "weird_sound.wav" for f in kit.unclassified)


def test_excluded_midi_file_never_reaches_assembler(source_dir, config):
    kits = _kits(source_dir, config)
    kit = kits["Zander Lowfi Drums"]
    all_names = {p.filename for bank in kit.banks for p in bank} | {f.filename for f in kit.unclassified}
    assert "should_be_excluded_kick.wav" not in all_names


def test_filename_kit_name_inference_splits_multi_kit_pack(source_dir, config):
    kits = _kits(source_dir, config)
    assert "Drum Bundle — Sugar" in kits
    assert "Drum Bundle — Spice" in kits
    assert "Drum Bundle" in kits  # leftover pool for the unlabeled file

    sugar = kits["Drum Bundle — Sugar"]
    assert sugar.weak is False
    filenames = {p.filename for bank in sugar.banks for p in bank}
    assert filenames == {"BB3_kick_sugar.wav", "BB3_snare_sugar.wav", "BB3_hat_closed_sugar.wav", "BB3_clap_sugar.wav"}

    leftover = kits["Drum Bundle"]
    assert {p.filename for bank in leftover.banks for p in bank} == {"random_fx_noise.wav"}


def test_filename_kit_name_inference_renames_single_kit(source_dir, config):
    kits = _kits(source_dir, config)
    assert "Random Folder Name — Glimmer" in kits
    assert "Random Folder Name" not in kits


def test_filename_inference_disabled_falls_back_to_pack_name(source_dir, config):
    config = dict(config)
    config["infer_kit_name_from_filename"] = False
    kits = _kits(source_dir, config)
    assert "Drum Bundle" in kits
    assert "Drum Bundle — Sugar" not in kits
    assert kits["Drum Bundle"].total_classified == 9
