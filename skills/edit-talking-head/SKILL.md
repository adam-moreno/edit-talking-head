---
name: edit-talking-head
description: Makes a first cut of a talking-head video (someone talking to the camera) on the user's own Mac with ffmpeg. It keeps the stronger take, cuts restarts, filler words like "um" and long pauses, and lists every cut with its time so any cut can be put back. Use when the user asks to edit, trim, tighten or cut down a talking-head video, a selfie video, a raw take or a recording of themselves talking, to pick their best take, or to cut the ums and pauses. Never changes the original file. Adds no music, captions or effects, and never posts or uploads anything.
---

# Claude edits your talking-head video (first cut)

You are helping a home-service business owner (a plumber, roofer, landscaper, contractor) with ONE job: turn their raw talking-head recording into a **first cut**. That means the stronger take is kept, and restarts, filler words and long pauses are gone. Their words stay in order, and every cut is listed with its time.

If they ask for music, captions, effects, colour, b-roll, a thumbnail or posting, say plainly that this skill doesn't do that. A finished, styled edit is what Terramore Studio does (terramore.io/studio).

`CUT` below means `python3 <this skill's folder>/scripts/cut.py`.

## Hard rules

- **Never change the original recording.** The first cut is always a new file (`<name>_first-cut.mp4`). Don't use `mv`, `rm` or Edit on their video files.
- **Preview before render.** Show the cut list and the new length. Run `CUT render PLAN --yes` only after the owner says yes to that list in this conversation.
- **Every cut has a why** that a person can read ("first take stops mid-sentence", "1.8 s pause shortened to 0.3 s").
- **Don't promise quality.** This is a first cut made from timings. Tell them to watch it before they post it. Never say it is "perfect", "pro" or "ready to post".
- **You can't hear or watch the video.** You judge takes from the words and the pauses. Say so when you choose between takes.
- **Nothing leaves the Mac.** The script makes no network calls. Installing ffmpeg or a transcriber downloads software, so ask first and say what will be downloaded.

## Steps

### 1. Check the tools

Run `CUT check`.

- **If ffmpeg is missing** (exit code 2), show the owner the install steps it prints (Homebrew, then `brew install ffmpeg`) and stop. Offer to run `brew install ffmpeg` for them, but only with their yes. If Homebrew isn't installed either, they need to install it from https://brew.sh first.
- Note whether a transcriber was found.

### 2. Get the recording and the words

Ask for the video file, if they haven't given one. Then you need **timed captions**, a `.srt` or `.vtt` file with times. Without them you can't see the words. Offer these options, in this order:

1. **They already have captions.** Many editing and phone apps can export a `.srt` file. **Word-by-word captions** (one word per line) let you cut single ums. **Sentence captions** let you cut whole takes, restarts and pauses, but not an um inside a sentence. Say which kind they gave you.
2. **A free transcriber on their Mac** (whisper.cpp, MIT licence). It's a one-time setup that downloads the program and a speech model of about 150 MB. Do it only with their yes:
   ```sh
   brew install whisper-cpp
   mkdir -p ~/whisper-models
   curl -L -o ~/whisper-models/ggml-base.en.bin https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin
   CUT audio VIDEO /tmp/talk.wav
   whisper-cli -m ~/whisper-models/ggml-base.en.bin -f /tmp/talk.wav -ml 1 -sow -osrt -of "<video name without extension>.words"
   ```
   That writes word-by-word captions (`<name>.words.srt`). If a command fails, show the error. Don't guess at other flags. For speech that isn't English, use `ggml-base.bin` in place of `ggml-base.en.bin`.
3. **No captions.** You can still cut long pauses and dead air at the start and end, and nothing else. Say that clearly before going on.

### 3. Read the timeline

Run `CUT timeline VIDEO --subs CAPTIONS` (leave out `--subs` if there are none). It prints the length, every pause over 0.7 s, and the timed words with filler words flagged.

If the pauses look wrong (none found, or the whole video counts as a pause), the room was noisy. Run it again with `--noise -30`, or with `--noise -40` for a very quiet room.

### 4. Draft the plan

Run `CUT suggest VIDEO --subs CAPTIONS`. It writes `<name>.plan.json` with the cuts it can find without judgement: long pauses (shortened to 0.3 s rather than removed), dead air at the start and end, and filler words when the captions are word by word.

Then read the words and add your own cuts to the plan's `cuts` list. Each cut is `{"start": …, "end": …, "kind": "take|restart|filler|pause|other", "why": "…", "said": "the words cut"}`:

- **Takes.** When they said the same thing more than once, keep the stronger one. The stronger take is the one that is complete, has fewer fillers and restarts, and says it in fewer words. Cut the others, and say in the `why` which take you kept and why.
- **Restarts.** A sentence they started, stopped ("no wait", "let me start again") and started again: cut the false start.
- **Fillers in sentence captions.** You can't cut inside a caption line, so leave them. List them in your report as "left in: can't cut without word-by-word captions".
- **Leave alone:** anything you're unsure about, words that carry meaning ("like" in "it looks like rust"), and pauses they may want for effect. When in doubt, keep it in.
- Cut from the end of the last kept word to the start of the next kept word, so a cut never clips a word.
- Never reorder or rewrite what they said. A first cut only removes.

### 5. Preview

Run `CUT preview PLAN`. Show the owner the numbered cut list, the before and after length, and which take you kept and why. Then ask: "Want me to make the first cut, or change any of these?" Stop until they answer.

To put a cut back, delete its entry from the plan file and preview again. To change one, edit its times.

### 6. Render, only on yes

Run `CUT render PLAN --yes`. It writes `<name>_first-cut.mp4` and `<name>_first-cut.cutlist.md` next to the original, and never overwrites an earlier first cut (it adds `-2`, `-3`). Tell them both paths. End with one next step: "Watch it through once. If a cut feels abrupt, tell me its number and I'll put it back."

## The report

Short, plain words, lists not tables:

1. **Length:** before, after, and how much was cut.
2. **Take kept:** which one and why (from the words, since you can't watch it).
3. **The cut list:** numbered, with times and the reason for each.
4. **Left in, and why:** fillers you couldn't reach, and anything you weren't sure about.
5. **Files:** the original (unchanged), the first cut, and the cut list.

## What this is, and is not

It's a first cut made by cutting at times, using ffmpeg on the owner's own Mac. It doesn't judge how they look or sound, and adds no music, captions, colour or effects. The result can have an abrupt join or a cut word if the captions' timings are off. That's why every cut is listed and can be put back.
