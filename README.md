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

Groups scanned files into candidate kits — normally one per pack folder,
but see "Kit naming" below — and fills every kit onto exactly **one** 16-pad
bank:

1. **Basics first**: one Kick, one Snare, one Hat (closed or open, whichever
   the pack has). A kit missing any of these three is **not proposed** —
   it's listed under "Skipped" at the bottom of the report instead (with
   what's missing), so you can hand-assemble it from `scan_index.json` if
   you want it anyway.
2. **Then everything else**, in `core_categories` priority order (Kick,
   Snare, Hat Closed, Hat Open, Clap, Rim/Stick, Tom, Cymbal, Perc), each
   capped at `max_variations_per_category` (default 2 — e.g. `Kick`,
   `Kick 2`, never `Kick 3`), up to a ceiling of `pads_per_bank -
   reserved_melodic_pads` (12 by default).
3. **The last `reserved_melodic_pads` pads** (4 by default) are set aside
   for `melodic_categories` content (Bass, FX, Vocal, Loop): the pack's own
   files first, then — since `auto_fill_melodic_from_library` defaults to
   true — any pads still empty get randomly filled with melodic samples
   from *anywhere else in the scanned library* (still capped at
   `max_variations_per_category` per category). Auto-filled pads are
   clearly marked 🎲 in the report, with the real source path right there
   so you can tell at a glance and swap out anything you don't want. Only
   pads that are still empty after both passes (the whole library came up
   short) are left free for you to drop your own melodic samples in later.
   They're never backfilled with extra drum/perc variations. Set
   `auto_fill_melodic_from_library: false` to go back to leaving unfilled
   pads empty.

Anything that doesn't fit (per-category cap, or the two ceilings above) is
listed under "Alternates" instead of being dropped. Unclassified ("Other")
files are listed per kit but never assigned a pad. Writes:

- `<out>/kits.md` — the source of truth. Each kit has a `## [ ] Kit Name`
  heading; tick it to `[x]` (or untick it) to change whether it's exported.
- `<out>/kits.html` — the same report, rendered from the same markdown, for
  easier skimming in a browser.

**Auto-approval.** Kits are listed best-first — fullest kit, then most
melodic content, then most category variety, then fewest files needing
format conversion — and the top `auto_approve_top_n` (10 by default) are
pre-checked `[x]`, so `kitbuilder export` works immediately with no manual
editing. Untick any you don't want, or tick more, before exporting. Set
`auto_approve_top_n: 0` in `categories.yaml` to leave everything unchecked
instead.

**Kit naming.** If a pack's filenames share a consistent, non-generic token
(e.g. `BB3_hat_closed_sugar.wav`, `BB3_kick_sugar.wav`, ...), that token is
used as the kit's real name instead of the folder name. A pack that bundles
multiple such kits (say "Sugar" and "Spice" one-shots dumped in one Splice
folder) gets split into separate kits — `<Pack> — Sugar`, `<Pack> — Spice`
— with anything left unlabeled staying in a `<Pack>` kit of its own. Set
`infer_kit_name_from_filename: false` in `categories.yaml` to always use the
plain folder name instead.

### `export --in <folder> --out <folder> [--config categories.yaml] [--dry-run] [--kits-per-project N]`

Reads only `kits.md` (never the `.html`) for which kits are checked — in the
same best-first order they're listed in — then copies (never moves) each
approved kit's assigned files into:

```
<out>/<Kit Name>/Bank_A/01_Kick.wav
<out>/<Kit Name>/Bank_A/02_Snare.wav
<out>/<Kit Name>/Bank_A/03_Hat_Closed.wav
...
```

Sequential numbering matches pad order, so you can select-all-in-order and
drag into the SP-404 MKII app's pad grid left-to-right, top-to-bottom. Any
file flagged `needs conversion` is converted to 16-bit/44.1kHz PCM on the
way out (via `ffmpeg` if present on `PATH`, otherwise a built-in resampler)
— your source library is never touched. Also writes
`<out>/export_manifest.csv` (kit, bank, pad, category, source path,
exported path, converted, project) for your own records.

**`--kits-per-project N`.** The SP-404 MKII holds 10 banks per project (16
pads each), so at most 10 kits are "loaded" at once. Pass `--kits-per-project
10` (or any N) to bundle approved kits — best-first — into project-sized
groups instead of one flat folder per kit:

```
<out>/Project_1/Bank_01_<Kit Name>/01_Kick.wav
<out>/Project_1/Bank_02_<Kit Name 2>/01_Kick.wav
...
<out>/Project_2/Bank_01_<Kit Name 11>/01_Kick.wav
```

`Bank_01`..`Bank_10` map directly to the hardware bank each kit would occupy
within that project — select-all-in-order within each `Project_N` folder and
you're loading one project's worth of kits at a time. Omit the flag for the
original flat `<Kit Name>/Bank_A/...` layout.

## Config (`categories.yaml`)

The classification keyword map, required-basics list, core/melodic category
groupings, per-category variation cap, reserved melodic-pad count,
library-wide melodic auto-fill toggle (and its `random_seed`), kit-name
inference toggle, excluded subfolders, and accepted extensions all live in
`categories.yaml`. `scan` copies its resolved config into
`<out>/categories.yaml`; edit that copy and re-run `report` (no `--config`
flag needed — it's picked up automatically) to retune classification without
rescanning. Pass an explicit `--config /path/to/file.yaml` to any subcommand
to override that lookup.

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
  kit, a `Bank_A` subfolder (kits never span more than one bank), sequentially
  numbered files, plus `export_manifest.csv`.

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

- One kit per top-level pack folder by default — subfolders inside a pack
  (e.g. `Kicks/`, `Claps/`) merge into that same kit rather than becoming
  their own mini-kits — unless filenames suggest otherwise (see "Kit
  naming" above).
- No packs are excluded by default beyond `exclude_folders` in
  `categories.yaml` (`midi`, `project files`, `documentation`).
- Export always copies, never symlinks.
- `--dry-run` is available on `scan`, `report`, and `export`.
- "Supported sample rate" (i.e. not flagged for conversion) is taken to mean
  44.1kHz or 48kHz PCM at 16 or 24 bits; anything else (including 32-bit
  float) is flagged `needs conversion` and fixed up at export time.
- Loop and Bass/FX/Vocal one-shots are treated as "melodic" content (they
  fill the reserved pads, not the core 12) rather than as part of the core
  drum/perc set — a judgment call, easy to change via `core_categories` /
  `melodic_categories` in `categories.yaml`.
- Kit-name inference from filenames is a best-effort heuristic (last
  non-generic, non-keyword token; a token shared by literally every file in
  a pack is treated as that pack's real name, anything shared by most-but-
  not-all files is treated as a boilerplate prefix like `BB3` and ignored).
  It only splits a pack into multiple named kits when at least two distinct
  labels each independently satisfy the Kick/Snare/Hat basics — otherwise it
  falls back to the plain folder name. Turn it off with
  `infer_kit_name_from_filename: false` if it ever mis-groups your files.
- Melodic auto-fill picks are deterministic per kit name + `random_seed`
  (not per-run), so re-running `report` without changing anything gives the
  same fillers — but doesn't dedupe a chosen file across *different* kits,
  so with a small library the same melodic sample can legitimately end up
  filling a slot in several kits. A real Splice library has enough variety
  that this mostly won't come up in practice.
