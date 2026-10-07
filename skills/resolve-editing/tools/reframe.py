"""Reframe an edit list for a timeline of another shape: static crops from the subject's boxes.

    python reframe.py EDIT_LIST.json OUT_DIR [--width 1920 --height 1080] [--subject mammal]
                      [--min-piece 3] [--keep 0.75] [--flag 0.6] [--batch 40] [--no-images]

Input: an edit list (reference/edit-list.md): items with ``video_id``, ``uid`` (media pool id),
``in_s``, ``out_s``, and optionally ``reframe`` = {"subject", "anchor", "rotation", "off",
"props"}. Output in OUT_DIR:

- ``plan.json``: the items cut into pieces, each with its Resolve ``props`` (ZoomX, ZoomY, Pan,
  Tilt, RotationAngle), the coverage of the subject at every keyframe, and ``flags``;
- ``b2_<k>.py``: ready-to-send ``run_script`` scripts (template B2) that build the timeline and
  apply the transforms, one batch each, in order;
- ``review.json`` + ``kf/*.jpg``: the keyframes of every reframed piece with its crop, for
  ``review_sheet.ps1`` on Windows or ``review_sheet.js`` on macOS (contact sheets to look at
  with Read).

Method (reference/reframe.md): Video Frame Expedition gives the subject's box at each keyframe
(``get_reframe``, about every 2 s). A subject bigger than the crop is aimed at by its top part
(the head of an upright animal or person) unless ``anchor`` says otherwise; one crop is kept as
long as every keyframe keeps at least ``keep`` of its target inside; pieces shorter than
``min-piece`` seconds and moves smaller than 150 timeline pixels are merged. Values follow the
application's formula (domain/framing.py): item scaled to Fit, Pan/Tilt in timeline pixels.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vfe_client import Client, ToolError

TARGET = 0.8  # share of the crop kept for the part of a subject bigger than the crop
MIN_JUMP_PX = 150.0  # timeline pixels: smaller moves between pieces are merged
GRID = 61  # positions tried along each free side


def fill_size(w: float, h: float, aspect: float) -> tuple[float, float]:
    """The largest ``aspect`` rectangle inside a w × h picture (as the application)."""
    return (h * aspect, h) if w / h > aspect else (w, w / aspect)


def target(box, w, h, cw, ch, anchor):
    """The part of the subject the crop must keep, in source pixels."""
    x1, y1, x2, y2 = box[0] * w, box[1] * h, box[2] * w, box[3] * h
    if x2 - x1 > cw:
        c = (x1 + x2) / 2
        x1, x2 = c - TARGET * cw / 2, c + TARGET * cw / 2
    if y2 - y1 > ch:
        if anchor == "center":
            c = (y1 + y2) / 2
            y1, y2 = c - TARGET * ch / 2, c + TARGET * ch / 2
        elif anchor == "bottom":
            y1 = y2 - TARGET * ch
        else:  # "top" / "auto": the head of an upright subject
            y2 = y1 + TARGET * ch
    return x1, y1, x2, y2


def coverage(region, x, y, cw, ch):
    x1, y1, x2, y2 = region
    area = (x2 - x1) * (y2 - y1)
    if area <= 0:
        return 1.0
    iw = min(x2, x + cw) - max(x1, x)
    ih = min(y2, y + ch) - max(y1, y)
    return max(0.0, iw) * max(0.0, ih) / area


def best_position(regions, w, h, cw, ch, prefer=None):
    """Crop origin (x, y) keeping the most of the regions: best mean coverage, then best minimum,
    then closest to the regions' centre (or to ``prefer``, the previous piece)."""
    xs = [0.0] if w - cw < 1 else [(w - cw) * i / (GRID - 1) for i in range(GRID)]
    ys = [0.0] if h - ch < 1 else [(h - ch) * i / (GRID - 1) for i in range(GRID)]
    cx = sum((r[0] + r[2]) / 2 for r in regions) / len(regions)
    cy = sum((r[1] + r[3]) / 2 for r in regions) / len(regions)
    scored = []
    for x in xs:
        for y in ys:
            covs = [coverage(r, x, y, cw, ch) for r in regions]
            scored.append((sum(covs) / len(covs), min(covs), x, y))
    top_mean = max(s[0] for s in scored)
    pool = [s for s in scored if s[0] >= top_mean - 0.01]
    top_min = max(s[1] for s in pool)
    pool = [s for s in pool if s[1] >= top_min - 0.01]
    px, py = prefer if prefer else (cx - cw / 2, cy - ch / 2)
    choice = min(pool, key=lambda s: (s[2] - px) ** 2 + (s[3] - py) ** 2)
    return (choice[2], choice[3]), choice[0], choice[1]


def transform(x, y, w, h, cw, ch, W, H, rotation):
    s = W / cw
    fit = min(W / w, H / h)
    props = {
        "ZoomX": round(s / fit, 4),
        "ZoomY": round(s / fit, 4),
        "Pan": round(-(x + cw / 2 - w / 2) * s, 1) + 0.0,
        "Tilt": round((y + ch / 2 - h / 2) * s, 1) + 0.0,
        "RotationAngle": 0.0,
    }
    if rotation == 180:
        props["Pan"], props["Tilt"], props["RotationAngle"] = (
            -props["Pan"] + 0.0,
            -props["Tilt"] + 0.0,
            180.0,
        )
    return props


def plan_item(client, item, W, H, subject, min_piece, keep, flag):
    """Pieces of one item: [{in_s, out_s, props, kf: [{t_s, cov, crop}], flags}]."""
    opts = item.get("reframe") or {}
    a, b = float(item["in_s"]), float(item["out_s"])
    if opts.get("off"):
        return [{"in_s": a, "out_s": b, "props": None, "flags": []}]
    if opts.get("props"):
        return [
            {"in_s": a, "out_s": b, "props": dict(opts["props"]), "flags": ["manual"]}
        ]
    rotation = int(opts.get("rotation", 0))
    anchor = opts.get("anchor", "auto")
    if (
        rotation == 180
    ):  # the boxes are in the upside-down picture: the head is at its bottom
        anchor = {"auto": "bottom", "top": "bottom", "bottom": "top"}.get(
            anchor, anchor
        )
    args = {
        "video_id": item["video_id"],
        "t_start": a,
        "t_end": b,
        "timeline_width": W,
        "timeline_height": H,
    }
    subj = opts.get("subject", subject)
    answer, flags = None, []
    for attempt in ([dict(args, subject=subj)] if subj else []) + [args]:
        try:
            answer = client.call("get_reframe", attempt)
            break
        except ToolError:
            if subj and "subject" in attempt:
                flags.append(
                    "other_subject"
                )  # none of `subject` here: the main subject instead
    if (
        answer is None
    ):  # no subject at all: the picture's size from the manifest, crop centred
        try:
            manifest = client.call("get_video", {"video_id": item["video_id"]})
            size = re.search(
                r"(\d{3,5})\s*×\s*(\d{3,5})",
                manifest if isinstance(manifest, str) else "",
            )
        except ToolError:
            size = None
        if not size:
            return [{"in_s": a, "out_s": b, "props": None, "flags": ["no_answer"]}]
        answer = {
            "width": float(size.group(1)),
            "height": float(size.group(2)),
            "keyframes": [],
        }
        flags = ["no_subject"]
    w, h = float(answer["width"]), float(answer["height"])
    if rotation in (90, -90):
        fit = min(W / w, H / h)
        zoom = round(max(W / (h * fit), H / (w * fit)), 4)
        return [
            {
                "in_s": a,
                "out_s": b,
                "flags": ["rotated_90"],
                "props": {
                    "ZoomX": zoom,
                    "ZoomY": zoom,
                    "Pan": 0.0,
                    "Tilt": 0.0,
                    "RotationAngle": float(rotation),
                },
                "size": [w, h],
            }
        ]
    cw, ch = fill_size(w, h, W / H)
    if cw >= w - 1 and ch >= h - 1 and rotation == 0:  # same shape as the timeline
        return [{"in_s": a, "out_s": b, "props": None, "flags": []}]
    kfs = sorted(
        (
            {"t": float(k["t_s"]), "box": k["box"]}
            for k in answer.get("keyframes") or []
            if k.get("box")
        ),
        key=lambda k: k["t"],
    )
    inside = [k for k in kfs if a - 0.5 <= k["t"] <= b + 0.5]
    if (
        len(inside) >= 2
    ):  # the application adds the keyframe before the range: only when needed
        kfs = inside
    if not kfs:
        x, y = (w - cw) / 2, (h - ch) / 2
        return [
            {
                "in_s": a,
                "out_s": b,
                "props": transform(x, y, w, h, cw, ch, W, H, rotation),
                "kf": [],
                "crop": [x / w, y / h, cw / w, ch / h],
                "flags": flags + ["no_subject"],
                "size": [w, h],
                "rotation": rotation,
            }
        ]
    for k in kfs:
        k["region"] = target(k["box"], w, h, cw, ch, anchor)

    # 1. hysteresis: one crop while every keyframe keeps `keep` of its target
    groups, current = [], [kfs[0]]
    for k in kfs[1:]:
        _, _, low = best_position([q["region"] for q in current + [k]], w, h, cw, ch)
        if low >= keep:
            current.append(k)
        else:
            groups.append(current)
            current = [k]
    groups.append(current)

    def pieces_of(groups):
        cuts = (
            [a]
            + [
                min(b, max(a, (g[-1]["t"] + n[0]["t"]) / 2))
                for g, n in zip(groups, groups[1:])
            ]
            + [b]
        )
        return [{"a": cuts[i], "b": cuts[i + 1], "g": g} for i, g in enumerate(groups)]

    def merge(pieces, i, j):
        lo, hi = sorted((i, j))
        pieces[lo : hi + 1] = [
            {
                "a": pieces[lo]["a"],
                "b": pieces[hi]["b"],
                "g": pieces[lo]["g"] + pieces[hi]["g"],
            }
        ]

    pieces = pieces_of(groups)
    # 2. pieces too short (or empty) join the neighbour that keeps the subject best
    while len(pieces) > 1:
        short = [i for i, p in enumerate(pieces) if p["b"] - p["a"] < min_piece]
        if not short:
            break
        i = min(short, key=lambda k: pieces[k]["b"] - pieces[k]["a"])
        nbs = [j for j in (i - 1, i + 1) if 0 <= j < len(pieces)]
        j = max(
            nbs,
            key=lambda n: best_position(
                [q["region"] for q in pieces[i]["g"] + pieces[n]["g"]], w, h, cw, ch
            )[2],
        )
        merge(pieces, i, j)
    # 3. positions, then small moves merged
    s = W / cw
    changed = True
    while changed:
        changed = False
        prev = None
        for p in pieces:
            p["pos"], p["mean"], p["min"] = best_position(
                [q["region"] for q in p["g"]], w, h, cw, ch, prev
            )
            prev = p["pos"]
        for i in range(len(pieces) - 1):
            (x1, y1), (x2, y2) = pieces[i]["pos"], pieces[i + 1]["pos"]
            if abs(x1 - x2) * s < MIN_JUMP_PX and abs(y1 - y2) * s < MIN_JUMP_PX:
                merge(pieces, i, i + 1)
                changed = True
                break

    out = []
    for p in pieces:
        x, y = p["pos"]
        kf = [
            {
                "t_s": q["t"],
                "cov": round(coverage(q["region"], x, y, cw, ch), 2),
                "body": round(
                    coverage(
                        (
                            q["box"][0] * w,
                            q["box"][1] * h,
                            q["box"][2] * w,
                            q["box"][3] * h,
                        ),
                        x,
                        y,
                        cw,
                        ch,
                    ),
                    2,
                ),
            }
            for q in p["g"]
        ]
        f = list(flags)
        if min(k["cov"] for k in kf) < flag:
            f.append("low_coverage")
        if s > 2.0:
            f.append(f"upscale_{s:.1f}")
        if rotation:
            f.append(f"rotated_{rotation}")
        out.append(
            {
                "in_s": round(p["a"], 3),
                "out_s": round(p["b"], 3),
                "props": transform(x, y, w, h, cw, ch, W, H, rotation),
                "kf": kf,
                "crop": [
                    round(x / w, 4),
                    round(y / h, 4),
                    round(cw / w, 4),
                    round(ch / h, 4),
                ],
                "flags": f,
                "size": [w, h],
                "rotation": rotation,
            }
        )
    return out


B2 = r'''import json
PARAMS = json.loads(r"""__PARAMS__""")

def all_clips(folder, found):
    found.extend(folder.GetClipList() or [])
    for sub in folder.GetSubFolderList() or []:
        all_clips(sub, found)
    return found

try:
    pm = resolve.GetProjectManager()
    proj = pm.GetCurrentProject()
    mp = proj.GetMediaPool()
    if PARAMS["create"]:
        tl = mp.CreateEmptyTimeline(PARAMS["timeline"])
        if tl is None:
            raise RuntimeError("timeline name already used")
        w, h = PARAMS["size"]
        # SetSettings answers False here yet applies the size: read it back
        tl.SetSettings({"useCustomSettings": "1", "timelineResolutionWidth": str(w),
                        "timelineResolutionHeight": str(h)})
    else:
        tl = None
        for i in range(1, proj.GetTimelineCount() + 1):
            t = proj.GetTimelineByIndex(i)
            if t.GetName() == PARAMS["timeline"]:
                tl = t
        if tl is None:
            raise RuntimeError("timeline not found")
    if not proj.SetCurrentTimeline(tl):
        raise RuntimeError("cannot make it current")
    st = tl.GetSettings()
    size = [int(st.get("timelineResolutionWidth")), int(st.get("timelineResolutionHeight"))]
    if size != PARAMS["size"]:
        raise RuntimeError("timeline is %dx%d, the plan is for %dx%d" % tuple(size + PARAMS["size"]))
    tl_fps = float(st.get("timelineFrameRate"))
    by_uid = {c.GetUniqueId(): c for c in all_clips(mp.GetRootFolder(), [])}
    infos, want = [], []
    for ui, a, b in PARAMS["it"]:
        clip = by_uid.get(PARAMS["u"][ui])
        if clip is None:
            raise RuntimeError("clip not found: " + PARAMS["u"][ui])
        p = clip.GetClipProperty()
        fps = float(p.get("FPS"))
        frames = int(p.get("Frames") or 0)
        s, e = int(round(a * fps)), int(round(b * fps))
        if frames:
            e = min(e, frames)
        infos.append({"mediaPoolItem": clip, "startFrame": s, "endFrame": e})
        want.append(int(round((e - s) * tl_fps / fps)))
    before = len([x for x in tl.GetItemListInTrack("video", 1) or [] if x.GetType() == "video"])
    mp.AppendToTimeline(infos)
    video = [x for x in tl.GetItemListInTrack("video", 1) or [] if x.GetType() == "video"]
    new = video[before:]
    bad = [i for i, (it, w) in enumerate(zip(new, want)) if abs(it.GetDuration() - w) > 1]
    fails = []
    for i, z, pan, tilt, rot in PARAMS["props"]:
        it = new[i]
        ok = it.SetProperties({"ZoomX": z, "ZoomY": z, "Pan": pan, "Tilt": tilt, "RotationAngle": rot})
        pr = it.GetProperties()
        if not ok or abs(pr.get("Tilt") - tilt) > 0.2 or abs(pr.get("ZoomX") - z) > 0.001:
            fails.append(i)
    result = {"timeline": tl.GetName(), "uid": tl.GetUniqueId(), "size": size, "new": len(new), "expected": len(infos),
              "bad_durations": bad, "prop_fails": fails, "video_items": len(video),
              "audio_items": len(tl.GetItemListInTrack("audio", 1) or []),
              "frames": tl.GetEndFrame() - tl.GetStartFrame()}
except Exception as ex:
    result = {"error": ascii(str(ex))}
'''


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("edit_list")
    ap.add_argument("out_dir")
    ap.add_argument("--width", type=int, default=None)
    ap.add_argument("--height", type=int, default=None)
    ap.add_argument(
        "--subject",
        default=None,
        help="mammal, person, bird... or the start of a label",
    )
    ap.add_argument("--min-piece", type=float, default=2.5)
    ap.add_argument("--keep", type=float, default=0.75)
    ap.add_argument("--flag", type=float, default=0.6)
    ap.add_argument("--batch", type=int, default=40)
    ap.add_argument("--no-images", action="store_true")
    ap.add_argument("--url", default=None)
    o = ap.parse_args()

    with open(o.edit_list, encoding="utf-8") as fh:
        edit = json.load(fh)
    fmt = edit.get("format") or {}
    W, H = o.width or fmt.get("width") or 1920, o.height or fmt.get("height") or 1080
    os.makedirs(os.path.join(o.out_dir, "kf"), exist_ok=True)
    client = Client(o.url)

    items = []
    for src_index, item in enumerate(edit["items"], 1):
        for k, piece in enumerate(
            plan_item(client, item, W, H, o.subject, o.min_piece, o.keep, o.flag)
        ):
            row = {
                key: item[key]
                for key in ("video_id", "uid", "file", "why")
                if key in item
            }
            row.update(piece, source_n=src_index, piece=k + 1)
            items.append(row)
    for n, row in enumerate(items, 1):
        row["n"] = n

    # review images
    review = {"flag": o.flag, "width": W, "height": H, "pieces": []}
    if not o.no_images:
        for row in items:
            if not row.get("props") or "crop" not in row:
                continue
            times = [k["t_s"] for k in row.get("kf", [])]
            if len(times) > 8:
                times = [times[round(i * (len(times) - 1) / 7)] for i in range(8)]
            if not times:
                times = [
                    row["in_s"] + 0.2,
                    (row["in_s"] + row["out_s"]) / 2,
                    row["out_s"] - 0.2,
                ]
            covs = {k["t_s"]: k["cov"] for k in row.get("kf", [])}
            try:
                parts = [
                    p
                    for p in client.raw(
                        "get_frames",
                        {
                            "video_id": row["video_id"],
                            "timestamps": times,
                            "max_images": 8,
                            "size": 256,
                        },
                    )
                    if p.get("type") == "image"
                ]
            except ToolError:
                parts = []
            images = []
            for i, (t, part) in enumerate(zip(times, parts)):
                path = os.path.abspath(
                    os.path.join(o.out_dir, "kf", f"n{row['n']:03d}_{i}.jpg")
                )
                with open(path, "wb") as fh:
                    fh.write(base64.b64decode(part["data"]))
                images.append({"file": path, "t_s": t, "cov": covs.get(t)})
            review["pieces"].append(
                {
                    "n": row["n"],
                    "title": f"{row.get('file', '')} {row['in_s']:.1f}-{row['out_s']:.1f} s",
                    "flags": row["flags"],
                    "crop": row["crop"],
                    "images": images,
                }
            )
    with open(os.path.join(o.out_dir, "review.json"), "w", encoding="utf-8") as fh:
        json.dump(review, fh, ensure_ascii=False, indent=1)

    # B2 scripts
    name = edit.get("timeline") or "Montage - vfe v1"
    batches = [items[i : i + o.batch] for i in range(0, len(items), o.batch)]
    for k, batch in enumerate(batches, 1):
        uids, rows, props = [], [], []
        for i, row in enumerate(batch):
            if row["uid"] not in uids:
                uids.append(row["uid"])
            rows.append([uids.index(row["uid"]), row["in_s"], row["out_s"]])
            p = row.get("props")
            if p:
                props.append(
                    [i, p["ZoomX"], p["Pan"], p["Tilt"], p.get("RotationAngle", 0.0)]
                )
        params = json.dumps(
            {
                "timeline": name,
                "create": k == 1,
                "size": [W, H],
                "u": uids,
                "it": rows,
                "props": props,
            },
            separators=(",", ":"),
            ensure_ascii=True,
        )
        with open(os.path.join(o.out_dir, f"b2_{k}.py"), "w", encoding="ascii") as fh:
            fh.write(B2.replace("__PARAMS__", params))

    total = sum(r["out_s"] - r["in_s"] for r in items)
    flagged = [(r["n"], r.get("file"), r["flags"]) for r in items if r["flags"]]
    summary = {
        "timeline": name,
        "items": len(items),
        "from": len(edit["items"]),
        "reframed": sum(1 for r in items if r.get("props")),
        "duration_s": round(total, 1),
        "batches": len(batches),
        "flagged": flagged,
    }
    with open(os.path.join(o.out_dir, "plan.json"), "w", encoding="utf-8") as fh:
        json.dump(
            {
                "format": {"width": W, "height": H},
                "timeline": name,
                "items": items,
                "summary": summary,
            },
            fh,
            ensure_ascii=False,
            indent=1,
        )
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
