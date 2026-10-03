import csv
import gzip
import shutil
import xml.etree.ElementTree as ET

import pytest
import soundfile as sf

from ableton_fixture import TEMPLATE_XML, write_template
from kitbuilder.assembler import assemble_kits
from kitbuilder.exporter import export_kits, write_manifest
from kitbuilder.scanner import scan_source
from rackbuilder.adg import read_adg, write_adg
from rackbuilder.builder import (
    build_all,
    read_export_manifest,
    resolve_sample,
    safe_folder_name,
    write_build_manifest,
)
from rackbuilder.rack import PadSpec, TemplateError, build_rack, read_pads


def _export(source_dir, config, tmp_path, names, **kwargs):
    records = scan_source(source_dir, config)
    scan_index = {"source": str(source_dir), "file_count": len(records), "files": [r.__dict__ for r in records]}
    kits = assemble_kits(scan_index, config)
    approved = {k.name: k.name in names for k in kits}
    export_root = tmp_path / "sp404_kits"
    rows, _ = export_kits(kits, approved, export_root, **kwargs)
    return write_manifest(rows, export_root)


def _pad(i):
    return PadSpec(
        name=f"Pad {i}", midi_note=36 + i, relative_path=f"Samples/Imported/K/{i:02d}.wav",
        absolute_path=f"/x/{i:02d}.wav", file_size=100 + i, frames=5000 + i, sample_rate=44100,
    )


# --- step 1: gzip+XML round trip -------------------------------------------

def test_adg_round_trip_preserves_xml(adg_template, tmp_path):
    out = write_adg(read_adg(adg_template), tmp_path / "copy.adg")
    raw = out.read_bytes()
    assert raw[:2] == b"\x1f\x8b"  # still gzipped
    assert gzip.decompress(raw).decode("utf-8") == TEMPLATE_XML.rstrip("\n")


def test_write_adg_is_deterministic(adg_template, tmp_path):
    tree = read_adg(adg_template)
    assert write_adg(tree, tmp_path / "a.adg").read_bytes() == write_adg(tree, tmp_path / "b.adg").read_bytes()


def test_read_adg_accepts_plain_xml(tmp_path):
    path = tmp_path / "plain.adg"
    path.write_text(TEMPLATE_XML, encoding="utf-8")
    assert read_adg(path).getroot().tag == "Ableton"


# --- step 2: chain cloning --------------------------------------------------

def test_build_rack_clones_one_chain_per_pad(adg_template):
    template = read_adg(adg_template)
    before = ET.tostring(template.getroot())
    tree = build_rack(template, [_pad(i) for i in range(16)])

    assert ET.tostring(template.getroot()) == before  # template untouched
    branches = tree.getroot().findall(".//BranchPresets/DrumBranchPreset")
    assert [b.get("Id") for b in branches] == [str(i) for i in range(16)]

    pads = read_pads(tree)
    assert [p["name"] for p in pads] == [f"Pad {i}" for i in range(16)]
    assert [p["midi_note"] for p in pads] == list(range(36, 52))
    assert pads[0]["relative_path"] == "Samples/Imported/K/00.wav"
    # pad 1 on C1 is stored as ReceivingNote 92
    assert branches[0].find("ZoneSettings/ReceivingNote").get("Value") == "92"
    # Live-style indentation is kept for every cloned chain
    xml = ET.tostring(tree.getroot(), encoding="unicode")
    assert xml.count('\n\t\t\t<DrumBranchPreset Id=') == 16
    # the rest of the rack survives
    assert tree.getroot().find("GroupDevicePreset/Device/DrumGroupDevice") is not None


def test_build_rack_rewrites_sample_reference(adg_template):
    tree = build_rack(read_adg(adg_template), [_pad(3)], relative_path_type=3)
    part = tree.getroot().find(".//MultiSamplePart")
    file_ref = part.find("SampleRef/FileRef")
    value = lambda el, tag: el.find(tag).get("Value")
    assert value(file_ref, "RelativePathType") == "3"
    assert value(file_ref, "RelativePath") == "Samples/Imported/K/03.wav"
    assert value(file_ref, "Path") == "/x/03.wav"
    assert value(file_ref, "LivePackName") == ""
    assert value(file_ref, "OriginalFileSize") == "103"
    assert value(file_ref, "OriginalCrc") == "0"
    assert value(part, "Name") == "Pad 3"
    assert value(part, "SampleStart") == "0"
    assert value(part, "SampleEnd") == "5003"
    assert value(part, "SustainLoop/End") == "5003"
    assert value(part, "SampleRef/DefaultDuration") == "5003"
    assert value(part, "SampleRef/DefaultSampleRate") == "44100"


def test_template_without_sample_is_rejected(tmp_path):
    xml = TEMPLATE_XML.replace("<MultiSamplePart Id=\"0\">", "<Other>").replace("</MultiSamplePart>", "</Other>")
    template = read_adg(write_template(tmp_path / "t.adg", xml))
    with pytest.raises(TemplateError, match="exactly one sample"):
        build_rack(template, [_pad(0)])


def test_template_with_two_chains_is_rejected(adg_template):
    tree = read_adg(adg_template)
    container = tree.getroot().find(".//BranchPresets")
    container.append(container[0].__copy__())
    with pytest.raises(TemplateError, match="exactly one Drum Rack chain"):
        build_rack(tree, [_pad(0)])


def test_live_set_style_branch_names_are_set(tmp_path):
    xml = TEMPLATE_XML.replace("BranchPresets", "Branches_").replace("<Branches />", "") \
        .replace("Branches_", "Branches").replace("DrumBranchPreset", "DrumBranch") \
        .replace('<Name Value="Template Pad" />', '<Name><EffectiveName Value="x" /><UserName Value="" /></Name>')
    tree = build_rack(read_adg(write_template(tmp_path / "t.adg", xml)), [_pad(0), _pad(1)])
    names = [b.find("Name/UserName").get("Value") for b in tree.getroot().iter("DrumBranch")]
    assert names == ["Pad 0", "Pad 1"]


# --- manifest -> racks ------------------------------------------------------

def test_build_all_from_kitbuilder_export(source_dir, config, adg_template, tmp_path):
    manifest = _export(source_dir, config, tmp_path, {"Tiny Pack", "Zander Lowfi Drums"})
    out = tmp_path / "ableton_racks"
    rows, warnings = build_all(manifest, adg_template, out, include=["Zander Lowfi Drums"])
    assert warnings == []

    kit_dir = out / "Zander Lowfi Drums"
    sample_dir = kit_dir / "Samples" / "Imported" / "Zander Lowfi Drums"
    tree = read_adg(kit_dir / "Zander Lowfi Drums.adg")
    pads = read_pads(tree)

    assert len(pads) == len(rows) == len(read_export_manifest(manifest)["Zander Lowfi Drums"])
    assert pads[0]["name"] == "Kick" and pads[0]["midi_note"] == 36  # kick on the base note
    assert [p["midi_note"] for p in pads] == list(range(36, 36 + len(pads)))
    for p in pads:
        # every reference is relative and points at a real file inside the kit folder
        assert not p["relative_path"].startswith("/")
        assert (kit_dir / p["relative_path"]).is_file()
    assert sorted(f.name for f in sample_dir.iterdir()) == sorted(r.relative_sample_path.split("/")[-1] for r in rows)
    assert not (out / "Tiny Pack").exists()

    frames = sf.info(str(kit_dir / pads[0]["relative_path"])).frames
    assert tree.getroot().find(".//MultiSamplePart/SampleEnd").get("Value") == str(frames)


def test_chain_names_keep_variation_numbers(source_dir, config, adg_template, tmp_path):
    manifest = _export(source_dir, config, tmp_path, {"Zander Lowfi Drums"})
    rows, _ = build_all(manifest, adg_template, tmp_path / "out")
    names = [r.chain_name for r in rows]
    assert "Kick" in names and "Kick 2" in names


def test_build_all_handles_project_layout_after_moving(source_dir, config, adg_template, tmp_path):
    manifest = _export(source_dir, config, tmp_path, {"Tiny Pack", "Zander Lowfi Drums"}, kits_per_project=10)
    moved = tmp_path / "moved_kits"
    shutil.move(str(manifest.parent), moved)
    rows, warnings = build_all(moved / manifest.name, adg_template, tmp_path / "out", exclude=["Tiny Pack"])
    assert warnings == []
    assert {r.kit for r in rows} == {"Zander Lowfi Drums"}


def test_missing_samples_and_unknown_kits_warn(source_dir, config, adg_template, tmp_path):
    manifest = _export(source_dir, config, tmp_path, {"Tiny Pack"})
    shutil.rmtree(manifest.parent / "Tiny Pack")
    rows, warnings = build_all(manifest, adg_template, tmp_path / "out", include=["Tiny Pack", "Nope"])
    assert rows == []
    assert any("'Nope' isn't a kit" in w for w in warnings)
    assert any("no samples found" in w for w in warnings)


def test_dry_run_writes_nothing(source_dir, config, adg_template, tmp_path):
    manifest = _export(source_dir, config, tmp_path, {"Tiny Pack"})
    rows, _ = build_all(manifest, adg_template, tmp_path / "out", dry_run=True)
    assert rows and not (tmp_path / "out").exists()


def test_write_build_manifest(source_dir, config, adg_template, tmp_path):
    manifest = _export(source_dir, config, tmp_path, {"Tiny Pack"})
    rows, _ = build_all(manifest, adg_template, tmp_path / "out")
    path = write_build_manifest(rows, tmp_path / "out")
    with open(path, newline="", encoding="utf-8") as f:
        written = list(csv.DictReader(f))
    assert list(written[0]) == ["kit", "pad", "category", "chain_name", "relative_sample_path", "midi_note"]
    assert written[0]["midi_note"] == "36"


def test_resolve_sample_from_windows_path(tmp_path):
    wav = tmp_path / "kits" / "My Kit" / "Bank_A" / "01_Kick.wav"
    wav.parent.mkdir(parents=True)
    wav.write_bytes(b"x")
    found = resolve_sample(r"C:\Users\me\sp404_kits\My Kit\Bank_A\01_Kick.wav", [tmp_path / "kits"])
    assert found == wav


def test_safe_folder_name():
    assert safe_folder_name('Drum Bundle — Sugar') == "Drum Bundle — Sugar"
    assert safe_folder_name('A/B:C?') == "A_B_C_"
