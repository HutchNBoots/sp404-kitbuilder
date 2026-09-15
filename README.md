# sp404-kitbuilder

Scan a Splice sample library, auto-group one-shots into candidate SP-404 MKII
drum kits, write a human-editable report of the proposed kits, and — once
you approve some — copy the chosen files into a clean per-kit folder ready
for manual drag-and-drop import into the Roland SP-404 MKII (via the SP-404
MKII app or SD card).

There's no public API for scripting pad assignment on the unit itself, so
that last step stays manual. This tool's job is to do all the tedious
sorting/deciding before that manual step.

## Prerequisites

- Python 3.10+
- Optionally, `ffmpeg` on your `PATH` for higher-quality format conversion
  (falls back to a built-in linear resampler via `soundfile`/`numpy` if
  `ffmpeg` isn't found — fine for one-shots, but `ffmpeg` is better for
  anything longer).

## Install

```bash
git clone <repo>          # or unzip the folder this was built in
cd sp404-kitbuilder
pip install -e .          # installs deps + registers the `kitbuilder` command
```

No PyPI publish needed — the editable install is enough for personal use.
If you'd rather not install anything yet, every command below also works
unpacked via `python -m kitbuilder ...` in place of `kitbuilder ...`.

## Usage

```bash
kitbuilder scan   --source "C:\Users\you\Documents\Splice\sounds\packs" --out .\kitbuilder_out
kitbuilder report --in .\kitbuilder_out
# edit kitbuilder_out\kits.md — tick the [ ] boxes for kits you approve, save
kitbuilder export --in .\kitbuilder_out --out "C:\SP404_Export"
```

Add `--dry-run` to any of the three subcommands to see what it *would* do
(counts, planned copies) without writing anything — handy for iterating on
`categories.yaml` before committing to a real run.

### `scan --source <folder> --out <folder> [--config categories.yaml] [--dry-run]`

Walks `--source` for `.wav`/`.aiff`/`.aif` files, records path/pack/size/
sample-rate/bit-depth/duration for each, classifies each by filename against
the ordered keyword map in `categories.yaml`, and flags anything that isn't
16/24-bit PCM at 44.1kHz/48kHz as `needs conversion`. Writes:

- `<out>/scan_index.json` — the full per-file inventory. `report` and
  `export` both read from this cache instead of re-scanning.
- `<out>/categories.yaml` — a copy of the config used for this scan. Edit
  this file and re-run `report` to retune classification without rescanning.

### `report --in <folder> [--config categories.yaml] [--dry-run]`

Groups scanned files into one candidate kit per pack folder, fills pads in
priority order (Kick, Snare, Clap, Hat Closed, Hat Open, Rim/Stick, Tom,
Cymbal, Perc, Bass, FX, Vocal, Loop — configurable), and writes:

- `<out>/kits.md` — the source of truth. Each kit has a `## [ ] Kit Name`
  heading; tick it to `[x]` to approve that kit for export.
- `<out>/kits.html` — the same report, rendered from the same markdown, for
  easier skimming in a browser.

Packs matching fewer than `weak_kit_category_threshold` categories (default
3) are flagged "weak kit — review manually" but still get a full kit
proposal. Multiple files in the same category are never collapsed — e.g.
three kicks become `Kick`, `Kick 2`, `Kick 3`, filled back-to-back. A pack
with more classified files than fit in one 16-pad bank overflows into a
second bank (up to `banks_per_kit_max`); anything beyond that is listed
under "Alternates" per category instead of being dropped. Unclassified
("Other") files are listed per kit but never assigned a pad.

### `export --in <folder> --out <folder> [--config categories.yaml] [--dry-run]`

Reads only `kits.md` (never the `.html`) for which kits are checked, then
copies (never moves) each approved kit's assigned files into:

```
<out>/<Kit Name>/Bank_A/01_Kick.wav
<out>/<Kit Name>/Bank_A/02_Kick_2.wav
<out>/<Kit Name>/Bank_A/03_Snare.wav
...
<out>/<Kit Name>/Bank_B/...   (only if the kit overflowed into a 2nd bank)
```

Sequential numbering matches pad order, so you can select-all-in-order and
drag into the SP-404 MKII app's pad grid left-to-right, top-to-bottom. Any
file flagged `needs conversion` is converted to 16-bit/44.1kHz PCM on the
way out (via `ffmpeg` if present on `PATH`, otherwise a built-in resampler)
— your source library is never touched. Also writes
`<out>/export_manifest.csv` (kit, bank, pad, category, source path,
exported path, converted) for your own records.

## Config (`categories.yaml`)

The classification keyword map, pad/bank layout, weak-kit threshold,
excluded subfolders, and accepted extensions all live in `categories.yaml`.
`scan` copies its resolved config into `<out>/categories.yaml`; edit that
copy and re-run `report` (no `--config` flag needed — it's picked up
automatically) to retune classification without rescanning. Pass an
explicit `--config /path/to/file.yaml` to any subcommand to override that
lookup.

## Importing into the SP-404 MKII (manual, by design)

Two supported ways, both manual — there's no public API for scripting pad
assignment directly:

1. **SP-404 MKII desktop app**: connect the unit, drag files from the
   exported per-kit folder straight onto pads in the app's grid.
2. **SD card**: copy the exported folder's files into the SD card's
   `ROLAND/IMPORT` folder, then on the unit: `SHIFT + Pad 14` → Import from
   SD Card → Sample, and assign one at a time.

## Output folders

- `kitbuilder_out/` (or whatever you pass to `--out` on `scan`): the working
  cache — `scan_index.json`, `categories.yaml`, `kits.md`, `kits.html`.
  Resumable: re-run `report` after hand-editing `categories.yaml` without
  rescanning.
- The export destination (e.g. `SP404_Export/`): one folder per approved
  kit, `Bank_A`/`Bank_B` subfolders, sequentially numbered files, plus
  `export_manifest.csv`.

## Development / testing

This was built and tested in a sandbox with no access to a real Splice
library, against synthetic silent-WAV fixtures under `tests/fixtures/packs/`
(regenerate with `python tests/generate_fixtures.py`). Run the test suite
with:

```bash
pip install -e ".[dev]"
pytest
```

The real library is only ever touched on your own machine, later — clone
this repo (or `pip install`) there and run `kitbuilder scan --source
"C:\...\Splice\sounds\packs" ...` in an environment with access to it.

## Assumptions made during the build

- One kit per top-level pack folder — subfolders inside a pack (e.g.
  `Kicks/`, `Claps/`) merge into that same kit rather than becoming their
  own mini-kits.
- No packs are excluded by default beyond `exclude_folders` in
  `categories.yaml` (`midi`, `project files`, `documentation`).
- Export always copies, never symlinks.
- `--dry-run` is available on `scan`, `report`, and `export`.
- "Supported sample rate" (i.e. not flagged for conversion) is taken to mean
  44.1kHz or 48kHz PCM at 16 or 24 bits; anything else (including 32-bit
  float) is flagged `needs conversion` and fixed up at export time.
