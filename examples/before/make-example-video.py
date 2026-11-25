#!/usr/bin/env python3
"""Rebuild the made-up example recording (Tidewell Plumbing is made up). macOS only: needs the built-in `say` and ffmpeg.

  python3 make-example-video.py OUT_FOLDER

Each word is spoken separately with `say`, so its exact time is known. That gives a word-by-word caption file
(water-heater-tip.words.srt, like the one in this folder; the timings depend on the Mac voice) and a test-pattern video with the voice on it."""
import json, os, subprocess, sys
out = sys.argv[1]; os.makedirs(out, exist_ok=True); w = os.path.join(out, "w"); os.makedirs(w, exist_ok=True)
script = [("Hi,",.1),("I'm",.05),("Dana",.05),("from",.05),("Tidewell",.05),("Plumbing.",.4),
 ("If",.05),("your",.05),("water",.05),("heater",.05),("is",.05),("making",.05),("a",.05),("pop-",.6),
 ("no",.05),("wait.",1.6),
 ("Hi,",.1),("I'm",.05),("Dana",.05),("from",.05),("Tidewell",.05),("Plumbing.",.4),
 ("If",.05),("your",.05),("water",.05),("heater",.05),("makes",.05),("a",.05),("popping",.05),("sound,",.3),
 ("um,",.4),("that's",.05),("usually",.05),("sediment",.05),("at",.05),("the",.05),("bottom",.05),("of",.05),("the",.05),("tank.",1.9),
 ("Draining",.05),("it",.05),("once",.05),("a",.05),("year",.05),("can",.05),("help.",.5),
 ("Uh,",.3),("call",.05),("us",.05),("if",.05),("you're",.05),("not",.05),("sure.",1.2)]
def dur(p): return float(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",p]).decode())
t=0.8; parts=[]; cues=[]
parts.append(("sil",0.8))
for i,(word,gap) in enumerate(script):
    f=os.path.join(w,f"{i:02d}.aiff"); subprocess.run(["say","-o",f,word.strip(",.-")],check=True)
    d=dur(f); cues.append((t,t+d,word)); parts.append((f,d)); parts.append(("sil",gap)); t+=d+gap
inputs=[];fc=[]
for j,(p,d) in enumerate(parts):
    if p=="sil": inputs+=["-f","lavfi","-t",f"{d:.3f}","-i","anullsrc=r=22050:cl=mono"]
    else: inputs+=["-i",p]
    fc.append(f"[{j}:a]aresample=48000,aformat=channel_layouts=mono[a{j}]")
fc.append("".join(f"[a{j}]" for j in range(len(parts)))+f"concat=n={len(parts)}:v=0:a=1[a]")
wav=os.path.join(out,"voice.wav")
subprocess.run(["ffmpeg","-y","-hide_banner","-loglevel","error",*inputs,"-filter_complex",";".join(fc),"-map","[a]",wav],check=True)
total=dur(wav)
subprocess.run(["ffmpeg","-y","-hide_banner","-loglevel","error","-f","lavfi","-i",f"testsrc2=size=720x1280:rate=30:duration={total:.3f}","-i",wav,
 "-c:v","libx264","-pix_fmt","yuv420p","-c:a","aac","-shortest",os.path.join(out,"water-heater-tip.mov")],check=True)
def ts(x):
    h,r=divmod(x,3600); m,s=divmod(r,60); return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int(round((s-int(s))*1000)):03d}"
with open(os.path.join(out,"water-heater-tip.words.srt"),"w") as f:
    for n,(a,b,word) in enumerate(cues,1): f.write(f"{n}\n{ts(a)} --> {ts(b)}\n{word}\n\n")
print(total, len(cues))
