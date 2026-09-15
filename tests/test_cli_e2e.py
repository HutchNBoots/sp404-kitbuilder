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


def test_full_pipeline_scan_report_export(source_dir, tmp_path):
    out_dir = tmp_path / "kitbuilder_out"
    export_dir = tmp_path / "SP404_Export"

    scan = run_cli("scan", "--source", str(source_dir), "--out", str(out_dir))
    assert scan.returncode == 0, scan.stderr
    assert (out_dir / "scan_index.json").exists()
    assert (out_dir / "categories.yaml").exists()

    report = run_cli("report", "--in", str(out_dir))
    assert report.returncode == 0, report.stderr
    kits_md = out_dir / KITS_MD_FILENAME
    assert kits_md.exists()
    assert (out_dir / "kits.html").exists()

    # approve exactly one kit
    text = kits_md.read_text(encoding="utf-8")
    text = text.replace("## [ ] Tiny Pack", "## [x] Tiny Pack")
    kits_md.write_text(text, encoding="utf-8")

    export = run_cli("export", "--in", str(out_dir), "--out", str(export_dir))
    assert export.returncode == 0, export.stderr
    assert (export_dir / "Tiny Pack" / "Bank_A" / "01_Kick.wav").exists()
    assert (export_dir / "export_manifest.csv").exists()
    assert not (export_dir / "Zander Lowfi Drums").exists()


def test_dry_run_flags_write_nothing(source_dir, tmp_path):
    out_dir = tmp_path / "kitbuilder_out"

    scan = run_cli("scan", "--source", str(source_dir), "--out", str(out_dir), "--dry-run")
    assert scan.returncode == 0, scan.stderr
    assert not out_dir.exists()

    # need a real scan to proceed to report/export dry-run checks
    run_cli("scan", "--source", str(source_dir), "--out", str(out_dir))
    report_dry = run_cli("report", "--in", str(out_dir), "--dry-run")
    assert report_dry.returncode == 0, report_dry.stderr
    assert not (out_dir / KITS_MD_FILENAME).exists()

    run_cli("report", "--in", str(out_dir))
    text = (out_dir / KITS_MD_FILENAME).read_text(encoding="utf-8")
    text = text.replace("## [ ] Tiny Pack", "## [x] Tiny Pack")
    (out_dir / KITS_MD_FILENAME).write_text(text, encoding="utf-8")

    export_dir = tmp_path / "SP404_Export"
    export_dry = run_cli("export", "--in", str(out_dir), "--out", str(export_dir), "--dry-run")
    assert export_dry.returncode == 0, export_dry.stderr
    assert not export_dir.exists()


def test_no_kits_checked_is_a_noop(source_dir, tmp_path):
    out_dir = tmp_path / "kitbuilder_out"
    export_dir = tmp_path / "SP404_Export"
    run_cli("scan", "--source", str(source_dir), "--out", str(out_dir))
    run_cli("report", "--in", str(out_dir))

    export = run_cli("export", "--in", str(out_dir), "--out", str(export_dir))
    assert export.returncode == 0, export.stderr
    assert "nothing to export" in export.stdout.lower()
    assert not export_dir.exists()
