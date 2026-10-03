# Ableton Drum Rack Builder for Push 3 Standalone — Project Spec

## 0. Goal
Take the kits already assembled by `kitbuilder` (one folder per kit, under `sp404_kits/<Kit>/Bank_A/*.wav`, described by `export_manifest.csv`) and generate real Ableton Live Drum Rack presets (`.adg`) — one per kit — with samples physically collected alongside them, ready to transfer to a **Push 3 running standalone**. Optionally, bake a per-pad or per-kit effects chain and rack-level macros into the rack too.

This is a second, separate tool from `kitbuilder` — it consumes `kitbuilder`'s output (`export_manifest.csv` + the exported wavs), it doesn't rescan Splice.

## 1. Reality check: how a rack actually gets onto Push 3 standalone
Confirmed from Ableton's own docs ([Presets on Push 3 standalone](https://help.ableton.com/hc/en-us/articles/8896436237340-Presets-on-Push-3-standalone), [Projects on Push 3 standalone](https://help.ableton.com/hc/en-us/articles/8863603744412-Projects-on-Push-3-standalone)) and a real-world walkthrough ([Kit Maker's transfer guide](https://www.kit-maker.com/transfer-ableton-kits-to-push-3-standalone/)):

- **No USB/filesystem drop.** Push 3's USB ports are not enabled for file transfer. There is no folder you can drag files into from Windows Explorer.
- **The only transfer path is Wi-Fi/Ethernet + Live's Browser.** Push 3 and the PC must be on the same network, paired through Ableton Live, and you drag a kit from Live's Browser panel onto the Push's icon. This is a manual, per-kit step with no scriptable API — the spec accepts this as an irreducible last step.
- **"Resolving missing media files is not possible on Push."** Samples only survive the transfer if the preset is fully self-contained *before* the drag: real audio physically sitting in a `Samples/Imported/` folder next to the `.adg`, referenced by **relative path** inside the XML — the same shape Live itself produces when you do `File > Collect All and Save`. Absolute `C:\...` paths won't resolve on Push's filesystem, and Push does not auto-collect from installed Packs either.
- **So the tool's job is to produce output that already looks like a real "Collect and Save" result** — preset + its own matching sample folder, relative-path-correct — so the one remaining manual step (drag onto Push in Live's Browser) just works.

## 2. Inputs
- `export_manifest.csv` from `kitbuilder` (kit, bank, pad, category, source_path, exported_path, converted).
- The exported wav files themselves (`sp404_kits/<Kit>/Bank_A/*.wav`).
- One **template `.adg`** that you (the user) export once from a real Ableton Live install — see Section 4. This is the one piece this tool cannot fabricate from nothing; XML generated from scratch, without a real Ableton-authored base, does not load reliably (confirmed by every community tool that's tackled this format — `mxgrp-to-drumrack`, `ableton-device-creator` — all use the "clone a real preset's chain" method rather than building XML from zero).

## 3. Output, per kit
```
ableton_racks/
  <Kit Name>/
    <Kit Name>.adg                     # the Drum Rack preset, relative sample refs
    Samples/
      Imported/
        <Kit Name>/
          01_Kick.wav
          02_Snare.wav
          ... (same files as kitbuilder's export, copied in again here)
```
- Pads mapped consecutively from a fixed base MIDI note so they land left-to-right, bottom-to-top on Push's 8×8 grid in the same pad order as the SP-404 export (pad 1 = bottom-left, etc.) — keeps the two instruments' layouts mentally consistent.
- Each kit's `.adg` + `Samples/` folder together are a self-contained, "already collected" unit — this whole `<Kit Name>/` folder is what gets added to Ableton's User Library / dragged onto Push.

## 4. One-time manual calibration (can't be skipped, but it's done once)
Because Push's importer can't tolerate any deviation from the real "collected" path convention, before building all 10 kits for real:
1. **Capture a template.** In Ableton Live, build one empty Drum Rack with a single Simpler chain (plus whatever default effects you want baked into every pad — see Section 6), save it as `.adg` into your User Library. This becomes `templates/pad_template.adg` in the repo.
2. **Capture a known-good "collected" reference.** Drag 2-3 real samples onto that rack, run `File > Collect All and Save`, and keep the resulting project folder. This is the ground truth for exactly how Ableton writes relative sample paths and folder structure — the script's output must match this byte-for-byte in *structure* (not literally identical, but same path convention, same XML elements). This reference folder is NOT committed to the repo (it's your personal content) but its *structure* is documented in the spec once inspected.
3. Only after step 2 confirms the convention does the script get trusted to generate all 10 kits' worth.

This calibration happens locally, on your PC, with your real Ableton Live — it's the one part of this whole project that must happen outside Claude Code's cloud sandbox, because it needs a licensed, running copy of Ableton Live.

## 5. Pipeline (CLI, mirrors kitbuilder's shape)
```
rackbuilder build --manifest ./kitbuilder_out/export_manifest.csv \
                   --samples-root ./sp404_kits \
                   --template ./templates/pad_template.adg \
                   --out ./ableton_racks
```
For each kit in the manifest:
1. Read its pad rows (pad #, category, exported_path).
2. Copy each referenced wav into `ableton_racks/<Kit>/Samples/Imported/<Kit>/`.
3. Decode `pad_template.adg` to XML, clone its single-chain fragment once per pad (12–16 times depending on the kit), and for each clone:
   - Set the sample reference (relative path matching the calibrated convention from Section 4).
   - Set chain name = category label (e.g. "Kick 2").
   - Set receiving MIDI note = base note + pad index.
4. Re-gzip to `<Kit Name>.adg`.
5. Write a `build_manifest.csv` (kit, pad, category, relative sample path, midi note) for your own records — same spirit as kitbuilder's `export_manifest.csv`.

## 6. Effects & macros (optional, confirmed feasible)
Because `.adg` is just XML, whatever lives in the template chain gets cloned onto every pad, and any parameter in it can be set programmatically:
- **Per-pad chain effects** — e.g. every pad gets Simpler → Saturator → EQ Eight by default, with the script nudging specific values per category (e.g. a touch more high-pass on hats, more low-end on kicks) if you want that level of control. Default: no per-category variation, just whatever's in the template, unless you specify rules.
- **Rack-level macros** — the Drum Rack's 8 Macro knobs can be mapped to parameters inside the chains (`MacroControls` XML elements), e.g. one "Kit Tone" macro wired to every pad's EQ simultaneously. Optional, off by default.
- **Scope decision needed**: do you want this in v1, or ship v1 as sample-mapping only (no effects) and add effects as a v2 pass once the core pipeline is proven? Recommendation: v1 = no effects (prove the harder problem — valid, Push-importable, self-contained racks — first), v2 = effects/macros once that's confirmed working on real hardware.

## 7. Build environment: Claude Code on the web (cloud)
Same split as the `kitbuilder` project:
- **Build & test in the cloud** against synthetic fixtures: a dummy `pad_template.adg`-shaped fixture (hand-built minimal valid gzipped-XML with one chain) and a fake `export_manifest.csv` + silent wavs, so the clone/relabel/re-gzip logic can be exercised without your real files or a real Ableton install.
- **You do NOT need to upload your real wavs or your real template `.adg`.** The cloud build proves the mechanism against fixtures; your actual rack generation happens locally, where your real `export_manifest.csv`, real exported wavs, and the one-time real Ableton-exported template already live.
- **The calibration step (Section 4) must happen locally** — it needs a real, running, licensed Ableton Live, which the cloud sandbox doesn't have.
- **Final verification also happens locally**: generate one kit, add it to your User Library, drag it onto Push 3 over Wi-Fi, confirm all pads sound correct before batch-generating the other 9.

## 8. Packaging
Same pattern as `kitbuilder` (see that spec's Section 6) — installable as a `rackbuilder` CLI via `pyproject.toml` + console-script entry point, `pip install -e .`, verified with `rackbuilder --help` in a clean shell before considering the cloud build done.

## 9. Open questions / things to confirm before build
1. **Effects in v1 or v2?** (Section 6) — recommend v2, confirm you agree.
2. **Base MIDI note** for pad 1 — any preference, or default to a sensible Push 3 standalone default (likely C1/note 36, matching typical Drum Rack convention)?
3. Original Ableton library template — are you on a specific Live version (Standard/Suite) I should account for in the calibration note, or is "whatever you currently have" fine?
4. Any kits from the manifest you want excluded from this pass (e.g. ones you've since decided not to use)?

## 10. Build order
1. Decode/encode round-trip on a synthetic fixture `.adg` — prove gzip+XML read/write works at all, in the cloud.
2. Chain-cloning logic against the fixture (N clones from 1, relabeled, renoted) — cloud, fixture-only.
3. **Local calibration** (Section 4) — you, with real Ableton, one time.
4. Wire the real relative-path convention from step 3 into the script.
5. Generate one real kit end-to-end locally, verify on Push 3 over Wi-Fi.
6. Batch-generate the remaining 9 kits.
7. (v2) Add effects-chain and macro support per Section 6.

## 11. Decisions (confirmed)
1. **Effects:** v2. v1 is sample mapping only.
2. **Base note:** C1 (MIDI 36), and the Kick sits on it. kitbuilder always puts Kick on pad 1, so pads map as base note + (pad - 1); rackbuilder warns if a kit ever has a Kick that isn't on pad 1.
3. **Live version:** 12.4.6 — the template and calibration reference get captured from that.
4. **Exclusions:** none hard-coded; `--kits` / `--exclude` pick per run.

### Corrections to the sections above, from the current kitbuilder code
- `export_manifest.csv` is written into the **export folder** (`sp404_kits/`), not `kitbuilder_out/`, and also has a `project` column.
- With `kitbuilder export --kits-per-project`, wavs live in `Project_N/Bank_XX_<Kit>/` instead of `<Kit>/Bank_A/`. rackbuilder locates samples from the manifest's `exported_path` (falling back to `--samples-root` and the manifest's own folder), so both layouts work.
- Every kit is one bank, so a rack has at most 16 pads.
- The template's chain must have **a sample loaded** in its Simpler (any sample — it's replaced). An empty Simpler has no sample-reference XML to clone.
- All Live-specific values (RelativePathType, ReceivingNote encoding, sample folder) live in `src/rackbuilder/calibration.py` and are UNCALIBRATED until Section 4 is done.
