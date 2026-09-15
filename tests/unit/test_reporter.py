from kitbuilder.assembler import assemble_kits
from kitbuilder.reporter import build_html, build_markdown, parse_approved_kits, rank_complete_kits, write_report
from kitbuilder.scanner import scan_source


def _scan_index(source_dir, config):
    records = scan_source(source_dir, config)
    return {"source": str(source_dir), "file_count": len(records), "files": [r.__dict__ for r in records]}


def _no_auto_approve(config):
    return {**config, "auto_approve_top_n": 0}


def test_markdown_has_checkbox_heading_per_kit(source_dir, config):
    scan_index = _scan_index(source_dir, config)
    kits = assemble_kits(scan_index, config)
    markdown_text = build_markdown(kits, scan_index, _no_auto_approve(config))
    assert "## [ ] Zander Lowfi Drums" in markdown_text
    assert "## [ ] Drum Bundle — Sugar" in markdown_text


def test_incomplete_kits_are_not_proposed(source_dir, config):
    scan_index = _scan_index(source_dir, config)
    kits = assemble_kits(scan_index, config)
    markdown_text = build_markdown(kits, scan_index, _no_auto_approve(config))
    # Tiny Pack has no Hat -> incomplete -> no checkbox heading, listed as skipped instead
    assert "## [ ] Tiny Pack" not in markdown_text
    assert "## [x] Tiny Pack" not in markdown_text
    assert "**Tiny Pack** — missing Hat Closed or Hat Open" in markdown_text
    assert "Skipped (incomplete" in markdown_text


def test_markdown_notes_free_melodic_pads(source_dir, config):
    scan_index = _scan_index(source_dir, config)
    kits = assemble_kits(scan_index, config)
    markdown_text = build_markdown(kits, scan_index, _no_auto_approve(config))
    assert "left free for your own melodic samples" in markdown_text


def test_html_is_derived_from_markdown_and_has_tables(source_dir, config):
    scan_index = _scan_index(source_dir, config)
    kits = assemble_kits(scan_index, config)
    markdown_text = build_markdown(kits, scan_index, _no_auto_approve(config))
    html_text = build_html(markdown_text)
    assert "<table>" in html_text
    assert "Zander Lowfi Drums" in html_text


def test_write_report_and_parse_checkboxes_roundtrip(source_dir, config, tmp_path):
    scan_index = _scan_index(source_dir, config)
    kits = assemble_kits(scan_index, config)
    md_path, html_path = write_report(kits, scan_index, tmp_path, _no_auto_approve(config))
    assert md_path.exists() and html_path.exists()

    approved = parse_approved_kits(md_path)
    assert "Tiny Pack" not in approved  # incomplete kits get no checkbox at all
    assert "Drum Bundle — Sugar" in approved
    assert all(v is False for v in approved.values())  # nothing auto-approved with top_n=0

    # simulate the user ticking one kit
    text = md_path.read_text(encoding="utf-8")
    text = text.replace("## [ ] Zander Lowfi Drums", "## [x] Zander Lowfi Drums")
    md_path.write_text(text, encoding="utf-8")

    approved_after = parse_approved_kits(md_path)
    assert approved_after["Zander Lowfi Drums"] is True
    assert approved_after["Drum Bundle — Sugar"] is False


def test_rank_complete_kits_best_first(source_dir, config):
    scan_index = _scan_index(source_dir, config)
    kits = assemble_kits(scan_index, config)
    ranked = rank_complete_kits(kits)
    assert all(not k.weak for k in ranked)  # incomplete kits never ranked
    # Zander Lowfi Drums is the fullest (14 pads, melodic content used) -> ranked first
    assert ranked[0].name == "Zander Lowfi Drums"


def test_auto_approve_top_n_checks_best_kits_and_leaves_rest_unchecked(source_dir, config):
    scan_index = _scan_index(source_dir, config)
    kits = assemble_kits(scan_index, config)
    ranked_names = [k.name for k in rank_complete_kits(kits)]

    small_n_config = {**config, "auto_approve_top_n": 2}
    markdown_text = build_markdown(kits, scan_index, small_n_config)
    approved = {
        name: markdown_text.count(f"## [x] {name}") == 1
        for name in ranked_names
    }
    assert [name for name, checked in approved.items() if checked] == ranked_names[:2]
    assert all(not checked for name, checked in approved.items() if name not in ranked_names[:2])


def test_auto_approve_top_n_zero_checks_nothing(source_dir, config):
    scan_index = _scan_index(source_dir, config)
    kits = assemble_kits(scan_index, config)
    markdown_text = build_markdown(kits, scan_index, _no_auto_approve(config))
    assert "## [x]" not in markdown_text


def test_auto_approve_default_checks_all_when_fewer_than_ten_complete_kits(source_dir, config):
    scan_index = _scan_index(source_dir, config)
    kits = assemble_kits(scan_index, config)
    ranked = rank_complete_kits(kits)
    assert len(ranked) < config["auto_approve_top_n"]  # fixtures have fewer than 10 complete kits

    markdown_text = build_markdown(kits, scan_index, config)
    for kit in ranked:
        assert f"## [x] {kit.name}" in markdown_text
