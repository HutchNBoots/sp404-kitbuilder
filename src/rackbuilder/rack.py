"""Clone a template Drum Rack's single chain once per pad.

The template is a real Live-exported .adg holding a Drum Rack with exactly
one chain whose Simpler has a sample loaded (any sample — it's replaced).
Live saves a Drum Rack preset's chains as GroupDevicePreset/BranchPresets/
DrumBranchPreset; a rack copied out of a Live Set uses DrumGroupDevice/
Branches/DrumBranch instead. Both shapes are handled.
"""

from __future__ import annotations

import copy
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from rackbuilder import calibration


class TemplateError(ValueError):
    """The template .adg isn't shaped the way rackbuilder needs."""


@dataclass
class PadSpec:
    name: str  # chain name shown on Push, e.g. "Kick 2"
    midi_note: int
    relative_path: str  # relative to the .adg's folder
    absolute_path: str  # where the sample sits on this machine (fallback only)
    file_size: int
    frames: int
    sample_rate: int


def _find_branches(root: ET.Element) -> tuple[ET.Element, list[ET.Element], str]:
    """Return (parent, branches, tag) for the template's chain list."""
    for container_tag, branch_tag in (("BranchPresets", "DrumBranchPreset"), ("Branches", "DrumBranch")):
        for container in root.iter(container_tag):
            branches = container.findall(branch_tag)
            if branches:
                return container, branches, branch_tag
    raise TemplateError(
        "No Drum Rack chain found in the template — expected a DrumBranchPreset "
        "(or DrumBranch). Save a Drum Rack with one Simpler pad as the template."
    )


def _set_value(parent: ET.Element, tag: str, value: object) -> None:
    """Set <tag Value="..."/> under parent, creating it if missing."""
    el = parent.find(tag)
    if el is None:
        el = ET.SubElement(parent, tag)
    el.set("Value", str(value))


def _set_existing(parent: ET.Element, path: str, value: object) -> None:
    for el in parent.findall(path):
        el.set("Value", str(value))


def _set_chain_name(branch: ET.Element, name: str) -> None:
    name_el = branch.find("Name")
    if name_el is None:
        name_el = ET.SubElement(branch, "Name")
    if name_el.find("EffectiveName") is not None or name_el.find("UserName") is not None:
        # DrumBranch (Live Set) form: <Name><EffectiveName/><UserName/>...</Name>
        _set_value(name_el, "EffectiveName", name)
        _set_value(name_el, "UserName", name)
    else:
        # DrumBranchPreset form: <Name Value="..."/>
        name_el.set("Value", name)


def _set_note(branch: ET.Element, midi_note: int) -> None:
    zone = branch.find("ZoneSettings")
    if zone is None:
        zone = next(branch.iter("ZoneSettings"), None)
    if zone is None:
        raise TemplateError("Template chain has no ZoneSettings — can't set its pad note")
    _set_value(zone, "ReceivingNote", calibration.receiving_note_value(midi_note))


def _set_sample(branch: ET.Element, pad: PadSpec, relative_path_type: int) -> None:
    parts = list(branch.iter("MultiSamplePart"))
    if len(parts) != 1:
        raise TemplateError(
            f"Template chain must have exactly one sample loaded in its Simpler (found {len(parts)}). "
            "Drag any sample onto the template's pad before saving it."
        )
    part = parts[0]
    file_ref = part.find("SampleRef/FileRef")
    if file_ref is None:
        raise TemplateError("Template sample has no SampleRef/FileRef")

    _set_value(file_ref, "RelativePathType", relative_path_type)
    _set_value(file_ref, "RelativePath", pad.relative_path)
    _set_value(file_ref, "Path", pad.absolute_path)
    _set_existing(file_ref, "LivePackName", "")
    _set_existing(file_ref, "LivePackId", "")
    _set_existing(file_ref, "OriginalFileSize", pad.file_size)
    # Live's CRC algorithm isn't public; 0 means "unknown" and Live
    # recomputes it rather than rejecting the file.
    _set_existing(file_ref, "OriginalCrc", 0)

    sample_ref = part.find("SampleRef")
    _set_existing(sample_ref, "DefaultDuration", pad.frames)
    _set_existing(sample_ref, "DefaultSampleRate", pad.sample_rate)

    _set_existing(part, "Name", pad.name)
    # Play the whole new sample, not the template sample's length.
    _set_existing(part, "SampleStart", 0)
    _set_existing(part, "SampleEnd", pad.frames)
    for loop_tag in ("SustainLoop", "ReleaseLoop"):
        _set_existing(part, f"{loop_tag}/Start", 0)
        _set_existing(part, f"{loop_tag}/End", pad.frames)


def build_rack(
    template: ET.ElementTree,
    pads: list[PadSpec],
    relative_path_type: int = calibration.RELATIVE_PATH_TYPE,
) -> ET.ElementTree:
    """Return a new tree: the template with its single chain replaced by one
    clone per pad. The template tree itself is left untouched."""
    if not pads:
        raise ValueError("No pads to build")
    tree = copy.deepcopy(template)
    parent, branches, tag = _find_branches(tree.getroot())
    if len(branches) != 1:
        raise TemplateError(f"Template must have exactly one Drum Rack chain (found {len(branches)} {tag})")
    prototype = branches[0]
    index = list(parent).index(prototype)
    # Keep the template's whitespace so the output stays Live-formatted.
    last_tail = prototype.tail
    sibling_tail = parent[index - 1].tail if index > 0 else parent.text
    parent.remove(prototype)

    for i, pad in enumerate(pads):
        branch = copy.deepcopy(prototype)
        branch.set("Id", str(i))
        _set_chain_name(branch, pad.name)
        _set_note(branch, pad.midi_note)
        _set_sample(branch, pad, relative_path_type)
        branch.tail = last_tail if i == len(pads) - 1 else (sibling_tail or last_tail)
        parent.insert(index + i, branch)
    return tree


def read_pads(tree: ET.ElementTree) -> list[dict[str, object]]:
    """Summarise a rack's chains (name, MIDI note, relative path) — used by
    tests and for sanity-checking output against a calibration reference."""
    _, branches, _ = _find_branches(tree.getroot())
    out = []
    for branch in branches:
        name_el = branch.find("Name")
        name = name_el.get("Value") if name_el is not None else None
        if name is None and name_el is not None:
            eff = name_el.find("EffectiveName")
            name = eff.get("Value") if eff is not None else None
        note_el = next(branch.iter("ReceivingNote"), None)
        rel_el = next(branch.iter("RelativePath"), None)
        out.append(
            {
                "name": name,
                "midi_note": calibration.midi_note_from_receiving(int(note_el.get("Value"))) if note_el is not None else None,
                "relative_path": rel_el.get("Value") if rel_el is not None else None,
            }
        )
    return out
