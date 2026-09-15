from kitbuilder.assembler import assemble_kits
from kitbuilder.reporter import build_html, build_markdown, parse_approved_kits, write_report
from kitbuilder.scanner import scan_source


def _scan_index(source_dir, config):
    records = scan_source(source_dir, config)
    return {"source": str(source_dir), "file_count": len(records), "files": [r.__dict__ for r in records]}


def test_markdown_has_checkbox_heading_per_kit(source_dir, config):
    scan_index = _scan_index(source_dir, config)
    kits = assemble_kits(scan_index, config)
    markdown_text = build_markdown(kits, scan_index)
    assert "## [ ] Zander Lowfi Drums" in markdown_text
    assert "## [ ] Drum Bundle — Sugar" in markdown_text


def test_incomplete_kits_are_not_proposed(source_dir, config):
    scan_index = _scan_index(source_dir, config)
    kits = assemble_kits(scan_index, config)
    markdown_text = build_markdown(kits, scan_index)
    # Tiny Pack has no Hat -> incomplete -> no checkbox heading, listed as skipped instead
    assert "## [ ] Tiny Pack" not in markdown_text
    assert "## [x] Tiny Pack" not in markdown_text
    assert "**Tiny Pack** — missing Hat Closed or Hat Open" in markdown_text
    assert "Skipped (incomplete" in markdown_text


def test_markdown_notes_free_melodic_pads(source_dir, config):
    scan_index = _scan_index(source_dir, config)
    kits = assemble_kits(scan_index, config)
    markdown_text = build_markdown(kits, scan_index)
    assert "left free for your own melodic samples" in markdown_text


def test_html_is_derived_from_markdown_and_has_tables(source_dir, config):
    scan_index = _scan_index(source_dir, config)
    kits = assemble_kits(scan_index, config)
    markdown_text = build_markdown(kits, scan_index)
    html_text = build_html(markdown_text)
    assert "<table>" in html_text
    assert "Zander Lowfi Drums" in html_text


def test_write_report_and_parse_checkboxes_roundtrip(source_dir, config, tmp_path):
    scan_index = _scan_index(source_dir, config)
    kits = assemble_kits(scan_index, config)
    md_path, html_path = write_report(kits, scan_index, tmp_path)
    assert md_path.exists() and html_path.exists()

    approved = parse_approved_kits(md_path)
    assert "Tiny Pack" not in approved  # incomplete kits get no checkbox at all
    assert "Drum Bundle — Sugar" in approved
    assert all(v is False for v in approved.values())  # nothing ticked yet

    # simulate the user ticking one kit
    text = md_path.read_text(encoding="utf-8")
    text = text.replace("## [ ] Zander Lowfi Drums", "## [x] Zander Lowfi Drums")
    md_path.write_text(text, encoding="utf-8")

    approved_after = parse_approved_kits(md_path)
    assert approved_after["Zander Lowfi Drums"] is True
    assert approved_after["Drum Bundle — Sugar"] is False
