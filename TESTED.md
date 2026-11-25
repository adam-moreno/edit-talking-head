# What was tested

2026-11-25, version 0.1.0.

**Tested**

- **Claude Code CLI 2.1.332, macOS 15.3.1, Python 3.13.1, ffmpeg 8.1 (Homebrew), project install, from a FRESH CLONE of this repository.** The skill folder was copied into a new, empty project's `.claude/skills/`, with only project settings loaded (`--setting-sources project`). The tools allowed were Read, Edit, Write and `python3` commands.
  - **The example recording** was rebuilt with `examples/before/make-example-video.py`: a made-up plumber, the Mac's `say` voice one word at a time, over a test pattern, with word-by-word captions.
  - **Turn 1** (`/edit-talking-head` with the video and captions): it ran check, timeline and suggest, and added the false-start cut with a reason. It showed the preview (33.4 s to 18.8 s, five cuts) and stopped. No video was written.
  - **Turn 2** ("Yes, make the first cut."): it rendered `water-heater-tip_first-cut.mp4` (18.9 s) and its cut list.
  - **The original `.mov`** had the same SHA-256 before and after.
  - **The first cut**, checked with the script's own pause finder, had one pause over 0.5 s left (0.7 s, between two sentences).
  - The outputs are in `examples/after/`, unedited.
- **Unit tests** (`python3 -m unittest discover -s tests`): 21 pass from the fresh clone. That includes a real ffmpeg render of a generated 10-second clip, which checks the length, that the original is unchanged, that nothing is written without `--yes`, and that an earlier first cut is never overwritten.
- **Negative controls:** the tests fail on deliberately broken copies of the script. The broken copies:
  - overwrote an earlier cut;
  - skipped filler cuts;
  - didn't take the gap after a filler;
  - accepted a cut with no reason;
  - kept cut parts in the render;
  - imported a network module.

**Not tested**

- **The whisper.cpp path** (`brew install whisper-cpp`, the model download, `whisper-cli ... -ml 1 -sow -osrt`). whisper.cpp isn't installed on the test Mac. The commands in SKILL.md are written from whisper.cpp's documented options and have not been run.
- **Real people talking:** a real voice, a phone recording, a noisy job site, iPhone HDR or HEVC footage, or recordings longer than 34 seconds. The example voice is synthetic, with exact word times. Real captions will have rougher times.
- **Sentence-level captions from a real editing or phone app.** Parsing is unit-tested on hand-written SRT and VTT only.
- **The missing-ffmpeg path on a real Mac without ffmpeg.** This is unit-tested by hiding ffmpeg from the script.
- **Whether the first cut sounds good.** No person listened to the output. The checks are length, pauses and file safety.
- A personal install in `~/.claude/skills/`; the Claude Code desktop app, web app and IDE extensions; Windows and Linux; Python other than 3.13.1 (written for 3.9+).
