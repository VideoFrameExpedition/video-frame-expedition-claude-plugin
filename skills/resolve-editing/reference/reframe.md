# Reframing with the subject's boxes (tools/reframe.py)

The application gives positions, the assistant decides the framing: `get_reframe` returns the
subject's box at each keyframe of a range (about every 2 s) plus one deterministic crop.
That crop alone is not enough for an edit. Two things go wrong:

- **it aims at the middle of the body.** A subject filmed close in a vertical video fills 60–90 %
  of the height while a 16:9 band keeps 32 %. The crop sits on the belly and cuts the head.
  (In a test edit of pets, 6 of 9 manual fixes were exactly this.)
- **it jumps every 2 s.** `segments` starts a new piece whenever the boxes' union stops fitting,
  so a subject bigger than the crop gets one piece per keyframe.

`tools/reframe.py` does the framing from the same boxes and with the application's formula, and
fixes both issues (the application's `plan_reframe` does the same, and also asks the vision model
where the head is):

1. **Target, not box.** For each keyframe the crop must keep the subject's *target*: the whole
   box when it fits, else a part of it 0.8 crop high, taken at its **top** (the head of an upright
   animal or person, `anchor: auto`). `anchor: center` or `bottom` change that per item. On a
   clip turned 180° (`rotation: 180`) the head is at the bottom of the boxes: the tool swaps the
   anchor itself.
2. **Hysteresis.** One crop is kept while every keyframe keeps at least `--keep` (0.75) of its
   target. A new piece starts only when that fails; the cut falls halfway between the two
   keyframes.
3. **No jumpy pieces.** Pieces shorter than `--min-piece` (2.5 s) join the neighbour that keeps
   the subject best. Neighbouring crops closer than 150 timeline pixels are merged.
4. **Position.** Along the free side, the crop keeps the most of the targets (mean, then
   minimum). Ties go to the targets' centre, or to the previous piece's position (fewer moves).
5. **Keyframes.** Only those inside the range (± 0.5 s) are used. The one the application adds
   before the range counts only when the range has fewer than two.
6. **Score.** For every keyframe: `cov` is the share of the target inside the crop, `body` the
   share of the whole box. A piece is flagged `low_coverage` when one keyframe keeps less than
   `--flag` (0.6).

## Use

1. Write the edit list with the final cuts (after `get_cut_points`). Give each item `video_id`,
   `uid` (media pool id from R1/M1), `in_s`, `out_s`, and `reframe` when needed (see below).
2. Run the plan:
   `python "${CLAUDE_PLUGIN_ROOT}/skills/resolve-editing/tools/reframe.py" edit.json OUT --subject mammal`
   (`python3` on macOS). Use the scratch folder for OUT; the timeline size comes from `format` or `--width/--height`.
   For people use `--subject person`, for a named animal the start of its label (`cat`).
   The printed summary lists the flagged pieces.
3. Look at the pieces:
   - Windows: `powershell -NoProfile -ExecutionPolicy Bypass -File "${CLAUDE_PLUGIN_ROOT}/skills/resolve-editing/tools/review_sheet.ps1" -Review OUT\review.json`
     (`-FlaggedOnly` for the flagged ones only);
   - macOS: `osascript -l JavaScript "${CLAUDE_PLUGIN_ROOT}/skills/resolve-editing/tools/review_sheet.js" OUT/review.json`
     (`--flagged-only` for the flagged ones only).

   Open the `review_NN.jpg` with Read. Each row is a
   piece and each image a keyframe: yellow frame = what the timeline shows, outside dimmed,
   percentage = `cov`, red = below `--flag`.
4. Fix, then run the plan again (it is deterministic and takes a minute):
   - head not at the top of the box: a cat seen from above or lying, a face looking up at the
     camera. Use `"reframe": {"anchor": "center"}` (or `"bottom"`);
   - footage filmed sideways or upside down (nothing detects it: look at the sheets):
     `"rotation": -90` / `90` / `180`. With ±90 the landscape picture fills the 16:9 timeline
     (zoom only); -90 turns the picture's left side up (checked on exported stills);
   - wrong subject: `"subject": "person"`…; no framing at all: `"off": true`;
     exact values: `"props": {"ZoomX":…, "ZoomY":…, "Pan":…, "Tilt":…, "RotationAngle":…}`.
5. Send `b2_1.py` from OUT, then `b2_2.py`… **unchanged** to `run_script` (template B2 below). Batch 1
   creates the timeline named in the edit list (`timeline`) and fails if the name exists. The
   others append to it by name. Each checks durations and read-back transforms (`bad_durations`,
   `prop_fails`).

Flags: `low_coverage` (look at it), `other_subject` (no `--subject` in the range: main subject
used), `no_subject` (no box: centred crop), `no_answer` (nothing known: not reframed),
`rotated_±90` / `rotated_180`, `upscale_N` (enlarged more than twice: soft), `manual`.

## Limits (say them to the user)

- **Positions every ~2 s.** A subject that changes place faster cannot be followed by static
  crops without jumps. Such pieces stay flagged. Keep them, pick another moment, or accept a
  wider framing.
- **No head position.** The detector gives the body's box, not the head's (human faces only,
  YuNet). `anchor` is a rule of thumb, and the sheets are there to catch its failures.
- **No keyframed transforms** in Resolve 21.1: a moving subject means several items.

## Don't

- Don't verify with template V1 on many items: `OpenPage("color")` + stills froze Resolve once
  (no script answered any more, the last `SetProperties` were lost after the restart). The
  review sheets need no Resolve at all; keep V1 for one or two checks, never in a loop.
- Don't trust the application's `close_up` framing label alone to pick close-ups: in the same
  test, 15 of 43 « close-up » passages were medium or wide shots, dark or blurred. Look at the
  frames.
