# edit-talking-head

**Your raw talking-head recording, cut down to the good part, on your own Mac.** A free Claude skill from Terramore.

- **What you give it:** a video of you talking to the camera, and ideally a caption file with times (`.srt` or `.vtt`).
- **What you get back:** a first cut as a new file, with the stronger take kept and restarts, ums and long pauses cut, plus a list of every cut with its time.
- **What it never does:** change your original file, add music, captions or effects, post or upload anything, or promise the cut is ready to post.

## What it does

1. **Checks your tools.** If ffmpeg (the free program that does the cutting) isn't installed, it tells you how to install it and stops.
2. **Reads the timeline.** It finds the pauses in the sound, and reads your words and their times from the caption file.
3. **Drafts the cuts.** Long pauses are shortened to 0.3 s, and dead air at the start and end is removed. With word-by-word captions, it also cuts fillers ("um", "uh").
4. **Adds judgement cuts.** Where you said something twice, Claude keeps the stronger take and says why. It also cuts false starts ("no wait").
5. **Shows you the cut list** and the new length, and waits for your yes.
6. **Makes the first cut** as `<name>_first-cut.mp4`, next to your original, with `<name>_first-cut.cutlist.md`. To put a cut back, remove it from the plan and run it again.

## What it needs to cut what

- **No caption file:** long pauses and dead air only. Claude can't hear the video, so it can't find takes or ums.
- **Sentence captions** (a line per sentence, like most auto-captions): pauses, whole takes and restarts. It can't cut an um in the middle of a line.
- **Word-by-word captions** (one word per line): all of the above, plus single ums and uhs.

To get word-by-word captions without an editing app, the skill can set up **whisper.cpp**, a free transcriber that runs on your Mac (MIT licence), with your yes. It's a one-time download of the program and a speech model of about 150 MB. Your recording is transcribed on your Mac and isn't uploaded. We haven't tested this path yet (see `TESTED.md`).

## Requirements

- A Mac with Claude Code (tested with 2.1.332 on macOS 15.3.1).
- Python 3.9 or newer (macOS asks to install the command-line tools the first time if it's missing).
- **ffmpeg**, free. Install it with [Homebrew](https://brew.sh): `brew install ffmpeg`. The skill checks for it and tells you if it's missing.
- Optional: whisper.cpp for word-by-word captions (`brew install whisper-cpp`, plus a model download).

## Install

Ask Claude: "Install the edit-talking-head skill from github.com/adam-moreno/edit-talking-head."

Or by hand. **For you, on every project:**

```sh
git clone https://github.com/adam-moreno/edit-talking-head.git
mkdir -p ~/.claude/skills
cp -R edit-talking-head/skills/edit-talking-head ~/.claude/skills/
```

**For one project:** copy `skills/edit-talking-head` into that project's `.claude/skills/` folder.

Start a new Claude Code session afterwards so the skill is picked up.

## Use

Type `/edit-talking-head`, or ask: "edit my talking-head video", "cut the ums out of this", "which take is better?". Give it the video file and the caption file if you have one.

You can also run the script yourself:

```sh
C=~/.claude/skills/edit-talking-head/scripts/cut.py
python3 $C check                                   # is ffmpeg installed?
python3 $C timeline take.mov --subs take.srt       # pauses and timed words, fillers flagged
python3 $C suggest  take.mov --subs take.srt       # writes take.plan.json (draft cuts); nothing else changes
python3 $C preview  take.plan.json                 # the cut list and new length; writes nothing
python3 $C render   take.plan.json --yes           # writes take_first-cut.mp4 and its cut list
```

## Example: before and after

Real input and output from `examples/`. Made-up businesses only, never a real client.

The example is a made-up plumber, Tidewell Plumbing. The voice is the Mac's built-in `say` voice, one word at a time so each word's time is exact, over a test pattern. The video isn't stored in this repo. To rebuild it on a Mac:

```sh
python3 examples/before/make-example-video.py examples/before
```

- `examples/before/water-heater-tip.words.srt`: the word-by-word captions. The recording has a false start ("If your water heater is making a pop- no wait."), an "um", an "uh" and long pauses.
- `examples/after/1-preview.md`: Claude's cut list in one real run, before anything was cut.
- `examples/after/2-after-yes.md`: what it said after "Yes, make the first cut."
- `examples/after/water-heater-tip.plan.json` and `water-heater-tip_first-cut.cutlist.md`: the plan and the cut list it wrote.

In that run, 33.4 s went to 18.9 s in five cuts:

1. the false start;
2. the "um";
3. a 2 s pause, shortened to 0.3 s;
4. the "uh";
5. the silence at the end.

The original file's checksum was the same afterwards.

## Limitations

- **It's a first cut, not a finished edit.** Cuts are made at times from the captions and the sound. A join can sound abrupt, or clip the edge of a word, if the caption times are off. Watch it before you post. Every cut is listed so you can put it back.
- **Claude can't watch or hear your video.** It picks takes from the words and pauses, not from how you looked or sounded.
- **Noisy job sites** can hide pauses. The skill can retry with a different loudness setting, but wind or machinery may still confuse it.
- **The first cut is re-encoded** as an H.264 MP4. iPhone HDR clips may look a little flatter than the original.
- **No music, captions, colour, b-roll or effects.** For a finished, styled edit, that's Terramore Studio.
- **Mac only.** Not tested on Windows or Linux.

## Privacy

No telemetry, and the script has no network code (a test checks it). Your video stays on your Mac. The only downloads are ffmpeg and, if you choose it, whisper.cpp and its model, each only with your yes. Claude Code itself sends your conversation to Claude, including the words of your captions, but not your video file.

## Credits

None: written by Terramore. It runs ffmpeg and, if you choose, whisper.cpp (MIT licence). You install both yourself; neither is included in this repo.

## Tests

`python3 -m unittest discover -s tests`

The ffmpeg tests make a 10-second tone-and-silence clip in a temporary folder. They're skipped, with the reason, if ffmpeg isn't installed.

## License

MIT. Made by Terramore (terramore.io). Want the video side done for you? Terramore Studio: terramore.io/studio
