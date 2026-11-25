"""Run: python3 -m unittest discover -s tests -v. The ffmpeg tests make a small tone-and-silence clip in a temp folder
and are skipped (with the reason) when ffmpeg isn't installed."""
import contextlib, hashlib, importlib.util, io, json, os, re, shutil, subprocess, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "skills", "edit-talking-head", "scripts", "cut.py")
spec = importlib.util.spec_from_file_location("cut", SCRIPT)
cut = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cut)
HAVE_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))

SRT = """1
00:00:01,000 --> 00:00:01,400
Hi,

2
00:00:01,500 --> 00:00:01,800
um,

3
00:00:02,600 --> 00:00:03,000
<i>pipes.</i>
"""


def run(*args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = cut.main(list(args))
        except SystemExit as e:
            code = e.code
    return code, out.getvalue() + err.getvalue()


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


class Pure(unittest.TestCase):
    def test_times(self):
        self.assertEqual(cut.secs("1:02.5"), 62.5)
        self.assertEqual(cut.secs("00:00:01,250"), 1.25)
        self.assertEqual(cut.secs(3), 3.0)
        self.assertEqual(cut.stamp(62.54), "1:02.5")

    def test_captions_read_and_fillers_flagged(self):
        cues = cut.parse_subs(SRT)
        self.assertEqual([c["text"] for c in cues], ["Hi,", "um,", "pipes."])
        self.assertEqual([c["filler"] for c in cues], [False, True, False])
        self.assertTrue(cut.word_level(cues))
        vtt = "WEBVTT\n\n00:01.000 --> 00:04.000 align:start\nso um the drain was full\n"
        v = cut.parse_subs(vtt)
        self.assertEqual(v[0]["start"], 1.0)
        self.assertFalse(v[0]["filler"])
        self.assertTrue(v[0]["has_filler"])
        self.assertFalse(cut.word_level(v), "sentence captions are not word by word")

    def test_silences_parsed_including_one_running_to_the_end(self):
        log = "[silencedetect @ 0x1] silence_start: 2.5\n[silencedetect @ 0x1] silence_end: 4 | silence_duration: 1.5\n" \
              "[silencedetect @ 0x1] silence_start: 9.2\n"
        self.assertEqual(cut.parse_silences(log, 10.0),
                         [{"start": 2.5, "end": 4.0, "length": 1.5}, {"start": 9.2, "end": 10.0, "length": 0.8}])

    def test_plan_keeps_the_rest_in_order(self):
        cuts, keeps, _ = cut.normalise({"cuts": [{"start": 6, "end": 7, "kind": "pause", "why": "p"},
                                                 {"start": 2, "end": 3, "kind": "take", "why": "t"},
                                                 {"start": 2.5, "end": 3.5, "kind": "filler", "why": "f"}]}, 10.0)
        self.assertEqual([c["start"] for c in cuts], [2, 2.5, 6], "each cut is listed on its own")
        self.assertEqual(keeps, [(0.0, 2), (3.5, 6), (7, 10.0)], "overlaps merge for the render")

    def test_bad_plans_are_refused(self):
        with self.assertRaisesRegex(ValueError, "why"):
            cut.normalise({"cuts": [{"start": 1, "end": 2, "kind": "pause"}]}, 10)
        with self.assertRaisesRegex(ValueError, "kind"):
            cut.normalise({"cuts": [{"start": 1, "end": 2, "kind": "music", "why": "x"}]}, 10)
        with self.assertRaisesRegex(ValueError, "nothing would be left"):
            cut.normalise({"cuts": [{"start": 0, "end": 10, "kind": "other", "why": "x"}]}, 10)

    def test_missing_ffmpeg_says_how_to_install(self):
        real = cut.tool
        cut.tool = lambda name: None
        try:
            code, out = run("check")
        finally:
            cut.tool = real
        self.assertEqual(code, 2)
        self.assertIn("brew install ffmpeg", out)

    def test_no_network_code(self):
        src = open(SCRIPT).read()
        bad = re.compile(r"\b(socket|urllib|http|requests|ftplib|smtplib|ssl)\b")
        for line in src.splitlines():
            if re.match(r"\s*(import|from)\s", line):
                self.assertIsNone(bad.search(line), line)


@unittest.skipUnless(HAVE_FFMPEG, "ffmpeg is not installed; install it with: brew install ffmpeg")
class WithFfmpeg(unittest.TestCase):
    """A 10 s clip: tone 0-2 s, silence 2-4 s, tone 4-6 s, silence 6-6.5 s, tone 6.5-10 s."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.video = os.path.join(self.tmp, "take.mov")
        expr = "if(between(t,2,4)+between(t,6,6.5),0,0.5*sin(2*PI*440*t))"
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                        "color=c=gray:size=320x240:rate=25:duration=10", "-f", "lavfi", "-i",
                        f"aevalsrc='{expr}':s=48000:d=10", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-shortest", self.video], check=True)
        self.before = sha(self.video)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_finds_the_long_pause_only(self):
        p = cut.pauses(self.video, 0.7, -35)
        self.assertEqual(len(p), 1)
        self.assertAlmostEqual(p[0]["start"], 2.0, delta=0.1)
        self.assertAlmostEqual(p[0]["end"], 4.0, delta=0.1)

    def test_suggest_cuts_a_word_level_filler_and_its_gap(self):
        subs = os.path.join(self.tmp, "take.srt")
        open(subs, "w").write("1\n00:00:04,100 --> 00:00:04,400\num\n\n2\n00:00:05,000 --> 00:00:05,500\npipes\n")
        self.assertEqual(run("suggest", self.video, "--subs", subs)[0], 0)
        fillers = [c for c in json.load(open(os.path.join(self.tmp, "take.plan.json")))["cuts"] if c["kind"] == "filler"]
        self.assertEqual(len(fillers), 1)
        self.assertEqual((fillers[0]["start"], fillers[0]["end"]), (4.1, 4.9), "up to 0.1 s before the next word")

    def test_suggest_preview_render(self):
        plan = os.path.join(self.tmp, "take.plan.json")
        self.assertEqual(run("suggest", self.video)[0], 0)
        data = json.load(open(plan))
        self.assertEqual([c["kind"] for c in data["cuts"]], ["pause"])
        data["cuts"].append({"start": 8, "end": 9, "kind": "take", "why": "test cut"})
        json.dump(data, open(plan, "w"))

        code, out = run("render", plan)                 # no --yes: a preview, nothing written
        self.assertEqual(code, 0)
        self.assertIn("Preview only", out)
        self.assertEqual(sorted(os.listdir(self.tmp)), ["take.mov", "take.plan.json"])

        code, out = run("render", plan, "--yes")
        self.assertEqual(code, 0, out)
        first = os.path.join(self.tmp, "take_first-cut.mp4")
        expected = 10 - 1.7 - 1.0                        # 2 s pause cut to 0.3 s, plus the 1 s take cut
        self.assertAlmostEqual(cut.probe(first)["duration"], expected, delta=0.15)
        self.assertTrue(os.path.exists(os.path.join(self.tmp, "take_first-cut.cutlist.md")))
        self.assertEqual(sha(self.video), self.before, "the original is never changed")

        self.assertEqual(run("render", plan, "--yes")[0], 0)
        self.assertTrue(os.path.exists(os.path.join(self.tmp, "take_first-cut-2.mp4")), "never overwrites")


if __name__ == "__main__":
    unittest.main()
