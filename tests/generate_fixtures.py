#!/usr/bin/env python3
"""Generate the tiny synthetic (silent) audio fixtures committed under
tests/fixtures/packs/. Re-run this to regenerate them from scratch:

    python tests/generate_fixtures.py

Only filenames/folder structure/format metadata matter for kitbuilder's
classification and format-flagging logic — the audio content itself is
silence, kept short to stay tiny in the repo.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np
import soundfile as sf

FIXTURES_ROOT = Path(__file__).parent / "fixtures" / "packs"
DURATION_SEC = 0.3


def write_wav(rel_path: str, samplerate: int = 44100, subtype: str = "PCM_16", channels: int = 1) -> None:
    path = FIXTURES_ROOT / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = int(DURATION_SEC * samplerate)
    data = np.zeros((frames, channels), dtype="float64")
    sf.write(str(path), data, samplerate, subtype=subtype)


def main() -> None:
    if FIXTURES_ROOT.exists():
        shutil.rmtree(FIXTURES_ROOT)

    # --- Zander Lowfi Drums: rich pack, one file per category, plus an
    # ambiguous filename, a subfolder that should still merge into this
    # same pack, and an excluded MIDI subfolder that should be skipped. ---
    pack = "Zander Lowfi Drums"
    write_wav(f"{pack}/kick_01.wav")
    write_wav(f"{pack}/kick_02.wav")
    write_wav(f"{pack}/snare_01.wav")
    write_wav(f"{pack}/clap_1.wav")
    write_wav(f"{pack}/hat_closed.wav")
    write_wav(f"{pack}/openhat_01.wav")  # ambiguous: matches "hat" (Hat Closed) and "openhat" (Hat Open)
    write_wav(f"{pack}/rim_01.wav")
    write_wav(f"{pack}/tom_01.wav")
    write_wav(f"{pack}/crash_01.aiff")
    write_wav(f"{pack}/perc_shaker.wav")
    write_wav(f"{pack}/bass_01.wav")
    write_wav(f"{pack}/fx_riser.wav")
    write_wav(f"{pack}/vox_chant.wav")
    write_wav(f"{pack}/loop_break.wav")
    write_wav(f"{pack}/weird_sound.wav")  # unclassified -> Other
    write_wav(f"{pack}/Kicks/kick_03.wav")  # subfolder: still belongs to "Zander Lowfi Drums"
    write_wav(f"{pack}/MIDI/should_be_excluded_kick.wav")  # exclude_folders: midi

    # --- Tiny Pack: only 2 categories -> should be flagged "weak kit". ---
    write_wav("Tiny Pack/kick_01.wav")
    write_wav("Tiny Pack/snare_01.wav")

    # --- Big Pack: 35 classifiable files across 3 categories -> forces
    # bank overflow (capacity 16*2=32) and category-level alternates. ---
    for i in range(1, 21):
        write_wav(f"Big Pack/kick_{i:02d}.wav")
    for i in range(1, 11):
        write_wav(f"Big Pack/snare_{i:02d}.wav")
    for i in range(1, 6):
        write_wav(f"Big Pack/clap_{i:02d}.wav")

    # --- Format Test Pack: format-flagging / conversion cases. ---
    write_wav("Format Test Pack/kick_float32.wav", subtype="FLOAT")  # 32-bit float -> needs conversion
    write_wav("Format Test Pack/kick_oddrate.wav", samplerate=22050)  # unsupported rate -> needs conversion
    write_wav("Format Test Pack/kick_ok24.wav", samplerate=48000, subtype="PCM_24")  # fine, no flag
    write_wav("Format Test Pack/snare_01.wav")

    print(f"Fixtures written under {FIXTURES_ROOT}")


if __name__ == "__main__":
    main()
