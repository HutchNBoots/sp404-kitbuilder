"""Read/write Ableton preset files (.adg/.adv/.als).

They're gzipped XML. Live writes a double-quoted XML declaration and tab
indentation; ElementTree keeps element text/tails verbatim, so a round trip
preserves the original layout apart from the declaration, which is
rewritten in Live's own style.
"""

from __future__ import annotations

import gzip
import xml.etree.ElementTree as ET
from pathlib import Path

XML_DECLARATION = '<?xml version="1.0" encoding="UTF-8"?>\n'


def read_adg(path: str | Path) -> ET.ElementTree:
    raw = Path(path).read_bytes()
    # Live always gzips, but accept a plain-XML file too (handy when
    # hand-editing a template while calibrating).
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return ET.ElementTree(ET.fromstring(raw))


def to_xml_string(tree: ET.ElementTree) -> str:
    return XML_DECLARATION + ET.tostring(tree.getroot(), encoding="unicode")


def write_adg(tree: ET.ElementTree, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # mtime=0 keeps output byte-identical across runs for the same input.
    path.write_bytes(gzip.compress(to_xml_string(tree).encode("utf-8"), mtime=0))
    return path
