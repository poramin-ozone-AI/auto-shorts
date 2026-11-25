import os, importlib.util, unittest

os.environ["GEMINI_API_KEY"] = "DUMMY_NOT_A_REAL_KEY"
spec = importlib.util.spec_from_file_location("generator", "generate.py")
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)

def scene_set(count=9, chars=85, prompt="Stickman examining an object"):
    return [{"narration": "ก" * chars, "image_prompt": prompt} for _ in range(count)]

class SafeTests(unittest.TestCase):
    def test_creative_identity(self):
        self.assertIn("ความรู้แปลกๆ", g.TOPIC_PROMPT)
        self.assertIn("white round-headed stickman", g.CHARACTER)
        self.assertIn("white and green mohawk", g.CHARACTER)
        self.assertIn("→ ฉากกลางเฉลยทีละชั้น", g.WRITER)

    def test_valid_nine_scenes(self):
        self.assertTrue(g.valid({"title": "ทดสอบ", "scenes": scene_set()}))

    def test_reject_too_few_scenes(self):
        self.assertFalse(g.valid({"title": "ทดสอบ", "scenes": scene_set(count=3, chars=150)}))

    def test_reject_too_many_scenes(self):
        self.assertFalse(g.valid({"title": "ทดสอบ", "scenes": scene_set(count=19, chars=40)}))

    def test_reject_way_too_short_narration(self):
        self.assertFalse(g.valid({"title": "ทดสอบ", "scenes": scene_set(chars=20)}))  # 180 ตัวอักษร

    def test_reject_way_too_long_narration(self):
        self.assertFalse(g.valid({"title": "ทดสอบ", "scenes": scene_set(chars=210)}))  # 1,890 ตัวอักษร

    def test_accept_outside_intended_but_sane(self):
        for d in (scene_set(count=7, chars=100), scene_set(count=15, chars=50),
                  scene_set(chars=50), scene_set(chars=125)):
            self.assertTrue(g.valid({"title": "ทดสอบ", "scenes": d}))

    def test_soft_notes(self):
        self.assertEqual(g.soft_notes({"scenes": scene_set()}), [])  # 9 ฉาก 765 ตัวอักษร
        self.assertEqual(len(g.soft_notes({"scenes": scene_set(count=7, chars=50)})), 2)
        self.assertEqual(len(g.soft_notes({"scenes": scene_set(chars=125)})), 1)

    def test_reject_empty_prompt(self):
        self.assertFalse(g.valid({"title": "ทดสอบ", "scenes": scene_set(prompt="")}))

    def test_reject_missing_title(self):
        self.assertFalse(g.valid({"scenes": scene_set()}))

import base64, struct, math, tempfile, subprocess, shutil

class FakeResp:
    def __init__(self, code, j=None):
        self.status_code, self._j, self.text = code, j, ""
    def json(self):
        return self._j

def run_call(seq, wait=True):
    calls = []
    it = iter(seq)
    def post(*a, **k):
        calls.append(1)
        return next(it)
    old_post, old_sleep = g.requests.post, g.time.sleep
    g.requests.post, g.time.sleep = post, lambda x: None
    try:
        return g.call("m", {}, wait=wait), len(calls)
    finally:
        g.requests.post, g.time.sleep = old_post, old_sleep

class MockApiTests(unittest.TestCase):
    def setUp(self):
        g.usage.clear()

    def test_usage_counts(self):
        run_call([FakeResp(503), FakeResp(200, {"ok": 1})])
        self.assertEqual(g.usage["m"], {"5xx": 1, "ok": 1})
        g.requests.post = lambda *a, **k: FakeResp(429)
        try:
            g.call("m2", {})
        except g.QuotaError:
            pass
        self.assertEqual(g.usage["m2"], {"429": 1})
        text = "\n".join(g.usage_lines())
        self.assertIn("m: ส่งคำขอ 2 ครั้ง", text)
        self.assertNotIn("DUMMY", text)

    def test_usage_empty(self):
        self.assertEqual(g.usage_lines(), ["- ไม่มีการเรียก Gemini"])

    def test_429_stops_immediately(self):
        old = g.requests.post
        n = []
        g.requests.post = lambda *a, **k: (n.append(1), FakeResp(429))[1]
        try:
            with self.assertRaises(g.QuotaError):
                g.call("m", {})
        finally:
            g.requests.post = old
        self.assertEqual(len(n), 1)

    def test_5xx_retries_once_then_ok(self):
        out, n = run_call([FakeResp(503), FakeResp(200, {"ok": 1})])
        self.assertEqual((out, n), ({"ok": 1}, 2))

    def test_5xx_no_wait_returns_fast(self):
        out, n = run_call([FakeResp(503), FakeResp(200, {"ok": 1})], wait=False)
        self.assertEqual((out, n), (None, 1))

    def test_4xx_no_retry(self):
        out, n = run_call([FakeResp(400)])
        self.assertEqual((out, n), (None, 1))

@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "needs ffmpeg")
class MockTtsTests(unittest.TestCase):
    def _tts(self, mime, seconds=2, rate=24000):
        pcm = b"".join(struct.pack("<h", int(8000 * math.sin(2 * math.pi * 440 * i / rate))) for i in range(rate * seconds))
        old = g.call
        g.call = lambda m, b, wait=True: {"candidates": [{"content": {"parts": [{"inlineData": {"mimeType": mime, "data": base64.b64encode(pcm).decode()}}]}}]}
        d = tempfile.mkdtemp()
        cwd = os.getcwd()
        try:
            os.chdir(d); os.makedirs("work")
            ok = g.tts_gemini("x", "m", "work/v.wav")
            return ok, g.audio_duration("work/v.wav")
        finally:
            os.chdir(cwd); g.call = old

    def test_pcm_24k(self):
        ok, dur = self._tts("audio/L16;codec=pcm;rate=24000")
        self.assertTrue(ok); self.assertAlmostEqual(dur, 2.0, delta=0.1)

    def test_pcm_other_rate_keeps_duration(self):
        ok, dur = self._tts("audio/L16;codec=pcm;rate=16000", rate=16000)
        self.assertTrue(ok); self.assertAlmostEqual(dur, 2.0, delta=0.1)

import json, contextlib

@contextlib.contextmanager
def in_tmp():
    d, cwd = tempfile.mkdtemp(), os.getcwd()
    os.chdir(d); os.makedirs("work")
    try:
        yield d
    finally:
        os.chdir(cwd)

class ImgResp:
    def __init__(self, code, headers=None, content=b""):
        self.status_code, self.headers, self.content = code, headers or {}, content

class WikiTitleTests(unittest.TestCase):
    def test_similar_title(self):
        self.assertFalse(g.similar_title("Taika meteorite crater", "Shūjin Riku"))
        self.assertTrue(g.similar_title("Mars", "Mars (planet)"))
        self.assertTrue(g.similar_title("Tardigrade", "Tardigrade"))
        self.assertTrue(g.similar_title("Taika_meteorite_crater", "Taika crater"))

    def test_find_article_rejects_unrelated_search_hit(self):
        old_f, old_w = g.fetch_article, g.wiki_get
        g.fetch_article = lambda t: None
        g.wiki_get = lambda p: {"query": {"search": [{"title": "Shūjin Riku"}]}}
        try:
            self.assertIsNone(g.find_article("Taika_meteorite_crater"))
        finally:
            g.fetch_article, g.wiki_get = old_f, old_w

    def test_find_article_accepts_matching_search_hit(self):
        old_f, old_w = g.fetch_article, g.wiki_get
        art = ("Taika crater", "https://x", "a" * 2500)
        g.fetch_article = lambda t: art if t == "Taika crater" else None
        g.wiki_get = lambda p: {"query": {"search": [{"title": "Shūjin Riku"}, {"title": "Taika crater"}]}}
        try:
            self.assertEqual(g.find_article("Taika meteorite crater"), art)
        finally:
            g.fetch_article, g.wiki_get = old_f, old_w

class ImageThrottleTests(unittest.TestCase):
    def setUp(self):
        g._img_not_before, g._consec_402 = 0.0, 0
        self.sleeps = []
        self.old = (g.requests.get, g.time.sleep)
        g.time.sleep = self.sleeps.append

    def tearDown(self):
        g.requests.get, g.time.sleep = self.old

    def test_two_consecutive_402_stop_and_wait_between(self):
        g.requests.get = lambda *a, **k: ImgResp(402, {"Retry-After": "5"})
        with in_tmp():
            with self.assertRaises(g.ImageBlocked):
                g.make_image("p", "work/img0.jpg", 1)
        self.assertTrue(any(s >= 45 for s in self.sleeps), self.sleeps)

    def test_402_then_success_resets_and_writes_marker(self):
        seq = iter([ImgResp(402), ImgResp(200, {"content-type": "image/jpeg"}, b"x" * 6000)])
        g.requests.get = lambda *a, **k: next(seq)
        with in_tmp():
            self.assertTrue(g.make_image("p", "work/img0.jpg", 1))
            self.assertTrue(os.path.exists("work/img0.jpg.ok"))
        self.assertEqual(g._consec_402, 0)

    def test_non_402_failures_never_raise(self):
        g.requests.get = lambda *a, **k: ImgResp(503)
        with in_tmp():
            self.assertFalse(g.make_image("p", "work/img0.jpg", 1))

    def test_gap_between_requests(self):
        g.requests.get = lambda *a, **k: ImgResp(200, {"content-type": "image/jpeg"}, b"x" * 6000)
        with in_tmp():
            g.make_image("p", "work/a.jpg", 1)
            g.make_image("p", "work/b.jpg", 1)
        self.assertTrue(any(s >= 45 for s in self.sleeps), self.sleeps)

class CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.old_env = os.environ.get("RESUME")

    def tearDown(self):
        if self.old_env is None:
            os.environ.pop("RESUME", None)
        else:
            os.environ["RESUME"] = self.old_env

    def test_roundtrip(self):
        script = {"title": "ทดสอบ", "scenes": scene_set()}
        with in_tmp():
            g.save_checkpoint(script, [{"title": "t", "uri": "u"}], 123)
            os.environ["RESUME"] = "1"
            ck = g.load_checkpoint()
            self.assertEqual(ck["script"], script)
            self.assertEqual(ck["clip_seed"], 123)

    def test_no_resume_flag_returns_none(self):
        os.environ["RESUME"] = "0"
        with in_tmp():
            g.save_checkpoint({"title": "t", "scenes": scene_set()}, [], 1)
            self.assertIsNone(g.load_checkpoint())

    def test_resume_without_file_exits_not_calls_gemini(self):
        os.environ["RESUME"] = "1"
        with in_tmp():
            with self.assertRaises(SystemExit):
                g.load_checkpoint()

    def test_expired_checkpoint_exits(self):
        os.environ["RESUME"] = "1"
        with in_tmp():
            g.save_checkpoint({"title": "t", "scenes": scene_set()}, [], 1)
            ck = json.load(open("checkpoint.json"))
            ck["created"] -= 13 * 3600
            json.dump(ck, open("checkpoint.json", "w"))
            with self.assertRaises(SystemExit):
                g.load_checkpoint()

if __name__ == "__main__":
    unittest.main(verbosity=2)
