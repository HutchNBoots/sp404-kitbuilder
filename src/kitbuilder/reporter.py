"""Phase 3 — render kits.md (source of truth) and kits.html (same content).

Both are generated from the same in-memory markdown build so they can't
drift: kits.html is produced by running kits.md through `markdown`.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import markdown as md

from kitbuilder.assembler import Kit

KITS_MD_FILENAME = "kits.md"
KITS_HTML_FILENAME = "kits.html"

_CHECKBOX_RE = re.compile(r"^##\s*\[([ xX])\]\s*(.+?)\s{2,}\(", re.MULTILINE)


def _escape_cell(text: str) -> str:
    return text.replace("|", r"\|")


def _pad_table(pads: list[dict[str, Any]]) -> str:
    lines = ["| Pad | Category | Filename | Path | Flags |", "|-----|----------|----------|------|-------|"]
    for p in pads:
        flags = ", ".join(p["format_flags"]) if p["format_flags"] else ""
        lines.append(
            f"| {p['pad']} | {_escape_cell(p['display_name'])} | {_escape_cell(p['filename'])} "
            f"| `{_escape_cell(p['path'])}` | {'⚠ ' + flags if flags else ''} |"
        )
    return "\n".join(lines)


def _alternates_table(alternates: dict[str, list[dict[str, Any]]]) -> str:
    lines = ["| Category | Filename | Path |", "|----------|----------|------|"]
    for category in alternates:
        for f in alternates[category]:
            lines.append(
                f"| {_escape_cell(f['display_name'])} | {_escape_cell(f['filename'])} "
                f"| `{_escape_cell(f['path'])}` |"
            )
    return "\n".join(lines)


def _rank_key(kit: Kit) -> tuple:
    """Best-first sort key: fullest kit, then most melodic content, then
    most category variety, then fewest files needing format conversion,
    then name (for a fully deterministic order)."""
    needs_conversion_count = sum(pad.needs_conversion for bank in kit.banks for pad in bank)
    return (
        -kit.total_pads_used,
        -kit.melodic_pads_used,
        -kit.distinct_category_count,
        needs_conversion_count,
        kit.name.lower(),
    )


def rank_complete_kits(kits: list[Kit]) -> list[Kit]:
    """Complete (non-incomplete) kits only, best first — see _rank_key."""
    return sorted((k for k in kits if not k.weak), key=_rank_key)


def _render_kit(kit_dict: dict[str, Any], checked: bool) -> str:
    box = "x" if checked else " "
    parts = [
        f"## [{box}] {kit_dict['name']}  ({kit_dict['total_pads_used']} pads, Bank A)",
        "",
    ]

    for bank in kit_dict["banks"]:
        parts.append(_pad_table(bank))
        parts.append("")

    free_melodic = kit_dict["melodic_pads_reserved"] - kit_dict["melodic_pads_used"]
    if free_melodic > 0:
        parts.append(
            f"_{free_melodic} pad(s) left free for your own melodic samples "
            f"({kit_dict['melodic_pads_used']}/{kit_dict['melodic_pads_reserved']} reserved slots used)._"
        )
        parts.append("")

    if kit_dict["alternates"]:
        parts += ["### Alternates", "", _alternates_table(kit_dict["alternates"]), ""]

    if kit_dict["unclassified"]:
        parts.append("### Unclassified (not assigned a pad)")
        parts.append("")
        for f in kit_dict["unclassified"]:
            parts.append(f"- {f['filename']} — `{f['path']}`")
        parts.append("")

    parts.append("---")
    parts.append("")
    return "\n".join(parts)


def _summary(
    complete: list[dict[str, Any]],
    skipped: list[dict[str, Any]],
    auto_approved_count: int,
    scan_index: dict[str, Any],
) -> str:
    packs_scanned = len({r["pack"] for r in scan_index["files"]})
    unclassified_total = sum(len(k["unclassified"]) for k in complete)
    needs_conversion_total = sum(1 for r in scan_index["files"] if r["needs_conversion"])
    ambiguous_total = sum(1 for r in scan_index["files"] if r["ambiguous_categories"])

    lines = [
        "# SP-404 Kit Builder Report",
        "",
        f"_Source: `{scan_index['source']}`_",
        "",
        "Only complete kits (at least one Kick, one Snare, and one Hat) are "
        "proposed below, best first (fullest kit, then most melodic content, "
        "then most variety, then fewest files needing format conversion). "
        "Incomplete ones are skipped — see the list at the bottom, or "
        "`scan_index.json`, to hand-assemble them yourself.",
        "",
        "## Summary",
        "",
        "| | |",
        "|---|---|",
        f"| Packs scanned | {packs_scanned} |",
        f"| Kits proposed | {len(complete)} |",
        f"| Auto-approved (best {auto_approved_count}) | {auto_approved_count} |",
        f"| Kits skipped (missing Kick/Snare/Hat) | {len(skipped)} |",
        f"| Unclassified files (total) | {unclassified_total} |",
        f"| Files needing format conversion | {needs_conversion_total} |",
        f"| Ambiguous classifications (see scan_index.json) | {ambiguous_total} |",
        "",
        f"The best {auto_approved_count} kits below are already ticked `[x]` — "
        "just run `kitbuilder export` to use them as-is, or tick `[ ]` to `[x]` "
        "(or the reverse) on any others first, save, then export.",
        "",
        "---",
        "",
    ]
    return "\n".join(lines)


def _skipped_section(skipped: list[dict[str, Any]]) -> str:
    if not skipped:
        return ""
    lines = ["## Skipped (incomplete — missing Kick/Snare/Hat)", ""]
    for kit_dict in skipped:
        missing = ", ".join(kit_dict["missing_basics"])
        lines.append(f"- **{kit_dict['name']}** — missing {missing}")
    lines.append("")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def build_markdown(kits: list[Kit], scan_index: dict[str, Any], config: dict[str, Any]) -> str:
    complete = [k.to_dict() for k in rank_complete_kits(kits)]
    skipped = [k.to_dict() for k in kits if k.weak]

    auto_approved_count = min(config["auto_approve_top_n"], len(complete))
    sections = [_summary(complete, skipped, auto_approved_count, scan_index)]
    sections += [_render_kit(k, checked=(i < auto_approved_count)) for i, k in enumerate(complete)]
    sections.append(_skipped_section(skipped))
    return "\n".join(sections)


def build_html(markdown_text: str) -> str:
    body = md.markdown(markdown_text, extensions=["tables"])
    return (
        "<!DOCTYPE html>\n<html><head><meta charset=\"utf-8\">"
        "<title>SP-404 Kit Builder Report</title>\n"
        "<style>body{font-family:sans-serif;max-width:960px;margin:2rem auto;padding:0 1rem}"
        "table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccc;padding:4px 8px;"
        "text-align:left}code{background:#f4f4f4;padding:1px 4px}</style>\n"
        f"</head><body>\n{body}\n</body></html>\n"
    )


def write_report(
    kits: list[Kit], scan_index: dict[str, Any], out_dir: str | Path, config: dict[str, Any]
) -> tuple[Path, Path]:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    markdown_text = build_markdown(kits, scan_index, config)
    html_text = build_html(markdown_text)

    md_path = out_path / KITS_MD_FILENAME
    html_path = out_path / KITS_HTML_FILENAME
    md_path.write_text(markdown_text, encoding="utf-8")
    html_path.write_text(html_text, encoding="utf-8")
    return md_path, html_path


def parse_approved_kits(kits_md_path: str | Path) -> dict[str, bool]:
    """Read kits.md and return {kit_name: approved} from the `## [ ]`/`## [x]` headings."""
    text = Path(kits_md_path).read_text(encoding="utf-8")
    approved: dict[str, bool] = {}
    for match in _CHECKBOX_RE.finditer(text):
        checked = match.group(1).strip().lower() == "x"
        name = match.group(2).strip()
        approved[name] = checked
    return approved
