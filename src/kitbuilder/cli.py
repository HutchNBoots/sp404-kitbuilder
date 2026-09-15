"""kitbuilder CLI: scan / report / export subcommands."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from typing import Any

from kitbuilder import config as config_mod
from kitbuilder.assembler import assemble_kits
from kitbuilder.exporter import export_kits, load_approved_and_kits, write_manifest
from kitbuilder.reporter import rank_complete_kits, write_report
from kitbuilder.scanner import load_scan_index, scan_source, write_scan_index


def _resolve_config(explicit: str | None, in_dir: str | Path | None) -> dict[str, Any]:
    if explicit:
        return config_mod.load_config(explicit)
    if in_dir is not None:
        default_copy = Path(in_dir) / config_mod.DEFAULT_CONFIG_FILENAME
        if default_copy.exists():
            return config_mod.load_config(default_copy)
    return config_mod.load_config(None)


def cmd_scan(args: argparse.Namespace) -> int:
    config = config_mod.load_config(args.config)
    records = scan_source(args.source, config)

    categories_seen: dict[str, int] = {}
    for r in records:
        categories_seen[r.category] = categories_seen.get(r.category, 0) + 1
    packs = sorted({r.pack for r in records})
    needs_conversion = sum(1 for r in records if r.needs_conversion)

    print(f"Scanned {len(records)} audio files across {len(packs)} pack(s).")
    for category, count in sorted(categories_seen.items(), key=lambda kv: -kv[1]):
        print(f"  {category}: {count}")
    print(f"Files needing format conversion: {needs_conversion}")

    if args.dry_run:
        print("[dry-run] scan_index.json not written.")
        return 0

    index_path = write_scan_index(records, args.out, args.source)
    config_copy = Path(args.out) / config_mod.DEFAULT_CONFIG_FILENAME
    source_config = Path(args.config) if args.config else config_mod.packaged_default_config_path()
    shutil.copyfile(source_config, config_copy)
    print(f"Wrote {index_path}")
    print(f"Wrote {config_copy} (edit this and re-run `report` to retune classification)")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    scan_index = load_scan_index(args.in_dir)
    config = _resolve_config(args.config, args.in_dir)
    kits = assemble_kits(scan_index, config)

    incomplete = sum(1 for k in kits if k.weak)
    ranked = rank_complete_kits(kits)
    auto_approved_count = min(config["auto_approve_top_n"], len(ranked))
    auto_approved_names = {k.name for k in ranked[:auto_approved_count]}

    print(f"Assembled {len(kits)} candidate kit(s) from {scan_index['file_count']} scanned files.")
    print(f"  Proposed in kits.md: {len(ranked)} (best {auto_approved_count} auto-approved)")
    print(f"  Skipped — incomplete, missing Kick/Snare/Hat: {incomplete}")
    for k in ranked:
        print(f"  - {k.name}: {k.total_pads_used} pads{' [AUTO-APPROVED]' if k.name in auto_approved_names else ''}")
    for k in kits:
        if k.weak:
            print(f"  - {k.name}: {k.total_pads_used} pads [SKIPPED: missing {', '.join(k.missing_basics)}]")

    if args.dry_run:
        print("[dry-run] kits.md / kits.html not written.")
        return 0

    md_path, html_path = write_report(kits, scan_index, args.in_dir, config)
    print(f"Wrote {md_path}")
    print(f"Wrote {html_path}")
    print(f"The best {auto_approved_count} kits are already checked — run `kitbuilder export` to use them as-is,")
    print("or edit kits.md to check/uncheck kits first, then run `kitbuilder export`.")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    scan_index = load_scan_index(args.in_dir)
    config = _resolve_config(args.config, args.in_dir)
    kits, approved = load_approved_and_kits(args.in_dir, scan_index, config)

    approved_names = [name for name, checked in approved.items() if checked]
    if not approved_names:
        print("No kits are checked in kits.md — nothing to export. Tick `[x]` on the kits you want first.")
        return 0

    rows, warnings = export_kits(kits, approved, args.out, dry_run=args.dry_run)
    for w in warnings:
        print(f"⚠ {w}", file=sys.stderr)

    verb = "Would export" if args.dry_run else "Exported"
    print(f"{verb} {len(rows)} file(s) across {len(approved_names)} approved kit(s) to {args.out}")
    if args.dry_run:
        for row in rows:
            print(f"  [dry-run] {row.source_path} -> {row.exported_path}"
                  f"{' (convert)' if row.converted else ''}")
        print("[dry-run] export_manifest.csv not written.")
        return 0

    manifest_path = write_manifest(rows, args.out)
    print(f"Wrote {manifest_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kitbuilder",
        description="Scan a Splice sample library and build SP-404 MKII kits.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_p = subparsers.add_parser("scan", help="Phase 1: scan --source and write scan_index.json")
    scan_p.add_argument("--source", required=True, help="Root folder of Splice packs")
    scan_p.add_argument("--out", required=True, help="Working output folder")
    scan_p.add_argument("--config", help="Path to a categories.yaml override")
    scan_p.add_argument("--dry-run", action="store_true", help="Print a summary; write nothing")
    scan_p.set_defaults(func=cmd_scan)

    report_p = subparsers.add_parser("report", help="Phase 2+3: assemble kits and write kits.md/kits.html")
    report_p.add_argument("--in", dest="in_dir", required=True, help="Working folder from `scan`")
    report_p.add_argument("--config", help="Path to a categories.yaml override (defaults to <in>/categories.yaml)")
    report_p.add_argument("--dry-run", action="store_true", help="Print a summary; write nothing")
    report_p.set_defaults(func=cmd_report)

    export_p = subparsers.add_parser("export", help="Phase 4: copy approved kits to --out")
    export_p.add_argument("--in", dest="in_dir", required=True, help="Working folder containing kits.md")
    export_p.add_argument("--out", required=True, help="Export destination root")
    export_p.add_argument("--config", help="Path to a categories.yaml override (defaults to <in>/categories.yaml)")
    export_p.add_argument("--dry-run", action="store_true", help="Print what would be copied; write nothing")
    export_p.set_defaults(func=cmd_export)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
