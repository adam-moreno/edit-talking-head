#!/usr/bin/env python3
"""edit-talking-head: make a first cut of a talking-head recording with ffmpeg.

Standard library only. No network. The recording you give it is never changed:
the first cut is written as a new file next to it.

  python3 cut.py check                          is ffmpeg installed? is a transcriber?
  python3 cut.py timeline VIDEO [--subs FILE]   pauses + timed words, filler words flagged
  python3 cut.py audio VIDEO OUT.wav            16 kHz mono WAV, for a local transcriber
  python3 cut.py suggest VIDEO [--subs FILE]    writes a draft plan (pauses + fillers); changes nothing else
  python3 cut.py preview PLAN                   the cut list and the new length; changes nothing
  python3 cut.py render PLAN --yes              writes <name>_first-cut.mp4 and its cut list

A plan is JSON: {"source": "...", "cuts": [{"start": 3.2, "end": 5.9, "kind": "take", "why": "..."}]}.
Times are seconds or "m:ss.s". Kinds: take, restart, filler, pause, other.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys

KINDS = ("take", "restart", "filler", "pause", "other")
FILLERS = {"um", "umm", "uh", "uhh", "uhm", "er", "erm", "ah", "hmm", "mm", "mhm"}
MIN_KEEP = 0.12      # a kept piece shorter than this is folded into the cut around it
FADE = 0.012         # tiny audio fade at each join, so cuts don't click

INSTALL = """ffmpeg is not installed (or not on your PATH). It is the free tool that does the cutting.

Install it on a Mac:
  1. Install Homebrew if you don't have it: https://brew.sh (one command, copy it from that page)
  2. Then run:  brew install ffmpeg
  3. Check it:  ffmpeg -version

Then ask again. Nothing was changed."""


# ---------- small helpers ----------

def secs(v):
    """3.2, "3.2", "0:03.2" or "1:02:03.5" -> seconds."""
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(",", ".")
    parts = s.split(":")
    if not 1 <= len(parts) <= 3:
        raise ValueError(f"not a time: {v!r}")
    total = 0.0
    for p in parts:
        total = total * 60 + float(p)
    return total


def stamp(t):
    """seconds -> m:ss.s (h:mm:ss.s past an hour)."""
    t = max(0.0, t)
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{int(h)}:{int(m):02d}:{s:04.1f}"
    return f"{int(m)}:{s:04.1f}"


def tool(name):
    return shutil.which(name)


def need_ffmpeg():
    if not (tool("ffmpeg") and tool("ffprobe")):
        print(INSTALL, file=sys.stderr)
        sys.exit(2)


def probe(video):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height",
         "-of", "json", video], capture_output=True, text=True)
    if out.returncode != 0:
        sys.exit(f"ffprobe could not read {video}: {out.stderr.strip()[:300]}")
    info = json.loads(out.stdout)
    streams = info.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), None)
    return {
        "duration": float(info["format"]["duration"]),
        "has_video": v is not None,
        "has_audio": any(s.get("codec_type") == "audio" for s in streams),
        "size": f"{v.get('width')}x{v.get('height')}" if v else None,
    }


# ---------- reading: pauses and captions ----------

def parse_silences(stderr_text, duration=None):
    """Read ffmpeg silencedetect output into [{start, end, length}]."""
    out, start = [], None
    for line in stderr_text.splitlines():
        m = re.search(r"silence_start: (-?[\d.]+)", line)
        if m:
            start = max(0.0, float(m.group(1)))
            continue
        m = re.search(r"silence_end: ([\d.]+)", line)
        if m and start is not None:
            end = float(m.group(1))
            out.append({"start": round(start, 3), "end": round(end, 3), "length": round(end - start, 3)})
            start = None
    if start is not None and duration is not None:   # silence that runs to the end
        out.append({"start": round(start, 3), "end": round(duration, 3), "length": round(duration - start, 3)})
    return out


def pauses(video, min_len=0.7, noise=-35.0):
    r = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", video, "-vn", "-af",
         f"silencedetect=noise={noise}dB:d={min_len}", "-f", "null", "-"],
        capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"ffmpeg could not read the audio in {video}: {r.stderr.strip()[-300:]}")
    return parse_silences(r.stderr, probe(video)["duration"])


TIME_LINE = re.compile(r"((?:\d+:)?\d{1,2}:\d{2}[.,]\d{1,3})\s*-->\s*((?:\d+:)?\d{1,2}:\d{2}[.,]\d{1,3})")


def parse_subs(text):
    """SRT or WebVTT text -> [{n, start, end, text, filler}]. Tags like <i> are dropped."""
    cues, cur = [], None
    for raw in text.replace("\r\n", "\n").split("\n"):
        line = raw.strip()
        m = TIME_LINE.search(line)
        if m:
            cur = {"start": secs(m.group(1)), "end": secs(m.group(2)), "lines": []}
            cues.append(cur)
        elif not line:
            cur = None
        elif cur is not None:
            cur["lines"].append(re.sub(r"<[^>]+>", "", line))
    out = []
    for i, c in enumerate(cues, 1):
        text = " ".join(c["lines"]).strip()
        words = re.findall(r"[a-z']+", text.lower())
        out.append({"n": i, "start": round(c["start"], 3), "end": round(c["end"], 3), "text": text,
                    "filler": bool(words) and all(w in FILLERS for w in words),
                    "has_filler": any(w in FILLERS for w in words)})
    return out


def word_level(cues):
    """True when the captions are (about) one word per line, so single words can be cut."""
    if not cues:
        return False
    counts = [len(c["text"].split()) for c in cues if c["text"]]
    return bool(counts) and sum(counts) / len(counts) <= 1.6


def read_subs(path):
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        return parse_subs(f.read())


# ---------- plans ----------

def normalise(plan, duration):
    """Check a plan and return (cuts, keeps, notes). Cuts are sorted, clamped and merged."""
    notes, cuts = [], []
    for i, c in enumerate(plan.get("cuts", []), 1):
        try:
            s, e = secs(c["start"]), secs(c["end"])
        except (KeyError, ValueError) as err:
            raise ValueError(f"cut {i}: needs a start and an end ({err})")
        kind = c.get("kind", "other")
        if kind not in KINDS:
            raise ValueError(f"cut {i}: kind must be one of {', '.join(KINDS)}, not {kind!r}")
        if not str(c.get("why", "")).strip():
            raise ValueError(f"cut {i}: every cut needs a 'why' a person can read")
        s, e = max(0.0, s), min(duration, e)
        if e - s <= 0.0:
            notes.append(f"cut {i} ({kind}) is empty or outside the video, skipped")
            continue
        cuts.append({"start": s, "end": e, "kind": kind, "why": c["why"].strip(), "said": c.get("said", "")})
    cuts.sort(key=lambda c: (c["start"], c["end"]))
    spans = []                       # overlapping or nearly touching cuts become one span for the render
    for c in cuts:
        if spans and c["start"] <= spans[-1][1] + MIN_KEEP:
            spans[-1][1] = max(spans[-1][1], c["end"])
        else:
            spans.append([c["start"], c["end"]])
    if spans and spans[0][0] < MIN_KEEP:
        spans[0][0] = 0.0
    if spans and duration - spans[-1][1] < MIN_KEEP:
        spans[-1][1] = duration
    keeps, t = [], 0.0
    for s, e in spans:
        if s - t > 0:
            keeps.append((t, s))
        t = e
    if duration - t > 0:
        keeps.append((t, duration))
    if not keeps:
        raise ValueError("this plan cuts the whole video; nothing would be left")
    return cuts, keeps, notes


def load_plan(path):
    with open(path, encoding="utf-8") as f:
        plan = json.load(f)
    src = plan.get("source")
    if not src:
        sys.exit("the plan has no 'source' (the path of the recording)")
    if not os.path.isabs(src):
        src = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(path)), src))
    if not os.path.exists(src):
        sys.exit(f"the recording in the plan isn't there: {src}")
    plan["source"] = src
    return plan


def cut_list_text(plan, cuts, keeps, duration, notes):
    new_len = sum(b - a for a, b in keeps)
    lines = [f"# Cut list: {os.path.basename(plan['source'])}", "",
             f"- Before: {stamp(duration)}  After: {stamp(new_len)}  Cut: {stamp(duration - new_len)} in {len(cuts)} cuts"
             " (cuts that touch are joined into one)",
             "- Times are in the ORIGINAL recording, which is not changed.",
             "- To put a cut back: delete it from the plan file and render again.", ""]
    for i, c in enumerate(cuts, 1):
        said = f' (said: "{c["said"]}")' if c.get("said") else ""
        lines.append(f"{i}. {stamp(c['start'])} to {stamp(c['end'])} ({c['end'] - c['start']:.1f}s), "
                     f"{c['kind']}: {c['why']}{said}")
    for n in notes:
        lines.append(f"- Note: {n}")
    return "\n".join(lines) + "\n"


def output_path(source):
    stem = os.path.splitext(source)[0]
    out, n = f"{stem}_first-cut.mp4", 2
    while os.path.exists(out):
        out, n = f"{stem}_first-cut-{n}.mp4", n + 1
    return out


def ffmpeg_args(source, keeps, out, info):
    parts, labels = [], []
    for i, (a, b) in enumerate(keeps):
        d = b - a
        fade = min(FADE, d / 4)
        if info["has_video"]:
            parts.append(f"[0:v]trim=start={a:.3f}:end={b:.3f},setpts=PTS-STARTPTS[v{i}]")
            labels.append(f"[v{i}]")
        parts.append(f"[0:a]atrim=start={a:.3f}:end={b:.3f},asetpts=PTS-STARTPTS,"
                     f"afade=t=in:d={fade:.3f},afade=t=out:st={max(0.0, d - fade):.3f}:d={fade:.3f}[a{i}]")
        labels.append(f"[a{i}]")
    v = 1 if info["has_video"] else 0
    parts.append("".join(labels) + f"concat=n={len(keeps)}:v={v}:a=1" + ("[v][a]" if v else "[a]"))
    args = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-i", source,
            "-filter_complex", ";".join(parts)]
    if v:
        enc = encoders()
        vcodec = ["-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p"] if "libx264" in enc \
            else ["-c:v", "h264_videotoolbox", "-b:v", "12M"]
        args += ["-map", "[v]", "-map", "[a]"] + vcodec
    else:
        args += ["-map", "[a]"]
    return args + ["-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out]


def encoders():
    r = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True)
    return r.stdout


# ---------- commands ----------

def cmd_check(_):
    ff, fp = tool("ffmpeg"), tool("ffprobe")
    if not (ff and fp):
        print(INSTALL)
        return 2
    ver = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True).stdout.splitlines()[0]
    print(f"ffmpeg: ok ({ver})")
    found = [n for n in ("whisper-cli", "whisper") if tool(n)]
    if found:
        print(f"transcriber: {', '.join(found)} found on this Mac")
    else:
        print("transcriber: none found. Without timed captions only long pauses can be cut.\n"
              "  Give it an .srt or .vtt caption file, or install a free local transcriber (see the skill's README).")
    return 0


def cmd_timeline(a):
    need_ffmpeg()
    info = probe(a.video)
    if not info["has_audio"]:
        sys.exit("this file has no sound track, so there is nothing to cut by")
    sil = pauses(a.video, a.min_pause, a.noise)
    cues = read_subs(a.subs) if a.subs else []
    data = {"video": a.video, **info, "pauses": sil, "captions": cues, "word_level": word_level(cues)}
    if a.json:
        print(json.dumps(data, indent=1))
        return 0
    print(f"{os.path.basename(a.video)}: {stamp(info['duration'])}, {info['size'] or 'audio only'}")
    print(f"pauses over {a.min_pause}s (quieter than {a.noise} dB): {len(sil)}")
    for p in sil:
        print(f"  pause {stamp(p['start'])} to {stamp(p['end'])} ({p['length']:.1f}s)")
    if a.subs:
        print(f"captions: {len(cues)} lines, " + ("word by word: single words can be cut" if data["word_level"]
              else "sentence lines: whole lines can be cut, single ums inside a line cannot"))
        for c in cues:
            flag = "  <- filler" if c["filler"] else ("  <- has a filler inside" if c["has_filler"] else "")
            print(f"  [{c['n']}] {stamp(c['start'])}-{stamp(c['end'])} {c['text']}{flag}")
    else:
        print("captions: none given. Takes, restarts and ums need timed captions (.srt or .vtt).")
    return 0


def cmd_audio(a):
    need_ffmpeg()
    if os.path.exists(a.out):
        sys.exit(f"{a.out} already exists; pick another name")
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-i", a.video,
                        "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", a.out])
    if r.returncode == 0:
        print(f"wrote {a.out}")
    return r.returncode


def cmd_suggest(a):
    need_ffmpeg()
    info = probe(a.video)
    if not info["has_audio"]:
        sys.exit("this file has no sound track, so there is nothing to cut by")
    cuts = []
    for p in pauses(a.video, a.min_pause, a.noise):
        s, e = p["start"] + a.leave / 2, p["end"] - a.leave / 2
        if p["start"] <= 0.01:
            s = 0.0                                     # dead air before you start talking
        if p["end"] >= info["duration"] - 0.01:
            e = info["duration"]                        # dead air after you stop
        if e - s > 0.2:
            cuts.append({"start": round(s, 3), "end": round(e, 3), "kind": "pause",
                         "why": f"{p['length']:.1f}s pause shortened to {a.leave:.1f}s"
                         if 0 < s and e < info["duration"] else f"{p['length']:.1f}s of silence at the "
                         + ("start" if s == 0 else "end")})
    cues = read_subs(a.subs) if a.subs else []
    if cues and word_level(cues):
        for i, c in enumerate(cues):
            if c["filler"]:
                end = c["end"]
                nxt = cues[i + 1]["start"] if i + 1 < len(cues) else None
                if nxt is not None and nxt - 0.1 > end:
                    end = round(nxt - 0.1, 3)           # take the gap after the um too, so no long pause is left
                cuts.append({"start": c["start"], "end": end, "kind": "filler",
                             "why": f'filler word "{c["text"]}"', "said": c["text"]})
    plan = {"source": os.path.abspath(a.video),
            "note": "Draft from pauses" + (" and filler words" if cues and word_level(cues) else "")
            + ". Add take and restart cuts by hand, each with a why.",
            "cuts": sorted(cuts, key=lambda c: c["start"])}
    out = a.out or os.path.splitext(a.video)[0] + ".plan.json"
    if os.path.exists(out) and not a.force:
        sys.exit(f"{out} already exists; pass --force to replace it, or --out to pick another name")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=1)
        f.write("\n")
    print(f"wrote {out} with {len(plan['cuts'])} draft cuts. Nothing else was changed.")
    return 0


def cmd_preview(a, render=False):
    need_ffmpeg()
    plan = load_plan(a.plan)
    info = probe(plan["source"])
    try:
        cuts, keeps, notes = normalise(plan, info["duration"])
    except ValueError as err:
        sys.exit(f"the plan has a problem: {err}")
    text = cut_list_text(plan, cuts, keeps, info["duration"], notes)
    print(text)
    if not render:
        print("Preview only: nothing was written. Run render with --yes to make the first cut.")
        return 0
    out = output_path(plan["source"])
    r = subprocess.run(ffmpeg_args(plan["source"], keeps, out, info))
    if r.returncode != 0:
        if os.path.exists(out):
            os.remove(out)                                # only ever our own half-written output
        sys.exit("ffmpeg stopped with an error; no first cut was written")
    list_path = os.path.splitext(out)[0] + ".cutlist.md"
    with open(list_path, "w", encoding="utf-8") as f:
        f.write(text)
    got = probe(out)["duration"]
    print(f"wrote {out} ({stamp(got)})\nwrote {list_path}\nThe original recording was not changed.")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description="First cut of a talking-head recording. Never changes the original.")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    for name in ("timeline", "suggest"):
        s = sub.add_parser(name)
        s.add_argument("video")
        s.add_argument("--subs", help=".srt or .vtt captions with times")
        s.add_argument("--min-pause", type=float, default=0.7, help="shortest pause to report, seconds")
        s.add_argument("--noise", type=float, default=-35.0, help="quieter than this (dB) counts as a pause")
        if name == "timeline":
            s.add_argument("--json", action="store_true")
        else:
            s.add_argument("--leave", type=float, default=0.3, help="seconds of pause to leave in each gap")
            s.add_argument("--out")
            s.add_argument("--force", action="store_true")
    s = sub.add_parser("audio")
    s.add_argument("video")
    s.add_argument("out")
    s = sub.add_parser("preview")
    s.add_argument("plan")
    s = sub.add_parser("render")
    s.add_argument("plan")
    s.add_argument("--yes", action="store_true", help="really write the first cut")
    a = p.parse_args(argv)
    if a.cmd == "check":
        return cmd_check(a)
    if a.cmd == "timeline":
        return cmd_timeline(a)
    if a.cmd == "audio":
        return cmd_audio(a)
    if a.cmd == "suggest":
        return cmd_suggest(a)
    if a.cmd == "preview":
        return cmd_preview(a)
    if a.cmd == "render":
        if not a.yes:
            print("render needs --yes. Showing the preview instead.\n")
        return cmd_preview(a, render=a.yes)


if __name__ == "__main__":
    sys.exit(main())
