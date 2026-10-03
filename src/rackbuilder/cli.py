"""rackbuilder CLI: `rackbuilder build ...`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rackbuilder import calibration
from rackbuilder.builder import build_all, write_build_manifest
from rackbuilder.rack import TemplateError

DEFAULT_MANIFEST = Path("sp404_kits") / "export_manifest.csv"
DEFAULT_TEMPLATE = Path("templates") / "pad_template.adg"


def cmd_build(args: argparse.Namespace) -> int:
    manifest = Path(args.manifest)
    template = Path(args.template)
    if not manifest.is_file():
        print(f"Manifest not found: {manifest} — run `kitbuilder export` first, or pass --manifest", file=sys.stderr)
        return 2
    if not template.is_file():
        print(
            f"Template not found: {template} — save a one-pad Drum Rack from Live as this file "
            "(see README: 'Ableton racks'), or pass --template",
            file=sys.stderr,
        )
        return 2

    try:
        rows, warnings = build_all(
            manifest,
            template,
            args.out,
            samples_root=args.samples_root,
            base_note=args.base_note,
            relative_path_type=args.relative_path_type,
            include=args.kits,
            exclude=args.exclude,
            dry_run=args.dry_run,
        )
    except (TemplateError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    for w in warnings:
        print(f"warning: {w}", file=sys.stderr)

    kits = list(dict.fromkeys(r.kit for r in rows))
    if args.dry_run:
        for r in rows:
            print(f"  [dry-run] {r.kit} | note {r.midi_note} | {r.chain_name} -> {r.relative_sample_path}")
        print(f"Dry run: would build {len(kits)} rack(s), {len(rows)} pad(s) into {args.out}")
        return 0

    manifest_out = write_build_manifest(rows, args.out)
    print(f"Built {len(kits)} rack(s), {len(rows)} pad(s) into {args.out}")
    print(f"Wrote {manifest_out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rackbuilder",
        description="Turn kitbuilder's exported kits into self-contained Ableton Drum Rack "
        "presets (.adg) for Push 3 standalone.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_p = subparsers.add_parser("build", help="Build one collected Drum Rack per kit in the manifest")
    build_p.add_argument(
        "--manifest", default=str(DEFAULT_MANIFEST),
        help=f"kitbuilder's export_manifest.csv (default: {DEFAULT_MANIFEST})",
    )
    build_p.add_argument(
        "--samples-root",
        help="Where kitbuilder's exported wavs now live, if not where the manifest says "
        "(default: the manifest's own folder is searched)",
    )
    build_p.add_argument(
        "--template", default=None,
        help=f"One-pad Drum Rack .adg saved from Live (default: {DEFAULT_TEMPLATE}, "
        f"or {DEFAULT_TEMPLATE.name} in the current folder)",
    )
    build_p.add_argument("--out", default="ableton_racks", help="Output folder (default: ableton_racks)")
    build_p.add_argument(
        "--base-note", type=int, default=calibration.DEFAULT_BASE_NOTE,
        help=f"MIDI note for pad 1 (the kick) — default {calibration.DEFAULT_BASE_NOTE} (C1)",
    )
    build_p.add_argument(
        "--relative-path-type", type=int, default=calibration.RELATIVE_PATH_TYPE,
        help="FileRef RelativePathType to write — set from your calibration reference "
        f"(default: {calibration.RELATIVE_PATH_TYPE})",
    )
    build_p.add_argument("--kits", nargs="+", metavar="KIT", help="Only build these kits")
    build_p.add_argument("--exclude", nargs="+", metavar="KIT", help="Skip these kits")
    build_p.add_argument("--dry-run", action="store_true", help="Print what would be built; write nothing")
    build_p.set_defaults(func=cmd_build)
    return parser


def _default_template() -> str:
    """templates\\pad_template.adg, or pad_template.adg sitting right next
    to where rackbuilder is run (simplest for the double-click exe)."""
    if not DEFAULT_TEMPLATE.is_file() and Path(DEFAULT_TEMPLATE.name).is_file():
        return DEFAULT_TEMPLATE.name
    return str(DEFAULT_TEMPLATE)


def main(argv: list[str] | None = None) -> int:
    raw_argv = sys.argv[1:] if argv is None else argv
    double_clicked = argv is None and not raw_argv
    # Bare `rackbuilder` (or double-clicking rackbuilder.exe) means `build`
    # with every default.
    if not raw_argv or raw_argv[0] not in ("build", "-h", "--help"):
        raw_argv = ["build", *raw_argv]
    args = build_parser().parse_args(raw_argv)
    if args.command == "build" and args.template is None:
        args.template = _default_template()
    code = args.func(args)
    if double_clicked:
        # Keep the console window open so the result can be read.
        try:
            input("\nPress Enter to close...")
        except EOFError:
            pass
    return code


if __name__ == "__main__":
    sys.exit(main())
