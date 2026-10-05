# Edit list

Write every edit as this JSON before touching Resolve. It is what you show the user, what B1
consumes (`items`), and what you compare against the timeline read back with R1.

```json
{
  "title": "Summer at the lake - 45 s",
  "timeline": "Lake - vfe v1",
  "format": {"width": 1920, "height": 1080},
  "items": [
    {
      "n": 1,
      "video_id": "01a0e013e8607cb7999cd9b596fcdef8",
      "file": "C:\\Users\\me\\Videos\\Lake\\20250726_113722.mp4",
      "uid": "b75858a2-2c56-43fd-92a0-8f248e304562",
      "in_s": 0.0,
      "out_s": 4.0,
      "why": "wide shot of the lake, usability 100/100",
      "transition_in": "cut",
      "props": null
    },
    {
      "n": 2,
      "video_id": "01a0de66de467be199cf80ad302fa1b5",
      "file": "C:\\Users\\me\\Videos\\Lake\\café terrace.mp4",
      "in_s": 4.006,
      "out_s": 10.006,
      "why": "highlight 1: a bee on the flowers",
      "transition_in": {"type": "dissolve", "frames": 15},
      "props": null
    }
  ]
}
```

Rules:
- `in_s`/`out_s` are seconds of the source file (0 = its first frame), taken from
  `get_cut_points` (`picture_in_s`/`picture_out_s`). B1 turns them into frames with the clip's FPS
  in Resolve.
- `uid` (media pool unique id from R1/M1) when the clip is already in the project; otherwise `file`
  (B1 imports it). When you put `file` into a script, escape non-ASCII characters (`\\u00e9`).
- `transition_in`: `"cut"` or `{"type": "dissolve", "frames": 8..30}` — the templates handle
  nothing else. Use dissolves sparingly (a change of place or time, the end of a sequence);
  default is cut.
- `props`: `ZoomX/ZoomY/Pan/Tilt` (and `RotationAngle`) for another aspect ratio or a tighter frame.
  Let `tools/reframe.py` compute them: it splits an item into pieces when the subject moves, and
  writes them back as consecutive items (`source_n`, `piece`).
- `reframe` (input of `tools/reframe.py`, optional): `{"anchor": "auto"|"top"|"center"|"bottom",
  "rotation": 0|90|-90|180, "subject": "person"|..., "off": true, "props": {...}}`. See
  `reference/reframe.md`.
- Durations: the total is the sum of `out_s - in_s` minus half of each dissolve. Check it against
  the requested length before building.
- For a modification, list the current timeline as an edit list first (from R1 + `match_clips`),
  then show the user the changed lines (added, removed, trimmed, reordered).
