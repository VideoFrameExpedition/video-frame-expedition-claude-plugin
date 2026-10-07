# run_script templates (tested in DaVinci Resolve Studio 21.1, Windows)

Copy a template, change only the `PARAMS` line, send it to `run_script` of DaVinci Resolve's MCP
server (`timeout` up to 60). Keep the whole script ASCII: inside `PARAMS`, write non-ASCII characters as
`\\u00e9` (the JSON escape, doubled because it sits in a Python string). Every template returns a
small `result` dict or `{"error": ...}`.

The paths in the examples are Windows ones. On macOS, write them the way Resolve shows them there
(`/Volumes/Rushs/Lake/...`, `/Users/me/Movies/...`); the templates themselves do not change.

Common helpers (paste at the top of the templates that need them):

```python
import json

def find_timeline(proj, uid=None, name=None):
    """By unique id (ASCII, stable: prefer it), else by name, else the current timeline."""
    if not uid and not name:
        return proj.GetCurrentTimeline()
    for i in range(1, proj.GetTimelineCount() + 1):
        t = proj.GetTimelineByIndex(i)
        if (uid and t.GetUniqueId() == uid) or (not uid and t.GetName() == name):
            return t
    return None

def all_clips(folder, found):
    found.extend(folder.GetClipList() or [])
    for sub in folder.GetSubFolderList() or []:
        all_clips(sub, found)
    return found

def norm(path):
    return str(path).replace("/", "\\").casefold()

def find_clip(mp, uid=None, path=None):
    for c in all_clips(mp.GetRootFolder(), []):
        if uid and c.GetUniqueId() == uid:
            return c
        if path and norm(c.GetClipProperty().get("File Path") or "") == norm(path):
            return c
    return None
```

## R1 — read a timeline

Returns the ids to keep (`project_uid`, `timeline_uid`, per item `item_uid` and `clip_uid`) and each
clip's source range in **seconds of the file** (`src_in_s`/`src_out_s`: `GetLeftOffset()` and
`GetDuration()` over the timeline's fps, since both count TIMELINE frames). They stay right when
the clip's frame rate differs from the timeline's (a 30 fps clip in a 24 fps timeline, placed from
its frame 135: `GetLeftOffset()` 108) and when a dissolve touches the clip
(`GetSourceStartTime()`/`GetSourceEndTime()` add its handles). The frame form, in clip frames, is
kept for AppendToTimeline-style work: `src_in` = `round(GetLeftOffset() * clip_fps / timeline_fps)`,
`src_out` = `src_in + round(GetDuration() * clip_fps / timeline_fps)` (within a frame when the
rates differ). `handles` stay in timeline frames, like a transition's duration.

```python
import json
PARAMS = json.loads('{"timeline_uid": null, "timeline": null}')  # both null = current timeline

def find_timeline(proj, uid=None, name=None):
    if not uid and not name:
        return proj.GetCurrentTimeline()
    for i in range(1, proj.GetTimelineCount() + 1):
        t = proj.GetTimelineByIndex(i)
        if (uid and t.GetUniqueId() == uid) or (not uid and t.GetName() == name):
            return t
    return None

try:
    proj = resolve.GetProjectManager().GetCurrentProject()
    tl = find_timeline(proj, PARAMS["timeline_uid"], PARAMS["timeline"])
    if tl is None:
        raise RuntimeError("timeline not found")
    s = tl.GetSettings()
    tl_fps = float(s.get("timelineFrameRate") or 0)
    cur = proj.GetCurrentTimeline()
    is_open = cur is not None and cur.GetUniqueId() == tl.GetUniqueId()  # track switches: open one only
    out = {"project": proj.GetName(), "project_uid": proj.GetUniqueId(), "timeline": tl.GetName(),
           "timeline_uid": tl.GetUniqueId(), "fps": tl_fps, "start_frame": tl.GetStartFrame(),
           "start_tc": tl.GetStartTimecode(), "width": int(s.get("timelineResolutionWidth")),
           "height": int(s.get("timelineResolutionHeight")), "items": []}
    for kind in ("video", "audio"):
        for ti in range(1, tl.GetTrackCount(kind) + 1):
            for it in tl.GetItemListInTrack(kind, ti) or []:
                row = {"kind": kind, "track": ti, "type": it.GetType(), "name": it.GetName(),
                       "item_uid": it.GetUniqueId(), "rec_in": it.GetStart(), "rec_out": it.GetEnd(),
                       "enabled": it.GetClipEnabled(), "track_enabled": tl.GetIsTrackEnabled(kind, ti) if is_open else None}
                mpi = it.GetMediaPoolItem() if it.GetType() in ("video", "audio") else None
                if mpi is not None:
                    p = mpi.GetClipProperty()
                    clip_fps = float(p.get("FPS") or 0)
                    left = it.GetLeftOffset()  # TIMELINE frames, like GetDuration
                    ratio = clip_fps / tl_fps if clip_fps and tl_fps else 1.0
                    in_s = left / tl_fps if tl_fps else 0.0
                    src_in = int(round(left * ratio))
                    row.update({"clip_uid": mpi.GetUniqueId(), "file_path": p.get("File Path"),
                                "clip_type": p.get("Type"), "clip_fps": clip_fps,
                                "resolution": p.get("Resolution"),
                                "src_in_s": round(in_s, 4),
                                "src_out_s": round(in_s + it.GetDuration() / tl_fps, 4) if tl_fps else None,
                                "src_in": src_in, "src_out": src_in + int(round(it.GetDuration() * ratio)),
                                "handles": [it.GetLeftOffset(), it.GetRightOffset()]})
                    if kind == "video":
                        pr = it.GetProperties()
                        row["transform"] = {k: pr.get(k) for k in ("ZoomX", "ZoomY", "Pan", "Tilt", "Scaling")}
                out["items"].append(row)
    result = out
except Exception as ex:
    result = {"error": ascii(str(ex))}
```

Then, for the video items: `match_clips(items=[{"file_path": row.file_path, "clip_uid": row.clip_uid,
"source_start_s": row.src_in_s, "source_end_s": row.src_out_s} ...])`. Items whose media pool type is
a compound clip, a multicam clip or a timeline have no file path: their content is not matched.

## M1 — list the media pool (ids, paths, fps, frames, resolution)

```python
import json
try:
    proj = resolve.GetProjectManager().GetCurrentProject()
    def walk(folder, bin_path, out):
        for c in folder.GetClipList() or []:
            p = c.GetClipProperty()
            out.append({"uid": c.GetUniqueId(), "name": c.GetName(), "bin": bin_path,
                        "path": p.get("File Path"), "fps": p.get("FPS"), "frames": p.get("Frames"),
                        "resolution": p.get("Resolution"), "start_tc": p.get("Start TC")})
        for sub in folder.GetSubFolderList() or []:
            walk(sub, bin_path + "/" + sub.GetName(), out)
        return out
    result = {"clips": walk(proj.GetMediaPool().GetRootFolder(), "", [])}
except Exception as ex:
    result = {"error": ascii(str(ex))}
```

To import a file that is not in the media pool yet: `proj.GetMediaPool().ImportMedia([path])`
with the path decoded from an escaped JSON string (never a raw accented literal).

## B1 — build a new timeline from an edit list

`items`: `uid` (preferred) or `path`, `in_s`, `out_s` (seconds of the source file, from
`get_cut_points`), optional `video_only`, optional `props` (from `get_reframe`).

```python
import json
PARAMS = json.loads('{"timeline": "Montage - vfe v1", "width": null, "height": null, "items": ['
                    '{"uid": "0f444227-9aa1-4d01-832e-d6a312908b46", "in_s": 4.006, "out_s": 6.006},'
                    '{"path": "C:\\\\Users\\\\me\\\\Videos\\\\Lake\\\\caf\\u00e9 terrace.mp4", "in_s": 6.0, "out_s": 8.0,'
                    ' "props": {"ZoomX": 1.2, "ZoomY": 1.2, "Pan": 0.0, "Tilt": 0.0}}]}')

def all_clips(folder, found):
    found.extend(folder.GetClipList() or [])
    for sub in folder.GetSubFolderList() or []:
        all_clips(sub, found)
    return found

def find_clip(mp, uid=None, path=None):
    for c in all_clips(mp.GetRootFolder(), []):
        if uid and c.GetUniqueId() == uid:
            return c
        if path and str(c.GetClipProperty().get("File Path") or "").replace("/", "\\").casefold() == path.replace("/", "\\").casefold():
            return c
    if path:
        got = mp.ImportMedia([path])
        return got[0] if got else None
    return None

try:
    pm = resolve.GetProjectManager()
    proj = pm.GetCurrentProject()
    mp = proj.GetMediaPool()
    tl = mp.CreateEmptyTimeline(PARAMS["timeline"])
    if tl is None:
        raise RuntimeError("timeline name already used")
    proj.SetCurrentTimeline(tl)
    out = {"timeline": tl.GetName()}
    if PARAMS.get("width") and PARAMS.get("height"):
        tl.SetSettings({"useCustomSettings": "1", "timelineResolutionWidth": str(PARAMS["width"]),
                        "timelineResolutionHeight": str(PARAMS["height"])})
    s = tl.GetSettings()
    out["size"] = [s.get("timelineResolutionWidth"), s.get("timelineResolutionHeight"), s.get("timelineFrameRate")]
    tl_fps = float(s.get("timelineFrameRate"))
    infos, wanted = [], []
    for e in PARAMS["items"]:
        clip = find_clip(mp, e.get("uid"), e.get("path"))
        if clip is None:
            raise RuntimeError("clip not found: " + ascii(e.get("uid") or e.get("path")))
        fps = float(clip.GetClipProperty().get("FPS"))
        info = {"mediaPoolItem": clip, "startFrame": int(round(e["in_s"] * fps)),
                "endFrame": int(round(e["out_s"] * fps))}
        if e.get("video_only"):
            info["mediaType"] = 1
        infos.append(info)
        # the timeline counts its own frames: a 30 fps clip in a 24 fps timeline is shorter in frames
        wanted.append(int(round((info["endFrame"] - info["startFrame"]) * tl_fps / fps)))
    for i in range(0, len(infos), 50):
        mp.AppendToTimeline(infos[i:i + 50])
    items = [it for it in tl.GetItemListInTrack("video", 1) if it.GetType() == "video"]
    out["items"] = []
    for it, e, n in zip(items, PARAMS["items"], wanted):
        ok = it.SetProperties(e["props"]) if e.get("props") else None
        out["items"].append({"rec": [it.GetStart(), it.GetEnd()],
                             "src_in_s": round(it.GetLeftOffset() / tl_fps, 3),
                             "dur": it.GetDuration(), "dur_ok": abs(it.GetDuration() - n) <= 1, "props_ok": ok})
    out["count_ok"] = len(items) == len(PARAMS["items"])
    result = out
except Exception as ex:
    result = {"error": ascii(str(ex))}
```

## B2 — build + transforms in one call (written by tools/reframe.py)

`tools/reframe.py` writes one `b2_<k>.py` per batch of 40 items: send them **unchanged**, in order.
PARAMS: `timeline` (name), `create` (true for the first batch: fails if the name exists; later
batches find the timeline by name), `size` (`[width, height]` of the edit list's `format`: set on
the new timeline, read back, and a batch stops before appending anything when the timeline has
another size), `u` (media pool uids), `it` (`[uid index, in_s, out_s]`, seconds
of the file), `props` (`[index in the batch, zoom, pan, tilt, rotation]`). It appends video + linked
audio, clamps the out point to the clip's `Frames`, sets `ZoomX/ZoomY/Pan/Tilt/RotationAngle`,
reads them back, and returns `bad_durations` and `prop_fails` (both must be empty). Tested
with 28 items of 4K footage: one call, well under the 60 s limit.
To use it by hand, copy a generated file and change PARAMS only.

## T1 — cross-dissolves between items (video + matching audio)

`cuts`: 1-based indexes of the **incoming** video items (on track 1) that get a dissolve, and the
duration in frames. Everything else stays a cut.

```python
import json
PARAMS = json.loads('{"timeline_uid": null, "timeline": null, "cuts": [2], "frames": 15, "audio": true}')
try:
    pm = resolve.GetProjectManager()
    proj = pm.GetCurrentProject()
    tl = proj.GetCurrentTimeline()
    for i in range(1, proj.GetTimelineCount() + 1):
        t = proj.GetTimelineByIndex(i)
        if (PARAMS["timeline_uid"] and t.GetUniqueId() == PARAMS["timeline_uid"]) or (
                not PARAMS["timeline_uid"] and PARAMS["timeline"] and t.GetName() == PARAMS["timeline"]):
            tl = t
    video = [it for it in tl.GetItemListInTrack("video", 1) if it.GetType() == "video"]
    out = {"done": [], "skipped": []}
    for idx in PARAMS["cuts"]:
        if idx < 2 or idx > len(video):
            out["skipped"].append([idx, "no previous item"])
            continue
        prev, cur = video[idx - 2], video[idx - 1]
        d = int(PARAMS["frames"])
        half = (d + 1) // 2
        room = min(prev.GetRightOffset(), cur.GetLeftOffset())
        if room < half:
            d = 2 * room
        if d < 4 or prev.GetEnd() != cur.GetStart():
            out["skipped"].append([idx, "not enough handles or not adjacent"])
            continue
        opts = {"category": "simple", "type": "Cross Dissolve", "position": "start",
                "alignment": "center", "duration": d}
        t = cur.AddTransition(opts)
        row = [idx, d, t is not None]
        if PARAMS.get("audio"):
            for a in cur.GetLinkedItems() or []:
                if a.GetType() == "audio":
                    ta = a.AddTransition({"category": "audio", "type": "Cross Fade +3 dB",
                                          "position": "start", "alignment": "center", "duration": d})
                    row.append(ta is not None)
        out["done"].append(row)
    out["track"] = [[x.GetType(), x.GetStart(), x.GetEnd()] for x in tl.GetItemListInTrack("video", 1)]
    result = out
except Exception as ex:
    result = {"error": ascii(str(ex))}
```

## X1 — set transform values on items (reframe)

```python
import json
PARAMS = json.loads('{"timeline_uid": null, "timeline": null, "items": [{"index": 1, "props": {"ZoomX": 3.1605, "ZoomY": 3.1605, "Pan": -30.0, "Tilt": 0.0}}]}')
try:
    pm = resolve.GetProjectManager()
    proj = pm.GetCurrentProject()
    tl = proj.GetCurrentTimeline()
    for i in range(1, proj.GetTimelineCount() + 1):
        t = proj.GetTimelineByIndex(i)
        if (PARAMS["timeline_uid"] and t.GetUniqueId() == PARAMS["timeline_uid"]) or (
                not PARAMS["timeline_uid"] and PARAMS["timeline"] and t.GetName() == PARAMS["timeline"]):
            tl = t
    video = [it for it in tl.GetItemListInTrack("video", 1) if it.GetType() == "video"]
    mode = proj.GetSettings().get("timelineInputResMismatchBehavior")
    out = {"project_scaling": mode, "set": []}
    for e in PARAMS["items"]:
        it = video[e["index"] - 1]
        scaling = it.GetProperties().get("Scaling")
        ok = it.SetProperties(e["props"])
        out["set"].append({"index": e["index"], "ok": ok, "item_scaling": scaling,
                           "now": {k: it.GetProperties().get(k) for k in ("ZoomX", "ZoomY", "Pan", "Tilt")}})
    result = out
except Exception as ex:
    result = {"error": ascii(str(ex))}
```

`get_reframe` values assume Fit: item `Scaling` 0 (= project) with project `scaleToFit`.

## V1 — export stills to check framing (then open them with Read)

**One or two checks only, never in a loop.** In one test, 9 stills after a Resolve restart timed
out the script. After that, no script answered any more (even `GetCurrentPage()`), until the user
cleared Resolve, and the `SetProperties` of that call were lost. To check many framings, use the
review sheets of `tools/reframe.py` instead: no Resolve needed.
The folder must exist (create it first with a shell command); ASCII path, ending with the
separator (`/tmp/vfe-stills/` on macOS).

```python
import json
PARAMS = json.loads('{"folder": "C:\\\\Users\\\\me\\\\AppData\\\\Local\\\\Temp\\\\vfe-stills\\\\", "timecodes": ["01:00:01:00", "01:00:03:00"]}')
try:
    proj = resolve.GetProjectManager().GetCurrentProject()
    tl = proj.GetCurrentTimeline()
    resolve.OpenPage("color")
    out = {}
    for i, tc in enumerate(PARAMS["timecodes"], 1):
        tl.SetCurrentTimecode(tc)
        out[tc] = proj.ExportCurrentFrameAsStill(PARAMS["folder"] + "still_%02d.png" % i)
    resolve.OpenPage("edit")
    result = out
except Exception as ex:
    result = {"error": ascii(str(ex))}
```

Pick timecodes in the middle of each item: `rec_in + (rec_out - rec_in) // 2` frames, converted
with the timeline fps and start (`01:00:00:00` = `GetStartFrame()`), or use
`tl.GetCurrentTimecode()` after `tl.SetCurrentTimecode()` to check.

## D1 — duplicate a timeline before modifying it

```python
import json
PARAMS = json.loads('{"source_uid": "f50b89b8-f303-4025-88a4-105627347b2d", "source": null, "copy": "My edit - vfe v1"}')
try:
    pm = resolve.GetProjectManager()
    proj = pm.GetCurrentProject()
    src = None
    for i in range(1, proj.GetTimelineCount() + 1):
        t = proj.GetTimelineByIndex(i)
        if (PARAMS["source_uid"] and t.GetUniqueId() == PARAMS["source_uid"]) or (
                not PARAMS["source_uid"] and t.GetName() == PARAMS["source"]):
            src = t
    if src is None:
        raise RuntimeError("timeline not found")
    proj.SetCurrentTimeline(src)
    dup = src.DuplicateTimeline(PARAMS["copy"])
    if dup is None:
        raise RuntimeError("duplicate failed (name used?)")
    proj.SetCurrentTimeline(dup)
    result = {"current": proj.GetCurrentTimeline().GetName(), "uid": dup.GetUniqueId()}
except Exception as ex:
    result = {"error": ascii(str(ex))}
```

The copy has a new timeline uid and new item uids; its media pool clips (`clip_uid`) are the
same. Ripple-remove an item and its sound on the copy:
`tl.DeleteClips([item] + list(item.GetLinkedItems() or []), True)` (its transitions go with it).
