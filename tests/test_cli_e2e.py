import subprocess
import sys

from kitbuilder.reporter import KITS_MD_FILENAME


def run_cli(*args):
    result = subprocess.run(
        [sys.executable, "-m", "kitbuilder", *args],
        capture_output=True,
        text=True,
    )
    return result


def _disable_auto_approve(out_dir):
    """scan writes a categories.yaml copy into out_dir; report reads it by
    default. Zero out auto_approve_top_n so tests can control checkboxes
    by hand without the top-N pre-check interfering."""
    config_path = out_dir / "categories.yaml"
    text = config_path.read_text(encoding="utf-8")
    config_path.write_text(text.replace("auto_approve_top_n: 10", "auto_approve_top_n: 0"), encoding="utf-8")


def test_full_pipeline_scan_report_export(source_dir, tmp_path):
    out_dir = tmp_path / "kitbuilder_out"
    export_dir = tmp_path / "SP404_Export"

    scan = run_cli("scan", "--source", str(source_dir), "--out", str(out_dir))
    assert scan.returncode == 0, scan.stderr
    assert (out_dir / "scan_index.json").exists()
    assert (out_dir / "categories.yaml").exists()
    _disable_auto_approve(out_dir)

    report = run_cli("report", "--in", str(out_dir))
    assert report.returncode == 0, report.stderr
    kits_md = out_dir / KITS_MD_FILENAME
    assert kits_md.exists()
    assert (out_dir / "kits.html").exists()

    # approve exactly one (complete) kit — Tiny Pack is incomplete (no Hat)
    # and so isn't even proposed in kits.md
    text = kits_md.read_text(encoding="utf-8")
    text = text.replace("## [ ] Zander Lowfi Drums", "## [x] Zander Lowfi Drums")
    kits_md.write_text(text, encoding="utf-8")

    export = run_cli("export", "--in", str(out_dir), "--out", str(export_dir))
    assert export.returncode == 0, export.stderr
    assert (export_dir / "Zander Lowfi Drums" / "Bank_A" / "01_Kick.wav").exists()
    assert (export_dir / "export_manifest.csv").exists()
    assert not (export_dir / "Tiny Pack").exists()
    assert not (export_dir / "Format Test Pack").exists()  # only the manually-ticked kit exports


def test_auto_approve_exports_best_kits_with_no_manual_edits(source_dir, tmp_path):
    out_dir = tmp_path / "kitbuilder_out"
    export_dir = tmp_path / "SP404_Export"

    run_cli("scan", "--source", str(source_dir), "--out", str(out_dir))
    report = run_cli("report", "--in", str(out_dir))
    assert "auto-approved" in report.stdout.lower()

    # no manual edits to kits.md at all — export should still do something,
    # because the best kits were pre-checked by `report`
    export = run_cli("export", "--in", str(out_dir), "--out", str(export_dir))
    assert export.returncode == 0, export.stderr
    assert (export_dir / "Zander Lowfi Drums" / "Bank_A" / "01_Kick.wav").exists()


def test_dry_run_flags_write_nothing(source_dir, tmp_path):
    out_dir = tmp_path / "kitbuilder_out"

    scan = run_cli("scan", "--source", str(source_dir), "--out", str(out_dir), "--dry-run")
    assert scan.returncode == 0, scan.stderr
    assert not out_dir.exists()

    # need a real scan to proceed to report/export dry-run checks
    run_cli("scan", "--source", str(source_dir), "--out", str(out_dir))
    _disable_auto_approve(out_dir)
    report_dry = run_cli("report", "--in", str(out_dir), "--dry-run")
    assert report_dry.returncode == 0, report_dry.stderr
    assert not (out_dir / KITS_MD_FILENAME).exists()

    run_cli("report", "--in", str(out_dir))
    text = (out_dir / KITS_MD_FILENAME).read_text(encoding="utf-8")
    text = text.replace("## [ ] Zander Lowfi Drums", "## [x] Zander Lowfi Drums")
    (out_dir / KITS_MD_FILENAME).write_text(text, encoding="utf-8")

    export_dir = tmp_path / "SP404_Export"
    export_dry = run_cli("export", "--in", str(out_dir), "--out", str(export_dir), "--dry-run")
    assert export_dry.returncode == 0, export_dry.stderr
    assert not export_dir.exists()


def test_kits_per_project_flag_groups_into_project_folders(source_dir, tmp_path):
    out_dir = tmp_path / "kitbuilder_out"
    export_dir = tmp_path / "SP404_Export"

    run_cli("scan", "--source", str(source_dir), "--out", str(out_dir))
    run_cli("report", "--in", str(out_dir))  # default auto-approve checks all 5 complete kits

    export = run_cli("export", "--in", str(out_dir), "--out", str(export_dir), "--kits-per-project", "2")
    assert export.returncode == 0, export.stderr
    assert "Grouped into 3 project(s) of up to 2 kit(s) each" in export.stdout

    assert (export_dir / "Project_1" / "Bank_01_Zander Lowfi Drums" / "01_Kick.wav").exists()
    assert not (export_dir / "Project_1" / "Bank_01_Zander Lowfi Drums" / "Bank_A").exists()
    assert (export_dir / "Project_3").is_dir()  # 5 kits / 2 per project -> 3 projects
    assert not (export_dir / "Zander Lowfi Drums").exists()  # no flat layout when grouping


def test_no_kits_checked_is_a_noop(source_dir, tmp_path):
    out_dir = tmp_path / "kitbuilder_out"
    export_dir = tmp_path / "SP404_Export"
    run_cli("scan", "--source", str(source_dir), "--out", str(out_dir))
    _disable_auto_approve(out_dir)
    run_cli("report", "--in", str(out_dir))

    export = run_cli("export", "--in", str(out_dir), "--out", str(export_dir))
    assert export.returncode == 0, export.stderr
    assert "nothing to export" in export.stdout.lower()
    assert not export_dir.exists()
