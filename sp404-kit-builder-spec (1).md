# SP-404 MKII Kit Builder — Project Spec

## 0. Goal
Scan a Splice sample library on the C: drive, auto-group one-shots into candidate drum "kits" based on folder (pack) and filename (kick/clap/snare/etc.), write a human-readable report of the proposed kits, and — once approved — copy the chosen files into a clean per-kit staging folder ready for manual drag-and-drop import into the Roland SP-404 MKII (via the SP-404 MKII app or SD card).

No SP-404 automation API exists, so the last mile (actually loading pads) stays manual. This tool's job is to do all the tedious sorting/deciding *before* that manual step.

## 1. Inputs
- `--source` root folder, e.g. `C:\Users\<you>\Documents\Splice\sounds\packs`
- Splice packs are typically one folder per pack (e.g. `Zander Lowfi Drums`), with one-shots as loose `.wav`/`.aiff` files, sometimes in subfolders like `Drums/`, `One Shots/`, `Kicks/`.
- File types: `.wav`, `.aiff`/`.aif` (SP-404 MKII app also takes mp3/flac/m4a, but we'll default to wav/aiff since that's what Splice ships and what the SD-card import path requires).

## 2. Pipeline (3 phases, run as a single CLI with subcommands)

```
kitbuilder scan   --source "C:\...\Splice\sounds\packs" --out ./kitbuilder_out
kitbuilder report --in ./kitbuilder_out           # writes kits.md + kits.html
# you edit kits.md, check the [ ] boxes for kits you approve
kitbuilder export --in ./kitbuilder_out --out "C:\...\SP404_Export"
```

### Phase 1 — Scan & Classify
For every audio file under `--source`:
1. Record: full path, pack folder name (top-level folder under `--source`, or nearest ancestor that looks like a pack), filename, file size, sample rate, bit depth, and duration (via `soundfile`/`mutagen` — no full decode needed).
2. Classify by filename using an ordered keyword map (case-insensitive, checks whole filename not just start):

   | Category    | Keywords (examples)                          |
   |-------------|-----------------------------------------------|
   | Kick        | kick, kck, bd, bassdrum                        |
   | Snare       | snare, snr, sd                                 |
   | Clap        | clap, clp                                      |
   | Hat Closed  | hat, hh, chh, closedhat                        |
   | Hat Open    | openhat, ohh                                   |
   | Rim/Stick   | rim, stick, clave                              |
   | Tom         | tom                                            |
   | Cymbal      | cymbal, crash, ride                            |
   | Perc        | perc, shaker, tamb, conga, bongo               |
   | Bass        | bass, sub                                       |
   | FX          | fx, riser, impact, sweep, noise                |
   | Vocal       | vox, vocal, chant                              |
   | Loop        | loop, break                                     |
   | Other       | (unmatched — logged separately, not auto-kitted) |

   - Config file (`categories.yaml`) holds this map so you can tune it without touching code.
   - A file can only match one category — first match by priority order above wins; log ambiguous matches (hits >1 category) for review.
3. Flag format issues: 32-bit float WAVs are rejected by the SP-404 outright; anything not 16/24-bit PCM at a supported rate gets a `⚠ needs conversion` flag.
4. Write `scan_index.json` — the raw per-file inventory. This is the reusable cache; `report` and `export` both read from it instead of re-scanning.

### Phase 2 — Kit Assembly
- **One candidate kit per pack folder** by default (a pack = one kit). Packs with almost nothing classifiable (e.g. <3 categories found) are flagged `weak kit — review manually` rather than silently dropped.
- **Pad layout**: SP-404 MKII = 16 pads/bank, 10 banks/project. Within one kit:
  - Fixed priority order fills pads first: Kick, Snare, Clap, Hat Closed, Hat Open, Rim, Tom, Cymbal, Perc, Bass, FX, Vocal, Loop.
  - Per your preference, **multiple matches in the same category are NOT collapsed** — e.g. 3 kicks in a pack → Kick, Kick 2, Kick 3 all get pads, back-to-back, as long as room remains.
  - If a pack has more classified files than fit in one 16-pad bank, overflow spills into "Bank 2" of the same kit (so a big pack can become a 2-bank kit) and the report says so.
  - Files landing in "Other"/unclassified are listed per-kit but **not** assigned a pad — you can hand-place these later.

### Phase 3 — Report
- Output both `kits.md` (source of truth, human-editable) and `kits.html` (same content, easier to skim/click through), generated from one template so they never drift.
- Per kit, a table: Pad # → Category → Filename → full path → format flags.
- Alternates section per category if extras existed beyond what fit.
- Top summary: packs scanned, kits proposed, weak kits, total unclassified files, total files needing format conversion.
- **Approval mechanism**: each kit heading has a markdown checkbox, e.g.
  ```
  ## [ ] Zander Lowfi Drums  (14 pads, Bank A)
  ```
  You tick the ones you want (`[x]`), save the file, then run `export`, which only reads from `kits.md` (not the html) and only processes checked kits.

### Phase 4 — Export
- For each approved kit, copy (never move) the assigned files into:
  ```
  <export-root>/<Kit Name>/Bank_A/01_Kick.wav
  <export-root>/<Kit Name>/Bank_A/02_Kick_2.wav
  <export-root>/<Kit Name>/Bank_A/03_Snare.wav
  ...
  ```
  Sequential numbering matches pad order, so you can select-all-in-order and drag into the SP-404 MKII app's pad grid left-to-right, top-to-bottom, with minimal guesswork.
- Any file flagged `needs conversion` (32-bit float, odd sample rate) gets converted to 16-bit/44.1kHz PCM during export via `ffmpeg`/`soundfile`, writing the fixed copy — original library is never touched.
- Writes `export_manifest.csv` (kit, pad, source path, exported path) for your own records.

## 3. Import into the SP-404 MKII (manual, by design)
Two supported ways, both manual — there's no public API for scripting pad assignment directly:
1. **SP-404 MKII desktop app**: connect the unit, drag files from the exported per-kit folder straight onto pads in the app's grid.
2. **SD card**: copy the exported folder's files into the SD card's `ROLAND/IMPORT` folder, then on the unit: `SHIFT + Pad 14` → Import from SD Card → Sample, and assign one at a time.
The export step's job is just to make either of these as close to "select all, drop in order" as possible.

## 4. Tech stack
- Python 3 (runs locally via Claude Code — needs real filesystem access to your C: drive, which this chat's sandbox doesn't have).
- Libraries: `pathlib`, `argparse`, `pyyaml`, `soundfile` or `mutagen` (audio metadata without full decode), `markdown` (md→html render), optional `ffmpeg-python`/`pydub` for the format-fix step.
- Single CLI entry point, `scan`/`report`/`export` subcommands as above, all reading/writing to a working `--out` folder so runs are resumable and you can re-run `report` after hand-editing `categories.yaml` without rescanning.
- See Section 6 for exactly how this gets packaged into a real downloadable/installable command, not loose scripts.

## 5. Config (`categories.yaml`)
```yaml
pads_per_bank: 16
banks_per_kit_max: 2
categories:
  Kick: [kick, kck, bd, bassdrum]
  Snare: [snare, snr, sd]
  Clap: [clap, clp]
  # ... etc, user-editable
exclude_folders: [midi, project files, documentation]
extensions: [.wav, .aiff, .aif]
```

## 6. Packaging & Distribution (must be a real downloadable CLI app, not just loose scripts)
Claude Code should build this as an installable command-line tool, not a folder of scripts you run with `python scan.py`. Concretely:

- **Project layout** — a proper package, not flat files:
  ```
  sp404-kitbuilder/
    pyproject.toml
    README.md
    src/kitbuilder/
      __init__.py
      cli.py            # argparse/click entry point: scan / report / export
      scanner.py
      classifier.py
      assembler.py
      reporter.py
      exporter.py
      categories.yaml   # default config, user can override with their own
    tests/
  ```
- **Packaging**: `pyproject.toml` with a `[project.scripts]` entry point, e.g.
  ```toml
  [project.scripts]
  kitbuilder = "kitbuilder.cli:main"
  ```
  Once installed, this gives you a real `kitbuilder` command on your PATH — no need to remember a script path or type `python something.py`.
- **Install & run, from scratch, on your machine (Windows, since the library is on C:)**:
  ```
  git clone <repo>        # or just download/unzip the folder Claude Code produces
  cd sp404-kitbuilder
  pip install -e .        # installs deps + registers the `kitbuilder` command
  kitbuilder scan   --source "C:\Users\you\Documents\Splice\sounds\packs" --out .\kitbuilder_out
  kitbuilder report --in .\kitbuilder_out
  kitbuilder export --in .\kitbuilder_out --out "C:\SP404_Export"
  ```
  `pip install -e .` (editable install) is enough for personal use — no PyPI publish needed. A regular `pip install .` also works if you don't need to keep editing `categories.yaml` inside the package.
- **Dependencies**: keep the list short and pinned in `pyproject.toml` (`pyyaml`, `soundfile` or `mutagen`, `markdown`, optionally `ffmpeg-python`) so `pip install -e .` is a one-shot setup with no manual dependency chasing.
- **Fallback for zero-install use**: also keep `cli.py` runnable directly via `python -m kitbuilder scan ...` without installing, for a quick first run before you bother with `pip install -e .`.
- **README.md** should include: prerequisites (Python 3.10+, optionally ffmpeg on PATH for format conversion), the install command, all three subcommands with real example paths, and what the output folders (`kitbuilder_out/`, the export folder) contain.
- **Sanity check before considering it done**: Claude Code should actually run `pip install -e .` and `kitbuilder --help` (or the `python -m` fallback) itself at the end of the build, in a clean shell, to confirm the packaging works end-to-end — not just that the individual functions run.

## 7. Build Environment: Claude Code on the Web (cloud)
This will be built via **Claude Code on the web** (claude.ai/code), which runs in an Anthropic-managed cloud VM against a **GitHub repo** — it has no access to the local C: drive or the real Splice library. That changes how testing works during the build:

- **Needs a GitHub repo.** Create an empty repo (e.g. `sp404-kitbuilder`) first and connect it in Claude Code on the web — there's nothing to build against otherwise.
- **Use synthetic fixtures for all testing in the cloud.** The repo should include a `tests/fixtures/` folder of tiny dummy audio files with realistic names (e.g. `Zander Lowfi Drums/kick_01.wav`, `.../clap_2.wav`, `.../hat_closed.wav`) — a few seconds of silence is fine, only filenames/folder structure matter for classification logic. Claude Code should generate these itself (e.g. with `soundfile`/`numpy`, writing short silent WAVs) rather than needing real samples. `scan`/`report`/`export` all get exercised end-to-end against these fixtures in the cloud sandbox.
- **The real Splice library is only touched locally, later.** Once the cloud build is done and pushed, you `git clone` (or `pip install`) it on your own machine and run `kitbuilder scan --source "C:\...\Splice\sounds\packs"` there — that's the only environment with access to the real files. Don't ask Claude Code on the web to try to reach the C: drive; it can't.
- **Format-conversion step (32-bit float → 16-bit PCM)** should still be built and unit-tested in the cloud against a synthetic 32-bit-float fixture, same reasoning.

## 8. Open questions / things to confirm before build
1. Should sub-genre folders inside a pack (e.g. `Zander Lowfi Drums/Kicks`, `/Claps`) be treated as **one kit** (current assumption) or should each subfolder become its own mini-kit?
2. Any packs/folders to exclude outright (loops-only packs, melodic one-shots, vocal packs)?
3. OK with copying files (extra disk space) rather than symlinking, for export?
4. Want a `--dry-run` flag that just prints the summary without writing files, for quick iteration on `categories.yaml`?

## 9. Build order
1. `scan` + `scan_index.json` — get this right first, it's the foundation. Validate against synthetic fixtures (Section 7) since the cloud build has no access to your real library.
2. `report` (md+html) — validate classification quality against the fixtures before writing any assembly logic tweaks.
3. `export` + format-fix, also against fixtures.
4. Package as an installable CLI (Section 6) and verify the clean-install `pip install -e .` → `kitbuilder --help` path actually works, in the cloud sandbox.
5. Push to GitHub, then locally: clone/install, and run `scan`/`report` against your real Splice library for the first time. Tune `categories.yaml` against real results.
