# DaVinci Resolve Studio 21.1 — calibrated facts

Observed in DaVinci Resolve Studio 21.1 on Windows (measured on 21.1.0 and 21.1.1), with the native MCP
`run_script`, on 3840×2160 phone and Resolve-exported clips, in test projects. Each point gives the
behaviour seen and the way to work with it; later versions may behave differently. Canonical 21.1
forms only: `GetSettings()`/`SetSettings({})`,
`GetProperties()`/`SetProperties({})`, `GetClipProperty()[key]`, `SetMetadata({})`,
`AppendToTimeline([{clipInfo}])`.

## run_script transport and sandbox
- Non-ASCII characters in the **script text** are corrupted: `ImportMedia([r"...\café.mp4"])`
  imported nothing, silently. Decode them inside Python: `json.loads('"caf\\u00e9.mp4"')`.
- Output is fine: names and paths come back correctly (JSON-escaped).
- No `globals()`, `os`, `sys`, `pathlib`, `open`. `resolve` and `project` are predefined.
- A traceback containing non-ASCII text crashes the sandbox's traceback printer (`NameError: _os`):
  catch exceptions yourself and return `ascii(str(ex))`.
- Timeout 10 s by default, 60 s max; no state between calls.
- `launch_resolve` gives up after 60 s; Resolve can need several minutes to start. Poll
  `get_resolve_status`.

## Timelines
- New project at 29.97: timeline start frame 108000 (01:00:00:00). Always use `tl.GetStartFrame()`.
- `mp.CreateEmptyTimeline(name)` returns None if the name exists.
- Custom size: `tl.SetSettings({'useCustomSettings': '1', 'timelineResolutionWidth': '1080',
  'timelineResolutionHeight': '1920', ...})` applied the resolution but returned False (the frame
  rate part is refused once media exists). Read `GetSettings()` back.
- `AppendToTimeline([{mediaPoolItem, startFrame, endFrame}])`: `endFrame` exclusive (0→24 = 24
  frames); sequential appends go end to end on track 1; no `mediaType` = video + linked audio,
  `mediaType: 1` = video only.
- `tl.DuplicateTimeline(name)` returns the copy and makes it current; the original is untouched.
- `tl.DeleteClips([item] + item.GetLinkedItems(), True)` ripple-deletes the item, its audio and its
  transitions.
- `GetItemListInTrack('video', 1)` lists transitions too (`GetType() == 'transition'`, name
  `Cross Dissolve`, no media pool item).

## Source ranges of timeline items
- `GetLeftOffset()`, `GetDuration()` and `GetRightOffset()` count **timeline** frames (whole
  frames). At the clip's own rate they are its frames too: `GetLeftOffset()` = source in-frame
  (0 = file's first frame) and the three add up to the clip's `Frames`. At another rate they are
  not: in a 24 fps timeline, a 30 fps clip placed from source frame 135 to 285 (4.5–9.5 s) read
  `GetLeftOffset()` 108, `GetDuration()` 120, `GetRightOffset()` 88 (its 396 frames = 316.8
  timeline frames), and a 29.97 fps clip placed from source frame 1491 read 1193 (= 1491 × 24 /
  29.97, truncated) (21.1.1). A 26 fps clip of 98 frames in a 29.97 timeline has `GetDuration()` 112.
- Best for the analyses: seconds of the file = `GetLeftOffset()` / timeline fps, out = that +
  `GetDuration()` / timeline fps (template R1: `src_in_s`/`src_out_s`), within one timeline frame;
  matches ffprobe's frame times (checked: 4.004–10.010 s for left 120, duration 180, clip and
  timeline at 29.97). In clip frames: in = `round(GetLeftOffset() × clip_fps / timeline_fps)`,
  out = in + `round(GetDuration() × clip_fps / timeline_fps)`.
- `AppendToTimeline` `startFrame`/`endFrame` are **clip** frames, whatever the timeline's rate.
- `GetSourceStartTime()` / `GetSourceEndTime()` are NOT the cut: they add the handles a transition
  blends in (7–8 frames each side for a 15-frame Cross Dissolve) and count the clip's `Start TC`
  as its frame count over the real rate (01:02:01:17 at 29.97 = 111647 / 29.97 = 3725.29 s, not
  3721.57 s). Right only without transitions and with that conversion.
- `GetSourceStartFrame()` returned 119 for an item starting at source frame 120 on a clip with a
  start timecode (01:02:01:17); correct on clips starting at 00:00:00:00. Don't use it.
- `GetSourceEndFrame()` inconsistent (inclusive on one clip, exclusive on another). Don't use it.
- Clip `FPS` for a phone's variable-frame-rate clip: 29.97 (ffprobe average 30) — convert seconds
  with Resolve's.

## Track switches
- `Timeline.GetIsTrackEnabled()` answers **False for every track of a timeline that is not the
  current one** (21.1.0.17: every closed timeline of a test project answered False, the open one
  True). Trust it only on `GetCurrentTimeline()`; elsewhere the state is unknown (R1
  returns `track_enabled: null`). `TimelineItem.GetClipEnabled()` is right on every timeline.

## Identities
- `GetUniqueId()` on a project, a timeline, a timeline item and a media pool item: ASCII uuids, the
  safest way to find things again in a script (names can carry accents).
- `DuplicateTimeline` gives the copy (and its items) new ids; the media pool clips keep theirs.
- The media pool uid is per project: use a stored one only when the link's project id equals
  `resolve.GetProjectManager().GetCurrentProject().GetUniqueId()`.
- Our markers script writes our video id into each clip's third-party metadata
  (`GetThirdPartyMetadata('vfe_video_id')`); the application reads it back as a link hint.

## Transitions
- `item.AddTransition({'type': 'Cross Dissolve', 'category': 'simple', 'position': 'start',
  'alignment': 'center', 'duration': 15})` on the incoming video item → centred on the cut
  (8 frames before, 7 after). Returns the transition item or None.
- Audio: same on the incoming **audio** item with `{'type': 'Cross Fade +3 dB', 'category': 'audio'}`.
- Handles needed: about `duration/2` on each side (outgoing `GetRightOffset()`, incoming
  `GetLeftOffset()`).

## Transform (reframe)
- `SetProperties({'ZoomX': 2.0, 'ZoomY': 2.0, 'Pan': 480.0})` → True. Zoom 1.0 = 100 %.
- Pan/Tilt in **timeline pixels**: +480 Pan moved the picture 480 px to the **right** on a
  1920-wide timeline; +270 Tilt moved it **up** 270 px (checked on exported stills).
- Default project `timelineInputResMismatchBehavior` = `scaleToFit`; item `Scaling` 0 = project.
- Centre a subject at (u, v) (v downwards) with the clip scaled to fit: `Pan = -(u-0.5)·w·s0·Z`,
  `Tilt = +(v-0.5)·h·s0·Z`, `s0 = min(W/w, H/h)`. `get_reframe` does this (and the clamping).
  3840×2160 on 1080×1920 needs Zoom ≥ 3.1605 to fill.
- No keyframe API for transforms: a moving subject → several items with their own values.
- `RotationAngle` (degrees) in `SetProperties` → True, and read back. 180 turns an upside-down
  phone clip upright; Pan/Tilt keep their on-screen meaning (+Tilt still moves the picture up), so
  the source-space Tilt of a crop is negated. -90 turned a 2160×3840 clip filmed sideways (scene's
  top on the picture's left) upright. With Zoom 1.7778 (= max(W/(h·fit), H/(w·fit))) it fills
  1920×1080 exactly (checked on stills).
- Tilt of a full-width 16:9 band in a vertical clip: `(v − 0.5) × 3413.3` for both 2160×3840 and
  1080×1920 in 1920×1080 (v = band centre, 0–1 from the top), limits ±1166.7.
- Keyframes of the analyses are ~2 s apart: always check with stills and nudge.

## Stills (visual checks)
- **Do not loop.** 9 stills in one script, just after a Resolve restart, hit the 60 s timeout. Resolve
  then answered no script at all (15–30 s timeouts on `GetCurrentPage()`) until the user dealt
  with it. The transforms set earlier in that call were lost after the restart (4K HDR10 clips,
  a vision model sharing the graphics card). Use the review sheets of `tools/reframe.py`.
- `resolve.OpenPage('color')`, `tl.SetCurrentTimecode('01:00:01:00')`,
  `proj.ExportCurrentFrameAsStill(path)` → True; returns False when the folder does not exist.
  Output is the timeline frame (1920×1080 or 1080×1920 PNG, ~6 MB).

## Markers and metadata (media pool clips)
- `AddMarker(frame, color, name, note, duration, customData)`: frame 0-based from the clip start;
  fractional frames are truncated; returns False if a marker already sits on that frame.
- `DeleteMarkerByCustomData(cd)` deletes one marker per call: loop.
- `SetMetadata({'Description': ..., 'Keywords': 'a, b'})` and `SetThirdPartyMetadata({...})` → True.
- The fixed script from `get_resolve_payload` handles all of this; use it as is.

## Other
- `Timeline.GetSelectedClips()` exists (21.0.4+): use it when the user speaks of « the selected
  clips ».
- Compound clips, multicam clips and nested timelines have no `File Path`: their media pool item
  `Type` says so; `MediaPoolItem.GetTimeline()` returns a nested timeline's own timeline.
- The application (Video Frame Expedition) reads Resolve itself through external scripting
  (preference « External scripting using: Local », or Network for Resolve on another computer;
  Studio only) in a child process. It writes only when asked: the user's « Create a timeline »
  (a new timeline of ticked videos) and its Resolve tools for the assistant (new timelines,
  markers). Files missing from the media pool are imported into the bin « Video Frame
  Expedition ». A timeline named like that may come from it.
- `mp.ImportMedia([path])` works inside the sandbox (the path string must be correct). The dict
  form `ImportMedia([{"FilePath": path}])`, called by the application's external script,
  returns nothing and imports nothing (bin read back: 0 clips): use the
  plain list. `AppendToTimeline([{"mediaPoolItem": clip}])` works (picture and linked sound).
- Markers a media pool clip has when it is appended are copied onto its timeline items (video
  and audio; `TimelineItem.GetMarkers()` shows them, in TIMELINE frames: a 24 fps clip's 2849
  is 3557 in a 29.97 timeline); markers added to the clip afterwards are not.
- Timeline files: FCPXML, FCP 7 XML and EDL exports carry no clip markers, and an FCPXML's
  `<marker>` are ignored on import; OTIO carries them (source time at the timeline's rate, color
  `BLUE`, note in `metadata.Resolve_OTIO.Note`). No timeline format carries subtitle tracks.
- Subtitles by script: `ImportMedia([path.srt])` makes a « Subtitle »
  clip. `AppendToTimeline([{"mediaPoolItem": srt}])` needs a subtitle track (`AddTrack
  ("subtitle")` first, else nothing) and lays the captions on the ENABLED subtitle track (none
  enabled or locked: lost; several: unreliable, so enable the target alone); `trackIndex` and
  `recordFrame` are ignored. Where: the end of that track, and of picture and sound only when
  a video was appended just before (after another subtitle clip, its own track's end); SRT times
  kept from there. NEVER pass `startFrame`/`endFrame` for a subtitle clip: Resolve 21.1 aborts
  (SIGABRT). A new track is added disabled while another is enabled; `AddTrack("subtitle",
  {"index": 1})` (undocumented) inserts one first. Recipe used: timeline-time SRTs laid on the
  empty timeline, one track each, then the videos by `recordFrame` (honoured for video).
  `ImportMedia` of a file the pool has hands back the OLD clip (old text); `DeleteClips` it
  first (timelines keep their captions). Subtitle items: `GetType()` "generator", name = the
  caption (line breaks as U+2028). The API has no other subtitle call than
  `Timeline.CreateSubtitlesFromAudio` (Resolve's own transcription).
- « Create a timeline » writes each video's subtitles next to it: `<name>_<LANG>.srt` (speech)
  and `<name>_SHOTS_<LANG>.srt` (shots), in the video's own time; never over a file the
  application did not write. It lays the timeline's own (data folder) in Resolve; for Resolve on
  another computer, from next to the timeline's first video (`<timeline>_TIMELINE_<LANG>.srt`,
  through the folder pairs; the share must be writable).
- Resolve on another computer: its firewall must let in `fuscript.exe` (port 1144) AND
  `Resolve.exe` (a port picked at each start). On Windows, the rules Resolve installs hold for
  « private » networks only (a network marked « public » is not covered): port 1144 open alone
  still gives « connection refused ».
- An MP4's chapter track is read on import as blue one-frame clip markers (« Start » at 0,
  then each chapter's title).
