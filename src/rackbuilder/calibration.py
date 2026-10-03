"""Every value that depends on how Ableton Live itself writes a collected
Drum Rack lives here, so the one-time calibration against a real
"Collect All and Save" result (spec Section 4) is a change to this file
only.

Status: UNCALIBRATED. These are best-known defaults from community tools,
not yet checked against a real Live 12.4.6 collected preset. Compare them
with your reference .adg (unzip it — it's gzipped XML — and look at a
DrumBranchPreset's SampleRef/FileRef and ZoneSettings) before trusting
the output on Push.
"""

from __future__ import annotations

from pathlib import PurePosixPath

# Live version the template was captured with (documentation only — the
# template's own <Ableton ...> header is kept as-is in the output).
LIVE_VERSION = "12.4.6"

# Folder (relative to the .adg) that collected samples go in, mirroring
# what Live's Collect All and Save produces.
SAMPLES_SUBDIR = PurePosixPath("Samples") / "Imported"

# FileRef/RelativePathType. CALIBRATE: copy whatever value your reference
# collected preset uses. Overridable with `rackbuilder build --relative-path-type`.
RELATIVE_PATH_TYPE = 1

# Drum Rack pad (MIDI) note for pad 1. Kick is always pad 1 in kitbuilder's
# export, so the kick lands here — bottom-left pad on Push.
DEFAULT_BASE_NOTE = 36  # C1


def relative_sample_path(kit_folder_name: str, filename: str) -> str:
    """Path written into FileRef/RelativePath — relative to the .adg's own
    folder, always forward slashes (Live uses '/' on Windows too)."""
    return str(SAMPLES_SUBDIR / kit_folder_name / filename)


def receiving_note_value(midi_note: int) -> int:
    """ZoneSettings/ReceivingNote is stored inverted: 128 - MIDI note
    (so C1 = 36 is written as 92). CALIBRATE: confirm against the
    reference — pad 1 of a default Drum Rack is C1."""
    if not 0 <= midi_note <= 127:
        raise ValueError(f"MIDI note {midi_note} out of range 0-127")
    return 128 - midi_note


def midi_note_from_receiving(value: int) -> int:
    """Inverse of receiving_note_value."""
    return 128 - value
