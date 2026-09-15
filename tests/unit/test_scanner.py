from kitbuilder.scanner import scan_source


def test_scan_finds_all_non_excluded_audio_files(source_dir, config):
    records = scan_source(source_dir, config)
    filenames = {r.filename for r in records}
    assert "kick_01.wav" in filenames
    assert "crash_01.aiff" in filenames
    # excluded MIDI subfolder must never appear
    assert "should_be_excluded_kick.wav" not in filenames


def test_subfolder_file_belongs_to_top_level_pack(source_dir, config):
    records = scan_source(source_dir, config)
    nested = next(r for r in records if r.path.replace("\\", "/").endswith("Kicks/kick_03.wav"))
    assert nested.pack == "Zander Lowfi Drums"


def test_pack_grouping(source_dir, config):
    records = scan_source(source_dir, config)
    packs = {r.pack for r in records}
    assert packs == {
        "Zander Lowfi Drums",
        "Tiny Pack",
        "Big Pack",
        "Format Test Pack",
        "Drum Bundle",
        "Random Folder Name",
    }


def test_classification_assigned_per_file(source_dir, config):
    records = scan_source(source_dir, config)
    by_name = {r.filename: r for r in records}
    assert by_name["kick_01.wav"].category == "Kick"
    assert by_name["snare_01.wav"].category == "Snare"
    assert by_name["weird_sound.wav"].category == "Other"


def test_ambiguous_classification_logged(source_dir, config):
    records = scan_source(source_dir, config)
    openhat = next(r for r in records if r.filename == "openhat_01.wav")
    assert openhat.category == "Hat Closed"
    assert "Hat Open" in openhat.ambiguous_categories


def test_format_flags(source_dir, config):
    records = scan_source(source_dir, config)
    by_name = {r.filename: r for r in records if r.pack == "Format Test Pack"}

    assert by_name["kick_float32.wav"].needs_conversion is True
    assert by_name["kick_float32.wav"].subtype == "FLOAT"

    assert by_name["snare_oddrate.wav"].needs_conversion is True
    assert by_name["snare_oddrate.wav"].sample_rate == 22050

    assert by_name["kick_ok24.wav"].needs_conversion is False
    assert by_name["kick_ok24.wav"].bit_depth == 24
    assert by_name["kick_ok24.wav"].sample_rate == 48000


def test_scan_index_roundtrip(source_dir, config, tmp_path):
    from kitbuilder.scanner import load_scan_index, write_scan_index

    records = scan_source(source_dir, config)
    write_scan_index(records, tmp_path, source_dir)
    index = load_scan_index(tmp_path)
    assert index["file_count"] == len(records)
    assert index["source"] == str(source_dir.resolve())
